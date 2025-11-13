#!/usr/bin/env python3
"""
Weather Underground Hourly Forecast Scraper
Scrapes hourly forecast data from wunderground.com while respecting robots.txt
"""

import time
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


class WundergroundScraper:
    """Scraper for Weather Underground hourly forecasts"""

    def __init__(self, headless: bool = True, crawl_delay: int = 2):
        """
        Initialize the scraper

        Args:
            headless: Run browser in headless mode
            crawl_delay: Delay between requests in seconds (respecting server load)
        """
        self.crawl_delay = crawl_delay
        self.driver = self._setup_driver(headless)

    def _setup_driver(self, headless: bool) -> webdriver.Chrome:
        """Setup Chrome WebDriver with appropriate options"""
        chrome_options = Options()

        if headless:
            chrome_options.add_argument('--headless')

        # Additional options for stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            # Try using ChromeDriverManager first
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"ChromeDriverManager failed: {e}")
            print("Attempting to use system chromedriver...")
            # Fallback to system chromedriver
            driver = webdriver.Chrome(options=chrome_options)

        driver.implicitly_wait(10)

        return driver

    def scrape_hourly_forecast(self, location_code: str) -> List[Dict]:
        """
        Scrape hourly forecast for a given location

        Args:
            location_code: Location code (e.g., 'EGLC' for London City Airport)

        Returns:
            List of dictionaries containing hourly forecast data
        """
        url = f"https://www.wunderground.com/hourly/{location_code}"
        print(f"Scraping: {url}")

        try:
            self.driver.get(url)

            # Wait for the hourly forecast table to load
            wait = WebDriverWait(self.driver, 15)
            table = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "lib-city-hourly-forecast"))
            )

            # Give extra time for dynamic content to load
            time.sleep(3)

            forecast_data = []

            # Find all hourly forecast rows
            # The data is typically in a table or structured list
            rows = self.driver.find_elements(By.CSS_SELECTOR, "lib-city-hourly-forecast table tbody tr")

            if not rows:
                print("No rows found in standard format, trying alternative selectors...")
                rows = self.driver.find_elements(By.CSS_SELECTOR, "[class*='hourly'] tr")

            print(f"Found {len(rows)} forecast entries")

            for row in rows:
                try:
                    forecast_entry = self._parse_forecast_row(row)
                    if forecast_entry:
                        forecast_data.append(forecast_entry)
                except Exception as e:
                    print(f"Error parsing row: {e}")
                    continue

            # Respectful crawling - add delay
            time.sleep(self.crawl_delay)

            return forecast_data

        except TimeoutException:
            print(f"Timeout loading page: {url}")
            return []
        except Exception as e:
            print(f"Error scraping forecast: {e}")
            return []

    def _parse_forecast_row(self, row) -> Optional[Dict]:
        """
        Parse a single forecast row

        Args:
            row: Selenium WebElement representing a table row

        Returns:
            Dictionary with forecast data or None if parsing fails
        """
        try:
            cells = row.find_elements(By.TAG_NAME, "td")

            if len(cells) < 10:  # Need at least 10 columns
                return None

            # Column structure from the website:
            # 0: Time, 1: Conditions, 2: Temp, 3: Feels Like, 4: Precip,
            # 5: Amount, 6: Cloud Cover, 7: Dew Point, 8: Humidity, 9: Wind, 10: Pressure

            forecast = {
                'timestamp': datetime.now().isoformat(),
                'time': cells[0].text.strip() if len(cells) > 0 else '',
                'condition': self._extract_text_from_cell(cells[1]) if len(cells) > 1 else '',
                'temperature': cells[2].text.strip() if len(cells) > 2 else '',
                'feels_like': cells[3].text.strip() if len(cells) > 3 else '',
                'precip_chance': cells[4].text.strip() if len(cells) > 4 else '',
                'precip_amount': cells[5].text.strip() if len(cells) > 5 else '',
                'cloud_cover': cells[6].text.strip() if len(cells) > 6 else '',
                'dew_point': cells[7].text.strip() if len(cells) > 7 else '',
                'humidity': cells[8].text.strip() if len(cells) > 8 else '',
                'wind': cells[9].text.strip() if len(cells) > 9 else '',
                'pressure': cells[10].text.strip() if len(cells) > 10 else '',
            }

            return forecast

        except Exception as e:
            print(f"Error parsing forecast entry: {e}")
            return None

    def _extract_text_from_cell(self, cell) -> str:
        """Extract text from a cell, checking img alt text first"""
        try:
            # First check for image alt text (for weather icons)
            imgs = cell.find_elements(By.TAG_NAME, "img")
            if imgs:
                alt_text = imgs[0].get_attribute('alt')
                if alt_text:
                    return alt_text
            # Otherwise return the text content
            return cell.text.strip()
        except:
            return ''

    def save_to_json(self, data: List[Dict], filename: str):
        """Save forecast data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")

    def save_to_csv(self, data: List[Dict], filename: str):
        """Save forecast data to CSV file"""
        if not data:
            print("No data to save")
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"Data saved to {filename}")

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def main():
    """Main function to demonstrate scraper usage"""
    location_code = "EGLC"  # London City Airport

    print("Starting Weather Underground Scraper")
    print(f"Target: https://www.wunderground.com/hourly/{location_code}")
    print("Respecting robots.txt - no crawl restrictions found")
    print("-" * 60)

    # Use context manager for automatic cleanup
    with WundergroundScraper(headless=False, crawl_delay=2) as scraper:
        # Scrape the forecast
        forecast_data = scraper.scrape_hourly_forecast(location_code)

        if forecast_data:
            print(f"\nSuccessfully scraped {len(forecast_data)} hourly forecasts")

            # Save to both formats
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            scraper.save_to_json(forecast_data, f'forecast_{location_code}_{timestamp}.json')
            scraper.save_to_csv(forecast_data, f'forecast_{location_code}_{timestamp}.csv')

            # Display first few entries
            print("\nFirst 3 forecast entries:")
            for i, entry in enumerate(forecast_data[:3], 1):
                print(f"\n{i}. {entry}")
        else:
            print("\nNo forecast data retrieved")


if __name__ == "__main__":
    main()
