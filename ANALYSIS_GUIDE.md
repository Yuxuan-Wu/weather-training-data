# Weather Data Analysis Guide

## Using the Jupyter Notebook

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch Jupyter Notebook

```bash
jupyter notebook weather_data_analysis.ipynb
```

Or use JupyterLab:
```bash
jupyter lab weather_data_analysis.ipynb
```

### 3. Run the Analysis

The notebook includes:

- **Section 1**: Load data from SQLite database
- **Section 2**: Data overview and statistics
- **Section 3**: Temperature analysis with time series plots
- **Section 4**: Humidity and pressure visualization
- **Section 5**: Wind speed and direction analysis
- **Section 6**: Thames River water temperature by depth
- **Section 7**: Correlation analysis between variables
- **Section 8**: Weather conditions frequency
- **Section 9**: Comprehensive dashboard view
- **Section 10**: Export options for further analysis

### Charts Included

1. **Temperature Over Time** - Air temp and dew point
2. **Temperature Distribution** - Histogram and box plots
3. **Humidity & Pressure** - Time series with filled areas
4. **Wind Analysis** - Speed over time and direction distribution
5. **Water Temperature** - Multi-depth comparison (0.35m, 2m, 7m)
6. **Correlation Heatmap** - All weather variables
7. **Air vs Water Temperature** - Scatter plot with trendline
8. **Weather Conditions** - Bar chart of condition frequency
9. **Dashboard** - 4-panel overview of all key metrics

### Quick Start

1. Open the notebook
2. Click "Cell" → "Run All" to execute all cells
3. All charts will be generated automatically
4. Scroll through to view different analyses

### Customization

To modify the analysis:

- **Change date range**: Filter `df_obs` DataFrame by date
- **Add new charts**: Use matplotlib/seaborn in new cells
- **Export data**: Uncomment the export cells at the end
- **Analyze specific conditions**: Filter by `condition` column

### Example Queries

```python
# Filter by date
df_filtered = df_obs[df_obs['observation_timestamp'] > '2025-11-15']

# Get observations with specific conditions
rainy = df_obs[df_obs['condition'].str.contains('Rain', na=False)]

# Calculate statistics for a specific day
daily_stats = df_obs.groupby(df_obs['observation_timestamp'].dt.date).agg({
    'temperature_f': ['min', 'max', 'mean'],
    'humidity_pct': 'mean',
    'wind_speed_mph': 'max'
})
```

### Tips

- Use "Shift + Enter" to run individual cells
- Charts are interactive - you can zoom and pan
- All data comes directly from the SQLite database
- The notebook auto-closes the database connection when done

## VS Code Integration

If using VS Code:
1. Install "Jupyter" extension
2. Open `weather_data_analysis.ipynb`
3. Click "Run All" or run cells individually
4. Charts appear inline in VS Code
