import asyncio
import aiohttp
import pandas as pd
import time
from datetime import datetime
import logging
import json
from typing import List, Dict
import os
import csv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class APITester:
    def __init__(self, csv_path: str, concurrent_requests: int = 5):
        self.csv_path = csv_path
        self.concurrent_requests = concurrent_requests
        self.api_url = "https://utils.flexiple.com/process-document/"
        self.results_dir = "test_results"
        os.makedirs(self.results_dir, exist_ok=True)
        self.headers = {
            'X-API-Key': '2beeac086729f8bbed029a469e96b38d',
            'accept': 'application/json'
        }

    async def process_url(self, session: aiohttp.ClientSession, url: str) -> Dict:
        """Process a single URL through the API"""
        start_time = time.time()
        try:
            data = aiohttp.FormData()
            data.add_field('url', url)
            
            async with session.post(self.api_url, data=data, headers=self.headers) as response:
                duration = time.time() - start_time
                status = response.status
                
                result = {
                    'url': url,
                    'status_code': status,
                    'duration': duration,
                    'timestamp': datetime.now().isoformat()
                }
                
                if status == 200:
                    result['response'] = await response.json()
                else:
                    result['error'] = await response.text()
                
                logger.info(f"Processed {url} - Status: {status}, Duration: {duration:.2f}s")
                return result
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error processing {url}: {str(e)}")
            return {
                'url': url,
                'status_code': 500,
                'error': str(e),
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            }

    async def process_batch(self, urls: List[str]) -> List[Dict]:
        """Process a batch of URLs concurrently"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.process_url(session, url) for url in urls]
            return await asyncio.gather(*tasks)

    def save_results(self, results: List[Dict], batch_num: int):
        """Save batch results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON (existing functionality)
        json_filename = os.path.join(self.results_dir, f"batch_{batch_num}_{timestamp}.json")
        with open(json_filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save CSV
        csv_filename = os.path.join(self.results_dir, f"batch_{batch_num}_{timestamp}.csv")
        if results and 'response' in results[0]:  # Check if we have successful results
            # Get columns from the first successful response
            fieldnames = ['url', 'status_code', 'duration', 'timestamp'] + list(results[0]['response'].keys())
            
            with open(csv_filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in results:
                    row = {
                        'url': result['url'],
                        'status_code': result['status_code'],
                        'duration': result['duration'],
                        'timestamp': result['timestamp']
                    }
                    if 'response' in result:
                        row.update(result['response'])
                    writer.writerow(row)
        
        logger.info(f"Saved results to {json_filename} and {csv_filename}")

    async def run(self):
        """Run the API test"""
        # Read URLs from CSV
        df = pd.read_csv(self.csv_path)
        urls = df['url'].tolist()  # Assuming the column with URLs is named 'url'
        
        # Process in batches
        batch_size = self.concurrent_requests
        batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
        
        all_results = []
        for i, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} URLs)")
            batch_start = time.time()
            
            results = await self.process_batch(batch)
            all_results.extend(results)
            
            batch_duration = time.time() - batch_start
            logger.info(f"Batch {i} completed in {batch_duration:.2f}s")
            
            # Save batch results
            self.save_results(results, i)
            
            # Add a small delay between batches to avoid overwhelming the server
            if i < len(batches):
                await asyncio.sleep(2)
        
        # Generate summary
        successful = sum(1 for r in all_results if r['status_code'] == 200)
        failed = len(all_results) - successful
        avg_duration = sum(r['duration'] for r in all_results) / len(all_results)
        
        summary = {
            'total_requests': len(all_results),
            'successful_requests': successful,
            'failed_requests': failed,
            'average_duration': avg_duration,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save summary
        with open(os.path.join(self.results_dir, 'summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Testing completed. Summary: {json.dumps(summary, indent=2)}")

def main():
    # Create tester instance
    tester = APITester(
        csv_path='pdf_urls.csv',  # Your CSV file with URLs
        concurrent_requests=5     # Number of concurrent requests
    )
    
    # Run the test
    asyncio.run(tester.run())

if __name__ == "__main__":
    main() 