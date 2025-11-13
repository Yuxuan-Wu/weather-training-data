#!/usr/bin/env python3
"""
Weather Underground Complete Scraper
Scrapes both forecast and historical (actual) weather data for ML training
Ensures data fields are aligned between forecast and actual data
"""

import time
import json
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


class WundergroundCompleteScraper:
    """Scraper for Weather Underground forecast and historical data"""

    def __init__(self, headless: bool = True, crawl_delay: int = 2):
        """
        Initialize the scraper

        Args:
            headless: Run browser in headless mode
            crawl_delay: Delay between requests in seconds
        """
        self.crawl_delay = crawl_delay
        self.driver = self._setup_driver(headless)
        # London timezone for EGLC
        self.london_tz = pytz.timezone('Europe/London')

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

    def get_eglc_current_time(self) -> datetime:
        """Get current time at EGLC airport (London timezone)"""
        utc_now = datetime.now(pytz.utc)
        london_now = utc_now.astimezone(self.london_tz)
        print(f"Current time at EGLC (London): {london_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        return london_now

    def scrape_forecast(self, location_code: str, current_time: datetime) -> List[Dict]:
        """
        Scrape hourly forecast for future hours only

        Args:
            location_code: Location code (e.g., 'EGLC')
            current_time: Current time at the location

        Returns:
            List of dictionaries containing forecast data for future hours
        """
        url = f"https://www.wunderground.com/hourly/{location_code}"
        print(f"\nScraping forecast: {url}")

        try:
            self.driver.get(url)

            # Wait for the hourly forecast table to load
            wait = WebDriverWait(self.driver, 15)
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "lib-city-hourly-forecast"))
            )

            # Give extra time for dynamic content to load
            time.sleep(3)

            forecast_data = []

            # Find all hourly forecast rows
            rows = self.driver.find_elements(By.CSS_SELECTOR, "lib-city-hourly-forecast table tbody tr")

            if not rows:
                print("No rows found in standard format, trying alternative selectors...")
                rows = self.driver.find_elements(By.CSS_SELECTOR, "[class*='hourly'] tr")

            print(f"Found {len(rows)} forecast entries")

            current_hour = current_time.hour

            for row in rows:
                try:
                    forecast_entry = self._parse_forecast_row(row)
                    if forecast_entry:
                        # Parse the time to check if it's in the future
                        time_str = forecast_entry['time'].strip()
                        hour = self._parse_hour(time_str)

                        # Only include future hours
                        if self._is_future_hour(hour, current_hour):
                            forecast_entry['data_type'] = 'forecast'
                            forecast_data.append(forecast_entry)
                except Exception as e:
                    print(f"Error parsing forecast row: {e}")
                    continue

            # Respectful crawling
            time.sleep(self.crawl_delay)

            return forecast_data

        except TimeoutException:
            print(f"Timeout loading page: {url}")
            return []
        except Exception as e:
            print(f"Error scraping forecast: {e}")
            return []

    def scrape_historical(self, location_code: str, date: datetime) -> List[Dict]:
        """
        Scrape historical (actual) weather data for a specific date

        Args:
            location_code: Location code (e.g., 'EGLC')
            date: Date to scrape historical data for

        Returns:
            List of dictionaries containing actual weather data
        """
        date_str = date.strftime('%Y-%m-%d')
        # URL format: /history/daily/gb/london/EGLC/date/2025-11-13
        url = f"https://www.wunderground.com/history/daily/gb/london/{location_code}/date/{date_str}"
        print(f"\nScraping historical data: {url}")

        try:
            self.driver.get(url)

            # Wait for the page to load
            wait = WebDriverWait(self.driver, 15)
            time.sleep(5)  # Extra time for dynamic content

            historical_data = []

            # Look for TABLE 2 (hourly observations table)
            # Based on debug script, we need the 2nd table on the page
            rows = []
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            print(f"Found {len(tables)} tables on the page")

            if len(tables) >= 2:
                # Use the 2nd table (index 1) which contains hourly observations
                hourly_table = tables[1]
                rows = hourly_table.find_elements(By.CSS_SELECTOR, "tbody tr")
                print(f"Using TABLE 2 (hourly observations): Found {len(rows)} historical entries")
            elif len(tables) == 1:
                # Fallback to first table if only one exists
                print("Only 1 table found, using it as fallback")
                rows = tables[0].find_elements(By.CSS_SELECTOR, "tbody tr")
                print(f"Found {len(rows)} entries")
            else:
                print("No tables found on the page")

            for row in rows:
                try:
                    historical_entry = self._parse_historical_row(row)
                    if historical_entry:
                        historical_entry['data_type'] = 'actual'
                        historical_data.append(historical_entry)
                except Exception as e:
                    print(f"Error parsing historical row: {e}")
                    continue

            # Respectful crawling
            time.sleep(self.crawl_delay)

            return historical_data

        except TimeoutException:
            print(f"Timeout loading page: {url}")
            return []
        except Exception as e:
            print(f"Error scraping historical data: {e}")
            return []

    def _parse_hour(self, time_str: str) -> int:
        """Parse hour from time string like '1 :00 am' or '12 :00 pm'"""
        try:
            # Remove extra spaces and parse
            time_str = time_str.replace(' :', ':').strip()
            time_obj = datetime.strptime(time_str, '%I:%M %p')
            return time_obj.hour
        except:
            return -1

    def _is_future_hour(self, forecast_hour: int, current_hour: int) -> bool:
        """Check if forecast hour is in the future"""
        if forecast_hour == -1:
            return True  # Include if we can't parse (to be safe)

        # Handle midnight wraparound
        if forecast_hour < current_hour:
            # Could be next day
            return True
        elif forecast_hour > current_hour:
            return True
        else:
            # Same hour - include it
            return True

    def _parse_forecast_row(self, row) -> Optional[Dict]:
        """Parse a forecast row - same as before"""
        try:
            cells = row.find_elements(By.TAG_NAME, "td")

            if len(cells) < 10:
                return None

            forecast = {
                'timestamp': datetime.now(self.london_tz).isoformat(),
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

    def _parse_historical_row(self, row) -> Optional[Dict]:
        """
        Parse a historical data row from TABLE 2 (hourly observations)
        Column structure:
        0: Time, 1: Temperature, 2: Dew Point, 3: Humidity, 4: Wind (direction),
        5: Wind Speed, 6: Wind Gust, 7: Pressure, 8: Precip., 9: Condition
        """
        try:
            cells = row.find_elements(By.TAG_NAME, "td")

            if len(cells) < 9:
                return None

            # Combine wind direction and speed for compatibility with forecast format
            wind_dir = cells[4].text.strip() if len(cells) > 4 else ''
            wind_speed = cells[5].text.strip() if len(cells) > 5 else ''
            wind_combined = f"{wind_speed} {wind_dir}".strip() if wind_dir and wind_speed else wind_speed

            # Map to same structure as forecast data
            historical = {
                'timestamp': datetime.now(self.london_tz).isoformat(),
                'time': cells[0].text.strip() if len(cells) > 0 else '',
                'temperature': cells[1].text.strip() if len(cells) > 1 else '',
                'dew_point': cells[2].text.strip() if len(cells) > 2 else '',
                'humidity': cells[3].text.strip() if len(cells) > 3 else '',
                'wind': wind_combined,
                'pressure': cells[7].text.strip() if len(cells) > 7 else '',
                'precip_amount': cells[8].text.strip() if len(cells) > 8 else '',
                'condition': cells[9].text.strip() if len(cells) > 9 else '',
                # Fields that are not in historical data
                'feels_like': '',
                'precip_chance': '',
                'cloud_cover': '',
            }

            return historical

        except Exception as e:
            print(f"Error parsing historical entry: {e}")
            return None

    def _extract_text_from_cell(self, cell) -> str:
        """Extract text from a cell, checking img alt text first"""
        try:
            imgs = cell.find_elements(By.TAG_NAME, "img")
            if imgs:
                alt_text = imgs[0].get_attribute('alt')
                if alt_text:
                    return alt_text
            return cell.text.strip()
        except:
            return ''

    def save_to_json(self, data: List[Dict], filename: str):
        """Save data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")

    def save_to_csv(self, data: List[Dict], filename: str):
        """Save data to CSV file"""
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
    """Main function"""
    location_code = "EGLC"  # London City Airport

    print("="*70)
    print("Weather Underground Complete Scraper")
    print("Collecting both FORECAST and ACTUAL weather data for ML training")
    print("="*70)

    with WundergroundCompleteScraper(headless=False, crawl_delay=2) as scraper:
        # Step 1: Get current time at EGLC
        current_time = scraper.get_eglc_current_time()

        # Step 2: Scrape forecast data (future hours only)
        print("\n" + "="*70)
        print("STEP 1: Scraping FORECAST data (future hours)")
        print("="*70)
        forecast_data = scraper.scrape_forecast(location_code, current_time)
        print(f"✓ Collected {len(forecast_data)} forecast records")

        # Step 3: Scrape historical data (today's actual data)
        print("\n" + "="*70)
        print("STEP 2: Scraping ACTUAL (historical) data for today")
        print("="*70)
        historical_data = scraper.scrape_historical(location_code, current_time)
        print(f"✓ Collected {len(historical_data)} actual records")

        # Combine data
        all_data = historical_data + forecast_data

        if all_data:
            timestamp = current_time.strftime('%Y%m%d_%H%M%S')

            # Save combined data
            scraper.save_to_json(all_data, f'weather_data_{location_code}_{timestamp}.json')
            scraper.save_to_csv(all_data, f'weather_data_{location_code}_{timestamp}.csv')

            # Save separate files for analysis
            if forecast_data:
                scraper.save_to_csv(forecast_data, f'forecast_{location_code}_{timestamp}.csv')
            if historical_data:
                scraper.save_to_csv(historical_data, f'actual_{location_code}_{timestamp}.csv')

            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(f"Location: {location_code} (London City Airport)")
            print(f"Local time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"Actual data records: {len(historical_data)}")
            print(f"Forecast data records: {len(forecast_data)}")
            print(f"Total records: {len(all_data)}")

            if forecast_data:
                print("\nSample forecast record:")
                print(json.dumps(forecast_data[0], indent=2))

            if historical_data:
                print("\nSample actual record:")
                print(json.dumps(historical_data[0], indent=2))

        else:
            print("\n✗ No data retrieved")


if __name__ == "__main__":
    main()
