from lowes import LOWES, NotFound
import os, csv, concurrent.futures, asyncio, aiohttp
from datetime import datetime
import json, time, uuid
from collections import deque


async def main_async():
    lowes = LOWES()

    products = lowes.load_products('Lowes Products 2025 12 09.csv')
    stores = lowes.load_stores()

    # Filter out products with invalid OMSID (critical since we use it for API calls)
    valid_products = []
    for product in products:
        omsid_val = product.get('omsid', '').strip()

        # Strict OMSID validation - disqualify on any of these invalid values
        if (omsid_val is None or
            omsid_val == '' or
            omsid_val.lower() in ['null', 'none', 'n/a', 'na'] or
            omsid_val == '0'):
            continue  # Skip this invalid product

        valid_products.append(product)

    print(f"Filtered {len(products)} to {len(valid_products)} valid products ({len(products) - len(valid_products)} invalid)")

    # Filter out stores with invalid/incorrect zipcodes
    valid_stores = []
    for store in stores:
        zipcode = store.get('zipcode', '').strip()
        if (zipcode and
            len(zipcode) >= 5 and
            zipcode.isdigit() and
            zipcode != '0'):
            valid_stores.append(store)

    print(f"Filtered {len(stores)} to {len(valid_stores)} valid stores ({len(stores) - len(valid_stores)} invalid)")

    test_store = valid_stores[0] if valid_stores else None

    # Calculate expected results
    total_combinations = len(valid_products) * len(valid_stores)
    print(f"🚀 Total combinations to process: {total_combinations:,} ({len(valid_products):,} products × {len(valid_stores)} stores)")

    headers = ['name', 'brand', 'url', 'mainImageurl', 'SKU', 'Reviews', 'Rating', 'Model', 'retailer', 'storesku', 'omsid','storeName','storeID','storeLocation','inventory']
    csv_file = f'product-{datetime.now().strftime("%Y-%m-%d")}.csv'
    results_folder = os.path.join(lowes.root_dir, 'results')

    if not os.path.exists(results_folder):
        os.makedirs(results_folder)

    with open(f'{results_folder}/{csv_file}', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    # Optimized concurrency configuration for token reuse
    NUM_WORKERS = 10  # Number of concurrent workers
    REQUESTS_PER_MINUTE = 60  # Per worker rate limit
    TOKEN_VALIDITY_MINUTES = 15
    GLOBAL_CONCURRENCY_LIMIT = 200  # Overall concurrent requests

    # Create queue of all product-store combinations
    combination_queue = asyncio.Queue()
    for product in valid_products:
        for store in valid_stores:
            await combination_queue.put((product, store))

    print(f"Created queue with {combination_queue.qsize()} combinations")

    # Global concurrency control
    global_semaphore = asyncio.Semaphore(GLOBAL_CONCURRENCY_LIMIT)
    write_lock = asyncio.Lock()

    async def worker(worker_id):
        """Worker with token reuse across multiple products"""
        request_times = deque(maxlen=REQUESTS_PER_MINUTE)  # Track request timestamps

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=50)  # Per-worker connection limit
        ) as session:

            # Initialize token and headers (reused across multiple products)
            token = None
            headers = None
            token_start_time = 0
            products_processed_with_token = 0

            while True:
                # Check if work is done
                try:
                    product, store = combination_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break  # No more work

                # Rate limiting: ensure we don't exceed per-minute limit
                now = time.time()
                if len(request_times) >= REQUESTS_PER_MINUTE:
                    # Calculate time to wait to maintain rate limit
                    oldest_request = request_times[0]
                    time_since_oldest = now - oldest_request
                    if time_since_oldest < 60:  # Within 1 minute window
                        sleep_time = 60 - time_since_oldest
                        await asyncio.sleep(sleep_time)

                # Token management: get new token if needed or expired
                if (token is None or
                    (now - token_start_time) > (TOKEN_VALIDITY_MINUTES * 60) or
                    products_processed_with_token >= 100):  # Refresh after 100 products

                    # Get new token
                    device_id = str(uuid.uuid4()).upper()
                    headers = lowes.headers.copy()
                    headers.update({
                        'deviceid': device_id,
                        'epid': str(uuid.uuid4()).upper(),
                        'adid': lowes.generate_sensor_data(type="random_number"),
                        'x-lowes-uuid': f'ca829819-f33a-44c5-b294-{lowes.generate_sensor_data(type="random_string")}',
                        'x-acf-sensor-data': lowes.generate_sensor_data(type="sensor_data"),
                    })

                    success_token, new_token, _ = await lowes.get_token_async(headers, worker_id, delay=0.1, timeout=30)
                    if not success_token:
                        print(f'Worker {worker_id}: Failed to get token, skipping combination')
                        combination_queue.task_done()
                        continue

                    token = new_token
                    token_start_time = now
                    products_processed_with_token = 0

                # Global concurrency control
                async with global_semaphore:
                    try:
                        # Call scan_items_async with provided headers and token
                        success, result = await lowes.scan_items_async(
                            session, store, product, headers, token, delay=0.1, timeout=30
                        )

                        # Record request time for rate limiting
                        request_times.append(time.time())
                        products_processed_with_token += 1

                        if success:
                            # Save successful result
                            async with write_lock:
                                with open(f'{results_folder}/{csv_file}', 'a', encoding='utf-8', newline='') as f:
                                    writer = csv.writer(f)
                                    writer.writerow(result['data'].values())
                        else:
                            # Handle API errors
                            if isinstance(result, dict) and result.get('status') == 401:
                                # Token expired - will refresh on next iteration
                                print(f'Worker {worker_id}: Token expired, will refresh')
                                token = None  # Force token refresh
                            else:
                                # Handle both dict and string result types
                                if isinstance(result, dict):
                                    error_msg = result.get('message', str(result))
                                else:
                                    error_msg = str(result)
                                print(f'Worker {worker_id}: API error for {product["SKU"]} at {store["store_name"]}: {error_msg}')

                    except Exception as e:
                        print(f'Worker {worker_id}: Exception processing {product["SKU"]} at {store["store_name"]}: {e}')

                combination_queue.task_done()

    # Create and run workers
    print(f"Starting {NUM_WORKERS} workers...")
    workers = [worker(i) for i in range(NUM_WORKERS)]
    await asyncio.gather(*workers)

    # All tasks completed

    print("All combinations processed!")
    return total_combinations


def main():
    print("Starting optimized Lowes scraper...")
    total_processed = asyncio.run(main_async())
    print(f"Scraper completed. Processed {total_processed} product-store combinations.")


if __name__ == '__main__':
    main()
