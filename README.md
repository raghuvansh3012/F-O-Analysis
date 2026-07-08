# F&O Analysis Dashboard

Welcome to my daily F&O Analysis tool! I built this to solve a personal problem: I was tired of manually downloading participant-wise Open Interest (OI) and Volume data from the NSE website every evening, compiling it in Excel, and trying to make sense of what FIIs, DIIs, PROs, and Retail Clients were doing.

This project automates that entire headache. It automatically pulls the daily reports from NSE, cleans the data, and builds a clean, interactive dashboard so I can see the exact market sentiment at a glance.

## Live Dashboard

You can view the live, automated dashboard here:
👉 [https://raghuvansh3012.github.io/F-O-Analysis/](https://raghuvansh3012.github.io/F-O-Analysis/)

*(It updates automatically every weekday at 7:30 PM IST).*

## Why this is useful

If you trade in the Indian derivatives market, knowing where the big money is flowing is crucial. This tool gives you a visual edge:
- **Participant-wise tracking:** See exactly who is carrying long or short positions.
- **OI vs Volume:** Toggle between Open Interest (carried overnight risk) and Intraday Volume.
- **Weekly Breakdown:** The dashboard automatically organizes data into weekly expiry tabs (from Wednesday to Tuesday), so you don't have to mentally separate weeks.
- **Raw Data Export:** A "Download JSON" button is built-in if you want the raw, structured data for your own backtesting or analysis.

## How it works behind the scenes

I designed this to be completely hands-off. 
We use **GitHub Actions** to run a python script (`run_fno_analysis.py`) every evening. 

1. The script fetches the daily CSV files from NSE.
2. It crunches the numbers using Pandas.
3. It generates an `index.html` file with interactive charts using Plotly.
4. Finally, the HTML file is hosted via GitHub Pages.

I also added an auto-cleanup feature so the repository doesn't get bloated. On the 1st of every month, it automatically deletes the previous month's raw CSV files.

## Running it locally

If you want to fork this and run it on your own machine:

1. Clone the repo and ensure you have Python 3 installed.
2. Install the basic dependencies:
   ```bash
   pip install pandas plotly requests
   ```
3. Run the main script. If you use the `--auto` flag, it will pull data for the current month:
   ```bash
   python run_fno_analysis.py --auto
   ```
4. Open `index.html` in your browser.

## Disclaimer

I built this for my own educational use and market analysis. It is not financial advice. Please don't blindly take trades based on this data. Do your own research!
