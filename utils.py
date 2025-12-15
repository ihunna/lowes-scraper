import os, json, random, string, time,pandas as pd
from datetime import datetime




root_dir = os.path.dirname(__file__)
logs_file = os.path.join(root_dir,'logs.txt')

class Utils:
    @staticmethod
    def divide_chunks(l, n):
        # looping till length l
        for i in range(0, len(l), n):
            yield l[i:i + n]
            
    @staticmethod
    def write_log(message, log_file_path=logs_file):
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(log_file_path, 'a') as log_file:
            log_file.write(f"[{current_datetime}] [LOG] {message}\n")
        # print(f"[{current_datetime}] [LOG] {message}\n")

    @staticmethod
    def load_proxies():
        proxies = []
        file = os.path.join(root_dir,'proxies.txt')
        with open(file,"r") as f:
            for proxy in f.readlines():
                proxy = proxy.replace("\n","").split(":")
                ip = proxy[0]
                port = proxy[1]
                username = proxy[2]
                password = proxy[3] if len(proxy) > 3 else None
                if password is not None:
                    proxy = {
                        "http": f'http://{username}:{password}@{ip}:{port}',
                        "https": f'http://{username}:{password}@{ip}:{port}'
                    }
                else:
                    proxy = {
                        "http": f'http://{username}:@{ip}:{port}',
                        "https": f'http://{username}:@{ip}:{port}'
                    }
                    
                proxies.append(proxy)

        return proxies
    
    @staticmethod
    def load_us_states():
        states = {"data":[]}
        file = os.path.join(root_dir,'us_states.json')
        with open(file,'r',encoding='utf-8') as f:
            states = json.load(f)

        return states


        

    @staticmethod
    def get_retries_count():return 3

    @staticmethod
    def safe_get(dictionary:dict, *keys, default=[]):
        for key in keys:
            if isinstance(dictionary, dict):
                dictionary = dictionary.get(key, default)
            elif isinstance(dictionary, list):
                return dictionary
            else:
                return default
        return dictionary if dictionary is not None else default
    


    @staticmethod
    def deduplicate_csv(file_path='homedepot_products.csv', subset=['SKU']):
        """
        Remove duplicate rows from CSV by key columns, keeping the latest record.
        """
        try:
            df = pd.read_csv(file_path)
            before = len(df)

            # Keep the last (latest) entry for each unique key
            df = df.drop_duplicates(subset=subset, keep='last')

            df.to_csv(file_path, index=False)
            after = len(df)
            print(f"✅ Deduplicated {file_path}: {before - after} duplicates removed, {after} rows remaining (latest kept).")

        except Exception as e:
            print(f"⚠️ Could not deduplicate {file_path}: {e}")