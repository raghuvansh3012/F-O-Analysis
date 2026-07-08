# NSE F&O Analyzer

A fully automated, zero-maintenance tool that tracks what Big Players (FII, DII, PRO) are doing in the Indian Stock Market. It fetches daily F&O data from the NSE website, crunches the numbers, and gives you a beautiful interactive dashboard.

## 🔥 What's New! (Latest Updates)
* **100% Automated:** Runs automatically every day at 7:30 PM using GitHub Actions. No need to run scripts manually anymore!
* **Live on GitHub Pages:** The dashboard is hosted online for free. You can view it from anywhere on your phone or PC.
* **Weekly Expiry Breakdown:** Data is automatically organized into weekly tabs based on expiry days (Wednesday to Tuesday).
* **Download Raw Data:** A dedicated "Download JSON" button is available inside the sidebar to export the week's F&O data in a clean, pretty-printed JSON format.
* **Auto-Cleanup:** Old CSV files are automatically deleted on the 1st of every month to keep the repository size small and fast.

## 🚀 How to View the Dashboard
You don't need to install anything to view the data. Just visit the live link:
👉 [https://raghuvansh3012.github.io/F-O-Analysis/](https://raghuvansh3012.github.io/F-O-Analysis/)

The dashboard updates automatically every Monday to Friday at 7:30 PM (IST).

## 🛠️ How to Run it Locally (For Developers)

If you want to run this project on your own computer:

1. Make sure you have Python installed.
2. Install the required libraries:
   ```bash
   pip install pandas plotly requests
   ```
3. Run the main script in "Auto" mode to fetch the current month's data:
   ```bash
   python run_fno_analysis.py --auto
   ```
4. Once it finishes, open the `index.html` file in your browser to view the dashboard.

## 📊 Features
* **Participant-wise Analysis**: Separate tabs for FII, DII, Pro, and Retail Clients.
* **OI & Volume Views**: Switch between Open Interest (carried positions) and Volume (intraday activity).
* **Net Summary Table**: A quick glance at who is turning bullish or bearish over the last few days.
* **Tree-view Sidebar Menu**: Easy navigation between different weeks of the current month.

## 📁 Project Structure
- `run_fno_analysis.py`: The main manager script.
- `fetch_nse_reports.py`: Downloads the raw CSV files directly from the NSE website.
- `fno_analysis_viz.py`: Processes the raw data, groups them into weeks, generates JSON, and builds the HTML dashboard.
- `cleanup_old_csvs.py`: Deletes last month's CSV data to save space.
- `.github/workflows/daily_fno_update.yml`: The magic file that runs the GitHub bot every day at 7:30 PM.

## ⚠️ Disclaimer
This tool is made for educational and informational purposes only. It does not provide financial advice. Please do your own research before making any trades in the stock market.
