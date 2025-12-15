# Home Depot Store Availability Scraper

A Python-based web scraper that checks product availability and inventory levels across thousands of Home Depot stores using their GraphQL API. This tool is designed for concurrent scanning with proxy rotation support to efficiently gather real-time product data.

## Features

- **Concurrent Store Scanning**: Uses thread pools to scan multiple stores simultaneously for faster processing
- **Proxy Rotation**: Built-in proxy support to avoid rate limiting and IP blocking
- **Comprehensive Product Data**: Extracts detailed product information including inventory, pricing, reviews, ratings, and store-specific data
- **Flexible Input**: Accepts CSV files for product lists and store databases
- **CSV Output**: Structured output format suitable for data analysis
- **Error Handling**: Robust retry mechanisms and error logging for reliable operation
- **GraphQL API Integration**: Directly queries Home Depot's mobile API for accurate, real-time data

## Installation

### Prerequisites
- Python 3.8 or higher

### Setup
1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Requirements for Peak Performance

- 🔥 High-Quality Proxies: 100+ residential proxies for rate limiting avoidance
- 💪 Server Infrastructure: EC2 or similar with 16+ CPU cores, 32GB+ RAM
- 🌐 Fast Network: Low-latency connection to minimize round-trip times
- 📊 Monitoring: Watch CPU/memory usage and request rates

## Configuration

### Store List
The scraper requires a `store_list.csv` file containing Home Depot store information. The expected columns are:
- `Store #`: Store ID (required)
- `Store Name`: Store name (required)
- `Store Address`: Street address (required)
- `Store City`: City (required)
- `Store ZIp`: ZIP code (required) - note the typo in header
- `State`: State (required)
- `LAT1`: Latitude (optional)
- `LONG1`: Longitude (optional)

### Product List
Create a CSV file with products to scan. The expected columns are:
- `name`: Product name
- `brand`: Brand name
- `url`: Product URL
- `mainImageurl`: Main image URL
- `SKU`: Store SKU number
- `Reviews`: Number of reviews
- `Rating`: Average rating
- `Model`: Model number
- `retailer`: Always "HomeDepot"
- `storesku`: Store SKU
- `omsid`: OMS ID (required for API queries)
- `storeName`: Store name (if specific store data)
- `storeID`: Store ID (if specific store data)
- `storeLocation`: Store location (if specific store data)
- `inventory`: Inventory count (if specific store data)

### Proxy Configuration (Optional)
Add proxy servers to `proxies.txt` (one per line) in the format:
```
ip:port:username:password
ip:port:username:password
```

If no proxies are provided, the scraper will use direct connections.

## Usage

### Optimized High-Performance Version (Recommended)
For large-scale scraping with 3.5M+ combinations, use the optimized version:
```bash
python main_optimized.py
```

This version features:
- **Async HTTP requests** with aiohttp for better concurrency
- **Concurrent product×store processing** (instead of sequential)
- **200 concurrent connections** with controlled rate limiting
- **Batch processing** for memory management
- **Minimal delays** (0.1s vs 3s) while respecting API limits

**Expected Performance**: 100K-500K requests/hour depending on network and proxies

### Original Version
For smaller-scale scraping or testing:
```bash
python main.py
```

This will:
1. Load products from "Reduced product List 2025 10 30.csv"
2. Load stores from "store_list.csv"
3. Scan all stores for each product concurrently
4. Save results to `results/product-YYYY-MM-DD.csv`

### Custom Product File
To use a different product file, modify the load_products call in main.py:
```python
products = homedepot.load_products('your_product_file.csv')
```

## Output Format

The scraper generates CSV files in the `results/` directory with the following columns:

- `name`: Product name
- `brand`: Brand name
- `url`: Product URL
- `mainImageurl`: Main product image URL
- `SKU`: Product SKU
- `Reviews`: Number of customer reviews
- `Rating`: Average customer rating
- `Model`: Model number
- `retailer`: Always "HomeDepot"
- `storesku`: Store-specific SKU
- `omsid`: OMS identifier
- `storeName`: Name of the store
- `storeID`: ID of the store
- `storeLocation`: Full store address
- `inventory`: Available inventory quantity

Each row represents the availability of one product at one specific store location.

## Dependencies

The project requires the following Python packages (automatically installed via requirements.txt):
- `certifi`: SSL certificate verification
- `charset-normalizer`: Character encoding detection
- `idna`: Internationalized domain names
- `numpy`: Numerical computing
- `pandas`: Data analysis and manipulation
- `python-dateutil`: Date parsing utilities
- `pytz`: Time zone support
- `requests`: HTTP library for API calls
- `six`: Python 2/3 compatibility
- `tzdata`: Time zone data
- `urllib3`: HTTP client

## How It Works

1. **Initialization**: Creates HomeDepot scraper instance with proxy configuration
2. **Store Loading**: Reads store list CSV to get store IDs, names, and locations
3. **Product Loading**: Reads product list CSV to get product details and OMS IDs
4. **Concurrent Scanning**: Uses ThreadPoolExecutor to scan stores simultaneously
5. **API Queries**: For each product-store combination, queries Home Depot's GraphQL API
6. **Data Formatting**: Extracts relevant fields (inventory, pricing, reviews, etc.)
7. **Output Writing**: Appends results to CSV file incrementally

The scraper handles retries for failed requests and rotates through available proxies to maintain reliability.

## Important Notes

- Some items/products has been delisted from homedepot so they would show as unavailable error
- The product list file should be updated for better success rate
- Some zipcodes in the store list are incorrect and therefoe result in errors
- The store list file should updated with the correct zipcodes for the incorrect ones

## Troubleshooting

- **API Rate Limiting**: Use more proxies or increase delays between requests
- **Missing Store Data**: Ensure store_list.csv has all required columns
- **Product Not Found**: Verify OMS ID is correct and product exists
- **Proxy Issues**: Check proxy format and availability in proxies.txt
