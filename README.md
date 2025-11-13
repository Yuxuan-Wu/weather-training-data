# Weather Underground Training Data Scraper

Automated scraper for collecting weather forecast and actual observation data from Weather Underground for EGLC (London City Airport). Data is collected for ML model training.

## 🎯 Purpose

This project collects weather and environmental data for EGLC (London City Airport):
1. **Actual Weather Data** - Historical observations scraped every hour
2. **Thames River Water Temperature** - Collected hourly alongside weather data
3. **Forecast Data** - Next-day forecasts scraped daily at 11:59 PM London time

The data fields are aligned to enable ML training where models can learn from forecasts and validate against actual observations, with additional environmental context from river temperature.

## 📊 Data Collection Schedule

### Hourly Actual Data + Water Temperature
- **Frequency**: Every hour at :05 (e.g., 1:05, 2:05, 3:05...)
- **Sources**:
  - Weather: `https://www.wunderground.com/history/daily/gb/london/EGLC/date/YYYY-MM-DD`
  - Water: `https://api.thingspeak.com/channels/521315` (Thames River, Docklands)
- **Saved to**: `data/actual/actual_EGLC_YYYY-MM-DD.csv`
- **Description**: Scrapes the most recent weather observation AND Thames River water temperature at 3 depths (0.35m, 2m, 7m), then appends to the daily file

### Daily Forecast
- **Frequency**: Once per day at 11:59 PM London time
- **Source**: `https://www.wunderground.com/hourly/EGLC`
- **Saved to**: `data/forecast/forecast_EGLC_YYYY-MM-DD_scraped_YYYYMMDD_HHMM.csv`
- **Description**: Scrapes the next 24 hours of forecast data for the upcoming day

## 📁 Data Structure

### Actual Data Fields
```
scrape_timestamp, observation_time, temperature, dew_point, humidity,
wind, pressure, precip_amount, condition, location, date,
water_temp_0_35m, water_temp_2m, water_temp_7m, water_temp_entry_id
```

**Note**: Water temperatures are in Celsius, weather temperatures in Fahrenheit (as provided by sources)

### Forecast Data Fields
```
scrape_timestamp, forecast_date, forecast_hour, condition, temperature,
feels_like, precip_chance, precip_amount, cloud_cover, dew_point,
humidity, wind, pressure, location
```

## 🚀 Fully Automated GitHub Actions

The scraping runs **completely automatically** via GitHub Actions once you push to GitHub. No manual intervention needed!

### Automatic Schedule
- **Hourly scraping**: Runs every hour at :05 past the hour (1:05, 2:05, 3:05, etc.)
- **Daily forecasts**: Runs once per day at 11:59 PM London time

### Optional Manual Trigger

If you want to test or run manually, you can trigger from the GitHub Actions tab:
1. Go to "Actions" tab in your repository
2. Select "Weather Data Scraper"
3. Click "Run workflow"
4. Choose scrape type:
   - `hourly-actual` - Scrape current actual data
   - `daily-forecast` - Scrape next-day forecast
   - `both` - Run both scrapers

### Setup (One-Time Only)
1. Push this code to your GitHub repository
2. GitHub Actions will automatically activate
3. Data collection begins immediately - no further action required!

## 🔧 Local Development

### Installation

```bash
pip install -r requirements.txt
```

### Run Scrapers Locally

```bash
# Scrape current actual data
python scrape_actual_hourly.py

# Scrape next-day forecast
python scrape_forecast_daily.py

# Run complete analysis (both forecast and actual)
python scraper_complete.py
```

## 📋 Requirements

- Python 3.11+
- Chrome/Chromium browser (for Selenium)
- Dependencies: see `requirements.txt`

## 🤖 Robots.txt Compliance

This scraper respects Weather Underground's `robots.txt`:
- No disallowed paths for `/hourly/` or `/history/` endpoints
- Implements 2-second crawl delay
- Uses appropriate user-agent string

## 📈 Data Usage

The collected data can be used for:
- Weather forecast accuracy analysis
- ML model training for weather prediction
- Time series analysis
- Forecast vs actual comparison studies

## 🗂️ File Structure

```
.
├── .github/
│   └── workflows/
│       └── scrape-weather.yml       # GitHub Actions workflow
├── data/
│   ├── actual/                      # Hourly actual observations
│   └── forecast/                    # Daily forecasts
├── scrape_actual_hourly.py          # Hourly scraper
├── scrape_forecast_daily.py         # Daily forecast scraper
├── scraper_complete.py              # Complete scraper (manual use)
├── scraper.py                       # Original forecast-only scraper
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## ⚙️ Configuration

### Location

Currently configured for **EGLC (London City Airport)**. To change location:
1. Update location code in both scraper scripts
2. Update timezone if needed (currently `Europe/London`)
3. Update URL paths if location is outside GB

### Schedule

To modify scraping schedule, edit `.github/workflows/scrape-weather.yml`:
- Hourly: Change `cron: '5 * * * *'`
- Daily: Change `cron: '59 22 * * *'`

Cron format: `minute hour day month weekday` (UTC time)

## 📝 Notes

- Data files are automatically committed by GitHub Actions
- Each actual data CSV contains one day's observations (24 rows)
- Each forecast CSV contains one 24-hour forecast snapshot
- Timestamps are in ISO format with timezone information
- All temperature values are in Fahrenheit (as provided by source)

## 🔒 License

This project is for educational and research purposes. Respect Weather Underground's terms of service when using scraped data.
