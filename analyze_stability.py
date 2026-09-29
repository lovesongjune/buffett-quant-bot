import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load data
prices_df = pd.read_csv('d:/lsj/antigravity/data/prices_top100.csv', index_col=0, parse_dates=True).dropna(subset=['KOSPI'])
universe_df = pd.read_csv('d:/lsj/antigravity/data/universe_top100.csv', dtype={'Code': str})
metrics_df = pd.read_csv('d:/lsj/antigravity/data/parsed_metrics.csv', dtype={'Code': str})

stock_prices = prices_df.drop(columns=['KOSPI']).ffill().bfill()
kospi_prices = prices_df['KOSPI'].ffill().bfill()

COMMISSION = 0.002
ANNUAL_RISK_FREE = 0.03
DAILY_RISK_FREE = (1 + ANNUAL_RISK_FREE) ** (1/252) - 1
start_idx = 200
dates = prices_df.index[start_idx:]
rebalance_dates = sorted(list(set([prices_df.index[prices_df.index.get_indexer([d], method='nearest')[0]] 
                                   for d in prices_df.resample('QE').last().index if d >= dates[0]])))

top50_codes = universe_df['Code'].head(50).tolist()

def get_picks(strat):
    df = metrics_df.copy()
    if strat == 'top20':
        return universe_df['Code'].head(20).tolist()
    elif strat == 'magic':
        df_val = df[(df['Debt_Ratio'] <= 150) & (df['PER'] > 3)].copy()
        df_val['ROC_Rank'] = (df_val['ROE_Avg3'] + df_val['OP_Margin']).rank(ascending=False)
        df_val['EY_Rank'] = (1 / df_val['PER']).rank(ascending=False)
        df_val['Magic_Rank'] = df_val['ROC_Rank'] + df_val['EY_Rank']
        return df_val.sort_values(by='Magic_Rank').head(15)['Code'].tolist()
    elif strat == 'strict_buffett':
        cond = (df['Code'].isin(top50_codes)) & (df['ROE_Avg3'] >= 8) & (df['OP_Margin'] >= 7) & (df['Debt_Ratio'] <= 120) & (df['PER'] >= 4) & (df['PER'] <= 25) & (df['PBR'] <= 3.5)
        df_val = df[cond].copy()
        if len(df_val) < 8:
            cond_rel = (df['Code'].isin(top50_codes)) & (df['ROE_Avg3'] >= 7) & (df['Debt_Ratio'] <= 140) & (df['PER'] <= 30)
            df_val = df[cond_rel].copy()
        df_val['Score'] = df_val['ROE_Avg3'] / (df_val['PBR'] + 0.1)
        return df_val.sort_values(by='Score', ascending=False).head(10)['Code'].tolist()
    elif strat == 'buffett_large_quant':
        df_val = df[(df['Code'].isin(top50_codes)) & (df['Debt_Ratio'] <= 150) & (df['PER'] > 3)].copy()
        df_val['ROC_Rank'] = (df_val['ROE_Avg3'] + df_val['OP_Margin']).rank(ascending=False)
        df_val['EY_Rank'] = (1 / df_val['PER']).rank(ascending=False)
        df_val['Magic_Rank'] = df_val['ROC_Rank'] + df_val['EY_Rank']
        return df_val.sort_values(by='Magic_Rank').head(10)['Code'].tolist()

def simulate(strat):
    if strat == 'kospi':
        return (kospi_prices.loc[dates] / kospi_prices.loc[dates[0]]) * 100
    
    current_cash = 100.0
    current_holdings = {}
    vals = [100.0]
    rebal_set = set(rebalance_dates)
    
    for i, date in enumerate(dates):
        if date in rebal_set or i == 0:
            tot = current_cash + sum(shares * stock_prices.loc[date, c] * (1 - COMMISSION) for c, shares in current_holdings.items())
            targets = get_picks(strat)
            alloc = (tot * 0.999) / len(targets)
            current_holdings = {c: (alloc * (1 - COMMISSION)) / stock_prices.loc[date, c] for c in targets if stock_prices.loc[date, c] > 0}
            current_cash = 0.0
            
        cur_val = current_cash + sum(shares * stock_prices.loc[date, c] for c, shares in current_holdings.items())
        if i > 0:
            vals.append(cur_val)
    return pd.Series(vals, index=dates)

series_dict = {
    '1. KOSPI 벤치마크': simulate('kospi'),
    '2. 시가총액 TOP 20': simulate('top20'),
    '3. 조엘 마법공식': simulate('magic'),
    '4. 정통 버핏 가치주': simulate('strict_buffett'),
    '5. 버핏 대형 우량주 퀀트 (최우수)': simulate('buffett_large_quant')
}

# 1. Yearly Returns Table
yearly_data = {}
for name, s in series_dict.items():
    y_res = s.resample('YE').last().pct_change() * 100
    # Also calculate the first period return (2020 end vs 2020 start)
    first_y = (s.loc['2020'].iloc[-1] / s.iloc[0] - 1) * 100
    y_res.loc[pd.Timestamp('2020-12-31')] = first_y
    y_res = y_res.sort_index()
    # Format
    y_dict = {d.strftime('%Y'): f"{v:+.1f}%" for d, v in y_res.items()}
    yearly_data[name] = y_dict

df_yearly = pd.DataFrame(yearly_data).T
print("=== 연도별 수익률 현황 (상세) ===")
print(df_yearly.to_string())

# 2. Advanced Stability Metrics
stability_rows = []
for name, s in series_dict.items():
    total_ret = (s.iloc[-1] / s.iloc[0] - 1) * 100
    years = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) * 100
    
    # Drawdowns
    cummax = s.cummax()
    drawdown = (s - cummax) / cummax
    mdd = drawdown.min() * 100
    
    # Volatility
    daily_rets = s.pct_change().dropna()
    ann_vol = daily_rets.std() * np.sqrt(252) * 100
    
    # Sharpe Ratio
    excess_rets = daily_rets - DAILY_RISK_FREE
    sharpe = (excess_rets.mean() / excess_rets.std()) * np.sqrt(252)
    
    # Sortino Ratio (Downside deviation only)
    downside_rets = daily_rets[daily_rets < 0]
    downside_std = np.sqrt((downside_rets ** 2).mean()) * np.sqrt(252)
    sortino = (excess_rets.mean() * 252) / downside_std if downside_std > 0 else 0
    
    # Calmar Ratio (CAGR / |MDD|)
    calmar = cagr / abs(mdd)
    
    # Monthly Win Rate & Worst Month
    monthly_rets = s.resample('ME').last().pct_change().dropna() * 100
    monthly_win = (monthly_rets > 0).mean() * 100
    worst_month = monthly_rets.min()
    best_month = monthly_rets.max()
    
    # Underwater duration (Max recovery days)
    is_underwater = drawdown < -0.01
    underwater_durations = []
    cur_dur = 0
    for uw in is_underwater:
        if uw:
            cur_dur += 1
        else:
            if cur_dur > 0:
                underwater_durations.append(cur_dur)
            cur_dur = 0
    if cur_dur > 0:
        underwater_durations.append(cur_dur)
    max_recovery_days = max(underwater_durations) if underwater_durations else 0
    
    stability_rows.append({
        '전략': name,
        'CAGR': f"{cagr:.1f}%",
        'MDD(최대낙폭)': f"{mdd:.1f}%",
        '연환산 변동성': f"{ann_vol:.1f}%",
        'Sharpe (위험대비)': f"{sharpe:.2f}",
        'Sortino (하방위험)': f"{sortino:.2f}",
        'Calmar (낙폭대비)': f"{calmar:.2f}",
        '월간 승률': f"{monthly_win:.1f}%",
        '최악의 한달': f"{worst_month:.1f}%",
        '최대 회복소요(영업일)': f"{max_recovery_days}일"
    })

df_stability = pd.DataFrame(stability_rows)
print("\n=== 정밀 안정성 및 리스크 지표 비교 ===")
print(df_stability.to_string(index=False))
