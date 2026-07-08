import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import os
import glob
import datetime
import json
import sys
import subprocess
import datetime

# --- basic setups ---
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(DATA_DIR, "index.html")
FETCH_SCRIPT = os.path.join(DATA_DIR, "fetch_nse_reports.py")

# --- 0. data lana start karte hain ---

def run_fetch(date_str):
    """Runs the fetch script for a specific date (DD-MM-YYYY). Returns True if files exist/downloaded."""
    dd, mm, yyyy = date_str.split('-')
    check_file = os.path.join(DATA_DIR, f"fao_participant_oi_{dd}{mm}{yyyy}.csv")
    
    if os.path.exists(check_file):
        return True
    
    print(f"[Fetching] Data for {date_str}...")
    try:
        subprocess.run([sys.executable, FETCH_SCRIPT, date_str], capture_output=True, text=True)
        if os.path.exists(check_file):
            print(f" -> Success: {date_str}")
            return True
        else:
            return False
    except Exception as e:
        print(f"Error executing fetch script: {e}")
        return False

def ensure_data_for_days(n_days):
    """Ensures we have data for the last n_days trading sessions."""
    if not n_days: return
    
    print(f"\nVerifying data for the last {n_days} days...")
    
    valid_days_count = 0
    current_date = datetime.date.today()
    max_lookback = n_days * 3 # Look back 3x just in case of holidays
    days_checked = 0
    
    while valid_days_count < n_days and days_checked < max_lookback:
        date_str = current_date.strftime("%d-%m-%Y")
        
        # Skip Weekends
        if current_date.weekday() >= 5: # 5=Sat, 6=Sun
            pass
        else:
            if run_fetch(date_str):
                valid_days_count += 1
            else:
                pass # Holiday or fail
        
        current_date -= datetime.timedelta(days=1)
        days_checked += 1
    print("Data verification complete.\n")

# --- 1. sab CSVs ko load karna ---

def load_data():
    """Loads and merges all CSV files into a single DataFrame structure."""
    
    # 1. Pehle OI files uthate hain
    oi_files = glob.glob(os.path.join(DATA_DIR, "fao_participant_oi_*.csv"))
    oi_list = []
    for f in oi_files:
        try:
            date_str = os.path.basename(f).split('_')[-1].replace('.csv', '')
            date_obj = datetime.datetime.strptime(date_str, "%d%m%Y").date()
            
            df = pd.read_csv(f, skiprows=1) 
            df.columns = df.columns.str.strip() # Fix trailing spaces
            df['Date'] = date_obj
            oi_list.append(df)
        except Exception as e:
            print(f"Skipping OI file {f}: {e}")
            
    if not oi_list:
        print("No Participant OI files found!")
        return None, None, None
        
    df_oi = pd.concat(oi_list)
    df_oi['Date'] = pd.to_datetime(df_oi['Date'])
    
    # 2. Ab volume wali files load karo
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

    # 3. Market data bhi chahiye (Nifty & VIX)
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
            
            nifty_val = nifty[0] if len(nifty) > 0 else 0
            vix_val = vix[0] if len(vix) > 0 else 0
            
            mkt_list.append({'Date': date_obj, 'Nifty': nifty_val, 'VIX': vix_val})
            
        except Exception as e:
            print(f"Skipping Market file {f}: {e}")

    df_mkt = pd.DataFrame(mkt_list)
    if not df_mkt.empty:
        df_mkt['Date'] = pd.to_datetime(df_mkt['Date'])
        
    # Sort
    df_oi = df_oi.sort_values('Date')
    if not df_vol.empty: df_vol = df_vol.sort_values('Date')
    if not df_mkt.empty: df_mkt = df_mkt.sort_values('Date')
    
    return df_oi, df_vol, df_mkt

def filter_last_n_days(df, n_days, date_col='Date'):
    """Filters the DataFrame to keep only the last n_days based on unique dates."""
    if df is None or df.empty or n_days is None:
        return df
    
    unique_dates = sorted(df[date_col].unique())
    if len(unique_dates) > n_days:
        cutoff_dates = unique_dates[-n_days:]
        return df[df[date_col].isin(cutoff_dates)]
    return df


def filter_current_month(df, date_col='Date'):
    if df is None or df.empty: return df
    current_month = datetime.date.today().month
    current_year = datetime.date.today().year
    return df[(df[date_col].dt.month == current_month) & (df[date_col].dt.year == current_year)]

def group_dates_into_weeks(dates):
    # Groups dates into weeks. A new week starts on Wednesday.
    weeks = []
    current_week = []
    
    for d in sorted(dates):
        # weekday() 0=Mon, 1=Tue, 2=Wed
        if current_week and d.weekday() == 2:
            weeks.append(current_week)
            current_week = []
        current_week.append(d)
        
    if current_week:
        weeks.append(current_week)
    return weeks

def export_week_json(df_oi, df_vol, df_mkt, week_dates, week_idx):
    json_dir = os.path.join(DATA_DIR, "json_data")
    os.makedirs(json_dir, exist_ok=True)
    
    # Filter data for this week
    if df_oi is not None: w_oi = df_oi[df_oi['Date'].isin(week_dates)]
    else: w_oi = pd.DataFrame()
    
    if df_vol is not None: w_vol = df_vol[df_vol['Date'].isin(week_dates)]
    else: w_vol = pd.DataFrame()
    
    if df_mkt is not None: w_mkt = df_mkt[df_mkt['Date'].isin(week_dates)]
    else: w_mkt = pd.DataFrame()
    
    # Convert dates to string for JSON serialization
    def serialize_df(df):
        if df.empty: return []
        temp = df.copy()
        temp['Date'] = temp['Date'].dt.strftime('%Y-%m-%d')
        return temp.to_dict(orient='records')
        
    data = {
        "week_name": f"Week {week_idx + 1}",
        "dates": [d.strftime('%Y-%m-%d') for d in week_dates],
        "oi_data": serialize_df(w_oi),
        "vol_data": serialize_df(w_vol),
        "market_data": serialize_df(w_mkt)
    }
    
    filepath = os.path.join(json_dir, f"week_{week_idx + 1}.json")
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)
    return filepath

# --- 2. Charts banane ka function ---

def generate_html_chart(df_part, df_mkt, title, metric_col, color, secondary_col_name, is_comparison=False, metric_short_col=None):
    merged = pd.merge(df_part, df_mkt, on='Date', how='left').fillna(0)
    merged['DateStr'] = merged['Date'].dt.strftime('%d-%m-%Y')
    
    y_data = merged[metric_col]
    y_chg = y_data.diff().fillna(0).astype(int)
    
    if is_comparison:
        y_short = merged[metric_short_col]
        y_short_chg = y_short.diff().fillna(0).astype(int)

    secondary_data = merged[secondary_col_name]
    
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": True}], [{"type": "table"}]]
    )
    
    fig.add_trace(
        go.Bar(
            x=merged['DateStr'], y=y_data, name=metric_col.replace('Future Index ','').replace('Option Index ',''),
            marker_color=color, customdata=y_chg,
            hovertemplate=f"{metric_col}: %{{y}}<br>Chg: %{{customdata:+}}"
        ), row=1, col=1, secondary_y=False
    )
    
    if is_comparison:
        fig.add_trace(
            go.Bar(
                x=merged['DateStr'], y=y_short, name="Short", marker_color='#ef4444', 
                customdata=y_short_chg, hovertemplate=f"Short: %{{y}}<br>Chg: %{{customdata:+}}"
            ), row=1, col=1, secondary_y=False
        )

    fig.add_trace(
        go.Scatter(
            x=merged['DateStr'], y=secondary_data, name=secondary_col_name,
            mode='lines+markers', line=dict(color='cyan', width=2)
        ), row=1, col=1, secondary_y=True
    )
    
    if is_comparison:
        header = ["Date", metric_col, "Change", "Short", "Change", secondary_col_name]
        cells = [merged.DateStr, y_data, y_chg.apply(lambda x: f"{x:+}"), y_short, y_short_chg.apply(lambda x: f"{x:+}"), secondary_data]
    else:
        header = ["Date", metric_col, "Change", secondary_col_name]
        cells = [merged.DateStr, y_data, y_chg.apply(lambda x: f"{x:+}"), secondary_data]
        
    fig.add_trace(
        go.Table(
            header=dict(values=header, fill_color='#1f222b', align='center', font=dict(color='white')),
            cells=dict(values=cells, fill_color='#2c303b', align='center', font=dict(color='#ccc'))
        ), row=2, col=1
    )
    
    fig.update_layout(
        title_text=f"<b style='color:white'>{title}</b>", barmode='group',
        xaxis=dict(type='category', title="Date", color='white'),
        yaxis=dict(color='white'),
        yaxis2=dict(color='cyan'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        template="plotly_dark", height=600, margin=dict(t=40, b=40),
        legend=dict(font=dict(color='white'))
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

# --- 3. Summary table ke helper functions ---

def format_num(val): return f"{int(val):,}"

def get_oi_status_html(change_val, is_long=True, is_put=False):
    abs_val = abs(change_val)
    if change_val == 0: return "-"
    val_fmt = format_num(abs_val)
    
    # Logic:
    # Call/Fut: Long Added (Green), Short Added (Red), Long Closed (Red), Short Closed (Green)
    # Put: Long Added (Red), Short Added (Green), Long Closed (Green), Short Closed (Red)
    
    is_added = change_val > 0
    
    if is_put:
        # PUT LOGIC
        if is_long:
            # Long Added -> Bearish (Red), Long Closed -> Bullish (Green)
            color_class = 'red' if is_added else 'green'
            text = "Added Longs" if is_added else "Closed Longs"
        else:
            # Short Added -> Bullish (Green), Short Closed -> Bearish (Red)
            color_class = 'green' if is_added else 'red'
            text = "Added Shorts" if is_added else "Closed Shorts"
    else:
        # CALL/FUT LOGIC
        if is_long:
            # Long Added -> Bullish (Green), Long Closed -> Bearish (Red)
            color_class = 'green' if is_added else 'red'
            text = "Added Longs" if is_added else "Closed Longs"
        else:
            # Short Added -> Bearish (Red), Short Closed -> Bullish (Green)
            color_class = 'red' if is_added else 'green'
            text = "Added Shorts" if is_added else "Closed Shorts"

    return f"<div class='status-cell {color_class}'>{text} <span class='val'>{val_fmt}</span></div>"

def get_vol_status_html(val, is_long=True, is_put=False):
    val_fmt = format_num(val)
    if val == 0: return "-"
    
    # Volume Logic:
    # Call/Fut: Buy Vol (Long) -> Bullish (Green), Sell Vol (Short) -> Bearish (Red)
    # Put: Buy Vol (Long) -> Bearish (Red), Sell Vol (Short) -> Bullish (Green)
    
    if is_put:
        if is_long: return f"<div class='status-cell red'>Buy Vol <span class='val'>{val_fmt}</span></div>"
        else: return f"<div class='status-cell green'>Sell Vol <span class='val'>{val_fmt}</span></div>"
    else:
        if is_long: return f"<div class='status-cell green'>Buy Vol <span class='val'>{val_fmt}</span></div>"
        else: return f"<div class='status-cell red'>Sell Vol <span class='val'>{val_fmt}</span></div>"

def get_net_action_html(net_val, is_put=False):
    abs_val = abs(net_val)
    if net_val == 0: return "-"
    val_fmt = format_num(abs_val)
    
    if is_put:
        # PUT: Net Buy -> Bearish (Red), Net Sell -> Bullish (Green)
        if net_val > 0: return f"<div class='status-cell red bold'>Bought Net <span class='val'>{val_fmt}</span></div>"
        else: return f"<div class='status-cell green bold'>Sold Net <span class='val'>{val_fmt}</span></div>"
    else:
        # CALL/FUT: Net Buy -> Bullish (Green), Net Sell -> Bearish (Red)
        if net_val > 0: return f"<div class='status-cell green bold'>Bought Net <span class='val'>{val_fmt}</span></div>"
        else: return f"<div class='status-cell red bold'>Sold Net <span class='val'>{val_fmt}</span></div>"

def get_net_oi_color(val, is_put=False):
    if val > 0: 
        # Positive Net (Longs > Shorts)
        # Put: Bearish (Red), Call: Bullish (Green)
        return "#ef4444" if is_put else "#10b981"
    if val < 0: 
        # Negative Net (Shorts > Longs)
        # Put: Bullish (Green), Call: Bearish (Red)
        return "#10b981" if is_put else "#ef4444"
    return "#8b949e"

def generate_summary_table(df, is_volume=False, n_days_history=5):
    # This logic comes from demo_summary_viz.py
    dates = sorted(df['Date'].unique())
    if len(dates) < 2: return "<p class='no-data'>Not enough data for summary</p>"
    n_days_history = min(n_days_history, len(dates))
    recent_dates = dates[-n_days_history:]
    recent_dates_desc = sorted(recent_dates, reverse=True)
    today, yesterday = dates[-1], dates[-2]
    df_today, df_prev = df[df['Date'] == today].copy(), df[df['Date'] == yesterday].copy()
    
    categories = [
        ("Index Futures", "Future Index Long", "Future Index Short"),
        ("Index Call", "Option Index Call Long", "Option Index Call Short"),
        ("Index Put", "Option Index Put Long", "Option Index Put Short"),
        ("Stock Futures", "Future Stock Long", "Future Stock Short"),
        ("Stock Calls", "Option Stock Call Long", "Option Stock Call Short"),
        ("Stock Puts", "Option Stock Put Long", "Option Stock Put Short"),
    ]
    
    history_header = "Net Volume Trend" if is_volume else "Total Net OI (Carried)"
    title_text = "Net Volume Summary" if is_volume else "Net OI Market Summary"
    
    html = f"<div class='summary-wrapper'><h2>{title_text}</h2>";
    
    for cat_name, long_col, short_col in categories:
        is_put = "Put" in cat_name
        html += f"<div class='category-block'><h3>{cat_name}</h3>"
        html += "<table class='summary-table'><thead>"
        html += "<tr><th rowspan='2'>Client Type</th><th colspan='3' class='section-header'>Action Today</th>"
        html += f"<th colspan='{len(recent_dates_desc)}' class='section-header'>{history_header}</th></tr>"
        html += "<tr><th>Longs</th><th>Shorts</th><th>Net Buy/Sell</th>"
        for d in recent_dates_desc:
            d_str = d.strftime('%d-%b')
            if d == today: d_str = "Today"
            html += f"<th>{d_str}</th>"
        html += "</tr></thead><tbody>"
        
        participants = ['Client', 'DII', 'FII', 'Pro']
        row_data = []
        for p in participants:
            p_data = {'Type': p}
            try:
                l_cur = df_today[df_today['Client Type'] == p][long_col].values[0]
                s_cur = df_today[df_today['Client Type'] == p][short_col].values[0]
                if is_volume:
                    p_data['L_val'] = l_cur; p_data['S_val'] = s_cur; p_data['Net_Act'] = l_cur - s_cur
                else:
                    l_last = df_prev[df_prev['Client Type'] == p][long_col].values[0]
                    s_last = df_prev[df_prev['Client Type'] == p][short_col].values[0]
                    p_data['L_val'] = l_cur - l_last; p_data['S_val'] = s_cur - s_last; p_data['Net_Act'] = p_data['L_val'] - p_data['S_val']
            except: p_data['L_val'] = 0; p_data['S_val'] = 0; p_data['Net_Act'] = 0
            
            for d in recent_dates_desc:
                try: 
                    row = df[(df['Date'] == d) & (df['Client Type'] == p)]
                    val = (row[long_col].values[0] - row[short_col].values[0])
                except: val = 0
                p_data[f'Net_{d}'] = val
            row_data.append(p_data)
        
        total_data = {'Type': 'TOTAL'}
        total_data['L_val'] = sum(r['L_val'] for r in row_data)
        total_data['S_val'] = sum(r['S_val'] for r in row_data)
        total_data['Net_Act'] = sum(r['Net_Act'] for r in row_data)
        for d in recent_dates_desc: total_data[f'Net_{d}'] = sum(r[f'Net_{d}'] for r in row_data)
        row_data.append(total_data)
        
        for r in row_data:
            row_class = "total-row" if r['Type'] == 'TOTAL' else ""
            html += f"<tr class='{row_class}'><td>{r['Type']}</td>"
            html += f"<td>{get_vol_status_html(r['L_val'],True, is_put) if is_volume else get_oi_status_html(r['L_val'],True, is_put)}</td>"
            html += f"<td>{get_vol_status_html(r['S_val'],False, is_put) if is_volume else get_oi_status_html(r['S_val'],False, is_put)}</td>"
            html += f"<td>{get_net_action_html(r['Net_Act'], is_put)}</td>"
            for d in recent_dates_desc:
                val = r[f'Net_{d}']; color = get_net_oi_color(val, is_put)
                html += f"<td style='color:{color}; font-weight:bold; text-align:right'>{format_num(val)}</td>"
            html += "</tr>"
        html += "</tbody></table></div>"
    html += "</div>"
    return html

def generate_activity_table(df, is_volume=False):
    dates = sorted(df['Date'].unique())
    if len(dates) < 2: return ""
    today, yesterday = dates[-1], dates[-2]
    df_today, df_prev = df[df['Date'] == today].copy(), df[df['Date'] == yesterday].copy()
    instruments = [("Index Futures", "Future Index Long", "Future Index Short"), ("Index Call", "Option Index Call Long", "Option Index Call Short"), ("Index Put", "Option Index Put Long", "Option Index Put Short"), ("Stock Futures", "Future Stock Long", "Future Stock Short"), ("Stock Calls", "Option Stock Call Long", "Option Stock Call Short"), ("Stock Puts", "Option Stock Put Long", "Option Stock Put Short")]
    participants = ['Client', 'DII', 'FII', 'Pro']
    
    title = f"Participant Activity ({'Volume' if is_volume else 'OI Positions Bought/Sold'})"
    
    html = f"<div class='activity-container'><h3>{title}</h3><table class='activity-table'>"
    html += "<thead><tr><th>Client Type</th><th>Action</th><th>Instrument</th><th style='text-align:right'>Net Qty</th></tr></thead><tbody>"
    for p in participants:
        first_row = True
        for inst_name, l_col, s_col in instruments:
            try:
                l_cur = df_today[df_today['Client Type'] == p][l_col].values[0]
                s_cur = df_today[df_today['Client Type'] == p][s_col].values[0]
                if is_volume: net_change = l_cur - s_cur
                else:
                    l_last = df_prev[df_prev['Client Type'] == p][l_col].values[0]
                    s_last = df_prev[df_prev['Client Type'] == p][s_col].values[0]
                    net_change = (l_cur - l_last) - (s_cur - s_last)
            except: net_change = 0
            
            action = "<span style='color:#10b981; font-weight:bold'>Bought Net</span>" if net_change > 0 else "<span style='color:#ef4444; font-weight:bold'>Sold Net</span>" if net_change < 0 else "<span style='color:#6b7280'>-</span>"
            row_style = "border-top: 2px solid #3b82f6;" if first_row else ""
            html += f"<tr style='{row_style}'><td><b>{p}</b>" if first_row else "<td>"
            html += f"</td><td>{action}</td><td>{inst_name}</td><td style='color:{get_net_oi_color(net_change)}; font-weight:bold; text-align:right'>{format_num(net_change)}</td></tr>"
            if first_row: first_row = False
    html += "</tbody></table></div>"
    return html

# --- 4. Main function jaha sab run hoga ---

def main():
    n_days = None
    auto_mode = False
    if len(sys.argv) > 1:
        if sys.argv[1] == '--auto':
            auto_mode = True
            print("Auto-Filtering for Current Month...")
        else:
            try:
                n_days = int(sys.argv[1])
                print(f"Auto-Filtering for last {n_days} days...")
            except ValueError:
                pass
    else:
        try:
            print("="*40)
            user_input = input("Enter number of days to analyze (Press Enter for All): ")
            if user_input.strip():
                n_days = int(user_input)
                print(f"Filtering for last {n_days} days...")
            else:
                print("Showing ALL historical data...")
            print("="*40)
        except ValueError:
            print("Invalid input, showing all data.")
            
    if n_days and not auto_mode:
        ensure_data_for_days(n_days)
    elif auto_mode:
        # In auto mode we want the script to try fetching all missing days of the current month
        current_date = datetime.date.today()
        ensure_data_for_days(current_date.day)

    print("Loading Data...")
    df_oi, df_vol, df_mkt = load_data()
    
    if df_oi is None: return

    if auto_mode:
        df_oi = filter_current_month(df_oi)
        df_vol = filter_current_month(df_vol)
        df_mkt = filter_current_month(df_mkt)
    elif n_days:
        df_oi = filter_last_n_days(df_oi, n_days)
        df_vol = filter_last_n_days(df_vol, n_days)
        df_mkt = filter_last_n_days(df_mkt, n_days)
    
    # Save original full dataframe for summary tables before filtering for charts? 
    # Actually, the summary tables need history too, which might be N days.
    # The chart filtering is good for the summary history too.
    
    if auto_mode:
        df_oi = filter_current_month(df_oi)
        df_vol = filter_current_month(df_vol)
        df_mkt = filter_current_month(df_mkt)
    elif n_days:
        df_oi = filter_last_n_days(df_oi, n_days)
        df_vol = filter_last_n_days(df_vol, n_days)
        df_mkt = filter_last_n_days(df_mkt, n_days)
    
    if df_oi is None: return

    # --- CSS Styles (thoda dark theme try kiya hai) ---
    css = """
    body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #121418; color: #e0e6ed; margin: 0; padding: 0; }
    
    
    /* Sidebar Hamburger Menu */
    .sidebar {
        height: 100%; width: 350px; position: fixed; z-index: 2000; top: 0; left: -350px;
        background-color: #1a1d21; overflow-x: hidden; transition: 0.3s;
        padding-top: 60px; border-right: 1px solid #2d323b;
        box-shadow: 2px 0 10px rgba(0,0,0,0.5);
    }
    .sidebar a {
        padding: 10px 15px 10px 30px; text-decoration: none; font-size: 16px;
        color: #8b949e; display: block; transition: 0.3s; cursor: pointer;
    }
    .sidebar a:hover, .sidebar a.active { color: #fff; background-color: #232730; border-left: 4px solid #3b82f6;}
    
    .sidebar .closebtn { position: absolute; top: 0; right: 25px; font-size: 36px; margin-left: 50px; }
    
    .hamburger-btn {
        font-size: 20px; cursor: pointer; background-color: transparent; color: white;
        padding: 10px 15px; border: none; position: fixed; top: 10px; left: 10px; z-index: 1500;
        border-radius: 8px;
    }
    .hamburger-btn:hover { background-color: #232730; }
    
    #main-content { transition: margin-left .3s; padding: 0px; }
    
    .week-container { display: none; }
    .week-container.active { display: block; }
    
    .download-json-btn {
        margin: 5px 30px 15px 40px; padding: 6px 12px; background-color: #3b82f6; color: white !important;
        text-align: left; border-radius: 4px; font-weight: normal; border-left: none !important;
        font-family: 'Segoe UI', Roboto, sans-serif; font-size: 13px; text-decoration: none;
    }
    .download-json-btn:hover { background-color: #2563eb !important; color: white !important; }

    /* Navbar Wrapper & Pill */
    .navbar-wrapper {
        position: sticky; top: 0; z-index: 1000;
        background-color: #121418; /* Match body bg to hide content behind */
        padding: 15px 0;
        display: flex; justify-content: center;
        border-bottom: 1px solid #2d323b; 
    }
    .navbar { 
        background-color: #1a1d21; 
        border-radius: 50px;
        padding: 5px;
        border: 1px solid #2d323b; 
        display: flex; 
        gap: 5px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        width: fit-content;
    }
    .navbar button { 
        background: transparent; border: none; color: #8b949e; 
        padding: 10px 30px; border-radius: 40px; font-size: 15px; font-weight: 600; cursor: pointer; 
        transition: all 0.3s ease; position: relative; white-space: nowrap;
    }
    .navbar button:hover { color: #fff; }
    .navbar button.active { 
        background: #232730; color: #60a5fa; border: 1px solid #3b82f6;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
    }
    
    .container { max-width: 1400px; margin: 30px auto; padding: 0 20px; }
    
    /* Sub Nav */
    .subnav { 
        display: flex; justify-content: center; gap: 15px; margin-bottom: 40px; 
        background: #1a1d21; padding: 10px; border-radius: 50px; 
        width: fit-content; margin-left: auto; margin-right: auto; border: 1px solid #2d323b;
    }
    .subnav button { 
        background: transparent; border: 1px solid transparent; color: #8b949e; 
        padding: 8px 24px; border-radius: 30px; cursor: pointer; font-size: 14px; transition: all 0.3s; 
    }
    .subnav button.active { 
        background: #232730; color: #60a5fa; border-color: #3b82f6; box-shadow: 0 0 15px rgba(59, 130, 246, 0.2); 
    }
    
    .card { background: #1e2229; border-radius: 12px; padding: 20px; margin-bottom: 30px; border: 1px solid #2d323b; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }
    h2 { color: #e0e6ed; text-align: center; margin-bottom: 20px; font-weight: 400; letter-spacing: 0.5px; }

    .tab-content { display: none; animation: fadeIn 0.4s; }
    .subtab-content { display: none; margin-top: 20px; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    
    /* Toggle & Summary Styles */
    .toggle-container { display: flex; justify-content: center; margin: 30px 0; }
    .toggle-pill { 
        background: #1a1d21; border-radius: 50px; padding: 5px; border: 1px solid #2d323b; 
        display: flex; gap: 5px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .toggle-btn {
        background: transparent; border: none; color: #8b949e; 
        padding: 10px 30px; border-radius: 40px; cursor: pointer; font-size: 15px; font-weight: 600;
        transition: all 0.3s ease;
    }
    .toggle-btn.active {
        background: #232730; color: #60a5fa; border: 1px solid #3b82f6;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
    }
    .result-section { display: none; animation: fadeIn 0.4s; }
    .result-section.active { display: block; }

    .summary-wrapper { display: flex; flex-direction: column; gap: 20px; margin-bottom: 40px; }
    .category-block { background: #1e2229; border-radius: 8px; padding: 15px; border: 1px solid #2d323b; width: 100%; overflow-x: auto; }
    .summary-table { width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }
    .summary-table th { background: #232730; padding: 8px; text-align: center; border: 1px solid #2d323b; color: #8b949e; }
    .summary-table td { padding: 6px 10px; border: 1px solid #2d323b; vertical-align: middle; }
    .status-cell { display: flex; justify-content: space-between; gap: 10px; }
    .val { color: #fff; font-weight: bold; }
    .green { color: #10b981; }
    .red { color: #ef4444; }
    .bold { font-weight: bold; }
    .total-row { background: #2d3342; font-weight: bold; border-top: 2px solid #3b82f6; }
    .total-row td { color: #fff; }
    .activity-container { background: #1e2229; border-radius: 8px; padding: 20px; border: 1px solid #2d323b; margin-top: 20px; max-width: 900px; margin-left: auto; margin-right: auto; }
    .activity-table { width: 100%; border-collapse: collapse; }
    .activity-table td { border: none; border-bottom: 1px solid #2d323b; padding: 10px; }
    """

    html = [f"""
    <!DOCTYPE html>
    <html><head><title>F&O Dashboard</title>
    <style>{css}</style>
    <script>
        function openNav() {{
            document.getElementById("mySidebar").style.left = "0";
            document.getElementById("main-content").style.marginLeft = "350px";
        }}
        function closeNav() {{
            document.getElementById("mySidebar").style.left = "-350px";
            document.getElementById("main-content").style.marginLeft = "0";
        }}
    </script>
    <script>
        function openParticipant(evt, pName) {{
            var weekContainer = evt.currentTarget.closest('.week-container');
            var tabcontent = weekContainer.querySelectorAll('.tab-content');
            for (var i = 0; i < tabcontent.length; i++) tabcontent[i].style.display = "none";
            var tablinks = weekContainer.querySelectorAll('.tablinks');
            for (var i = 0; i < tablinks.length; i++) tablinks[i].classList.remove("active");
            
            weekContainer.querySelector('#' + pName).style.display = "block";
            evt.currentTarget.classList.add("active");
            
            var subbtn = weekContainer.querySelector('#' + pName + ' .subnav button');
            if(subbtn) subbtn.click();
            setTimeout(function() {{ window.dispatchEvent(new Event('resize')); }}, 100);
        }}
        function openMetric(evt, mName, pId) {{
            var parent = evt.currentTarget.closest('#' + pId);
            var content = parent.getElementsByClassName("subtab-content");
            for (var i = 0; i < content.length; i++) content[i].style.display = "none";
            var links = parent.querySelectorAll(".subnav button");
            for (var i = 0; i < links.length; i++) links[i].className = links[i].className.replace(" active", "");
            parent.querySelector("." + mName).style.display = "block";
            evt.currentTarget.className += " active";
            setTimeout(function() {{ window.dispatchEvent(new Event('resize')); }}, 100);
        }}
        function toggleSummary(viewName, weekId) {{
            var wc = document.getElementById('week-container-' + weekId);
            wc.querySelectorAll('.result-section').forEach(el => el.classList.remove('active'));
            wc.querySelectorAll('.toggle-btn').forEach(el => el.classList.remove('active'));
            wc.querySelector('#view-' + viewName).classList.add('active');
            wc.querySelector('#btn-' + viewName).classList.add('active');
        }}
    </script>
    </head><body>
    
    <div id="mySidebar" class="sidebar">
        <a href="javascript:void(0)" class="closebtn" onclick="closeNav()">&times;</a>
    """]
    
    # Group dates into weeks
    all_dates = sorted(df_oi['Date'].unique()) if df_oi is not None else []
    weeks = group_dates_into_weeks(all_dates)
    
    # Get current month header
    if all_dates:
        month_header = all_dates[-1].strftime("%B %Y")
        html.append(f'<div style="padding: 10px 15px; color: #8892b0; font-size: 14px; text-transform: uppercase; margin-top: 10px; font-family: monospace;">📅 {month_header}</div>')

    # Generate Sidebar Links
    import urllib.parse
    for idx, week_dates in enumerate(weeks):
        active_cls = "active" if idx == len(weeks)-1 else ""
        num_days = len(week_dates)
        is_current = " (current)" if idx == len(weeks)-1 else ""
        trading_days_str = f" ({num_days} trading days)" if not is_current else ""
        label = f'Week {idx+1} (Expiry: {week_dates[-1].strftime("%b %d")}){trading_days_str}{is_current}'
        
        # Wrapping each week block
        html.append(f'<div class="sidebar-item-wrapper" style="padding-left: 20px;">')
        prefix = '└─ ' if idx == len(weeks) - 1 else '├─ '
        
        # Link part
        html.append(f'<div style="color: #8892b0; font-family: monospace; display: flex; align-items: flex-start; padding-right: 15px; margin-top: 10px;">')
        html.append(f'<span style="white-space: pre;">{prefix}</span>')
        html.append(f'<a id="sidebar-link-{idx}" class="sidebar-week-link {active_cls}" style="font-family: monospace; font-size: 14px; padding: 0; line-height: 1.4; display: inline-block; word-wrap: break-word; white-space: normal;" onclick="switchWeek({idx})">{label}</a>')
        html.append('</div>')
        
        # Export JSON for the week
        export_week_json(df_oi, df_vol, df_mkt, week_dates, idx)
        
        # Encode as Data URI so download works offline locally without fetching
        try:
            with open(f"json_data/week_{idx+1}.json", "r", encoding="utf-8") as f:
                encoded_json = urllib.parse.quote(f.read())
            data_uri = "data:application/json;charset=utf-8," + encoded_json
            html.append(f'<a href="{data_uri}" download="week_{idx+1}.json" class="download-json-btn" id="json-link-{idx}" style="{"display:block" if active_cls else "display:none"}">⬇️ Download JSON</a>')
        except Exception as e:
            html.append(f'<a href="#" onclick="alert(\'JSON generation failed.\')" class="download-json-btn" id="json-link-{idx}" style="{"display:block" if active_cls else "display:none"}">⬇️ Download JSON</a>')
            
        html.append('</div>')
        
    # --- Option Chain Menu ---
    html.append('<div style="padding: 10px 15px; color: #8892b0; font-size: 14px; text-transform: uppercase; margin-top: 20px; font-family: monospace;">🔗 Option Chain</div>')
    
    import glob
    option_files = glob.glob(os.path.join(DATA_DIR, "FY_*", "*", "*_nifty_options.csv"))
    oc_dates = []
    
    current_month_val = all_dates[-1].month if all_dates else None
    current_year_val = all_dates[-1].year if all_dates else None
        
    for f in option_files:
        basename = os.path.basename(f)
        date_str = basename.split("_")[0]
        try:
            oc_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if current_month_val and current_year_val:
                if oc_date.month == current_month_val and oc_date.year == current_year_val:
                    oc_dates.append((oc_date, f))
            else:
                oc_dates.append((oc_date, f))
        except:
            pass

    oc_dates.sort(key=lambda x: x[0])
    oc_date_list = [d[0] for d in oc_dates]
    oc_weeks_dates = group_dates_into_weeks(oc_date_list)
    date_to_path = {d[0]: d[1] for d in oc_dates}
    
    for idx, week_dates in enumerate(oc_weeks_dates):
        if not week_dates: continue
        label = f'Week {idx+1} (Expiry: {week_dates[-1].strftime("%b %d")})'
        html.append(f'<div class="sidebar-item-wrapper" style="padding-left: 20px;">')
        prefix = '└─ ' if idx == len(oc_weeks_dates) - 1 else '├─ '
        html.append(f'<div style="color: #8892b0; font-family: monospace; display: flex; align-items: flex-start; padding-right: 15px; margin-top: 10px;">')
        html.append(f'<span style="white-space: pre;">{prefix}</span>')
        html.append(f'<span style="font-family: monospace; font-size: 14px; padding: 0; line-height: 1.4; display: inline-block;">{label}</span>')
        html.append('</div>')
        
        html.append(f'<div style="padding-left: 25px; margin-top: 5px;">')
        for d_idx, dt in enumerate(week_dates):
            d_prefix = '└─ ' if d_idx == len(week_dates) - 1 else '├─ '
            date_str_display = dt.strftime("%d-%b-%Y")
            f_path = date_to_path.get(dt)
            if f_path:
                rel_path = os.path.relpath(f_path, DATA_DIR).replace("\\", "/")
                html.append(f'<div style="color: #8892b0; font-family: monospace; display: flex; align-items: center; margin-top: 3px;">')
                html.append(f'<span style="white-space: pre;">{d_prefix}</span>')
                html.append(f'<a href="{rel_path}" download class="sidebar-week-link" style="font-family: monospace; font-size: 13px; padding: 0; display: inline-block; text-decoration: none; color: #58a6ff;" onmouseover="this.style.color=\'#79c0ff\'" onmouseout="this.style.color=\'#58a6ff\'">{date_str_display} ⬇️</a>')
                html.append('</div>')
        html.append('</div>')
        html.append('</div>')
        
    html.append('</div>\n<div id="main-content">\n<button class="hamburger-btn" onclick="openNav()">&#9776;</button>')
    html.append('<script>function switchWeek(weekId) { document.querySelectorAll(".week-container").forEach(el => el.classList.remove("active")); document.querySelectorAll(".sidebar-week-link").forEach(el => el.classList.remove("active")); document.getElementById("week-container-" + weekId).classList.add("active"); document.querySelectorAll(".download-json-btn").forEach(el => el.style.display="none"); document.getElementById("json-link-" + weekId).style.display="block"; closeNav(); var firstTab = document.querySelector("#week-container-" + weekId + " .tablinks"); if(firstTab) firstTab.click(); setTimeout(function() { window.dispatchEvent(new Event("resize")); }, 100); }</script>')
    
    # Iterate through each week
    for idx, week_dates in enumerate(weeks):
        active_cls = "active" if idx == len(weeks)-1 else ""
        html.append(f"<div id='week-container-{idx}' class='week-container {active_cls}'>")
        
        # --- Filter Data for this week ---
        w_oi = df_oi[df_oi['Date'].isin(week_dates)] if df_oi is not None else None
        w_vol = df_vol[df_vol['Date'].isin(week_dates)] if df_vol is not None else None
        w_mkt = df_mkt[df_mkt['Date'].isin(week_dates)] if df_mkt is not None else None

        html.append('<div class="navbar-wrapper"><div class="navbar">')

    # Updated: FII, DII, Pro, Client, Summary
    nav_tabs = ['FII', 'DII', 'Pro', 'Client', 'Summary']
    for p in nav_tabs:
         html.append(f"<button class='tablinks' onclick=\"openParticipant(event, '{p}')\">{p}</button>")
    html.append("</div></div>") # End Navbar
    
    # --- Generate Content ---
    
    op_types = [
        ("Option Index Call Long", "Call Long", "#10b981"),
        ("Option Index Put Short", "Put Short", "#10b981"),
        ("Option Index Put Long", "Put Long", "#ef4444"), 
        ("Option Index Call Short", "Call Short", "#ef4444"), 
        ("Option Stock Call Long", "Stock Call Long", "#10b981"),
        ("Option Stock Put Short", "Stock Put Short", "#10b981"),
        ("Option Stock Put Long", "Stock Put Long", "#ef4444"),
        ("Option Stock Call Short", "Stock Call Short", "#ef4444")
    ]
    
    participants = ['FII', 'DII', 'Pro', 'Client']
    
    # 1. Loop for Regular Participants
    for p in participants:
        print(f"Generating charts for {p}...")
        html.append(f"<div id='{p}' class='tab-content'><div class='container'>")
        
        # Sub Nav
        html.append(f"""
        <div class="subnav">
            <button onclick="openMetric(event, 'oi-view', '{p}')">OI Analysis</button>
            <button onclick="openMetric(event, 'vol-view', '{p}')">Volume Analysis</button>
        </div>
        """)
        
        # --- OI View ---
        p_oi = w_oi[w_oi['Client Type'] == p].copy()
        html.append("<div class='oi-view subtab-content'>")
        
        # Futures
        html.append(f"<h2>{p} Futures OI</h2>")
        c1 = generate_html_chart(p_oi, w_mkt, f"{p} Future Index OI", "Future Index Long", "#10b981", "Nifty", True, "Future Index Short")
        c2 = generate_html_chart(p_oi, w_mkt, f"{p} Future Stock OI", "Future Stock Long", "#10b981", "Nifty", True, "Future Stock Short")
        html.append(f"<div class='card'>{c1}</div><div class='card'>{c2}</div>")
        
        # Options
        html.append(f"<h2>{p} Options OI</h2>")
        for col_full, col_short, color in op_types:
            c = generate_html_chart(p_oi, w_mkt, f"{p} {col_full} OI", col_full, color, "Nifty")
            html.append(f"<div class='card'>{c}</div>")
            
        html.append("</div>") 
        
        # --- Volume View ---
        if w_vol is not None and not w_vol.empty:
            p_vol = w_vol[w_vol['Client Type'] == p].copy()
            html.append("<div class='vol-view subtab-content'>")
            
            # Futures Vol
            html.append(f"<h2>{p} Futures Volume</h2>")
            c3 = generate_html_chart(p_vol, w_mkt, f"{p} Future Index Volume", "Future Index Long", "#10b981", "VIX", True, "Future Index Short")
            c4 = generate_html_chart(p_vol, w_mkt, f"{p} Future Stock Volume", "Future Stock Long", "#10b981", "VIX", True, "Future Stock Short")
            html.append(f"<div class='card'>{c3}</div><div class='card'>{c4}</div>")
            
            # Options Vol
            html.append(f"<h2>{p} Options Volume</h2>")
            for col_full, col_short, color in op_types:
                c = generate_html_chart(p_vol, w_mkt, f"{p} {col_full} Volume", col_full, color, "VIX")
                html.append(f"<div class='card'>{c}</div>")
            html.append("</div>")
        else:
            html.append("<div class='vol-view subtab-content'><p>No Volume Data</p></div>")

        html.append("</div></div>") # End Participant Tab
        
    # 2. Add 'Summary' Tab Content
    html.append(f"<div id='Summary' class='tab-content'><div class='container'>")
    
    # Toggle Controls
    html.append("""
    <div class="toggle-container">
        <div class="toggle-pill">
            <button id="btn-oi" class="toggle-btn active" onclick="toggleSummary('oi', {idx})">OI Analysis</button>
            <button id="btn-vol" class="toggle-btn" onclick="toggleSummary('vol', {idx})">Volume Analysis</button>
        </div>
    </div>
    """)
    
    # OI View of Summary
    html.append("<div id='view-oi' class='result-section active'>")
    html.append(generate_summary_table(w_oi, is_volume=False, n_days_history=5))
    html.append(generate_activity_table(w_oi, is_volume=False))
    html.append("</div>")
    
    # Vol View of Summary
    html.append("<div id='view-vol' class='result-section'>")
    html.append(generate_summary_table(w_vol, is_volume=True, n_days_history=5))
    html.append(generate_activity_table(w_vol, is_volume=True))
    html.append("</div>")
    
    html.append("</div></div>") # End Summary Tab
        
    
    html.append("</div>") # End Week Container
        
    html.append("</div>") # End Main Content
    
    # Auto click the active week's first tab
    html.append(f"<script>document.querySelector('#week-container-{len(weeks)-1} .tablinks').click();</script></body></html>")

    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("".join(html))
    print(f"Dashboard generated: {OUTPUT_FILE}")
    try:
        import webbrowser
        webbrowser.open(f"file://{OUTPUT_FILE}")
    except Exception as e:
        print(f"Could not open file automatically: {e}")

if __name__ == "__main__":
    main()
