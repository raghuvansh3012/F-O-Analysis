"""
Nifty 50 Option Chain Data Downloader
======================================
Downloads NSE F&O bhavcopy data, filters for NIFTY options,
and organizes into expiry-cycle folders.

Usage: python download_nifty_options.py
"""

import os
import sys
import re
import time
import random
import zipfile
import io
import json
import calendar
import logging
from datetime import datetime, timedelta

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

try:
    import pandas as pd
except ImportError:
    print("Installing pandas...")
    os.system(f"{sys.executable} -m pip install pandas")
    import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
SUMMARY_FILE = os.path.join(BASE_DIR, "summary.csv")
LOG_FILE = os.path.join(BASE_DIR, "download.log")

# Weekly expiry for NIFTY started on Feb 11, 2019
WEEKLY_EXPIRY_START = datetime(2019, 2, 11)

# Rate limiting
MIN_DELAY = 2.0   # Increased minimum delay
MAX_DELAY = 4.0   # Increased maximum delay
MAX_RETRIES = 5   # More retries
BACKOFF_FACTOR = 3 # Stronger backoff
COOLDOWN_AFTER = 50 # Sleep long after this many downloads
COOLDOWN_TIME = (30, 60) # Range of seconds for cooldown

# NSE URLs to try (in order)
URL_TEMPLATES = [
    # 1. Legacy F&O Bhavcopy (Pre-July 8, 2024)
    "https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{year}/{month}/fo{datestr}bhav.csv.zip",
    "https://archives.nseindia.com/content/historical/DERIVATIVES/{year}/{month}/fo{datestr}bhav.csv.zip",
    # 2. New UDiFF Common Bhavcopy (Post-July 8, 2024 - Archive)
    "https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{year}/{month}/BhavCopy_NSE_FO_0_0_0_{yymmdd}_F_0000.csv.zip",
    "https://archives.nseindia.com/content/historical/DERIVATIVES/{year}/{month}/BhavCopy_NSE_FO_0_0_0_{yymmdd}_F_0000.csv.zip",
    # 3. Official API (Post-July 2024 - Recent/Latest)
    'https://www.nseindia.com/api/reports?archives=%5B%7B%22name%22%3A%22F%26O+-+UDiFF+Common+Bhavcopy+Final+(zip)%22%2C%22type%22%3A%22daily-reports%22%2C%22category%22%3A%22derivatives%22%2C%22section%22%3A%22fno%22%7D%5D&date={dd}-{Mon}-{year}&type=derivatives'
]

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/all-reports-derivatives',
    'X-Requested-With': 'XMLHttpRequest'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.nseindia.com/',
}


# ============================================================
# LOGGING SETUP
# ============================================================
def setup_logging():
    os.makedirs(BASE_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


# ============================================================
# PROGRESS TRACKING
# ============================================================
def load_progress():
    """Load download progress from JSON file."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"downloaded": [], "failed": [], "holidays": []}


def save_progress(progress):
    """Save download progress to JSON file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


# ============================================================
# NSE SESSION MANAGEMENT
# ============================================================
def create_nse_session():
    """Create a session with NSE cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        logging.info("Establishing NSE session (getting cookies)...")
        # Visit NSE homepage to get cookies
        resp = session.get("https://www.nseindia.com/", timeout=15)
        if resp.status_code == 200:
            logging.info("NSE session established successfully.")
        else:
            logging.warning(f"NSE homepage returned status {resp.status_code}, proceeding anyway...")
    except Exception as e:
        logging.warning(f"Could not establish NSE session: {e}. Proceeding without cookies...")
    
    return session


# ============================================================
# DATE UTILITIES
# ============================================================
def get_fy_dates(fy_start_year):
    """Get start and end dates for a financial year.
    FY 2008-09 means April 2008 to March 2009.
    """
    start = datetime(fy_start_year, 4, 1)
    end = datetime(fy_start_year + 1, 3, 31)
    
    # Cap at today
    today = datetime.now()
    if end > today:
        end = today
    
    return start, end


def get_trading_dates(start_date, end_date):
    """Generate all weekdays (potential trading days) between start and end."""
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0 to Friday=4
            dates.append(current)
        current += timedelta(days=1)
    return dates


# ============================================================
# DOWNLOAD & EXTRACT
# ============================================================
def download_bhavcopy(date, session):
    """Download F&O bhavcopy for a given date. Returns raw ZIP bytes or None."""
    # Prepare date variations
    datestr = date.strftime('%d%b%Y').upper()  # 01AUG2024
    yymmdd = date.strftime('%Y%m%d')           # 20240801
    dd = date.strftime('%d')                   # 01
    Mon = date.strftime('%b')                  # Aug
    year = date.strftime('%Y')
    month = date.strftime('%b').upper()        # AUG
    
    for url_template in URL_TEMPLATES:
        url = url_template.format(
            year=year, 
            month=month, 
            datestr=datestr, 
            yymmdd=yymmdd,
            dd=dd,
            Mon=Mon
        )
        
        # Use specialized headers for API URL (some NSE endpoints require specific Referer/Accept)
        current_headers = API_HEADERS if "api/reports" in url else HEADERS
        
        for attempt in range(MAX_RETRIES):
            try:
                resp = session.get(url, headers=current_headers, timeout=30)
                
                if resp.status_code == 200:
                    # Verify it's actually a ZIP file
                    if len(resp.content) > 100:
                        return resp.content
                    else:
                        continue
                
                elif resp.status_code == 404:
                    # File doesn't exist at this URL structure, move to the next template
                    break
                
                elif resp.status_code in (403, 429):
                    # Rate limited - strong backoff
                    wait = 120 if resp.status_code == 429 else (BACKOFF_FACTOR ** (attempt + 1) + random.uniform(5, 10))
                    logging.warning(f"Rate limited ({resp.status_code}). Waiting {wait:.1f}s...")
                    time.sleep(wait)
                    # Refresh session on last attempts
                    if attempt >= MAX_RETRIES - 2:
                        logging.info("Refreshing session due to rate limiting...")
                        session = create_nse_session()
                    continue
                
                else:
                    logging.debug(f"Status {resp.status_code} for {url}")
                    break
                    
            except requests.exceptions.Timeout:
                logging.debug(f"Timeout for {url}, attempt {attempt + 1}")
                time.sleep(2)
            except requests.exceptions.ConnectionError:
                logging.debug(f"Connection error for {url}, attempt {attempt + 1}")
                time.sleep(3)
            except Exception as e:
                logging.debug(f"Error downloading {url}: {e}")
                break
    
    return None


def extract_nifty_options(zip_content, date):
    """Extract NIFTY options data from bhavcopy ZIP bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            for filename in zf.namelist():
                if filename.lower().endswith('.csv'):
                    with zf.open(filename) as f:
                        df = pd.read_csv(f)
                        
                        # Handle New UDiFF Format (Post-July 2024)
                        # Mapping: UDiFF -> Legacy
                        udiff_map = {
                            'TCKRSYMB': 'SYMBOL',
                            'FININSTRMTP': 'INSTRUMENT',
                            'XPRYDT': 'EXPIRY_DT',
                            'STRKPRIC': 'STRIKE_PR',
                            'OPTNTP': 'OPTION_TYP',
                            'OPNPRIC': 'OPEN',
                            'HGHPRIC': 'HIGH',
                            'LWPRIC': 'LOW',
                            'CLSPRIC': 'CLOSE',
                            'STTLMPRIC': 'SETTLE_PR',
                            'TTLTRADGVOL': 'CONTRACTS',
                            'TTLTRFVAL': 'VAL_INLAKH',
                            'OPNINTRST': 'OPEN_INT',
                            'CHNGINOPNINTRST': 'CHG_IN_OI',
                            'TRADDT': 'TIMESTAMP'
                        }
                        
                        # Normalize columns
                        df.columns = [c.strip().upper() for c in df.columns]
                        
                        # Rename if it's UDiFF format
                        if 'TCKRSYMB' in df.columns:
                            df = df.rename(columns=udiff_map)
                        
                        # Filter for NIFTY index options
                        if 'INSTRUMENT' not in df.columns or 'SYMBOL' not in df.columns:
                            return None
                            
                        mask = (
                            (df['INSTRUMENT'].fillna('').str.strip().isin(['OPTIDX', 'IDO'])) &
                            (df['SYMBOL'].str.strip() == 'NIFTY')
                        )
                        nifty_opts = df[mask].copy()
                        
                        if len(nifty_opts) == 0:
                            return None
                        
                        # Select and clean columns
                        columns_to_keep = [
                            'SYMBOL', 'EXPIRY_DT', 'STRIKE_PR', 'OPTION_TYP',
                            'OPEN', 'HIGH', 'LOW', 'CLOSE', 'SETTLE_PR',
                            'CONTRACTS', 'VAL_INLAKH', 'OPEN_INT', 'CHG_IN_OI',
                            'TIMESTAMP'
                        ]
                        available_cols = [c for c in columns_to_keep if c in nifty_opts.columns]
                        nifty_opts = nifty_opts[available_cols].reset_index(drop=True)
                        
                        return nifty_opts
                        
                elif filename.lower().endswith('.zip'):
                    # Handle nested ZIP (NSE API often returns a ZIP inside a ZIP)
                    inner_zip_bytes = zf.read(filename)
                    with zipfile.ZipFile(io.BytesIO(inner_zip_bytes)) as inner_zf:
                        for inner_file in inner_zf.namelist():
                            if inner_file.lower().endswith('.csv'):
                                with inner_zf.open(inner_file) as f:
                                    df = pd.read_csv(f)
                                    df.columns = [c.strip().upper() for c in df.columns]
                                    udiff_map = {'TCKRSYMB': 'SYMBOL', 'FININSTRMTP': 'INSTRUMENT', 'XPRYDT': 'EXPIRY_DT', 'STRKPRIC': 'STRIKE_PR', 'OPTNTP': 'OPTION_TYP', 'OPNPRIC': 'OPEN', 'HGHPRIC': 'HIGH', 'LWPRIC': 'LOW', 'CLSPRIC': 'CLOSE', 'STTLMPRIC': 'SETTLE_PR', 'TTLTRADGVOL': 'CONTRACTS', 'TTLTRFVAL': 'VAL_INLAKH', 'OPNINTRST': 'OPEN_INT', 'CHNGINOPNINTRST': 'CHG_IN_OI', 'TRADDT': 'TIMESTAMP'}
                                    if 'TCKRSYMB' in df.columns:
                                        df = df.rename(columns=udiff_map)
                                    if 'INSTRUMENT' not in df.columns or 'SYMBOL' not in df.columns:
                                        continue
                                    mask = ((df['INSTRUMENT'].fillna('').str.strip().isin(['OPTIDX', 'IDO'])) & (df['SYMBOL'].str.strip() == 'NIFTY'))
                                    nifty_opts = df[mask].copy()
                                    if len(nifty_opts) == 0:
                                        continue
                                    columns_to_keep = ['SYMBOL', 'EXPIRY_DT', 'STRIKE_PR', 'OPTION_TYP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'SETTLE_PR', 'CONTRACTS', 'VAL_INLAKH', 'OPEN_INT', 'CHG_IN_OI', 'TIMESTAMP']
                                    available_cols = [c for c in columns_to_keep if c in nifty_opts.columns]
                                    nifty_opts = nifty_opts[available_cols].reset_index(drop=True)
                                    return nifty_opts
    except zipfile.BadZipFile:
        logging.warning(f"Bad ZIP file for {date.strftime('%Y-%m-%d')}")
    except Exception as e:
        logging.warning(f"Error extracting data for {date.strftime('%Y-%m-%d')}: {e}")
    
    return None


# ============================================================
# FOLDER ORGANIZATION
# ============================================================
def get_actual_expiry(trade_date, df):
    """Determine the actual current expiry date for a given trading date by analyzing the downloaded data."""
    if 'EXPIRY_DT' not in df.columns:
        return None
        
    try:
        # Convert to datetime using mixed format
        expiry_series = pd.to_datetime(df['EXPIRY_DT'], format='mixed', dayfirst=True)
        # Filter for expiries >= trade_date
        trade_date_ts = pd.Timestamp(trade_date)
        valid_expiries = expiry_series[expiry_series >= trade_date_ts]
        
        if valid_expiries.empty:
            # Fallback to max expiry if all somehow expired (shouldn't happen in clean data)
            return expiry_series.max().to_pydatetime()
            
        return valid_expiries.min().to_pydatetime()
    except Exception as e:
        logging.warning(f"Error parsing expiry dates for {trade_date.strftime('%Y-%m-%d')}: {e}")
        return None


def organize_into_folders(base_dir, all_data):
    """Organize downloaded data into actual expiry-cycle folders.
    
    Handles incremental downloads correctly:
    - Scans existing expiry folders to avoid creating duplicates
    - Merges new CSVs into existing folders if the expiry date matches
    - Only creates new folders for genuinely new expiry dates
    - Continues numbering from the highest existing expiry number in each FY
    """
    if not all_data:
        return []
    
    # Sort data by date
    all_data.sort(key=lambda x: x[0])
    
    # Group by expiry cycle
    cycles = {}
    for trade_date, df in all_data:
        expiry = get_actual_expiry(trade_date, df)
        if expiry is None:
            continue
        expiry_key = expiry.strftime('%Y-%m-%d')
        if expiry_key not in cycles:
            cycles[expiry_key] = []
        cycles[expiry_key].append((trade_date, df))
    
    # ── Scan ALL existing expiry folders across all FY directories ──
    # Maps expiry_date_str → existing folder absolute path
    existing_expiry_folders = {}
    # Maps fy_folder → highest expiry number (for continuing numbering)
    fy_max_number = {}
    
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if not os.path.isdir(item_path) or not item.startswith('FY_'):
            continue
        
        max_num = 0
        for subfolder in os.listdir(item_path):
            subfolder_path = os.path.join(item_path, subfolder)
            if not os.path.isdir(subfolder_path):
                continue
            # Parse: 2026-07-07_Expiry_0014
            m = re.match(r'(\d{4}-\d{2}-\d{2})_Expiry_(\d+)', subfolder)
            if m:
                exp_date_str = m.group(1)
                exp_num = int(m.group(2))
                existing_expiry_folders[exp_date_str] = subfolder_path
                max_num = max(max_num, exp_num)
        
        fy_max_number[item] = max_num
    
    # ── Process each expiry cycle ──
    summary_rows = []
    
    # Determine FY for each expiry
    fy_new_expiries = {}  # fy_folder → list of new expiry_keys (not yet in existing folders)
    
    for expiry_key in sorted(cycles.keys()):
        dt = datetime.strptime(expiry_key, '%Y-%m-%d')
        if dt.month >= 4:
            fy_start = dt.year
            fy_end = dt.year + 1
        else:
            fy_start = dt.year - 1
            fy_end = dt.year
        fy_folder = f"FY_{fy_start}-{str(fy_end)[-2:]}"
        
        if expiry_key in existing_expiry_folders:
            # ── MERGE into existing folder ──
            folder_path = existing_expiry_folders[expiry_key]
            total_contracts = 0
            new_files = 0
            
            for trade_date, df in cycles[expiry_key]:
                csv_name = f"{trade_date.strftime('%Y-%m-%d')}_nifty_options.csv"
                csv_path = os.path.join(folder_path, csv_name)
                if not os.path.exists(csv_path):
                    df.to_csv(csv_path, index=False)
                    new_files += 1
                if 'CONTRACTS' in df.columns:
                    total_contracts += df['CONTRACTS'].sum()
            
            # Count total trading days in folder after merge
            csv_count = len([f for f in os.listdir(folder_path) if f.endswith('.csv')])
            rel_folder = os.path.relpath(folder_path, base_dir)
            
            if new_files > 0:
                logging.info(f"  [MERGE] {rel_folder}: +{new_files} new files ({csv_count} total)")
            else:
                logging.info(f"  [SKIP] {rel_folder}: all files already exist ({csv_count} total)")
            
            summary_rows.append({
                'Financial_Year': fy_folder,
                'Folder': rel_folder,
                'Expiry_Date': expiry_key,
                'Trading_Days': csv_count,
                'Total_Contracts': int(total_contracts),
                'Action': 'merged' if new_files > 0 else 'skipped',
            })
        else:
            # ── CREATE new folder ──
            if fy_folder not in fy_new_expiries:
                fy_new_expiries[fy_folder] = []
            fy_new_expiries[fy_folder].append(expiry_key)
    
    # Create new folders with correct sequential numbering
    for fy_folder, new_expiries in fy_new_expiries.items():
        fy_path = os.path.join(base_dir, fy_folder)
        os.makedirs(fy_path, exist_ok=True)
        
        # Start numbering from the next available number
        next_num = fy_max_number.get(fy_folder, 0) + 1
        
        for expiry_key in sorted(new_expiries):
            folder_name = f"{expiry_key}_Expiry_{next_num:04d}"
            folder_path = os.path.join(fy_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            total_contracts = 0
            trading_days = 0
            
            for trade_date, df in cycles[expiry_key]:
                csv_name = f"{trade_date.strftime('%Y-%m-%d')}_nifty_options.csv"
                csv_path = os.path.join(folder_path, csv_name)
                df.to_csv(csv_path, index=False)
                trading_days += 1
                if 'CONTRACTS' in df.columns:
                    total_contracts += df['CONTRACTS'].sum()
            
            rel_folder = os.path.join(fy_folder, folder_name)
            logging.info(f"  [FOLDER] {rel_folder}: {trading_days} trading days")
            
            summary_rows.append({
                'Financial_Year': fy_folder,
                'Folder': rel_folder,
                'Expiry_Date': expiry_key,
                'Trading_Days': trading_days,
                'Total_Contracts': int(total_contracts),
                'Action': 'created',
            })
            
            # Register this new folder so subsequent runs see it
            existing_expiry_folders[expiry_key] = folder_path
            next_num += 1
        
        # Update the max number tracker
        fy_max_number[fy_folder] = next_num - 1
    
    return summary_rows


# ============================================================
# MAIN
# ============================================================
def print_banner():
    print()
    print("=" * 65)
    print("  +-------------------------------------------------------+")
    print("  |     NIFTY 50 OPTION CHAIN DATA DOWNLOADER             |")
    print("  |     Organized by Expiry Cycles                        |")
    print("  |     Source: NSE F&O Bhavcopy Archive                  |")
    print("  +-------------------------------------------------------+")
    print("=" * 65)
    print()
    print("  This tool downloads daily Nifty option chain data from NSE")
    print("  and organizes it into folders by expiry cycle.")
    print()
    print("  Data includes: Strike Price, Call/Put, OHLC, Settle Price,")
    print("                 Volume, Open Interest, Change in OI")
    print()
    print("  [!] Download one financial year at a time to avoid rate limits.")
    print("  [!] Pre-Feb 2019 = Monthly expiry folders.")
    print("  [!] Post-Feb 2019 = Weekly expiry folders.")
    print()


def get_user_input():
    """Get download mode and parameters from user."""
    print("-" * 65)
    print("  DOWNLOAD MODES:")
    print("  1. By Financial Year(s)")
    print("  2. By Specific Date or Date Range")
    print("-" * 65)
    print()
    
    while True:
        mode = input("  >> Select mode (1 or 2): ").strip()
        if mode in ['1', '2']:
            break
        print("    [X] Invalid selection.")
        
    print()
    if mode == '1':
        current_year = datetime.now().year
        current_month = datetime.now().month
        max_fy = current_year if current_month >= 4 else current_year - 1
        
        print("-" * 65)
        print("  AVAILABLE FINANCIAL YEARS")
        print("-" * 65)
        print()
        print(f"  You can download data from FY 2001-02 to FY {max_fy}-{str(max_fy + 1)[-2:]}")
        print()
        print("  Examples:")
        print("    Enter 2008 for FY 2008-09 (April 2008 - March 2009)")
        print("    Enter 2024 for FY 2024-25 (April 2024 - March 2025)")
        print()
        
        while True:
            try:
                start_fy = int(input("  >> Enter START financial year (e.g., 2008): ").strip())
                if start_fy < 2001 or start_fy > max_fy:
                    print(f"    [X] Please enter a year between 2001 and {max_fy}")
                    continue
                break
            except ValueError:
                print("    [X] Please enter a valid number.")
        
        while True:
            try:
                end_fy = int(input("  >> Enter END financial year   (e.g., 2025): ").strip())
                if end_fy < start_fy or end_fy > max_fy:
                    print(f"    [X] Please enter a year between {start_fy} and {max_fy}")
                    continue
                break
            except ValueError:
                print("    [X] Please enter a valid number.")
        
        print()
        print("-" * 65)
        total_fys = end_fy - start_fy + 1
        print(f"  Selected: FY {start_fy}-{str(start_fy+1)[-2:]} to FY {end_fy}-{str(end_fy+1)[-2:]}  ({total_fys} year{'s' if total_fys > 1 else ''})")
        
        total_days = total_fys * 250
        est_time = total_days * 2.5 / 60
        print(f"  Estimated: ~{total_days} trading days, ~{est_time:.0f} minutes download time")
        print("-" * 65)
        print()
        
        confirm = input("  Proceed? (y/n): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("  Cancelled.")
            sys.exit(0)
            
        return {'mode': 'fy', 'start': start_fy, 'end': end_fy}
        
    else:
        print("-" * 65)
        print("  DATE RANGE DOWNLOAD")
        print("-" * 65)
        print("  Enter dates in YYYY-MM-DD format (e.g., 2024-05-15).")
        print()
        while True:
            try:
                start_date_str = input("  >> Enter START date (YYYY-MM-DD): ").strip()
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                break
            except ValueError:
                print("    [X] Invalid format. Use YYYY-MM-DD.")
        while True:
            try:
                end_date_str = input("  >> Enter END date (YYYY-MM-DD) [Press Enter for same as start]: ").strip()
                if not end_date_str:
                    end_date = start_date
                    break
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date < start_date:
                    print("    [X] End date cannot be before start date.")
                    continue
                break
            except ValueError:
                print("    [X] Invalid format. Use YYYY-MM-DD.")
                
        print()
        print("-" * 65)
        total_days = (end_date - start_date).days + 1
        trading_days_est = int(total_days * (5/7)) + 1
        print(f"  Selected: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        est_time = trading_days_est * 2.5 / 60
        print(f"  Estimated: ~{trading_days_est} trading days, ~{max(1, int(est_time))} minutes download time")
        print("-" * 65)
        print()
        
        confirm = input("  Proceed? (y/n): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("  Cancelled.")
            sys.exit(0)
            
        return {'mode': 'date', 'start': start_date, 'end': end_date}


def process_data_for_dates(start_date, end_date, label, session, progress):
    """Download and process data for a specific date range."""
    trading_dates = get_trading_dates(start_date, end_date)
    
    logging.info(f"")
    logging.info(f"{'=' * 65}")
    logging.info(f"  [RUN] {label}")
    logging.info(f"  [INFO] {len(trading_dates)} potential trading days")
    logging.info(f"{'=' * 65}")
    
    downloaded_set = set(progress.get("downloaded", []))
    holiday_set = set(progress.get("holidays", []))
    
    all_data = []
    new_downloads = 0
    skipped = 0
    failed = 0
    holidays = 0
    
    for i, trade_date in enumerate(trading_dates):
        date_str = trade_date.strftime('%Y-%m-%d')
        
        if date_str in downloaded_set:
            skipped += 1
            continue
        
        is_recent = trade_date >= datetime(2024, 4, 1)
        if date_str in holiday_set and not is_recent:
            holidays += 1
            continue
        
        pct = ((i + 1) / len(trading_dates)) * 100
        sys.stdout.write(f"\r  [{pct:5.1f}%] Downloading {date_str}... ({new_downloads} downloaded, {holidays} holidays, {failed} failed)    ")
        sys.stdout.flush()
        
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)
        
        zip_data = download_bhavcopy(trade_date, session)
        
        if zip_data is None:
            holiday_set.add(date_str)
            progress.setdefault("holidays", []).append(date_str)
            holidays += 1
            continue
        
        df = extract_nifty_options(zip_data, trade_date)
        
        if df is not None and len(df) > 0:
            all_data.append((trade_date, df))
            downloaded_set.add(date_str)
            progress.setdefault("downloaded", []).append(date_str)
            new_downloads += 1
        else:
            downloaded_set.add(date_str)
            progress.setdefault("downloaded", []).append(date_str)
        
        if new_downloads > 0 and new_downloads % COOLDOWN_AFTER == 0:
            cd_time = random.uniform(*COOLDOWN_TIME)
            logging.info(f"\n  [COOLDOWN] Taking a breather for {cd_time:.1f}s to stay safe...")
            time.sleep(cd_time)
            session = create_nse_session()
            
        if new_downloads % 15 == 0 and new_downloads > 0:
            save_progress(progress)
    
    print()  
    
    save_progress(progress)
    
    logging.info(f"  [DONE] {label}: {new_downloads} new, {skipped} skipped, {holidays} holidays, {failed} failed")
    
    if all_data:
        logging.info(f"  [ORGANIZE] Creating expiry-cycle folders...")
        summary_rows = organize_into_folders(BASE_DIR, all_data)
        return summary_rows, session
    else:
        if skipped > 0:
            logging.info(f"  [INFO] All data for {label} was already downloaded previously.")
        else:
            logging.info(f"  [WARN] No data found for {label}.")
        return [], session


def process_financial_year(fy_year, session, progress):
    """Download and process data for one financial year."""
    fy_label = f"FY {fy_year}-{str(fy_year + 1)[-2:]}  (April {fy_year} -> March {fy_year + 1})"
    start_date, end_date = get_fy_dates(fy_year)
    return process_data_for_dates(start_date, end_date, fy_label, session, progress)


def main():
    print_banner()
    setup_logging()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        today = datetime.now()
        start_date = today.replace(day=1)
        end_date = today
        user_choices = {'mode': 'date', 'start': start_date, 'end': end_date}
    else:
        user_choices = get_user_input()
    
    os.makedirs(BASE_DIR, exist_ok=True)
    progress = load_progress()
    
    # Create session
    session = create_nse_session()
    time.sleep(1)
    
    all_summary = []
    start_time = time.time()
    
    if user_choices['mode'] == 'fy':
        for fy in range(user_choices['start'], user_choices['end'] + 1):
            summary_rows, session = process_financial_year(fy, session, progress)
            all_summary.extend(summary_rows)
            
            # Save summary after each FY
            if all_summary:
                summary_df = pd.DataFrame(all_summary)
                summary_df.to_csv(SUMMARY_FILE, index=False)
            
            # Pause between FYs to be nice to NSE servers
            if fy < user_choices['end']:
                pause = random.uniform(5, 10)
                logging.info(f"  [PAUSE] Waiting {pause:.0f}s before next financial year...")
                time.sleep(pause)
    else:
        start_date = user_choices['start']
        end_date = user_choices['end']
        label = f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        summary_rows, session = process_data_for_dates(start_date, end_date, label, session, progress)
        all_summary.extend(summary_rows)
        
        if all_summary:
            summary_df = pd.DataFrame(all_summary)
            summary_df.to_csv(SUMMARY_FILE, index=False)
    
    elapsed = time.time() - start_time
    minutes = elapsed / 60
    
    print()
    print("=" * 65)
    print("  [OK] ALL DOWNLOADS COMPLETE!")
    print("=" * 65)
    print(f"  Data saved to:      {BASE_DIR}")
    print(f"  Total expiry cycles: {len(all_summary)}")
    print(f"  Time taken:          {minutes:.1f} minutes")
    print(f"  Summary file:        {SUMMARY_FILE}")
    print(f"  Log file:            {LOG_FILE}")
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
