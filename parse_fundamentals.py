import json
import pandas as pd
import numpy as np

with open('d:/lsj/antigravity/data/fundamentals_top100.json', 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

universe = pd.read_csv('d:/lsj/antigravity/data/universe_top100.csv', dtype={'Code': str})
name_map = dict(zip(universe['Code'], universe['Name']))

records = []
for code, data in raw_data.items():
    if not data or 'financeInfo' not in data:
        continue
    finfo = data['financeInfo']
    tr_list = finfo.get('trTitleList', [])
    # Get actual periods (excluding consensus if possible, or taking latest reported)
    actual_periods = [p for p in tr_list if p.get('isConsensus') == 'N']
    if not actual_periods:
        actual_periods = tr_list
    
    # Map rows
    row_map = {}
    for r in finfo.get('rowList', []):
        row_map[r['title']] = r['columns']
    
    def get_val(title, period_idx=-1):
        if title not in row_map or not actual_periods:
            return np.nan
        key = actual_periods[period_idx]['key']
        val_str = row_map[title].get(key, {}).get('value', '-')
        if val_str in ['-', '', 'N/A', None]:
            return np.nan
        try:
            return float(val_str.replace(',', ''))
        except:
            return np.nan

    def get_avg(title, count=3):
        vals = []
        for i in range(-min(len(actual_periods), count), 0):
            v = get_val(title, i)
            if not np.isnan(v):
                vals.append(v)
        return np.mean(vals) if vals else np.nan

    roe_latest = get_val('ROE', -1)
    roe_avg3 = get_avg('ROE', 3)
    op_margin_latest = get_val('영업이익률', -1)
    debt_ratio = get_val('부채비율', -1)
    per = get_val('PER', -1)
    pbr = get_val('PBR', -1)
    quick_ratio = get_val('당좌비율', -1)

    records.append({
        'Code': code,
        'Name': name_map.get(code, code),
        'ROE_Latest': roe_latest,
        'ROE_Avg3': roe_avg3,
        'OP_Margin': op_margin_latest,
        'Debt_Ratio': debt_ratio,
        'PER': per,
        'PBR': pbr,
        'Quick_Ratio': quick_ratio
    })

df_metrics = pd.DataFrame(records)
df_metrics.to_csv('d:/lsj/antigravity/data/parsed_metrics.csv', index=False, encoding='utf-8-sig')
print("Parsed metrics shape:", df_metrics.shape)
print("\nTop 10 highest ROE (3-yr avg) stocks:")
print(df_metrics.sort_values(by='ROE_Avg3', ascending=False)[['Code', 'Name', 'ROE_Avg3', 'OP_Margin', 'Debt_Ratio', 'PER', 'PBR']].head(10))
