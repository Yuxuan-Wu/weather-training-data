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


def fetch_thames_water_temp(num_results=10):
    """Fetch recent Thames water temperature readings from ThingSpeak API

    Args:
        num_results: Number of recent readings to fetch (default 10 for backfill)

    Returns:
        List of water temperature readings, ordered oldest to newest
    """
    url = f"https://api.thingspeak.com/channels/521315/feeds.json?results={num_results}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        feeds = data.get('feeds', [])
        if not feeds:
            print("Warning: No Thames water temperature data available")
            return []

        # Convert all feeds to our format
        water_readings = []
        for feed in feeds:
            water_readings.append({
                'water_temp_0_35m': feed.get('field1', ''),
                'water_temp_2m': feed.get('field2', ''),
                'water_temp_7m': feed.get('field3', ''),
                'water_temp_entry_id': feed.get('entry_id', ''),
                'water_temp_timestamp': feed.get('created_at', '')  # ISO timestamp from ThingSpeak
            })

        print(f"✓ Fetched {len(water_readings)} water temperature readings from ThingSpeak")
        return water_readings

    except Exception as e:
        print(f"Warning: Could not fetch Thames water temperature: {e}")
        return []


def scrape_all_observations(location_code='EGLC'):
    """Scrape ALL available weather observations from the hourly table for backfill

    Returns:
        List of observations (oldest to newest)
    """
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
            return []

        # Get ALL rows from TABLE 2
        hourly_table = tables[1]
        rows = hourly_table.find_elements(By.CSS_SELECTOR, "tbody tr")

        if not rows:
            print("No data rows found")
            return []

        observations = []

        # Parse ALL rows (they're already in chronological order, oldest to newest)
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")

            if len(cells) < 9:
                print(f"Warning: Row has only {len(cells)} cells, skipping")
                continue

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

            observations.append(observation)

        print(f"✓ Scraped {len(observations)} observations from Weather Underground")
        return observations

    except Exception as e:
        print(f"Error scraping: {e}")
        return []
    finally:
        driver.quit()


def load_existing_observations(filename):
    """Load existing observations from CSV to check for duplicates

    Returns:
        Set of observation_time strings that already exist
    """
    if not os.path.isfile(filename):
        return set()

    existing_times = set()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_times.add(row['observation_time'])
    except Exception as e:
        print(f"Warning: Could not read existing file {filename}: {e}")

    return existing_times


def find_closest_water_temp(observation_time, water_readings):
    """Find the water temperature reading closest in time to the weather observation

    Args:
        observation_time: String like "1:50 AM" or "12:20 PM"
        water_readings: List of water temp dicts with 'water_temp_timestamp'

    Returns:
        Water temp dict with the closest timestamp, or None if no readings available
    """
    if not water_readings:
        return None

    # For now, just return the most recent reading
    # TODO: Could improve by parsing observation_time and matching timestamps
    return water_readings[-1]


def save_observations_to_csv(observations, water_readings, data_dir='data/actual'):
    """Save multiple observations to CSV, skipping duplicates

    Args:
        observations: List of weather observation dicts
        water_readings: List of water temperature reading dicts

    Returns:
        Tuple of (filename, num_new, num_skipped)
    """
    if not observations:
        return None, 0, 0

    os.makedirs(data_dir, exist_ok=True)

    # Use date from first observation
    date_str = observations[0]['date']
    location = observations[0]['location']
    filename = os.path.join(data_dir, f"actual_{location}_{date_str}.csv")

    # Load existing observations to avoid duplicates
    existing_times = load_existing_observations(filename)
    file_exists = os.path.isfile(filename)

    # Define fieldnames (including water temp fields)
    fieldnames = [
        'scrape_timestamp', 'observation_time', 'temperature', 'dew_point',
        'humidity', 'wind', 'pressure', 'precip_amount', 'condition',
        'location', 'date', 'water_temp_0_35m', 'water_temp_2m',
        'water_temp_7m', 'water_temp_entry_id'
    ]

    num_new = 0
    num_skipped = 0

    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Write header if new file
        if not file_exists:
            writer.writeheader()

        # Write each observation if it's new
        for obs in observations:
            obs_time = obs['observation_time']

            if obs_time in existing_times:
                print(f"  ⊘ Skipping duplicate: {obs_time}")
                num_skipped += 1
                continue

            # Find matching water temperature reading
            water_data = find_closest_water_temp(obs_time, water_readings)

            if water_data:
                obs.update({
                    'water_temp_0_35m': water_data.get('water_temp_0_35m', ''),
                    'water_temp_2m': water_data.get('water_temp_2m', ''),
                    'water_temp_7m': water_data.get('water_temp_7m', ''),
                    'water_temp_entry_id': water_data.get('water_temp_entry_id', '')
                })
            else:
                obs.update({
                    'water_temp_0_35m': '',
                    'water_temp_2m': '',
                    'water_temp_7m': '',
                    'water_temp_entry_id': ''
                })

            writer.writerow(obs)
            existing_times.add(obs_time)  # Track what we just added
            num_new += 1
            print(f"  ✓ Added: {obs_time}")

    print(f"\n✓ Saved to {filename}")
    return filename, num_new, num_skipped


def main():
    print("="*70)
    print("Hourly Actual Weather + Water Temperature Scraper (with Backfill)")
    print("="*70)

    # Scrape ALL available weather observations (backfill mode)
    print("\nScraping all available observations from Weather Underground...")
    observations = scrape_all_observations('EGLC')

    if not observations:
        print("\n✗ FAILED: No weather data scraped")
        exit(1)

    print(f"Found {len(observations)} total observations on the page")

    # Fetch recent Thames water temperature readings (backfill mode)
    print("\nFetching recent Thames River water temperature readings...")
    water_readings = fetch_thames_water_temp(num_results=20)

    if water_readings:
        print(f"✓ Fetched {len(water_readings)} water temperature readings")
        print(f"  Latest: {water_readings[-1].get('water_temp_0_35m', 'N/A')}°C @ 0.35m")
    else:
        print("⚠ No water temperature data available")

    # Save all new observations with matched water temperature data
    print("\nSaving observations (skipping duplicates)...")
    filename, num_new, num_skipped = save_observations_to_csv(observations, water_readings)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total observations found:    {len(observations)}")
    print(f"New observations added:      {num_new}")
    print(f"Duplicates skipped:          {num_skipped}")
    print(f"File: {filename}")

    if num_new == 0:
        print("\n✓ SUCCESS: No new data to add (all observations already recorded)")
    else:
        print(f"\n✓ SUCCESS: Added {num_new} new observation(s) with water temperature")


if __name__ == "__main__":
    main()
