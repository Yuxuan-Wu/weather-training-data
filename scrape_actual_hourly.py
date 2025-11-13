#!/usr/bin/env python3
"""
Hourly Actual Data Scraper
Scrapes the most recent actual weather observation for EGLC
AND Thames River water temperature at 0.35m depth
Runs every hour via GitHub Actions
"""

import os
import time
import csv
from datetime import datetime
import pytz
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def setup_driver():
    """Setup Chrome WebDriver for GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')

    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    return driver


def fetch_thames_water_temp():
    """Fetch latest Thames water temperature from ThingSpeak API"""
    url = "https://api.thingspeak.com/channels/521315/feeds.json?results=1"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        feeds = data.get('feeds', [])
        if not feeds:
            print("Warning: No Thames water temperature data available")
            return None

        latest = feeds[0]

        return {
            'water_temp_0_35m': latest.get('field1', ''),  # Surface temp at 0.35m
            'water_temp_2m': latest.get('field2', ''),      # Mid-depth at 2m
            'water_temp_7m': latest.get('field3', ''),      # Deep at 7m
            'water_temp_entry_id': latest.get('entry_id', '')
        }
    except Exception as e:
        print(f"Warning: Could not fetch Thames water temperature: {e}")
        return None


def scrape_latest_actual(location_code='EGLC'):
    """Scrape the most recent actual weather observation"""
    london_tz = pytz.timezone('Europe/London')
    current_time = datetime.now(london_tz)
    date_str = current_time.strftime('%Y-%m-%d')

    url = f"https://www.wunderground.com/history/daily/gb/london/{location_code}/date/{date_str}"

    print(f"Scraping actual data: {url}")
    print(f"Current time at EGLC: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    driver = setup_driver()

    try:
        driver.get(url)
        time.sleep(8)  # Wait for page to load

        # Get TABLE 2 (hourly observations)
        tables = driver.find_elements(By.TAG_NAME, "table")

        if len(tables) < 2:
            print(f"Error: Expected 2 tables, found {len(tables)}")
            return None

        # Get the last row from TABLE 2 (most recent observation)
        hourly_table = tables[1]
        rows = hourly_table.find_elements(By.CSS_SELECTOR, "tbody tr")

        if not rows:
            print("No data rows found")
            return None

        # Get the most recent observation (last row)
        latest_row = rows[-1]
        cells = latest_row.find_elements(By.TAG_NAME, "td")

        if len(cells) < 9:
            print(f"Error: Row has only {len(cells)} cells, expected at least 9")
            return None

        # Parse the data
        wind_dir = cells[4].text.strip()
        wind_speed = cells[5].text.strip()
        wind_combined = f"{wind_speed} {wind_dir}".strip() if wind_dir and wind_speed else wind_speed

        observation = {
            'scrape_timestamp': current_time.isoformat(),
            'observation_time': cells[0].text.strip(),
            'temperature': cells[1].text.strip(),
            'dew_point': cells[2].text.strip(),
            'humidity': cells[3].text.strip(),
            'wind': wind_combined,
            'pressure': cells[7].text.strip(),
            'precip_amount': cells[8].text.strip(),
            'condition': cells[9].text.strip() if len(cells) > 9 else '',
            'location': location_code,
            'date': date_str
        }

        print(f"✓ Scraped observation at {observation['observation_time']}")
        return observation

    except Exception as e:
        print(f"Error scraping: {e}")
        return None
    finally:
        driver.quit()


def save_to_csv(observation, data_dir='data/actual'):
    """Append observation to daily CSV file"""
    os.makedirs(data_dir, exist_ok=True)

    # Use date for filename
    date_str = observation['date']
    filename = os.path.join(data_dir, f"actual_{observation['location']}_{date_str}.csv")

    # Check if file exists to determine if we need to write headers
    file_exists = os.path.isfile(filename)

    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=observation.keys())

        if not file_exists:
            writer.writeheader()

        writer.writerow(observation)

    print(f"✓ Data saved to {filename}")
    return filename


def main():
    print("="*70)
    print("Hourly Actual Weather + Water Temperature Scraper")
    print("="*70)

    # Scrape weather data
    observation = scrape_latest_actual('EGLC')

    if not observation:
        print("\n✗ FAILED: No weather data scraped")
        exit(1)

    # Fetch Thames water temperature
    print("\nFetching Thames River water temperature...")
    water_data = fetch_thames_water_temp()

    if water_data:
        # Merge water temperature data into observation
        observation.update(water_data)
        print(f"✓ Added water temperature: {water_data['water_temp_0_35m']}°C @ 0.35m")
    else:
        # Add empty fields if water data unavailable
        observation.update({
            'water_temp_0_35m': '',
            'water_temp_2m': '',
            'water_temp_7m': '',
            'water_temp_entry_id': ''
        })

    # Save combined data
    filename = save_to_csv(observation)
    print(f"\n✓ SUCCESS: Scraped and saved 1 observation with water temperature")
    print(f"File: {filename}")


if __name__ == "__main__":
    main()
