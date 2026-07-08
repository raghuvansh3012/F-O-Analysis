"""
F&O Analysis JSON Export Tool
=============================
Ye script saari NSE CSV files (OI, Volume, Market data) read karta hai,
wahi analysis karta hai jo HTML dashboard me hoti hai,
aur sab kuch ek structured JSON file me dump kar deta hai.

Usage:
    python generate_json_report.py          # Saari available data
    python generate_json_report.py 5        # Last 5 days ka data

Output:
    ../fno_analysis_report.json (project root me)

NOTE: Ye script original project files me KUCH BHI CHANGE NAHI KARTA.
      Sirf CSV read karta hai aur JSON likhta hai.
"""

import pandas as pd
import os
import glob
import datetime
import sys
import json
import numpy as np


# --- Paths ---
# Script json_export/ folder me hai, data upar project root me hai
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(SCRIPT_DIR)  # parent = project root
OUTPUT_FILE = os.path.join(DATA_DIR, "fno_analysis_report.json")


# ============================================================
#  SECTION 1: DATA LOADING (copied logic from fno_analysis_viz.py)
# ============================================================

def load_data():
    """Loads and merges all CSV files into DataFrames. 
    Returns (df_oi, df_vol, df_mkt)"""

    # 1. Participant OI files
    oi_files = glob.glob(os.path.join(DATA_DIR, "fao_participant_oi_*.csv"))
    oi_list = []
    for f in oi_files:
        try:
            date_str = os.path.basename(f).split('_')[-1].replace('.csv', '')
            date_obj = datetime.datetime.strptime(date_str, "%d%m%Y").date()
            df = pd.read_csv(f, skiprows=1)
            df.columns = df.columns.str.strip()
            df['Date'] = date_obj
            oi_list.append(df)
        except Exception as e:
            print(f"Skipping OI file {f}: {e}")

    if not oi_list:
        print("No Participant OI files found!")
        return None, None, None

    df_oi = pd.concat(oi_list)
    df_oi['Date'] = pd.to_datetime(df_oi['Date'])

    # 2. Participant Volume files
    vol_files = glob.glob(os.path.join(DATA_DIR, "fao_participant_vol_*.csv"))
    vol_list = []
    for f in vol_files:
        try:
            date_str = os.path.basename(f).split('_')[-1].replace('.csv', '')
            date_obj = datetime.datetime.strptime(date_str, "%d%m%Y").date()
            df = pd.read_csv(f, skiprows=1)
            df.columns = df.columns.str.strip()
            df['Date'] = date_obj
            vol_list.append(df)
        except Exception as e:
            print(f"Skipping Vol file {f}: {e}")

    df_vol = pd.concat(vol_list) if vol_list else pd.DataFrame()
    if not df_vol.empty:
        df_vol['Date'] = pd.to_datetime(df_vol['Date'])

    # 3. Market data (Nifty & VIX)
    mkt_files = glob.glob(os.path.join(DATA_DIR, "ind_close_all_*.csv"))
    mkt_list = []
    for f in mkt_files:
        try:
            date_str = os.path.basename(f).split('_')[-1].replace('.csv', '')
            date_obj = datetime.datetime.strptime(date_str, "%d%m%Y").date()
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip()

            nifty = df[df['Index Name'] == 'Nifty 50']['Closing Index Value'].values
            vix = df[df['Index Name'] == 'India VIX']['Closing Index Value'].values
            bank_nifty = df[df['Index Name'] == 'Nifty Bank']['Closing Index Value'].values

            nifty_val = float(nifty[0]) if len(nifty) > 0 else 0
            vix_val = float(vix[0]) if len(vix) > 0 else 0
            bank_nifty_val = float(bank_nifty[0]) if len(bank_nifty) > 0 else 0

            mkt_list.append({
                'Date': date_obj,
                'Nifty': nifty_val,
                'VIX': vix_val,
                'Bank_Nifty': bank_nifty_val
            })
        except Exception as e:
            print(f"Skipping Market file {f}: {e}")

    df_mkt = pd.DataFrame(mkt_list)
    if not df_mkt.empty:
        df_mkt['Date'] = pd.to_datetime(df_mkt['Date'])

    # Sort by date
    df_oi = df_oi.sort_values('Date')
    if not df_vol.empty:
        df_vol = df_vol.sort_values('Date')
    if not df_mkt.empty:
        df_mkt = df_mkt.sort_values('Date')

    return df_oi, df_vol, df_mkt


def filter_last_n_days(df, n_days, date_col='Date'):
    """Filters DataFrame to keep only last n_days unique dates."""
    if df is None or df.empty or n_days is None:
        return df
    unique_dates = sorted(df[date_col].unique())
    if len(unique_dates) > n_days:
        cutoff_dates = unique_dates[-n_days:]
        return df[df[date_col].isin(cutoff_dates)]
    return df


# ============================================================
#  SECTION 2: RAW DATA TO JSON
# ============================================================

# All 12 data columns in the CSVs
DATA_COLUMNS = [
    'Future Index Long', 'Future Index Short',
    'Future Stock Long', 'Future Stock Short',
    'Option Index Call Long', 'Option Index Put Long',
    'Option Index Call Short', 'Option Index Put Short',
    'Option Stock Call Long', 'Option Stock Put Long',
    'Option Stock Call Short', 'Option Stock Put Short',
    'Total Long Contracts', 'Total Short Contracts'
]

PARTICIPANTS = ['Client', 'DII', 'FII', 'Pro']

# Categories for summary (same as original viz script)
CATEGORIES = [
    ("Index Futures", "Future Index Long", "Future Index Short"),
    ("Index Call", "Option Index Call Long", "Option Index Call Short"),
    ("Index Put", "Option Index Put Long", "Option Index Put Short"),
    ("Stock Futures", "Future Stock Long", "Future Stock Short"),
    ("Stock Calls", "Option Stock Call Long", "Option Stock Call Short"),
    ("Stock Puts", "Option Stock Put Long", "Option Stock Put Short"),
]


def safe_int(val):
    """Safely convert to int, handle NaN/inf."""
    if pd.isna(val) or np.isinf(val):
        return 0
    return int(val)


def date_to_str(d):
    """Convert any date/datetime/Timestamp to DD-MM-YYYY string."""
    if isinstance(d, pd.Timestamp):
        return d.strftime('%d-%m-%Y')
    if isinstance(d, (datetime.date, datetime.datetime)):
        return d.strftime('%d-%m-%Y')
    return str(d)


def build_participant_data(df, data_type_label):
    """Build per-participant, per-date data dict from OI or Vol DataFrame."""
    result = {}
    if df is None or df.empty:
        return result

    for p in PARTICIPANTS:
        p_data = {}
        p_df = df[df['Client Type'] == p]
        for _, row in p_df.iterrows():
            d = date_to_str(row['Date'])
            day_data = {}
            for col in DATA_COLUMNS:
                # Replace spaces with underscores for JSON keys
                key = col.replace(' ', '_')
                day_data[key] = safe_int(row.get(col, 0))
            p_data[d] = day_data
        result[p] = p_data
    return result


def build_market_data(df_mkt):
    """Build market data dict keyed by date string."""
    result = {}
    if df_mkt is None or df_mkt.empty:
        return result

    for _, row in df_mkt.iterrows():
        d = date_to_str(row['Date'])
        result[d] = {
            "Nifty": round(float(row.get('Nifty', 0)), 2),
            "VIX": round(float(row.get('VIX', 0)), 2),
            "Bank_Nifty": round(float(row.get('Bank_Nifty', 0)), 2)
        }
    return result


# ============================================================
#  SECTION 3: ANALYSIS COMPUTATIONS
# ============================================================

def compute_oi_changes(df_oi):
    """
    Compute OI changes between latest and previous date.
    Returns dict per participant with changes for each instrument.
    """
    if df_oi is None or df_oi.empty:
        return {}

    dates = sorted(df_oi['Date'].unique())
    if len(dates) < 2:
        return {"error": "Not enough dates for change calculation (need at least 2)"}

    today = dates[-1]
    yesterday = dates[-2]
    df_today = df_oi[df_oi['Date'] == today]
    df_prev = df_oi[df_oi['Date'] == yesterday]

    result = {}
    for p in PARTICIPANTS:
        p_result = {
            "latest_date": date_to_str(today),
            "vs_previous_date": date_to_str(yesterday)
        }
        try:
            row_t = df_today[df_today['Client Type'] == p].iloc[0]
            row_p = df_prev[df_prev['Client Type'] == p].iloc[0]

            for col in DATA_COLUMNS:
                key = col.replace(' ', '_')
                cur = safe_int(row_t.get(col, 0))
                prev = safe_int(row_p.get(col, 0))
                p_result[f"{key}_Current"] = cur
                p_result[f"{key}_Previous"] = prev
                p_result[f"{key}_Change"] = cur - prev
        except (IndexError, KeyError):
            pass

        # Net changes for key instruments
        for cat_name, long_col, short_col in CATEGORIES:
            key_prefix = cat_name.replace(' ', '_')
            l_key = long_col.replace(' ', '_')
            s_key = short_col.replace(' ', '_')
            l_chg = p_result.get(f"{l_key}_Change", 0)
            s_chg = p_result.get(f"{s_key}_Change", 0)
            p_result[f"Net_{key_prefix}_Change"] = l_chg - s_chg

        result[p] = p_result
    return result


def compute_net_positions(df):
    """
    Compute net positions (Long - Short) per participant, per date, per instrument.
    """
    if df is None or df.empty:
        return {}

    result = {}
    for p in PARTICIPANTS:
        p_data = {}
        p_df = df[df['Client Type'] == p]
        for _, row in p_df.iterrows():
            d = date_to_str(row['Date'])
            nets = {}
            for cat_name, long_col, short_col in CATEGORIES:
                key = cat_name.replace(' ', '_')
                l_val = safe_int(row.get(long_col, 0))
                s_val = safe_int(row.get(short_col, 0))
                nets[f"{key}_Net"] = l_val - s_val
                nets[f"{key}_Long"] = l_val
                nets[f"{key}_Short"] = s_val
            p_data[d] = nets
        result[p] = p_data
    return result


def compute_summary_table(df, is_volume=False, n_days_history=5):
    """
    Compute the summary table data (same logic as generate_summary_table in viz script).
    Returns structured dict.
    """
    if df is None or df.empty:
        return {}

    dates = sorted(df['Date'].unique())
    if len(dates) < 2:
        return {"error": "Not enough data for summary"}

    n_days_history = min(n_days_history, len(dates))
    recent_dates = dates[-n_days_history:]
    recent_dates_desc = sorted(recent_dates, reverse=True)
    today = dates[-1]
    yesterday = dates[-2]
    df_today = df[df['Date'] == today].copy()
    df_prev = df[df['Date'] == yesterday].copy()

    summary = {}
    for cat_name, long_col, short_col in CATEGORIES:
        is_put = "Put" in cat_name
        cat_data = {}

        for p in PARTICIPANTS:
            p_entry = {}
            try:
                l_cur = safe_int(df_today[df_today['Client Type'] == p][long_col].values[0])
                s_cur = safe_int(df_today[df_today['Client Type'] == p][short_col].values[0])
                if is_volume:
                    p_entry['long_value'] = l_cur
                    p_entry['short_value'] = s_cur
                    p_entry['net_action'] = l_cur - s_cur
                else:
                    l_last = safe_int(df_prev[df_prev['Client Type'] == p][long_col].values[0])
                    s_last = safe_int(df_prev[df_prev['Client Type'] == p][short_col].values[0])
                    p_entry['long_change'] = l_cur - l_last
                    p_entry['short_change'] = s_cur - s_last
                    p_entry['net_action'] = (l_cur - l_last) - (s_cur - s_last)
            except (IndexError, KeyError):
                if is_volume:
                    p_entry['long_value'] = 0
                    p_entry['short_value'] = 0
                else:
                    p_entry['long_change'] = 0
                    p_entry['short_change'] = 0
                p_entry['net_action'] = 0

            # Sentiment label (same logic as HTML version)
            net = p_entry['net_action']
            if is_put:
                p_entry['sentiment'] = "Bearish" if net > 0 else ("Bullish" if net < 0 else "Neutral")
            else:
                p_entry['sentiment'] = "Bullish" if net > 0 else ("Bearish" if net < 0 else "Neutral")

            # Historical net by date
            net_by_date = {}
            for d in recent_dates_desc:
                try:
                    row = df[(df['Date'] == d) & (df['Client Type'] == p)]
                    val = safe_int(row[long_col].values[0]) - safe_int(row[short_col].values[0])
                except (IndexError, KeyError):
                    val = 0
                net_by_date[date_to_str(d)] = val
            p_entry['net_by_date'] = net_by_date

            cat_data[p] = p_entry

        # TOTAL row
        total = {}
        if is_volume:
            total['long_value'] = sum(cat_data[p].get('long_value', 0) for p in PARTICIPANTS)
            total['short_value'] = sum(cat_data[p].get('short_value', 0) for p in PARTICIPANTS)
        else:
            total['long_change'] = sum(cat_data[p].get('long_change', 0) for p in PARTICIPANTS)
            total['short_change'] = sum(cat_data[p].get('short_change', 0) for p in PARTICIPANTS)
        total['net_action'] = sum(cat_data[p].get('net_action', 0) for p in PARTICIPANTS)
        total_net = total['net_action']
        if is_put:
            total['sentiment'] = "Bearish" if total_net > 0 else ("Bullish" if total_net < 0 else "Neutral")
        else:
            total['sentiment'] = "Bullish" if total_net > 0 else ("Bearish" if total_net < 0 else "Neutral")

        total_net_by_date = {}
        for d in recent_dates_desc:
            total_net_by_date[date_to_str(d)] = sum(
                cat_data[p]['net_by_date'].get(date_to_str(d), 0) for p in PARTICIPANTS
            )
        total['net_by_date'] = total_net_by_date
        cat_data['TOTAL'] = total

        summary[cat_name] = cat_data

    return summary


def compute_activity_table(df, is_volume=False):
    """
    Compute the activity table (same logic as generate_activity_table in viz script).
    Per participant, per instrument: net action with quantity.
    """
    if df is None or df.empty:
        return {}

    dates = sorted(df['Date'].unique())
    if len(dates) < 2:
        return {"error": "Not enough data for activity table"}

    today = dates[-1]
    yesterday = dates[-2]
    df_today = df[df['Date'] == today].copy()
    df_prev = df[df['Date'] == yesterday].copy()

    result = {}
    for p in PARTICIPANTS:
        p_data = {}
        for cat_name, long_col, short_col in CATEGORIES:
            try:
                l_cur = safe_int(df_today[df_today['Client Type'] == p][long_col].values[0])
                s_cur = safe_int(df_today[df_today['Client Type'] == p][short_col].values[0])
                if is_volume:
                    net_change = l_cur - s_cur
                else:
                    l_last = safe_int(df_prev[df_prev['Client Type'] == p][long_col].values[0])
                    s_last = safe_int(df_prev[df_prev['Client Type'] == p][short_col].values[0])
                    net_change = (l_cur - l_last) - (s_cur - s_last)
            except (IndexError, KeyError):
                net_change = 0

            is_put = "Put" in cat_name
            if net_change > 0:
                action = "Bought Net"
                if is_put:
                    sentiment = "Bearish"
                else:
                    sentiment = "Bullish"
            elif net_change < 0:
                action = "Sold Net"
                if is_put:
                    sentiment = "Bullish"
                else:
                    sentiment = "Bearish"
            else:
                action = "No Change"
                sentiment = "Neutral"

            p_data[cat_name] = {
                "action": action,
                "net_qty": net_change,
                "sentiment": sentiment
            }
        result[p] = p_data
    return result


def build_raw_csv_data(df_oi, df_vol, df_mkt):
    """Include raw CSV data as-is for AI reference."""
    raw = {"oi_files": {}, "volume_files": {}, "market_files": {}}

    # OI raw
    if df_oi is not None and not df_oi.empty:
        for d in sorted(df_oi['Date'].unique()):
            d_str = date_to_str(d)
            rows = df_oi[df_oi['Date'] == d]
            day_rows = []
            for _, row in rows.iterrows():
                entry = {"Client_Type": row.get('Client Type', '')}
                for col in DATA_COLUMNS:
                    entry[col.replace(' ', '_')] = safe_int(row.get(col, 0))
                day_rows.append(entry)
            raw['oi_files'][d_str] = day_rows

    # Volume raw
    if df_vol is not None and not df_vol.empty:
        for d in sorted(df_vol['Date'].unique()):
            d_str = date_to_str(d)
            rows = df_vol[df_vol['Date'] == d]
            day_rows = []
            for _, row in rows.iterrows():
                entry = {"Client_Type": row.get('Client Type', '')}
                for col in DATA_COLUMNS:
                    entry[col.replace(' ', '_')] = safe_int(row.get(col, 0))
                day_rows.append(entry)
            raw['volume_files'][d_str] = day_rows

    # Market raw
    if df_mkt is not None and not df_mkt.empty:
        for _, row in df_mkt.iterrows():
            d_str = date_to_str(row['Date'])
            raw['market_files'][d_str] = {
                "Nifty": round(float(row.get('Nifty', 0)), 2),
                "VIX": round(float(row.get('VIX', 0)), 2),
                "Bank_Nifty": round(float(row.get('Bank_Nifty', 0)), 2)
            }

    return raw


# ============================================================
#  SECTION 4: MAIN — ASSEMBLE AND OUTPUT
# ============================================================

def main():
    print("=" * 60)
    print("   F&O ANALYSIS — JSON EXPORT TOOL")
    print("=" * 60)

    # --- Parse args ---
    n_days = None
    if len(sys.argv) > 1:
        try:
            n_days = int(sys.argv[1])
            print(f"\nFiltering for last {n_days} days...")
        except ValueError:
            pass
    else:
        try:
            user_input = input("\nEnter number of days to analyze (Press Enter for All): ")
            if user_input.strip():
                n_days = int(user_input)
                print(f"Filtering for last {n_days} days...")
            else:
                print("Exporting ALL available data...")
        except ValueError:
            print("Invalid input, exporting all data.")

    # --- Load Data ---
    print("\n[1/4] Loading CSV data...")
    df_oi, df_vol, df_mkt = load_data()

    if df_oi is None:
        print("ERROR: No OI data found. Make sure CSV files exist in the project folder.")
        print(f"Looking in: {DATA_DIR}")
        sys.exit(1)

    # --- Filter ---
    if n_days:
        df_oi = filter_last_n_days(df_oi, n_days)
        df_vol = filter_last_n_days(df_vol, n_days)
        df_mkt = filter_last_n_days(df_mkt, n_days)

    # --- Get date range ---
    all_dates = sorted(df_oi['Date'].unique())
    date_strings = [date_to_str(d) for d in all_dates]
    print(f"   Found {len(date_strings)} trading days: {date_strings}")

    # --- Compute Everything ---
    print("[2/4] Computing analysis...")

    report = {
        "report_metadata": {
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "data_dates": date_strings,
            "n_days_analyzed": len(date_strings),
            "n_days_requested": n_days if n_days else "all"
        },
        "market_data": build_market_data(df_mkt),
        "participant_oi": build_participant_data(df_oi, "OI"),
        "participant_volume": build_participant_data(df_vol, "Volume"),
        "analysis": {
            "oi_changes": compute_oi_changes(df_oi),
            "net_oi_positions": compute_net_positions(df_oi),
            "net_volume_positions": compute_net_positions(df_vol),
            "summary_table": {
                "oi": compute_summary_table(df_oi, is_volume=False, n_days_history=5),
                "volume": compute_summary_table(df_vol, is_volume=True, n_days_history=5)
            },
            "activity_table": {
                "oi": compute_activity_table(df_oi, is_volume=False),
                "volume": compute_activity_table(df_vol, is_volume=True)
            }
        },
        "raw_csv_data": build_raw_csv_data(df_oi, df_vol, df_mkt)
    }

    # --- Write JSON ---
    print(f"[3/4] Writing JSON to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    file_size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"[4/4] Done! File size: {file_size_kb:.1f} KB")
    print(f"\n{'=' * 60}")
    print(f"JSON Report saved: {OUTPUT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
