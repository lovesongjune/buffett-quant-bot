import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load data
prices_df = pd.read_csv('d:/lsj/antigravity/data/prices_top100.csv', index_col=0, parse_dates=True)
prices_df = prices_df.dropna(subset=['KOSPI']) # align to KOSPI valid dates
universe_df = pd.read_csv('d:/lsj/antigravity/data/universe_top100.csv', dtype={'Code': str})
metrics_df = pd.read_csv('d:/lsj/antigravity/data/parsed_metrics.csv', dtype={'Code': str})
name_map = dict(zip(universe_df['Code'], universe_df['Name']))

print(f"Data range: {prices_df.index[0].strftime('%Y-%m-%d')} ~ {prices_df.index[-1].strftime('%Y-%m-%d')} ({len(prices_df)} trading days)")

# Fill missing prices with forward fill then backward fill
stock_prices = prices_df.drop(columns=['KOSPI']).ffill().bfill()
kospi_prices = prices_df['KOSPI'].ffill().bfill()

# Transaction cost: 0.20% (tax 0.18% + commission/slippage 0.02%)
COMMISSION = 0.002
ANNUAL_RISK_FREE = 0.03 # 3% cash rate
DAILY_RISK_FREE = (1 + ANNUAL_RISK_FREE) ** (1/252) - 1

# KOSPI 200-day moving average for market timing
kospi_sma200 = kospi_prices.rolling(window=200).mean()

# Identify rebalance dates (last trading day of each quarter)
# Using resample('QE') or quarterly month ends
resampled = prices_df.resample('QE').last()
rebalance_dates = [prices_df.index[prices_df.index.get_indexer([d], method='nearest')[0]] for d in resampled.index]
rebalance_dates = sorted(list(set(rebalance_dates)))
# Start after 200 trading days so SMA200 is available
start_idx = 200
start_date = prices_df.index[start_idx]
rebalance_dates = [d for d in rebalance_dates if d >= start_date]

print(f"Backtest starts from {start_date.strftime('%Y-%m-%d')}. Total rebalance events: {len(rebalance_dates)}")

# Helper to filter metrics
def select_stocks(strategy, current_date, available_codes):
    df = metrics_df[metrics_df['Code'].isin(available_codes)].copy()
    
    if strategy == 'TOP20_CAP':
        # Top 20 by market cap
        return universe_df[universe_df['Code'].isin(available_codes)]['Code'].head(20).tolist()
    
    elif strategy == 'BUFFETT_QUALITY_VALUE':
        # Buffett Criteria:
        # ROE_Avg3 >= 10, OP_Margin >= 8, Debt_Ratio <= 120, PER between 4 and 35, PBR <= 3.5
        cond = (
            (df['ROE_Avg3'] >= 10) & 
            (df['OP_Margin'] >= 8) & 
            (df['Debt_Ratio'] <= 120) & 
            (df['PER'] >= 4) & (df['PER'] <= 35) & 
            (df['PBR'] <= 3.5)
        )
        candidates = df[cond].copy()
        if len(candidates) < 5:
            # Relax conditions if too few
            cond = (df['ROE_Avg3'] >= 8) & (df['Debt_Ratio'] <= 150) & (df['PER'] <= 40)
            candidates = df[cond].copy()
        # Rank by ROE / PBR (Quality relative to price)
        candidates['Score'] = candidates['ROE_Avg3'] / (candidates['PBR'] + 0.1)
        selected = candidates.sort_values(by='Score', ascending=False)['Code'].head(15).tolist()
        return selected

    elif strategy == 'MAGIC_FORMULA':
        # Magic Formula: Earnings Yield Rank + ROC Rank
        # Proxy: ROC -> OP_Margin & ROE_Avg3, EY -> 1 / PER
        df_valid = df[(df['Debt_Ratio'] <= 150) & (df['PER'] > 3)].copy()
        df_valid['ROC_Rank'] = (df_valid['ROE_Avg3'] + df_valid['OP_Margin']).rank(ascending=False)
        df_valid['EY_Rank'] = (1 / df_valid['PER']).rank(ascending=False)
        df_valid['Magic_Rank'] = df_valid['ROC_Rank'] + df_valid['EY_Rank']
        selected = df_valid.sort_values(by='Magic_Rank')['Code'].head(15).tolist()
        return selected

    elif strategy == 'BUFFETT_MOMENTUM':
        # Buffett Quality + 6-month Relative Momentum
        cond = (df['ROE_Avg3'] >= 8) & (df['OP_Margin'] >= 6) & (df['Debt_Ratio'] <= 150)
        candidates = df[cond].copy()
        # Calculate 6-month momentum (126 trading days)
        loc = stock_prices.index.get_loc(current_date)
        if loc >= 126:
            p_now = stock_prices.iloc[loc]
            p_past = stock_prices.iloc[loc - 126]
            mom = (p_now - p_past) / p_past
            candidates['Momentum'] = candidates['Code'].map(mom)
            selected = candidates.dropna(subset=['Momentum']).sort_values(by='Momentum', ascending=False)['Code'].head(12).tolist()
            return selected
        return candidates['Code'].head(12).tolist()

    return []

# Simulation Function
def simulate_strategy(strategy_name, use_market_filter=False):
    dates = prices_df.index[start_idx:]
    portfolio_value = [100.0] # start with 100
    
    current_cash = 100.0
    current_holdings = {} # code: shares
    
    rebal_set = set(rebalance_dates)
    
    for i, date in enumerate(dates):
        current_kospi = kospi_prices.loc[date]
        current_sma = kospi_sma200.loc[date]
        market_bull = current_kospi > current_sma if not np.isnan(current_sma) else True
        
        # Check if rebalance day
        if date in rebal_set or i == 0:
            # 1. Liquidate current holdings
            tot_value = current_cash
            for code, shares in current_holdings.items():
                p = stock_prices.loc[date, code]
                tot_value += shares * p * (1 - COMMISSION)
            
            current_holdings = {}
            current_cash = tot_value
            
            # 2. Market timing check
            if use_market_filter and not market_bull:
                # Bear market: Stay in 100% Cash
                pass
            else:
                # Bull market or no filter: Buy target portfolio
                available_codes = [c for c in stock_prices.columns if not np.isnan(stock_prices.loc[date, c])]
                targets = select_stocks(strategy_name, date, available_codes)
                
                if targets:
                    alloc_per_stock = (current_cash * 0.999) / len(targets)
                    for code in targets:
                        p = stock_prices.loc[date, code]
                        if p > 0:
                            shares = (alloc_per_stock * (1 - COMMISSION)) / p
                            current_holdings[code] = shares
                    current_cash = 0.0 # fully invested
        
        # Daily market timing exit check (if market breaks below 200 SMA mid-quarter)
        elif use_market_filter and not market_bull and len(current_holdings) > 0:
            # Emergency exit to cash on trend breakdown
            tot_value = current_cash
            for code, shares in current_holdings.items():
                p = stock_prices.loc[date, code]
                tot_value += shares * p * (1 - COMMISSION)
            current_holdings = {}
            current_cash = tot_value

        # Calculate daily valuation
        day_stock_val = 0.0
        for code, shares in current_holdings.items():
            p = stock_prices.loc[date, code]
            day_stock_val += shares * p
            
        # Add risk-free interest to cash component
        current_cash *= (1 + DAILY_RISK_FREE)
        
        total_day_val = day_stock_val + current_cash
        if i > 0:
            portfolio_value.append(total_day_val)
            
    return pd.Series(portfolio_value, index=dates)

# Run simulations
print("\nRunning Backtest Simulations...")

# 1. Benchmark: KOSPI
kospi_bench = (kospi_prices.loc[start_date:] / kospi_prices.loc[start_date]) * 100

# 2. KOSPI Top 20 Market Cap
res_top20 = simulate_strategy('TOP20_CAP', use_market_filter=False)

# 3. Magic Formula
res_magic = simulate_strategy('MAGIC_FORMULA', use_market_filter=False)

# 4. Pure Buffett Quality-Value
res_buffett = simulate_strategy('BUFFETT_QUALITY_VALUE', use_market_filter=False)

# 5. Buffett Quality-Value + 200 SMA Market Timing Filter (Recommended ⭐)
res_buffett_trend = simulate_strategy('BUFFETT_QUALITY_VALUE', use_market_filter=True)

# 6. Buffett Quality + Momentum Hybrid + Market Filter
res_buffett_mom_trend = simulate_strategy('BUFFETT_MOMENTUM', use_market_filter=True)

results = {
    '1. KOSPI 벤치마크': kospi_bench,
    '2. 시가총액 TOP 20': res_top20,
    '3. 조엘 그린블랫 마법공식': res_magic,
    '4. 순수 버핏 퀄리티가치': res_buffett,
    '5. 버핏 퀄리티 + 추세필터 (추천 ⭐)': res_buffett_trend,
    '6. 버핏+모멘텀+추세필터': res_buffett_mom_trend
}

# Performance Metrics Evaluation
summary_rows = []
for name, s in results.items():
    s = s.dropna()
    total_ret = (s.iloc[-1] / s.iloc[0] - 1) * 100
    years = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) * 100
    
    # Max Drawdown (MDD)
    cummax = s.cummax()
    drawdown = (s - cummax) / cummax
    mdd = drawdown.min() * 100
    
    # Sharpe Ratio
    daily_rets = s.pct_change().dropna()
    excess_rets = daily_rets - DAILY_RISK_FREE
    sharpe = (excess_rets.mean() / excess_rets.std()) * np.sqrt(252) if excess_rets.std() > 0 else 0
    
    # Win rate (annual or monthly)
    monthly_rets = s.resample('ME').last().pct_change().dropna()
    win_rate = (monthly_rets > 0).mean() * 100
    
    summary_rows.append({
        '전략': name,
        '총수익률(%)': f"{total_ret:.1f}%",
        'CAGR(연평균%)': f"{cagr:.1f}%",
        'MDD(최대낙폭%)': f"{mdd:.1f}%",
        'Sharpe Ratio': f"{sharpe:.2f}",
        '월간 승률(%)': f"{win_rate:.1f}%"
    })

summary_df = pd.DataFrame(summary_rows)
print("\n" + "="*80)
print("=== 2020~2026 백테스트 성과 분석 종합 비교표 ===")
print("="*80)
print(summary_df.to_string(index=False))
print("="*80)

# Save results to CSV
summary_df.to_csv('d:/lsj/antigravity/data/backtest_summary.csv', index=False, encoding='utf-8-sig')

# Plotting Equity Curves
plt.figure(figsize=(14, 8))
plt.rcParams['font.family'] = 'DejaVu Sans' # fallback
plt.plot(kospi_bench, label='1. KOSPI Benchmark', color='gray', linestyle='--', alpha=0.7)
plt.plot(res_top20, label='2. KOSPI Top 20 Cap', color='orange', alpha=0.7)
plt.plot(res_magic, label='3. Magic Formula', color='purple', alpha=0.8)
plt.plot(res_buffett, label='4. Pure Buffett Quality-Value', color='blue', alpha=0.8)
plt.plot(res_buffett_trend, label='5. Buffett + Trend Filter (Best)', color='red', linewidth=2.5)
plt.plot(res_buffett_mom_trend, label='6. Buffett + Momentum + Trend', color='green', linewidth=1.8)

plt.title('Backtest Comparison: Buffett & Quant Strategies (2020 - 2026)', fontsize=15, pad=15)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Portfolio Equity (Base = 100)', fontsize=12)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(loc='upper left', fontsize=11)
plt.tight_layout()

chart_path = 'd:/lsj/antigravity/data/backtest_chart.png'
plt.savefig(chart_path, dpi=200)
print(f"\nEquity curve chart saved to: {chart_path}")
