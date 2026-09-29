import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load data
prices_df = pd.read_csv('d:/lsj/antigravity/data/prices_top100.csv', index_col=0, parse_dates=True)
prices_df = prices_df.dropna(subset=['KOSPI'])
universe_df = pd.read_csv('d:/lsj/antigravity/data/universe_top100.csv', dtype={'Code': str})
metrics_df = pd.read_csv('d:/lsj/antigravity/data/parsed_metrics.csv', dtype={'Code': str})
name_map = dict(zip(universe_df['Code'], universe_df['Name']))

stock_prices = prices_df.drop(columns=['KOSPI']).ffill().bfill()
kospi_prices = prices_df['KOSPI'].ffill().bfill()

COMMISSION = 0.002
ANNUAL_RISK_FREE = 0.03
DAILY_RISK_FREE = (1 + ANNUAL_RISK_FREE) ** (1/252) - 1

start_idx = 200
start_date = prices_df.index[start_idx]
dates = prices_df.index[start_idx:]

resampled = prices_df.resample('QE').last()
rebalance_dates = [prices_df.index[prices_df.index.get_indexer([d], method='nearest')[0]] for d in resampled.index]
rebalance_dates = sorted(list(set([d for d in rebalance_dates if d >= start_date])))

top50_codes = universe_df['Code'].head(50).tolist()

def select_hybrid_picks():
    # Large Cap 50 Universe + Buffett-Magic Formula (ROE + 1/PER)
    df = metrics_df[metrics_df['Code'].isin(top50_codes)].copy()
    # Financial health: Debt_Ratio <= 150, PER > 3
    df = df[(df['Debt_Ratio'] <= 150) & (df['PER'] > 3)].copy()
    df['ROC_Rank'] = (df['ROE_Avg3'] + df['OP_Margin']).rank(ascending=False)
    df['EY_Rank'] = (1 / df['PER']).rank(ascending=False)
    df['Magic_Rank'] = df['ROC_Rank'] + df['EY_Rank']
    top10 = df.sort_values(by='Magic_Rank').head(10)['Code'].tolist()
    return top10

def simulate_hybrid(use_rebalance=True):
    current_cash = 100.0
    current_holdings = {}
    portfolio_value = [100.0]
    
    rebal_set = set(rebalance_dates)
    
    for i, date in enumerate(dates):
        if (date in rebal_set and use_rebalance) or i == 0:
            tot_val = current_cash
            for c, shares in current_holdings.items():
                p = stock_prices.loc[date, c]
                tot_val += shares * p * (1 - COMMISSION)
            
            targets = select_hybrid_picks()
            alloc_per_stock = (tot_val * 0.999) / len(targets)
            current_holdings = {}
            for c in targets:
                p = stock_prices.loc[date, c]
                shares = (alloc_per_stock * (1 - COMMISSION)) / p
                current_holdings[c] = shares
            current_cash = 0.0
            
        day_stock_val = sum(shares * stock_prices.loc[date, c] for c, shares in current_holdings.items())
        total_day_val = day_stock_val + current_cash
        if i > 0:
            portfolio_value.append(total_day_val)
            
    return pd.Series(portfolio_value, index=dates)

res_hybrid = simulate_hybrid(use_rebalance=True)

# Performance calculation
def calc_metrics(s, name):
    total_ret = (s.iloc[-1] / s.iloc[0] - 1) * 100
    years = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) * 100
    drawdown = (s - s.cummax()) / s.cummax()
    mdd = drawdown.min() * 100
    daily_rets = s.pct_change().dropna()
    excess_rets = daily_rets - DAILY_RISK_FREE
    sharpe = (excess_rets.mean() / excess_rets.std()) * np.sqrt(252) if excess_rets.std() > 0 else 0
    monthly_rets = s.resample('ME').last().pct_change().dropna()
    win_rate = (monthly_rets > 0).mean() * 100
    return {
        '전략': name,
        '총수익률(%)': f"{total_ret:.1f}%",
        'CAGR(연평균%)': f"{cagr:.1f}%",
        'MDD(최대낙폭%)': f"{mdd:.1f}%",
        'Sharpe Ratio': f"{sharpe:.2f}",
        '월간 승률(%)': f"{win_rate:.1f}%"
    }

print("=== 하이브리드 버핏 퀀트 (시총 50 대형주 + 마법공식 TOP 10) ===")
print(pd.DataFrame([calc_metrics(res_hybrid, '버핏 대형 우량주 퀀트 (TOP 10)')]).to_string(index=False))

picks = select_hybrid_picks()
print("\n[현재 편입 종목 10개]")
for i, c in enumerate(picks, 1):
    m = metrics_df[metrics_df['Code'] == c].iloc[0]
    print(f"{i:2d}. {m['Name']:12s} ({c}) - ROE(3년평균): {m['ROE_Avg3']:5.1f}%, 영업이익률: {m['OP_Margin']:5.1f}%, PER: {m['PER']:5.1f}, PBR: {m['PBR']:4.2f}, 부채비율: {m['Debt_Ratio']:5.1f}%")
