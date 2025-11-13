# Quick Start Guide

## Deploy to GitHub (3 Steps)

### 1. Initialize Git Repository
```bash
cd /Users/charleswu/workspace/fetch-wunderground-trainingdata
git init
git add .
git commit -m "Initial commit: Automated weather scraper"
```

### 2. Create GitHub Repository
1. Go to https://github.com/new
2. Name it: `weather-training-data` (or any name you prefer)
3. **Do NOT** initialize with README, .gitignore, or license (we already have these)
4. Click "Create repository"

### 3. Push to GitHub
```bash
# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/weather-training-data.git
git branch -M main
git push -u origin main
```

## ✅ Done!

That's it! The system is now live and will:

- **Scrape actual weather data every hour** (at :05 past the hour)
- **Scrape daily forecasts at 11:59 PM London time**
- **Automatically commit data to your repository**

## 📊 Monitoring

### Check if it's working:
1. Go to your GitHub repository
2. Click the **"Actions"** tab
3. You'll see workflow runs as they happen

### View collected data:
- Actual data: `data/actual/actual_EGLC_YYYY-MM-DD.csv`
- Forecast data: `data/forecast/forecast_EGLC_YYYY-MM-DD_scraped_*.csv`

## 🔧 Customization

### Change Location
Edit these files and replace `EGLC` with your desired location code:
- `scrape_actual_hourly.py` (line with `location_code='EGLC'`)
- `scrape_forecast_daily.py` (line with `location_code='EGLC'`)

Also update the URL if not in GB:
- Current: `https://www.wunderground.com/history/daily/gb/london/EGLC/...`
- Change: `gb/london` to your country/city

### Change Schedule
Edit `.github/workflows/scrape-weather.yml`:
- Hourly: Line with `cron: '5 * * * *'`
- Daily: Line with `cron: '59 22 * * *'`

Cron syntax: `minute hour day month weekday` (all times in UTC)

## 🧪 Test Locally First

Before pushing, test the scrapers locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Test hourly scraper
python scrape_actual_hourly.py

# Test daily scraper
python scrape_forecast_daily.py

# Check output
ls -la data/actual/
ls -la data/forecast/
```

## ❓ Troubleshooting

### GitHub Actions not running?
- Check if workflows are enabled: Settings → Actions → Allow all actions
- Check the schedule in the workflow file

### No data appearing?
- Check Actions tab for error messages
- Make sure Chrome/ChromeDriver is working in GitHub Actions
- Check if commits are failing (permissions issue)

### Want to run manually?
1. Go to Actions tab
2. Select "Weather Data Scraper"
3. Click "Run workflow"
4. Choose what to scrape

## 📈 Data Growth Estimates

- **Hourly data**: ~24 rows per day = ~720 rows per month
- **Daily forecasts**: ~24 rows per day = ~720 rows per month
- **Total**: ~1,440 rows per month
- **File size**: Approximately 150-200 KB per month per CSV

After 1 year: ~17,500 rows of training data!
