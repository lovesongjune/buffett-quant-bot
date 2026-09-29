import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

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

def select_strict_buffett_picks():
    df = metrics_df[metrics_df['Code'].isin(top50_codes)].copy()
    # Strict Buffett Value + Quality constraints:
    # 1. ROE >= 8%
    # 2. Operating margin >= 7%
    # 3. Debt ratio <= 120%
    # 4. PER <= 25 (안전마진 - 고평가 제외)
    # 5. PBR <= 3.5 (순자산 대비 과도한 프리미엄 제외)
    cond = (
        (df['ROE_Avg3'] >= 8) & 
        (df['OP_Margin'] >= 7) & 
        (df['Debt_Ratio'] <= 120) & 
        (df['PER'] >= 4) & (df['PER'] <= 25) & 
        (df['PBR'] <= 3.5)
    )
    df_val = df[cond].copy()
    if len(df_val) < 8:
        cond_relaxed = (df['ROE_Avg3'] >= 7) & (df['Debt_Ratio'] <= 140) & (df['PER'] <= 30)
        df_val = df[cond_relaxed].copy()
    # Rank by Quality / Price ratio: ROE / (PBR + 0.1)
    df_val['Score'] = df_val['ROE_Avg3'] / (df_val['PBR'] + 0.1)
    picks = df_val.sort_values(by='Score', ascending=False).head(10)['Code'].tolist()
    return picks

def simulate(picks_func):
    current_cash = 100.0
    current_holdings = {}
    vals = [100.0]
    rebal_set = set(rebalance_dates)
    
    for i, date in enumerate(dates):
        if date in rebal_set or i == 0:
            tot = current_cash + sum(shares * stock_prices.loc[date, c] * (1 - COMMISSION) for c, shares in current_holdings.items())
            targets = picks_func()
            alloc = (tot * 0.999) / len(targets)
            current_holdings = {c: (alloc * (1 - COMMISSION)) / stock_prices.loc[date, c] for c in targets if stock_prices.loc[date, c] > 0}
            current_cash = 0.0
            
        cur_val = current_cash + sum(shares * stock_prices.loc[date, c] for c, shares in current_holdings.items())
        if i > 0:
            vals.append(cur_val)
    return pd.Series(vals, index=dates)

res_strict = simulate(select_strict_buffett_picks)

def calc_stats(s, name):
    tot = (s.iloc[-1] / s.iloc[0] - 1) * 100
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1) * 100
    mdd = ((s - s.cummax()) / s.cummax()).min() * 100
    d_rets = s.pct_change().dropna()
    sharpe = ((d_rets - DAILY_RISK_FREE).mean() / d_rets.std()) * np.sqrt(252)
    win = (s.resample('ME').last().pct_change().dropna() > 0).mean() * 100
    return {'전략': name, '총수익률(%)': f"{tot:.1f}%", 'CAGR(연평균%)': f"{cagr:.1f}%", 'MDD(최대낙폭%)': f"{mdd:.1f}%", 'Sharpe': f"{sharpe:.2f}", '월간승률(%)': f"{win:.1f}%"}

print(pd.DataFrame([calc_stats(res_strict, '엄격한 버핏 퀄리티-가치 10선')]).to_string(index=False))

picks = select_strict_buffett_picks()
print("\n[엄격한 버핏 포트폴리오 10개 종목]")
for i, c in enumerate(picks, 1):
    m = metrics_df[metrics_df['Code'] == c].iloc[0]
    print(f"{i:2d}. {m['Name']:12s} ({c}) - ROE(3년): {m['ROE_Avg3']:5.1f}%, 영업이익률: {m['OP_Margin']:5.1f}%, PER: {m['PER']:5.1f}, PBR: {m['PBR']:4.2f}, 부채비율: {m['Debt_Ratio']:5.1f}%")
