# NSE F&O Analyzer

An automated quantitative analysis engine and ETL data-pipeline built for the Indian Derivatives Market. It orchestrates the ingestion of daily NSE datasets to decode the institutional flow across Futures and Options, rendering complex buy/sell metrics into a high-performance interactive visual ecosystem.

## What does it do?
This engine automates the extraction, transformation, and loading (ETL) of raw structural market data released by the NSE. Its primary objective is to track and visualize the exact daily buy and sell activities of major market participants: **FII (Foreign Institutional Investors), DII (Domestic Institutional Investors), Pro (Proprietary Desks), and Retail Clients**.

1. **Algorithmic Data Ingestion**: Automatically scrapes and validates daily Participant Open Interest (OI) and Volume reports directly from the NSE archives.
2. **Quantitative Processing Engine**: Utilizes a Pandas-based architecture to clean unstructured CSVs, compute net long/short deltas, and cross-reference derivatives flow with Nifty 50 and India VIX closing metrics.
3. **Interactive Analytics Dashboard**: Deploys a Plotly-driven dynamic UI that visualizes the exact daily F&O buying and selling activity of FII, DII, Pro, and Clients, exposing hidden market sentiments in real-time.

## Why I made this
I initially built this tool for my own daily use. Manually downloading CSV files from the NSE website every day and comparing them with previous days was a very tedious and boring task. I wanted to automate this process to save time and replace manual Excel number-crunching with a clean, automated visual summary.

## How to use it
It's very easy to run!

1. Make sure you have Python installed on your computer.
2. Install the required libraries by running:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the main script:
   ```bash
   python run_fno_analysis.py
   ```
4. The script will ask you how many days of data you want to analyze. Enter a number (like `5` for the last week) or press Enter to analyze all available data.
5. Once it finishes downloading and processing, it will automatically open a file called `fno_dashboard.html` in your default web browser.

## Features
* **Participant-wise Analysis**: Separate tabs for FII, DII, Pro, and Retail Clients.
* **OI & Volume Views**: Switch between Open Interest (carried positions) and Volume (intraday activity).
* **Net Summary Table**: A quick glance at who is turning bullish or bearish over the last few days.
* **No Database Required**: Uses simple CSV files to store and read data, so it works perfectly offline once the data is fetched.
* **Modern UI**: The dashboard is responsive, visually pleasing, and built with Plotly.

## Project Structure
Here is a quick overview of what the files in this repository do:
- `run_fno_analysis.py`: This is the main script that you run. It acts as the manager.
- `fetch_nse_reports.py`: This script handles downloading the raw CSV files directly from the NSE website.
- `fno_analysis_viz.py`: This script processes the raw data and builds the beautiful HTML dashboard.
- `requirements.txt`: Contains a list of all the Python libraries needed to run the project.


## Disclaimer
This tool is made for educational and informational purposes only. It does not provide financial advice. Please do your own research before making any trades in the stock market.
