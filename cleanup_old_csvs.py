import os
import glob
import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def cleanup_old_data():
    today = datetime.date.today()
    
    # Only run the full cleanup if it's the 1st day of the month.
    # But to be safe and robust, let's just run it every time and delete 
    # anything that is older than 30 days or not from the current/previous month.
    # Actually, the requirement says "delete last month's CSVs on the 1st of every month".
    
    if today.day != 1:
        print("Not the 1st of the month. Skipping cleanup.")
        return

    print("Running monthly cleanup of old CSV files...")
    current_month = today.month
    current_year = today.year
    
    patterns = [
        "fao_participant_oi_*.csv",
        "fao_participant_vol_*.csv",
        "ind_close_all_*.csv"
    ]
    
    deleted_count = 0
    for pattern in patterns:
        files = glob.glob(os.path.join(DATA_DIR, pattern))
        for f in files:
            filename = os.path.basename(f)
            # Extact date from filename, e.g. fao_participant_oi_05072026.csv
            try:
                date_str = filename.split('_')[-1].replace('.csv', '')
                file_date = datetime.datetime.strptime(date_str, "%d%m%Y").date()
                
                # If the file does not belong to the current month and year, delete it.
                if file_date.month != current_month or file_date.year != current_year:
                    os.remove(f)
                    print(f"Deleted old file: {filename}")
                    deleted_count += 1
            except Exception as e:
                print(f"Error parsing date for {filename}: {e}")
                
    print(f"Cleanup complete. Deleted {deleted_count} files.")

if __name__ == "__main__":
    cleanup_old_data()
