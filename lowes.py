import requests,json,os,uuid,time,random,string,csv, http.client, asyncio, aiohttp
from utils import Utils

from requests.exceptions import ProxyError, ConnectionError, Timeout
http.client._MAXHEADERS = 1000
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
from datetime import datetime,timedelta,timezone
import concurrent.futures


"""
Creating a class for Lowes
"""

class NotFound(Exception):
    def __init__(self, message="Product not found"):
        super().__init__(message)

class LOWES():
    def __init__(self,proxies = None):
        self.proxies = Utils.load_proxies() if proxies is None else [proxies]
        self.proxy_cert = False
        self.headers = {
            'user-agent': 'lowesMobileApp/25.10.6 (iPhone; iOS 18.6.2)',
            'os': 'ios',
            'x-lowes-originating-server-hostname': 'LowesiOSConsumer',
            'isguestuser': 'true',
            'accept-language': 'en-GB,en;q=0.9',
            'accept': '*/*',
            'app-version': '25.10.6',
            'x-api-version': 'v3',
            'device-idiom': 'phone'
        }

        self.root_dir = os.path.dirname(__file__)
        self.name = 'lowes'
        
    def generate_sensor_data(self,type="sensor_data"):
        if type == "sensor_data":
            return '4,i,' +''.join(random.choices(string.ascii_letters + string.digits, k=1242)) + f'==${random.randint(1,20)},{random.randint(1,20)},{random.randint(1,20)}$$'

        elif type == "client_id":
            return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

        elif type == "client_secret":
            return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

        elif type == "random_string":
            return  ''.join(random.choices(string.digits + string.ascii_letters.lower(), k=14))
        
        elif type == "random_number":
            return  ''.join(random.choices(string.hexdigits[:6] + string.digits, k=40))
        
        elif type == "random_string_upper":
            return  ''.join(random.choices(string.ascii_letters.upper() + string.ascii_letters + string.digits, k=40))
    
        
    def format_data(self,store,sku,data:dict):
        try:
            name = data.get('description', '')
            brand = data.get('brand', '')
            canonicalUrl = data.get('pdURL')
            url = f"https://www.lowes.com/{canonicalUrl}" if canonicalUrl else ''

            reviews = data.get('reviewCount', 0)
            rating = data.get('rating', 0)

            model = data.get('modelId')
            retailer = "Lowes"
            storesku = data.get('itemNumber')
            omsid = data.get('omniItemId')
            store_name = Utils.safe_get(store, 'store_name', default='')
            store_id = Utils.safe_get(store, 'store_id', default='')
            store_location = f"{Utils.safe_get(store, 'address', default='')}, {Utils.safe_get(store, 'city', default='')}, {Utils.safe_get(store, 'state', default='')} {Utils.safe_get(store, 'zipcode', default='')}"

            total = data.get('itemInventory',{}).get('totalQty',0)

            mainImageurl = data.get('imageUrl', None)
            
            result = {
                "name":name,
                "brand":brand,
                "url":url,
                "mainImageurl":mainImageurl,
                "sku":storesku,
                "reviews":reviews,
                "rating":rating,
                "model":model,
                "retailer":retailer,
                "storesku":storesku,
                "omsid":omsid,
                "store_name":store_name,
                "store_id":store_id,
                "store_location":store_location,
                "inventory":total
            }
            print(f"{sku} at {store_name} - {total} items in stock")
            return True,result
        except Exception as error:
            return False,'Could not format data: ' + str(error)

    async def get_product_details_async(self, headers, session,  store, sku, delay=0.1, timeout=30, retries=Utils.get_retries_count()):
        success, result = False, {}
        try:
            await asyncio.sleep(delay)
            proxies = random.choice(self.proxies) if self.proxies is not None and len(self.proxies) > 0 else None

            # Handle multiple product requests
            params = {
                'enablePaintConfig': 'true',
                'enableFulfillmentV2': 'true',
                'showAtc': 'true',
                'enableNewBadges': 'true',
                'customerType': 'REGULAR',
                'carouselBadge': 'true',
                'purchaseFromCatalog': 'false',
                'associations': 'pd',
                'promoType': 'unknown',
                'promotionId':'' ,
                'storeNumber': f'{store["store_id"]}',
                'enableLiftOffRecs': 'true',
                'supportBuyAgain': 'false',
                'enableCurbsideSelection': 'true',
                'hasAdditionalServices': 'true',
                'organizationId':'',
                'role': '',
                'enableSameDayDelivery': 'true',
            }

            # Create proxy format for aiohttp
            proxy_url = None
            if proxies:
                if isinstance(proxies, str) and proxies.startswith('http'):
                    proxy_url = proxies
                elif isinstance(proxies, dict):
                    proxy_url = proxies.get('http') or proxies.get('https')

            try:
                async with session.get(
                    f'https://apis.lowes.com/fulcra/pd/productId/{sku}',
                    params=params,
                    headers=headers,
                    proxy=proxy_url,
                    timeout=timeout,
                    verify_ssl=self.proxy_cert
                ) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        if resp_json.get('errors'):
                            error_msg = resp_json.get('errors', [{}])[0].get('message', 'Unknown error')
                            # Check if this is a product-not-available error (don't retry)
                            if any(keyword in error_msg.lower() for keyword in [
                                'product not found', 'discontinued', 'no longer available',
                                'invalid product', 'not found', 'does not exist'
                            ]):
                                raise NotFound(f'Item {sku} not available: {error_msg}')
                            else:
                                # Retryable API error
                                if retries > 0:
                                    print(f'API error for item {sku} at {store["store_name"]}, retrying: {error_msg}')
                                    success, result = await self.get_product_details_async(
                                        headers, session, store, sku, delay=delay, timeout=timeout, retries=retries - 1
                                    )
                                    return success, result
                                else:
                                    raise Exception(error_msg)
                        # Validate product data exists
                        products = resp_json.get('product')
                        if not products:
                            raise NotFound(f'Item {sku} not available - no product data in response')
                        success, result = True, resp_json
                    elif response.status == 401:  # Token expired
                        return False, {'status': 401, 'message': 'Token expired'}
                    elif response.status in [429, 503, 504, 408] and retries > 0:  # Rate limit or server errors - retry
                        print(f'Rate limit/server error {response.status} for item {sku} at {store["store_name"]}, retrying...')
                        success, result = await self.get_product_details_async(
                            headers, session, store, sku, delay=delay, timeout=timeout, retries=retries - 1
                        )
                        return success, result
                    else:
                        # Client errors (4xx except 401, 429) or other status codes - assume permanent issue
                        error_text = await response.text()
                        raise Exception(f'Response status {response.status}: {error_text}')
            except (aiohttp.ClientError) as e:
                # Network/proxy/connection errors - should retry
                if retries > 0:
                    print(f'Network/proxy error for item {sku} at {store["store_name"]}, retrying: {str(e)}')
                    success, result = await self.get_product_details_async(
                        headers, session, store, sku, delay=delay, timeout=timeout, retries=retries - 1
                    )
                else:
                    raise Exception(f'Network error (retries exhausted): {str(e)}')
                
        except NotFound as nf:
            success, result = False, 'Not Available'

        except Exception as error:
            success, result = False, f"error getting product: {error}"

        return success, result

    def load_stores(self):
        # Load store details from store_list.csv
        stores = []
        stores_file = os.path.join(self.root_dir, 'store_ids.json')
        with open(stores_file, 'r', encoding='utf-8') as f:
            stores = json.load(f)['data']
        return stores
    

    async def get_token_async(self, headers, batch_num, delay=0.1, timeout=30, verify=True, retries=None):
        if retries is None:
            retries = Utils.get_retries_count()
        success, result = False, {}
        try:
            if verify:
                verify = self.proxy_cert

            await asyncio.sleep(delay)

            data = {
                'client_id': '5e86eb19bbdaf5858ba1cef79ad4b826',
                'client_secret': 'c8c44f2f520dc07b8a854ad06807a256',
                'grant_type': 'client_credentials',
            }

            proxies = random.choice(self.proxies) if self.proxies is not None and len(self.proxies) > 0 else None
            proxy_url = None
            if proxies:
                if isinstance(proxies, str) and proxies.startswith('http'):
                    proxy_url = proxies
                elif isinstance(proxies, dict):
                    proxy_url = proxies.get('http') or proxies.get('https')

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                try:
                    async with session.post(
                        'https://apis.lowes.com/v1/oauthprovider/oauth2/token',
                        headers=headers,
                        data=data,
                        proxy=proxy_url,
                        verify_ssl=verify
                    ) as response:
                        if response.status == 200:
                            resp_json = await response.json()
                            success, result = True, resp_json['access_token']
                        elif response.status in [503, 412, 456, 522, 408, 502, 403] and retries > 0:
                            print('Failed to get token, retrying...')
                            success, result, retries = await self.get_token_async(delay, timeout, verify, retries - 1)
                        else:
                            error_text = await response.text()
                            return False, error_text, retries
                except aiohttp.ClientError as e:
                    Utils.write_log(e)
                    if retries > 0:
                        print('Failed to get token, retrying...')
                        success, result, retries = await self.get_token_async(delay, timeout, verify, retries - 1)
                    else:
                        return False, str(e), retries

        except Exception as error:
            return False, f'Error getting token for batch {batch_num} : {error}', retries

        return success, result, retries

    def load_products(self,products_file):
        # Load store details from store_list.csv
        products = []
        products_file_path = os.path.join(self.root_dir,products_file)
        with open(products_file_path, 'r', encoding='utf-8') as csvf:
            reader = csv.DictReader(csvf)
            for row in reader:
                product = {
                    'name': row['name'],
                    'brand': row['brand'],
                    'url': row['url'],
                    'mainImageurl': row['mainImageurl'],
                    'SKU': row['SKU'],
                    'Reviews': row['Reviews'],
                    'Rating': row['Rating'],
                    'Model': row['Model'],
                    'retailer': row['retailer'],
                    'storesku': row['storesku'],
                    'omsid': row['omsid'],
                    'storeName': row.get('storeName'),
                    'storeID': row.get('storeID'),
                    'storeLocation': row.get('storeLocation'),
                    'inventory': row.get('inventory'),
                }
                if product.get('SKU') is not None and product.get('omsid') is not None:products.append(product)
        return products
               
    async def scan_items_async(self, session, store, product, headers, token, delay=0.1, timeout=30):
        try:
            # Headers and token are provided by caller (worker)
            headers['authorization'] = f'Bearer {token}'

            success, item = await self.get_product_details_async(
                headers, session, store, product['omsid'], delay=delay, timeout=timeout
            )

            if not success:
                return False, item

            # Single product response
            product = item.get('product', {})
            if product:
                success_format, formatted = self.format_data(store, product['omniItemId'], product)
                if success_format:
                    return True, {"store": store['store_id'], "data": formatted}
                else:
                    return False, {"store": store['store_id'], "message": f'Format error: {formatted}'}
            else:
                return False, {"store": store['store_id'], "message": "No product data in response"}

        except Exception as error:
            return False, {"store": store['store_id'], "message": f'Error scanning item: {error}'}
