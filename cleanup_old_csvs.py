import os
import glob
import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def cleanup_old_data():
    today = datetime.date.today()

    # Import expiry utils for dynamic cycle detection
    try:
        from expiry_utils import get_current_expiry_cycle
        cycle_start, cycle_end, label = get_current_expiry_cycle(today)
        print(f"Current expiry cycle: {label}")
        print(f"Cycle start: {cycle_start}, Cycle end: {cycle_end}")
    except Exception as e:
        # Fallback: if expiry_utils fails, use calendar month
        print(f"Warning: Could not determine expiry cycle ({e}), falling back to calendar month.")
        cycle_start = today.replace(day=1)

    print(f"Running cleanup — deleting data files before {cycle_start}...")

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
            # Extract date from filename, e.g. fao_participant_oi_05072026.csv
            try:
                date_str = filename.split('_')[-1].replace('.csv', '')
                file_date = datetime.datetime.strptime(date_str, "%d%m%Y").date()

                # Delete files that are BEFORE the current cycle start
                if file_date < cycle_start:
                    os.remove(f)
                    print(f"Deleted old file: {filename}")
                    deleted_count += 1
            except Exception as e:
                print(f"Error parsing date for {filename}: {e}")

    print(f"Cleanup complete. Deleted {deleted_count} files.")

if __name__ == "__main__":
    cleanup_old_data()
