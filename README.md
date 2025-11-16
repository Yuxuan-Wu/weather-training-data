# Weather Training Data Scraper

Automated weather data collection system for ML training, scraping actual observations and forecasts for London City Airport (EGLC) with integrated Thames River water temperature data.

## 🎯 Features

- **Unified SQLite Database**: All data stored in a single, structured database optimized for ML workflows
- **Dual Data Sources**:
  - Actual weather observations (hourly with automatic backfill)
  - Weather forecasts (daily, next 24 hours)
- **Water Temperature Integration**: Thames River temperature data matched by time proximity
- **Automatic Deduplication**: Prevents duplicate entries using unique constraints
- **Time-Based Matching**: Precise UTC timestamps with timezone-aware parsing
- **GitHub Actions Automation**: Runs hourly for actual data + daily for forecasts

## 📊 Database Schema

### Weather Observations Table
```sql
weather_observations (
  id INTEGER PRIMARY KEY,
  scrape_timestamp TIMESTAMP,          -- When data was scraped
  observation_timestamp TIMESTAMP,      -- When observation was made (UTC)
  location TEXT,                        -- Airport code (EGLC)
  temperature_f REAL,
  dew_point_f REAL,
  humidity_pct INTEGER,
  wind_speed_mph REAL,
  wind_direction TEXT,
  wind_gust_mph REAL,
  pressure_in REAL,
  precip_amount_in REAL,
  condition TEXT,
  water_temp_0_35m_c REAL,             -- Thames water @ 0.35m depth
  water_temp_2m_c REAL,                 -- Thames water @ 2m depth
  water_temp_7m_c REAL,                 -- Thames water @ 7m depth
  water_temp_entry_id INTEGER,         -- ThingSpeak entry ID
  created_at TIMESTAMP,
  UNIQUE(location, observation_timestamp)
)
```

### Weather Forecasts Table
```sql
weather_forecasts (
  id INTEGER PRIMARY KEY,
  scrape_timestamp TIMESTAMP,
  forecast_timestamp TIMESTAMP,         -- What time the forecast is for (UTC)
  location TEXT,
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
  created_at TIMESTAMP,
  UNIQUE(location, forecast_timestamp, scrape_timestamp)
)
```

## 🚀 Usage

### Command Line Interface

```bash
# Scrape actual observations only (with water temperature)
python weather_scraper.py --mode actual

# Scrape forecasts only
python weather_scraper.py --mode forecast

# Scrape both actual and forecast
python weather_scraper.py --mode both

# Specify custom database location
python weather_scraper.py --mode actual --db custom/path/weather.db

# Different location (e.g., Heathrow)
python weather_scraper.py --mode actual --location EGLL
```

### Automated Schedule (GitHub Actions)

The scraper automatically runs:
- **Hourly**: Actual observations at :05 past each hour (UTC)
- **Daily**: Forecasts at 23:59 UTC

### Querying the Database

```bash
# Recent observations with water temperature
sqlite3 data/weather_data.db "
  SELECT
    datetime(observation_timestamp) as time,
    temperature_f,
    humidity_pct,
    water_temp_0_35m_c
  FROM weather_observations
  ORDER BY observation_timestamp DESC
  LIMIT 10;
"

# Observations per day
sqlite3 data/weather_data.db "
  SELECT
    DATE(observation_timestamp) as date,
    COUNT(*) as count,
    AVG(temperature_f) as avg_temp
  FROM weather_observations
  GROUP BY DATE(observation_timestamp)
  ORDER BY date DESC;
"

# Compare forecast accuracy
sqlite3 data/weather_data.db "
  SELECT
    datetime(f.forecast_timestamp) as time,
    f.temperature_f as forecast,
    o.temperature_f as actual,
    ROUND(ABS(f.temperature_f - o.temperature_f), 1) as error
  FROM weather_forecasts f
  JOIN weather_observations o
    ON datetime(f.forecast_timestamp) = datetime(o.observation_timestamp)
  ORDER BY f.forecast_timestamp DESC
  LIMIT 10;
"

# Water temperature trends
sqlite3 data/weather_data.db "
  SELECT
    DATE(observation_timestamp) as date,
    ROUND(AVG(water_temp_0_35m_c), 2) as avg_surface_temp,
    ROUND(AVG(water_temp_7m_c), 2) as avg_deep_temp
  FROM weather_observations
  WHERE water_temp_0_35m_c IS NOT NULL
  GROUP BY DATE(observation_timestamp)
  ORDER BY date DESC;
"
```

### Exporting for ML

```python
import sqlite3
import pandas as pd

# Load observations
conn = sqlite3.connect('data/weather_data.db')
df = pd.read_sql_query("SELECT * FROM weather_observations", conn)

# Convert timestamps
df['observation_timestamp'] = pd.to_datetime(df['observation_timestamp'])

# Export to CSV
df.to_csv('observations.csv', index=False)

# Export to parquet (better for large datasets)
df.to_parquet('observations.parquet')
```

## 📁 Project Structure

```
.
├── weather_scraper.py           # Unified scraper with SQLite
├── data/
│   └── weather_data.db          # SQLite database (auto-created)
├── .github/workflows/
│   └── scrape-weather.yml       # Automation workflow
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 📦 Requirements

```txt
selenium
pytz
requests
```

Install with:
```bash
pip install -r requirements.txt
```

## 🔧 Development

### Local Testing

```bash
# Test actual weather scraping
python weather_scraper.py --mode actual

# Verify database
sqlite3 data/weather_data.db ".tables"
sqlite3 data/weather_data.db "SELECT COUNT(*) FROM weather_observations;"

# Check for duplicates (should return 0)
sqlite3 data/weather_data.db "
  SELECT location, observation_timestamp, COUNT(*)
  FROM weather_observations
  GROUP BY location, observation_timestamp
  HAVING COUNT(*) > 1;
"
```

### Database Maintenance

```bash
# Optimize database (reclaim space)
sqlite3 data/weather_data.db "VACUUM;"

# Check integrity
sqlite3 data/weather_data.db "PRAGMA integrity_check;"

# View full schema
sqlite3 data/weather_data.db ".schema"

# Database statistics
sqlite3 data/weather_data.db "
  SELECT
    'Observations' as table_name,
    COUNT(*) as record_count,
    (SELECT COUNT(DISTINCT DATE(observation_timestamp)) FROM weather_observations) as days
  FROM weather_observations
  UNION ALL
  SELECT
    'Forecasts',
    COUNT(*),
    (SELECT COUNT(DISTINCT DATE(forecast_timestamp)) FROM weather_forecasts)
  FROM weather_forecasts;
"
```

## 🌐 Data Sources

1. **Weather Underground** (wunderground.com)
   - Actual observations: `/history/daily/gb/london/EGLC/date/{date}`
   - Forecasts: `/hourly/EGLC`
   - Updates: Every ~30 minutes for observations

2. **ThingSpeak API** (api.thingspeak.com)
   - Channel: 521315 (Docklands London Water Temperature Monitor)
   - 3 temperature probes at depths: 0.35m, 2m, 7m
   - Updates: Every ~5 minutes

## 🎓 ML Use Cases

This dataset is ideal for:
- Weather forecast accuracy analysis
- Time series prediction models
- Multi-variable regression (temperature, humidity, pressure)
- Environmental correlation studies (weather vs water temperature)
- Anomaly detection
- Forecast error modeling

## 📝 Notes

- **Timestamps**: All stored in UTC for consistency
- **Backfill**: Scraper captures all available observations on each run, skipping duplicates
- **Water Matching**: Water temperature readings matched to nearest observation time (within minutes)
- **Data Frequency**: Weather observations every ~30 min, water temperature every ~5 min
- **GitHub Actions**: Database automatically committed after each successful scrape

## 🤖 Automation Details

The GitHub Actions workflow (`scrape-weather.yml`):
- Runs on schedule (hourly for actual, daily for forecast)
- Can be manually triggered with mode selection
- Automatically commits updated database to repository
- Unified workflow (single job, multiple modes)

## ⚙️ Configuration

### Change Location

Edit `weather_scraper.py` or pass via CLI:
```bash
python weather_scraper.py --mode actual --location EGLL  # Heathrow
python weather_scraper.py --mode actual --location EGKK  # Gatwick
```

### Modify Schedule

Edit `.github/workflows/scrape-weather.yml`:
```yaml
schedule:
  - cron: '5 * * * *'    # Hourly actual (at :05)
  - cron: '59 23 * * *'  # Daily forecast (at 23:59 UTC)
```

## 📄 License

MIT - For educational and research purposes. Please respect data source terms of service.
