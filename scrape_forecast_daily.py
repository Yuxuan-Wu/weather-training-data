#!/usr/bin/env python3
"""
Daily Forecast Scraper
Scrapes the next day's hourly forecast for EGLC
Runs daily at 11:59 PM London time via GitHub Actions
"""

import os
import time
import csv
from datetime import datetime, timedelta
import pytz

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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


def scrape_next_day_forecast(location_code='EGLC'):
    """Scrape the next 24 hours of forecast data"""
    london_tz = pytz.timezone('Europe/London')
    current_time = datetime.now(london_tz)
    tomorrow = current_time + timedelta(days=1)

    url = f"https://www.wunderground.com/hourly/{location_code}"

    print(f"Scraping forecast: {url}")
    print(f"Current time at EGLC: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Forecasting for: {tomorrow.strftime('%Y-%m-%d')}")

    driver = setup_driver()
    forecast_data = []

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

        # We want approximately the next 24 hours
        # Take all rows (typically shows next 24-48 hours)
        for row in rows[:24]:  # Limit to 24 hours
            try:
                cells = row.find_elements(By.TAG_NAME, "td")

                if len(cells) < 10:
                    continue

                # Extract condition from image alt text
                condition = ''
                if len(cells) > 1:
                    imgs = cells[1].find_elements(By.TAG_NAME, "img")
                    if imgs:
                        condition = imgs[0].get_attribute('alt') or ''
                    if not condition:
                        condition = cells[1].text.strip()

                forecast = {
                    'scrape_timestamp': current_time.isoformat(),
                    'forecast_date': tomorrow.strftime('%Y-%m-%d'),
                    'forecast_hour': cells[0].text.strip(),
                    'condition': condition,
                    'temperature': cells[2].text.strip(),
                    'feels_like': cells[3].text.strip(),
                    'precip_chance': cells[4].text.strip(),
                    'precip_amount': cells[5].text.strip(),
                    'cloud_cover': cells[6].text.strip(),
                    'dew_point': cells[7].text.strip(),
                    'humidity': cells[8].text.strip(),
                    'wind': cells[9].text.strip(),
                    'pressure': cells[10].text.strip() if len(cells) > 10 else '',
                    'location': location_code
                }

                forecast_data.append(forecast)

            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        print(f"✓ Scraped {len(forecast_data)} forecast records")
        return forecast_data

    except Exception as e:
        print(f"Error scraping forecast: {e}")
        return []
    finally:
        driver.quit()


def save_to_csv(forecast_data, data_dir='data/forecast'):
    """Save forecast data to CSV file"""
    if not forecast_data:
        print("No data to save")
        return None

    os.makedirs(data_dir, exist_ok=True)

    # Use forecast date for filename
    forecast_date = forecast_data[0]['forecast_date']
    location = forecast_data[0]['location']
    scrape_time = datetime.fromisoformat(forecast_data[0]['scrape_timestamp'])

    filename = os.path.join(
        data_dir,
        f"forecast_{location}_{forecast_date}_scraped_{scrape_time.strftime('%Y%m%d_%H%M')}.csv"
    )

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=forecast_data[0].keys())
        writer.writeheader()
        writer.writerows(forecast_data)

    print(f"✓ Data saved to {filename}")
    return filename


def main():
    print("="*70)
    print("Daily Forecast Scraper (Next 24 Hours)")
    print("="*70)

    forecast_data = scrape_next_day_forecast('EGLC')

    if forecast_data:
        filename = save_to_csv(forecast_data)
        print(f"\n✓ SUCCESS: Scraped {len(forecast_data)} forecast records")
        print(f"File: {filename}")
    else:
        print("\n✗ FAILED: No forecast data scraped")
        exit(1)


if __name__ == "__main__":
    main()
