#!/usr/bin/env python3
"""
Unified Weather Data Scraper with SQLite Storage
Scrapes actual observations and forecasts for EGLC
Integrates Thames River water temperature data
Optimized for ML training data collection
"""

import os
import sys
import time
import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================================
# DATABASE MANAGEMENT
# ============================================================================

class WeatherDatabase:
    """Manages SQLite database for weather data"""

    def __init__(self, db_path='data/weather_data.db'):
        """Initialize database connection and create tables if needed"""
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries

        # Register datetime adapters/converters
        sqlite3.register_adapter(datetime, lambda val: val.isoformat())
        sqlite3.register_converter("TIMESTAMP", lambda val: datetime.fromisoformat(val.decode()))

        self._create_tables()

    def _create_tables(self):
        """Create database schema"""
        cursor = self.conn.cursor()

        # Actual weather observations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scrape_timestamp TIMESTAMP NOT NULL,
                observation_timestamp TIMESTAMP NOT NULL,
                location TEXT NOT NULL,
                temperature_f REAL,
                dew_point_f REAL,
                humidity_pct INTEGER,
                wind_speed_mph REAL,
                wind_direction TEXT,
                wind_gust_mph REAL,
                pressure_in REAL,
                precip_amount_in REAL,
                condition TEXT,
                water_temp_0_35m_c REAL,
                water_temp_2m_c REAL,
                water_temp_7m_c REAL,
                water_temp_entry_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(location, observation_timestamp)
            )
        ''')

        # Weather forecasts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scrape_timestamp TIMESTAMP NOT NULL,
                forecast_timestamp TIMESTAMP NOT NULL,
                location TEXT NOT NULL,
                temperature_f REAL,
                feels_like_f REAL,
                dew_point_f REAL,
                humidity_pct INTEGER,
                wind_speed_mph REAL,
                wind_direction TEXT,
                pressure_in REAL,
                precip_chance_pct INTEGER,
                precip_amount_in REAL,
                cloud_cover_pct INTEGER,
                condition TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(location, forecast_timestamp, scrape_timestamp)
            )
        ''')

        # Create indexes for fast queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_obs_timestamp
            ON weather_observations(observation_timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_obs_location
            ON weather_observations(location)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_forecast_timestamp
            ON weather_forecasts(forecast_timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_forecast_scrape
            ON weather_forecasts(scrape_timestamp)
        ''')

        self.conn.commit()

    def insert_observation(self, obs: Dict) -> bool:
        """Insert weather observation, skip if duplicate"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO weather_observations (
                    scrape_timestamp, observation_timestamp, location,
                    temperature_f, dew_point_f, humidity_pct,
                    wind_speed_mph, wind_direction, wind_gust_mph,
                    pressure_in, precip_amount_in, condition,
                    water_temp_0_35m_c, water_temp_2m_c, water_temp_7m_c,
                    water_temp_entry_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                obs['scrape_timestamp'], obs['observation_timestamp'], obs['location'],
                obs.get('temperature_f'), obs.get('dew_point_f'), obs.get('humidity_pct'),
                obs.get('wind_speed_mph'), obs.get('wind_direction'), obs.get('wind_gust_mph'),
                obs.get('pressure_in'), obs.get('precip_amount_in'), obs.get('condition'),
                obs.get('water_temp_0_35m_c'), obs.get('water_temp_2m_c'), obs.get('water_temp_7m_c'),
                obs.get('water_temp_entry_id')
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate entry, skip
            return False

    def insert_forecast(self, forecast: Dict) -> bool:
        """Insert weather forecast, skip if duplicate"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO weather_forecasts (
                    scrape_timestamp, forecast_timestamp, location,
                    temperature_f, feels_like_f, dew_point_f, humidity_pct,
                    wind_speed_mph, wind_direction, pressure_in,
                    precip_chance_pct, precip_amount_in, cloud_cover_pct, condition
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                forecast['scrape_timestamp'], forecast['forecast_timestamp'], forecast['location'],
                forecast.get('temperature_f'), forecast.get('feels_like_f'), forecast.get('dew_point_f'),
                forecast.get('humidity_pct'), forecast.get('wind_speed_mph'), forecast.get('wind_direction'),
                forecast.get('pressure_in'), forecast.get('precip_chance_pct'), forecast.get('precip_amount_in'),
                forecast.get('cloud_cover_pct'), forecast.get('condition')
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate entry, skip
            return False

    def get_observation_count(self, location: str = None) -> int:
        """Get total number of observations"""
        cursor = self.conn.cursor()
        if location:
            cursor.execute('SELECT COUNT(*) FROM weather_observations WHERE location = ?', (location,))
        else:
            cursor.execute('SELECT COUNT(*) FROM weather_observations')
        return cursor.fetchone()[0]

    def get_forecast_count(self, location: str = None) -> int:
        """Get total number of forecasts"""
        cursor = self.conn.cursor()
        if location:
            cursor.execute('SELECT COUNT(*) FROM weather_forecasts WHERE location = ?', (location,))
        else:
            cursor.execute('SELECT COUNT(*) FROM weather_forecasts')
        return cursor.fetchone()[0]

    def close(self):
        """Close database connection"""
        self.conn.close()


# ============================================================================
# UTILITIES
# ============================================================================

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


def parse_temperature(temp_str: str) -> Optional[float]:
    """Parse temperature string like '55 °F' to float"""
    try:
        return float(temp_str.replace('°F', '').replace('°', '').strip())
    except (ValueError, AttributeError):
        return None


def parse_percentage(pct_str: str) -> Optional[int]:
    """Parse percentage string like '77 %' to int"""
    try:
        return int(pct_str.replace('%', '').strip())
    except (ValueError, AttributeError):
        return None


def parse_inches(inch_str: str) -> Optional[float]:
    """Parse inches string like '29.60 in' or '0.0 in' to float"""
    try:
        return float(inch_str.replace('in', '').strip())
    except (ValueError, AttributeError):
        return None


def parse_wind(wind_str: str) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """Parse wind string like '12 mph E' or '23 mph' to (speed, direction, gust)

    Returns:
        (speed_mph, direction, gust_mph)
    """
    try:
        parts = wind_str.strip().split()
        speed = float(parts[0]) if len(parts) > 0 else None
        direction = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 and not parts[1] == 'mph' else None)
        # Note: gust not typically in this format, would need separate parsing
        return speed, direction, None
    except (ValueError, IndexError, AttributeError):
        return None, None, None


def parse_observation_time_to_utc(obs_time_str: str, date_str: str) -> Optional[datetime]:
    """Parse observation time like '1:50 AM' and convert to UTC datetime

    Args:
        obs_time_str: String like "1:50 AM" or "12:20 PM"
        date_str: Date string like "2025-11-15"

    Returns:
        datetime object in UTC, or None if parsing fails
    """
    try:
        london_tz = pytz.timezone('Europe/London')

        # Parse the time string
        time_obj = datetime.strptime(obs_time_str.strip(), '%I:%M %p').time()

        # Combine with date to get local datetime
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        local_dt = datetime.combine(date_obj, time_obj)

        # Localize to London timezone, then convert to UTC
        local_dt = london_tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.UTC)

        return utc_dt

    except Exception as e:
        print(f"Warning: Could not parse observation time '{obs_time_str}': {e}")
        return None


# ============================================================================
# WATER TEMPERATURE DATA
# ============================================================================

def fetch_water_temperature_data(num_results=300) -> List[Dict]:
    """Fetch recent Thames water temperature readings from ThingSpeak API

    Args:
        num_results: Number of recent readings to fetch (default 300 for ~25 hours)

    Returns:
        List of water temperature readings with timestamps
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
            try:
                water_readings.append({
                    'timestamp': datetime.fromisoformat(feed['created_at'].replace('Z', '+00:00')),
                    'temp_0_35m': float(feed.get('field1', 0)) if feed.get('field1') else None,
                    'temp_2m': float(feed.get('field2', 0)) if feed.get('field2') else None,
                    'temp_7m': float(feed.get('field3', 0)) if feed.get('field3') else None,
                    'entry_id': int(feed.get('entry_id', 0)) if feed.get('entry_id') else None
                })
            except (ValueError, TypeError) as e:
                print(f"Warning: Skipping malformed water temp reading: {e}")
                continue

        return water_readings

    except Exception as e:
        print(f"Warning: Could not fetch Thames water temperature: {e}")
        return []


def find_closest_water_temp(target_timestamp: datetime, water_readings: List[Dict]) -> Optional[Dict]:
    """Find the water temperature reading closest in time to target timestamp

    Args:
        target_timestamp: UTC datetime to match
        water_readings: List of water temp readings with 'timestamp' field

    Returns:
        Water temp dict with closest timestamp, or None
    """
    if not water_readings or not target_timestamp:
        return None

    closest_reading = None
    min_time_diff = None

    for reading in water_readings:
        time_diff = abs((reading['timestamp'] - target_timestamp).total_seconds())

        if min_time_diff is None or time_diff < min_time_diff:
            min_time_diff = time_diff
            closest_reading = reading

    return closest_reading


# ============================================================================
# ACTUAL WEATHER SCRAPER
# ============================================================================

class ActualWeatherScraper:
    """Scrapes actual weather observations from Weather Underground"""

    def __init__(self, location='EGLC'):
        self.location = location
        self.london_tz = pytz.timezone('Europe/London')

    def scrape_observations(self) -> List[Dict]:
        """Scrape ALL available weather observations for today

        Returns:
            List of observation dictionaries
        """
        current_time = datetime.now(self.london_tz)
        date_str = current_time.strftime('%Y-%m-%d')

        url = f"https://www.wunderground.com/history/daily/gb/london/{self.location}/date/{date_str}"

        print(f"Scraping actual observations: {url}")
        print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        driver = setup_driver()
        observations = []

        try:
            driver.get(url)
            time.sleep(8)  # Wait for page to load

            # Get TABLE 2 (hourly observations)
            tables = driver.find_elements(By.TAG_NAME, "table")

            if len(tables) < 2:
                print(f"Error: Expected 2 tables, found {len(tables)}")
                return []

            # Get ALL rows from the hourly observations table
            hourly_table = tables[1]
            rows = hourly_table.find_elements(By.CSS_SELECTOR, "tbody tr")

            if not rows:
                print("No observation rows found")
                return []

            # Parse ALL rows
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")

                if len(cells) < 9:
                    continue

                # Parse observation time to UTC
                obs_time_str = cells[0].text.strip()
                obs_timestamp = parse_observation_time_to_utc(obs_time_str, date_str)

                if not obs_timestamp:
                    print(f"Skipping observation with unparseable time: {obs_time_str}")
                    continue

                # Parse wind (may include direction)
                wind_str = f"{cells[5].text.strip()} {cells[4].text.strip()}".strip()
                wind_speed, wind_direction, wind_gust = parse_wind(wind_str)

                observation = {
                    'scrape_timestamp': current_time.astimezone(pytz.UTC),
                    'observation_timestamp': obs_timestamp,
                    'location': self.location,
                    'temperature_f': parse_temperature(cells[1].text),
                    'dew_point_f': parse_temperature(cells[2].text),
                    'humidity_pct': parse_percentage(cells[3].text),
                    'wind_speed_mph': wind_speed,
                    'wind_direction': wind_direction,
                    'wind_gust_mph': wind_gust,
                    'pressure_in': parse_inches(cells[7].text),
                    'precip_amount_in': parse_inches(cells[8].text),
                    'condition': cells[9].text.strip() if len(cells) > 9 else None
                }

                observations.append(observation)

            print(f"✓ Scraped {len(observations)} observations")
            return observations

        except Exception as e:
            print(f"Error scraping observations: {e}")
            return []
        finally:
            driver.quit()


# ============================================================================
# FORECAST SCRAPER
# ============================================================================

class ForecastScraper:
    """Scrapes weather forecasts from Weather Underground"""

    def __init__(self, location='EGLC'):
        self.location = location
        self.london_tz = pytz.timezone('Europe/London')

    def _parse_forecast_hour(self, hour_str: str, base_time: datetime) -> Optional[datetime]:
        """Parse forecast hour string to timestamp

        Args:
            hour_str: String like "12 :00 am" or "1 :00 pm"
            base_time: Base time for calculating the forecast timestamp

        Returns:
            UTC datetime for the forecast hour
        """
        try:
            # Clean up the hour string (remove extra spaces)
            hour_str = hour_str.replace(' :', ':').strip()

            # Parse the time
            forecast_time = datetime.strptime(hour_str, '%I:%M %p').time()

            # Start from current day
            forecast_dt = datetime.combine(base_time.date(), forecast_time)
            forecast_dt = self.london_tz.localize(forecast_dt)

            # If forecast time is before current time, it must be for the next day
            if forecast_dt <= base_time:
                forecast_dt += timedelta(days=1)

            return forecast_dt.astimezone(pytz.UTC)

        except Exception as e:
            print(f"Warning: Could not parse forecast hour '{hour_str}': {e}")
            return None

    def scrape_forecast(self, hours=24) -> List[Dict]:
        """Scrape hourly forecast data

        Args:
            hours: Number of hours to forecast (default 24)

        Returns:
            List of forecast dictionaries
        """
        current_time = datetime.now(self.london_tz)

        url = f"https://www.wunderground.com/hourly/{self.location}"

        print(f"Scraping forecast: {url}")
        print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        driver = setup_driver()
        forecasts = []

        try:
            driver.get(url)

            # Wait for the table to load
            wait = WebDriverWait(driver, 15)
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "lib-city-hourly-forecast"))
            )
            time.sleep(5)

            # Find all forecast rows
            rows = driver.find_elements(By.CSS_SELECTOR, "lib-city-hourly-forecast table tbody tr")

            if not rows:
                print("No forecast rows found")
                return []

            print(f"Found {len(rows)} forecast entries")

            # Parse forecast rows (limit to requested hours)
            for row in rows[:hours]:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")

                    if len(cells) < 10:
                        continue

                    # Parse forecast hour to timestamp
                    hour_str = cells[0].text.strip()
                    forecast_timestamp = self._parse_forecast_hour(hour_str, current_time)

                    if not forecast_timestamp:
                        print(f"Skipping forecast with unparseable time: {hour_str}")
                        continue

                    # Extract condition from image alt text
                    condition = ''
                    if len(cells) > 1:
                        imgs = cells[1].find_elements(By.TAG_NAME, "img")
                        if imgs:
                            condition = imgs[0].get_attribute('alt') or ''
                        if not condition:
                            condition = cells[1].text.strip()

                    # Parse wind
                    wind_speed, wind_direction, _ = parse_wind(cells[9].text)

                    forecast = {
                        'scrape_timestamp': current_time.astimezone(pytz.UTC),
                        'forecast_timestamp': forecast_timestamp,
                        'location': self.location,
                        'condition': condition,
                        'temperature_f': parse_temperature(cells[2].text),
                        'feels_like_f': parse_temperature(cells[3].text),
                        'precip_chance_pct': parse_percentage(cells[4].text),
                        'precip_amount_in': parse_inches(cells[5].text),
                        'cloud_cover_pct': parse_percentage(cells[6].text),
                        'dew_point_f': parse_temperature(cells[7].text),
                        'humidity_pct': parse_percentage(cells[8].text),
                        'wind_speed_mph': wind_speed,
                        'wind_direction': wind_direction,
                        'pressure_in': parse_inches(cells[10].text) if len(cells) > 10 else None
                    }

                    forecasts.append(forecast)

                except Exception as e:
                    print(f"Error parsing forecast row: {e}")
                    continue

            print(f"✓ Scraped {len(forecasts)} forecasts")
            return forecasts

        except Exception as e:
            print(f"Error scraping forecast: {e}")
            return []
        finally:
            driver.quit()


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Unified Weather Data Scraper with SQLite storage'
    )
    parser.add_argument(
        '--mode',
        choices=['actual', 'forecast', 'both'],
        default='actual',
        help='Scraping mode: actual observations, forecast, or both'
    )
    parser.add_argument(
        '--location',
        default='EGLC',
        help='Location code (default: EGLC)'
    )
    parser.add_argument(
        '--db',
        default='data/weather_data.db',
        help='Database file path (default: data/weather_data.db)'
    )

    args = parser.parse_args()

    print("="*70)
    print(f"Weather Data Scraper - Mode: {args.mode.upper()}")
    print("="*70)

    # Initialize database
    db = WeatherDatabase(args.db)

    total_new = 0
    total_skipped = 0

    # Scrape actual observations
    if args.mode in ['actual', 'both']:
        print("\n[ACTUAL OBSERVATIONS]")
        scraper = ActualWeatherScraper(args.location)
        observations = scraper.scrape_observations()

        if observations:
            # Fetch water temperature data
            print("\nFetching water temperature data...")
            water_readings = fetch_water_temperature_data(num_results=300)
            print(f"✓ Fetched {len(water_readings)} water temperature readings")

            # Save observations with matched water temp
            print("\nSaving to database...")
            new_count = 0
            skipped_count = 0

            for obs in observations:
                # Find closest water temp reading
                water_data = find_closest_water_temp(obs['observation_timestamp'], water_readings)

                if water_data:
                    obs['water_temp_0_35m_c'] = water_data['temp_0_35m']
                    obs['water_temp_2m_c'] = water_data['temp_2m']
                    obs['water_temp_7m_c'] = water_data['temp_7m']
                    obs['water_temp_entry_id'] = water_data['entry_id']

                # Insert to database
                if db.insert_observation(obs):
                    new_count += 1
                else:
                    skipped_count += 1

            total_new += new_count
            total_skipped += skipped_count

            print(f"✓ Added {new_count} new observations")
            print(f"⊘ Skipped {skipped_count} duplicates")

    # Scrape forecasts
    if args.mode in ['forecast', 'both']:
        print("\n[WEATHER FORECASTS]")
        scraper = ForecastScraper(args.location)
        forecasts = scraper.scrape_forecast()

        if forecasts:
            print("\nSaving to database...")
            new_count = 0
            skipped_count = 0

            for forecast in forecasts:
                if db.insert_forecast(forecast):
                    new_count += 1
                else:
                    skipped_count += 1

            total_new += new_count
            total_skipped += skipped_count

            print(f"✓ Added {new_count} new forecasts")
            print(f"⊘ Skipped {skipped_count} duplicates")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Database: {args.db}")
    print(f"Total observations: {db.get_observation_count()}")
    print(f"Total forecasts: {db.get_forecast_count()}")
    print(f"New records added: {total_new}")
    print(f"Duplicates skipped: {total_skipped}")
    print("\n✓ SUCCESS")

    db.close()


if __name__ == "__main__":
    main()
