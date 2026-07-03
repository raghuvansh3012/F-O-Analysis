import os
import sys
import datetime
import subprocess
import time

# paths aur directories set kar lete hain
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
FETCH_SCRIPT = os.path.join(DATA_DIR, "fetch_nse_reports.py")
VIZ_SCRIPT = os.path.join(DATA_DIR, "fno_analysis_viz.py")

def run_fetch(date_str):
    """specific date ka fetch script run karne ke liye. agar file aagyi toh True return karega"""
    
    # 1. pehle check kar lo ki file already hai ya nahi time bachane ke liye
    # (sirf 'fao_participant_oi' check karna kaafi hai, agar ye hai matlab baaki bhi honge)
    dd, mm, yyyy = date_str.split('-')
    check_file = os.path.join(DATA_DIR, f"fao_participant_oi_{dd}{mm}{yyyy}.csv")
    
    if os.path.exists(check_file):
        print(f"[Skipping] Data for {date_str} already exists.")
        return True
    
    # 2. fetch script run karo
    # subprocess use kar rahe hain taaki logs clean rahein
    print(f"[Fetching] Data for {date_str}...")
    try:
        # date pass kar rahe hain fetch script ko
        result = subprocess.run([sys.executable, FETCH_SCRIPT, date_str], capture_output=True, text=True)
        
        # dekh lo successful hua ki nahi, wapas file dhoond ke
        if os.path.exists(check_file):
            print(f" -> Success: {date_str}")
            return True
        else:
            # agar holiday hai ya data nahi aaya toh us error ko chup kara do
            # print(f" -> Failed/Holiday: {date_str}") 
            return False
            
    except Exception as e:
        print(f"Error executing fetch script: {e}")
        return False

def main():
    print("="*60)
    print("   NSE F&O AUTOMATED ANALYZER   ")
    print("="*60)
    
    # 1. User Input le lo
    if len(sys.argv) > 1:
        n_days = int(sys.argv[1])
    else:
        try:
            n_days = int(input("\nEnter number of trading days to analyze (e.g., 5): "))
        except ValueError:
            print("Invalid input! Please enter a number.")
            return

    print(f"\nScanning for last {n_days} valid data points...")
    
    # 2. pichle N valid trading days nikalne ka jugaad
    valid_days_count = 0
    current_date = datetime.date.today()
    
    # infinite loop se bachne ke liye ek limit lagani padegi
    max_lookback = n_days * 4 
    days_checked = 0
    
    collected_dates = []

    while valid_days_count < n_days and days_checked < max_lookback:
        date_str = current_date.strftime("%d-%m-%Y")
        
        # weekends skip kar do, faltu ka network call waste mat karo
        if current_date.weekday() >= 5: # 5=Sat, 6=Sun
            # print(f"Skipping Weekend: {date_str}")
            pass
        else:
            # data lane ka try karte hain
            if run_fetch(date_str):
                valid_days_count += 1
                collected_dates.append(date_str)
            else:
                pass # lagta hai aaj chhutti thi ya nse ne data abhi update nahi kiya
        
        # ek din piche jao
        current_date -= datetime.timedelta(days=1)
        days_checked += 1
        
    print("-" * 50)
    if valid_days_count < n_days:
        print(f"Warning: Could only find {valid_days_count} valid days in the last {days_checked} days.")
    else:
        print(f"Successfully collected {valid_days_count} days: {collected_dates}")
        
    # 3. ab dashboard generate karne ka time aa gaya
    print("\n[Running Analysis] Generating Dashboard...")
    subprocess.run([sys.executable, VIZ_SCRIPT, str(n_days)])
    
    print("\nDone! Dashboard Updated.")
    print(r"Open: e:\daily report\Option_Aanalysis\fno_dashboard.html")

if __name__ == "__main__":
    main()
