"""Quick validation script for the generated JSON report."""
import json
import os

json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fno_analysis_report.json")

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== TOP LEVEL KEYS ===")
for k in data.keys():
    print(f"  {k}")

print("\n=== ANALYSIS KEYS ===")
for k in data['analysis'].keys():
    print(f"  {k}")

print("\n=== MARKET DATA ===")
for d, vals in data['market_data'].items():
    print(f"  {d}: Nifty={vals['Nifty']}, VIX={vals['VIX']}, BankNifty={vals['Bank_Nifty']}")

print("\n=== FII OI CHANGES (Latest) ===")
fii = data['analysis']['oi_changes']['FII']
print(f"  Latest: {fii['latest_date']} vs {fii['vs_previous_date']}")
print(f"  Future Index Long Change: {fii['Future_Index_Long_Change']}")
print(f"  Future Index Short Change: {fii['Future_Index_Short_Change']}")
print(f"  Net Index Futures Change: {fii['Net_Index_Futures_Change']}")

print("\n=== SUMMARY TABLE (OI) - Index Futures ===")
summ = data['analysis']['summary_table']['oi']['Index Futures']
for p in ['Client', 'DII', 'FII', 'Pro', 'TOTAL']:
    s = summ[p]
    print(f"  {p}: net_action={s['net_action']}, sentiment={s['sentiment']}")

print("\n=== ACTIVITY TABLE (OI) - All Participants ===")
for p in ['Client', 'DII', 'FII', 'Pro']:
    print(f"  --- {p} ---")
    act = data['analysis']['activity_table']['oi'][p]
    for inst, v in act.items():
        print(f"    {inst}: {v['action']} {v['net_qty']:+,} ({v['sentiment']})")

print("\n=== RAW CSV DATA CHECK ===")
print(f"  OI dates: {list(data['raw_csv_data']['oi_files'].keys())}")
print(f"  Vol dates: {list(data['raw_csv_data']['volume_files'].keys())}")
print(f"  Market dates: {list(data['raw_csv_data']['market_files'].keys())}")

# Cross-verify one value with CSV
oi_06 = data['raw_csv_data']['oi_files']['06-07-2026']
fii_raw = [r for r in oi_06 if r['Client_Type'] == 'FII'][0]
fii_structured = data['participant_oi']['FII']['06-07-2026']
print(f"\n=== CROSS-VERIFY: FII OI on 06-07-2026 ===")
print(f"  Raw CSV:    Future_Index_Long = {fii_raw['Future_Index_Long']}")
print(f"  Structured: Future_Index_Long = {fii_structured['Future_Index_Long']}")
assert fii_raw['Future_Index_Long'] == fii_structured['Future_Index_Long'], "MISMATCH!"
print("  [OK] Values match!")

print("\n=== ALL VALIDATIONS PASSED ===")
