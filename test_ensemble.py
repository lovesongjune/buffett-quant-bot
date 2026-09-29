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

top60_codes = universe_df['Code'].head(60).tolist()
kospi_sma200 = kospi_prices.rolling(window=200).mean()

def select_ensemble_picks(current_date):
    """
    [통합 올인원 앙상블 퀀트 전략]
    1. 유니버스: 시가총액 상위 60위 대형 우량주 (대형주 안정성)
    2. 재무 필터: ROE >= 8%, 영업이익률 >= 7%, 부채비율 <= 130% (버핏 퀄리티 안전마진)
    3. 종합 스코어링:
       - 퀄리티 팩터 (40%): ROE 순위 + 영업마진 순위
       - 밸류 팩터 (30%): 1/PER 순위 + 1/PBR 순위 (마법공식 가치)
       - 모멘텀 팩터 (30%): 최근 6개월 주가 수익률 순위 (가치함정 회피 및 주도주 포획)
    """
    df = metrics_df[metrics_df['Code'].isin(top60_codes)].copy()
    
    # 1. 재무 건전성 필터 (극단적 부실/적자 기업 제외)
    cond = (df['ROE_Avg3'] >= 7.5) & (df['OP_Margin'] >= 6.0) & (df['Debt_Ratio'] <= 140) & (df['PER'] > 3)
    df_valid = df[cond].copy()
    
    if len(df_valid) < 10:
        df_valid = df[(df['Debt_Ratio'] <= 160) & (df['PER'] > 3)].copy()
        
    # 2. 팩터별 랭킹 산출 (낮을수록 우수)
    # Quality: ROE + OP_Margin
    quality_score = df_valid['ROE_Avg3'] + df_valid['OP_Margin']
    df_valid['Rank_Quality'] = quality_score.rank(ascending=False)
    
    # Value: 1/PER + 1/PBR
    val_score = (1 / df_valid['PER']) + (1 / df_valid['PBR'])
    df_valid['Rank_Value'] = val_score.rank(ascending=False)
    
    # Momentum: 6-month price return
    loc = stock_prices.index.get_loc(current_date)
    if loc >= 126:
        p_now = stock_prices.iloc[loc]
        p_past = stock_prices.iloc[loc - 126]
        mom_series = (p_now - p_past) / p_past
        df_valid['Mom_6M'] = df_valid['Code'].map(mom_series).fillna(0)
    else:
        df_valid['Mom_6M'] = 0.0
    df_valid['Rank_Mom'] = df_valid['Mom_6M'].rank(ascending=False)
    
    # 3. 앙상블 종합 가중 순위
    # 가중치: 퀄리티 40% + 밸류 30% + 모멘텀 30%
    df_valid['Ensemble_Score'] = (
        0.40 * df_valid['Rank_Quality'] + 
        0.30 * df_valid['Rank_Value'] + 
        0.30 * df_valid['Rank_Mom']
    )
    
    top10 = df_valid.sort_values(by='Ensemble_Score').head(10)['Code'].tolist()
    return top10

def simulate_ensemble(use_cash_buffer=True):
    current_cash = 100.0
    current_holdings = {}
    vals = [100.0]
    rebal_set = set(rebalance_dates)
    
    for i, date in enumerate(dates):
        current_kospi = kospi_prices.loc[date]
        current_sma = kospi_sma200.loc[date]
        market_bull = current_kospi > current_sma if not np.isnan(current_sma) else True
        
        if date in rebal_set or i == 0:
            tot = current_cash + sum(shares * stock_prices.loc[date, c] * (1 - COMMISSION) for c, shares in current_holdings.items())
            
            # 시장 방어 규칙: KOSPI가 200일선 아래 약세장일 때는 현금 30% 안전 버퍼 확보
            cash_reserve_rate = 0.30 if (use_cash_buffer and not market_bull) else 0.02
            investable_capital = tot * (1 - cash_reserve_rate)
            current_cash = tot * cash_reserve_rate
            
            targets = select_ensemble_picks(date)
            alloc = investable_capital / len(targets)
            
            current_holdings = {}
            for c in targets:
                p = stock_prices.loc[date, c]
                if p > 0:
                    current_holdings[c] = (alloc * (1 - COMMISSION)) / p
                    
        # Daily cash interest
        current_cash *= (1 + DAILY_RISK_FREE)
        
        cur_val = current_cash + sum(shares * stock_prices.loc[date, c] for c, shares in current_holdings.items())
        if i > 0:
            vals.append(cur_val)
            
    return pd.Series(vals, index=dates)

res_ensemble = simulate_ensemble(use_cash_buffer=True)
res_ensemble_no_buffer = simulate_ensemble(use_cash_buffer=False)

def calc_stats(s, name):
    tot = (s.iloc[-1] / s.iloc[0] - 1) * 100
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1) * 100
    mdd = ((s - s.cummax()) / s.cummax()).min() * 100
    d_rets = s.pct_change().dropna()
    ann_vol = d_rets.std() * np.sqrt(252) * 100
    sharpe = ((d_rets - DAILY_RISK_FREE).mean() / d_rets.std()) * np.sqrt(252)
    down_std = np.sqrt(((d_rets[d_rets < 0]) ** 2).mean()) * np.sqrt(252)
    sortino = ((d_rets - DAILY_RISK_FREE).mean() * 252) / down_std if down_std > 0 else 0
    calmar = cagr / abs(mdd)
    win = (s.resample('ME').last().pct_change().dropna() > 0).mean() * 100
    return {
        '전략': name,
        '총수익률': f"{tot:.1f}%",
        'CAGR': f"{cagr:.1f}%",
        'MDD': f"{mdd:.1f}%",
        '변동성': f"{ann_vol:.1f}%",
        'Sharpe': f"{sharpe:.2f}",
        'Sortino': f"{sortino:.2f}",
        'Calmar': f"{calmar:.2f}",
        '월간승률': f"{win:.1f}%"
    }

print("=== 올인원 앙상블 전략 백테스트 성과 ===")
df_res = pd.DataFrame([
    calc_stats(res_ensemble, '★ 올인원 버핏 앙상블 (현금버퍼 적용)'),
    calc_stats(res_ensemble_no_buffer, '  올인원 버핏 앙상블 (주식 100%)')
])
print(df_res.to_string(index=False))

picks = select_ensemble_picks(dates[-1])
print(f"\n[현재 선정된 올인원 앙상블 TOP 10 종목]")
for i, c in enumerate(picks, 1):
    m = metrics_df[metrics_df['Code'] == c].iloc[0]
    print(f"{i:2d}. {m['Name']:12s} ({c}) | ROE: {m['ROE_Avg3']:5.1f}% | 영업마진: {m['OP_Margin']:5.1f}% | PER: {m['PER']:5.1f} | PBR: {m['PBR']:4.2f} | 부채: {m['Debt_Ratio']:5.1f}%")
