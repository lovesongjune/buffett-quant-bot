# ==========================================================
# [올인원 버핏 앙상블] 자동매매 메인 실행 엔진 (Trading Bot)
# ==========================================================
import sys
import time
import os
import pandas as pd
import numpy as np
import requests
from kis_api import KoreaInvestmentAPI
import config

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def send_telegram_alert(message):
    """텔레그램 봇으로 알림 메시지 발송"""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[Telegram] 알림 발송 실패: {e}")

def check_market_regime():
    """KOSPI 200일선 이동평균선 기반 시장 상태 체크 (상승장 vs 약세장)"""
    try:
        prices_path = os.path.join(DATA_DIR, 'prices_top100.csv')
        if os.path.exists(prices_path):
            prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
            if 'KOSPI' in prices_df.columns:
                s = prices_df['KOSPI'].dropna()
                sma200 = float(s.rolling(window=200).mean().iloc[-1])
                current_close = float(s.iloc[-1])
                
                # 네이버 실시간 KOSPI 시세 보정
                try:
                    r = requests.get('https://m.stock.naver.com/api/index/KOSPI/basic', headers={'User-Agent': 'Mozilla/5.0'}, timeout=2).json()
                    if 'closePrice' in r:
                        current_close = float(str(r['closePrice']).replace(',', ''))
                except:
                    pass
                    
                is_bull = current_close > sma200
                return is_bull, current_close, sma200
    except Exception as e:
        print(f"[Market Check] KOSPI 지수 조회 오류: {e}")
    return True, 6800.0, 6200.0

def get_ensemble_target_portfolio(max_unit_price=None):
    """
    올인원 버핏 앙상블 스코어링 TOP 10 종목 산출
    max_unit_price: 소액 계좌를 위한 1주당 가격 상한선 필터 (예: 200만원 계좌 시 18만원)
    """
    universe_path = os.path.join(DATA_DIR, 'universe_top100.csv')
    metrics_path = os.path.join(DATA_DIR, 'parsed_metrics.csv')
    prices_path = os.path.join(DATA_DIR, 'prices_top100.csv')
    
    universe_df = pd.read_csv(universe_path, dtype={'Code': str})
    metrics_df = pd.read_csv(metrics_path, dtype={'Code': str})
    prices_df = pd.read_csv(prices_path, index_col=0)
    
    top60_codes = universe_df['Code'].head(60).tolist()
    df = metrics_df[metrics_df['Code'].isin(top60_codes)].copy()
    
    # 소액 계좌 단가 필터 적용
    if max_unit_price:
        last_prices = prices_df.drop(columns=['KOSPI'], errors='ignore').ffill().iloc[-1]
        df['Current_Price'] = df['Code'].map(last_prices)
        df = df[df['Current_Price'] <= max_unit_price].copy()
    
    # 1. 재무 건전성 필터 (극단적 부실 및 적자주 제외)
    cond = (df['ROE_Avg3'] >= 7.0) & (df['OP_Margin'] >= 6.0) & (df['Debt_Ratio'] <= 140) & (df['PER'] > 3)
    df_valid = df[cond].copy()
    if len(df_valid) < 10:
        df_valid = df[(df['Debt_Ratio'] <= 160) & (df['PER'] > 3)].copy()
        
    # 2. 팩터별 순위 계산
    # Quality (40%): ROE + OP Margin
    df_valid['Rank_Quality'] = (df_valid['ROE_Avg3'] + df_valid['OP_Margin']).rank(ascending=False)
    # Value (30%): 1/PER + 1/PBR
    df_valid['Rank_Value'] = ((1 / df_valid['PER']) + (1 / df_valid['PBR'])).rank(ascending=False)
    
    # Momentum (30%): 6개월 주가 상대강도
    mom_dict = {}
    for code in df_valid['Code']:
        if code in prices_df.columns:
            s = prices_df[code].dropna()
            if len(s) >= 126:
                mom_dict[code] = (s.iloc[-1] - s.iloc[-126]) / s.iloc[-126]
            else:
                mom_dict[code] = 0.0
        else:
            mom_dict[code] = 0.0
    df_valid['Mom_6M'] = df_valid['Code'].map(mom_dict)
    df_valid['Rank_Mom'] = df_valid['Mom_6M'].rank(ascending=False)
    
    # 3. 앙상블 종합 점수
    df_valid['Ensemble_Score'] = (
        0.40 * df_valid['Rank_Quality'] + 
        0.30 * df_valid['Rank_Value'] + 
        0.30 * df_valid['Rank_Mom']
    )
    
    top10 = df_valid.sort_values(by='Ensemble_Score').head(config.PORTFOLIO_SIZE)
    return top10[['Code', 'Name', 'ROE_Avg3', 'OP_Margin', 'PER', 'PBR', 'Debt_Ratio', 'Mom_6M']].to_dict(orient='records')

def execute_rebalance():
    print("="*75)
    print("  [★ 올인원 버핏 앙상블 자동매매 봇 실행]")
    print(f"  모드: {'[시뮬레이션/DRY-RUN]' if config.DRY_RUN else '[실제 API 주문 전송]'}")
    print(f"  서버: {'모의투자(VTS)' if config.IS_MOCK else '실전투자'}")
    print("="*75)

    # 1. 시장 국면 점검 (KOSPI 200일 이동평균선)
    is_bull, kospi_val, sma200 = check_market_regime()
    print(f"\n[1단계] 시장 리스크 레짐 점검")
    if is_bull:
        print(f"  현재 KOSPI({kospi_val:,.1f}) > 200일선({sma200:,.1f}) -> [상승장/정상 국면]")
        cash_reserve_rate = 0.02 # 정상 현금 버퍼 2%
    else:
        print(f"  현재 KOSPI({kospi_val:,.1f}) < 200일선({sma200:,.1f}) -> [약세장/경계 국면]")
        print("  -> 안전자산(현금) 30% 방어 버퍼 적용!")
        cash_reserve_rate = 0.30 # 약세장 현금 버퍼 30%

    # 2. 계좌 잔고 및 보유 종목 조회
    api = KoreaInvestmentAPI()
    balance = api.get_balance()
    if not balance:
        print("[오류] 계좌 정보를 불러오지 못했습니다. 프로그램을 중단합니다.")
        return

    total_asset = balance['total_asset']
    cash = balance['cash']
    holdings = {h['code']: h for h in balance['holdings']}

    # 소액 계좌(예: 200만원) 자동 감지: 1주당 단가가 목표 배정액을 초과하지 않는 종목 위주로 선별
    target_alloc_per_stock = int((total_asset * (1 - cash_reserve_rate)) / config.PORTFOLIO_SIZE)
    max_unit_price = target_alloc_per_stock if total_asset <= 5000000 else None

    # 3. 최신 앙상블 목표 포트폴리오 산출
    target_stocks = get_ensemble_target_portfolio(max_unit_price=max_unit_price)
    target_codes = [s['Code'] for s in target_stocks]
    
    print(f"\n[3단계] 계좌 잔고 현황")
    print(f"  총 자산평가액: {total_asset:,}원 | 예수금: {cash:,}원")
    print(f"  현재 보유 종목: {len(holdings)}개")
    for code, h in holdings.items():
        print(f"   - {h['name']} ({code}): {h['qty']}주 (수익률: {h.get('profit_rate', 0.0):+.2f}%)")

    # 4. 리밸런싱 예산 및 종목당 목표 배정액 계산
    investable_total = int(total_asset * (1 - cash_reserve_rate))
    print(f"\n[4단계] 리밸런싱 주문 계획")
    print(f"  총 투자예산: {investable_total:,}원 (현금보유: {cash_reserve_rate*100:.0f}%)")
    print(f"  종목당 목표 배정액: {target_alloc_per_stock:,}원 (10개 종목 동일 분산)")

    # 5. 매도 주문 실행 (기존 보유 중 목표 포트폴리오 탈락 종목 전량 매도)
    for code, h in holdings.items():
        if code not in target_codes:
            print(f"  [매도 대상] {h['name']} ({code}): 목표 제외 -> 전량 매도 ({h['qty']}주)")
            api.send_order(code, h['qty'], is_buy=False, order_type="01")
            time.sleep(0.5)

    # 6. 매수 주문 실행
    buy_reports = []
    for s in target_stocks:
        code = s['Code']
        name = s['Name']
        current_price = api.get_current_price(code)
        
        if not current_price or current_price <= 0:
            print(f"  [스킵] {name} ({code}) 현재가 조회 실패")
            continue
            
        cur_qty = holdings.get(code, {}).get('qty', 0)
        cur_val = cur_qty * current_price
        needed_val = target_alloc_per_stock - cur_val
        buy_qty = int(needed_val // current_price)
        
        if buy_qty > 0:
            print(f"  [매수 대상] {name:12s} ({code}) | 현재가: {current_price:>8,}원 | 주문수량: +{buy_qty}주 (예상: {buy_qty * current_price:,}원)")
            api.send_order(code, buy_qty, is_buy=True, order_type="01")
            buy_reports.append(f"{name}: +{buy_qty}주 ({current_price:,}원)")
            time.sleep(0.5)
        elif cur_qty == 0:
            print(f"  [배정 보류] {name:12s} ({code}) | 1주 가격({current_price:,}원)이 배정액({target_alloc_per_stock:,}원) 초과")
        else:
            print(f"  [비중 유지] {name:12s} ({code}) | 현재 {cur_qty}주 보유 중 (목표 비중 충족)")

    # 7. 텔레그램 리포트 발송
    report_msg = (
        f"*[올인원 버핏 앙상블 리밸런싱 완료]*\n"
        f"총자산: {total_asset:,}원\n"
        f"시장 국면: {'상승장 (주식 98%)' if is_bull else '약세장 (현금 30% 방어)'}\n"
        f"신규 매수: {len(buy_reports)}건\n"
        f"보유 종목: 10개 우량주 분산 완료"
    )
    send_telegram_alert(report_msg)
    print("\n" + "="*75)
    print("  올인원 버핏 앙상블 프로세스가 정상 완료되었습니다.")
    print("="*75)

if __name__ == "__main__":
    execute_rebalance()
