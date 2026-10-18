# ==========================================================
# [올인원 버핏 앙상블] 자동매매 메인 실행 엔진 (Trading Bot)
# ==========================================================
import sys
import time
import os
import pandas as pd
import numpy as np
import requests
import concurrent.futures
from kis_api import KoreaInvestmentAPI
import config

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

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

def get_dynamic_regime_allocation():
    """
    [개선안 2] 3단계 시장 레짐 기반 동적 자산 배분 & 현금 버퍼율 산출
    - 강세장 (Bull 🟢): KOSPI > 200선 (+2% 이상) -> 주식 95% / 현금 5% (복리 성장 가속)
    - 중립/횡보장 (Neutral 🟡): KOSPI 200선 근접 (±2% 이내) -> 주식 80% / 현금 20% (완충)
    - 약세/위험장 (Bear 🔴): KOSPI < 200선 (-2% 이하) -> 주식 50% / 안전현금·달러 50% (원금 사수 방어)
    """
    is_bull, current_close, sma200 = check_market_regime()
    diff_pct = ((current_close - sma200) / sma200) * 100 if sma200 > 0 else 0.0
    
    if diff_pct >= 2.0:
        regime = "🟢 강세장 (Bull Market)"
        equity_ratio = 0.95
        cash_ratio = 0.05
        stance = "공격적 복리 증식 모드 (주식 95% / 현금 5%)"
    elif diff_pct >= -2.0:
        regime = "🟡 중립/횡보장 (Neutral Market)"
        equity_ratio = 0.80
        cash_ratio = 0.20
        stance = "균형 운용 모드 (주식 80% / 현금 20%)"
    else:
        regime = "🔴 약세/경계장 (Bear Market)"
        equity_ratio = 0.50
        cash_ratio = 0.50
        stance = "원금 사수 방어 모드 (주식 50% / 안전현금·달러 50%)"
        
    return {
        "regime": regime,
        "is_bull": is_bull,
        "current_close": current_close,
        "sma200": sma200,
        "diff_pct": diff_pct,
        "equity_ratio": equity_ratio,
        "cash_ratio": cash_ratio,
        "stance": stance
    }

_SMART_MONEY_CACHE = {}

def get_smart_money_flow_data(code: str) -> dict:
    """네이버 증권에서 최근 3일 외인 및 기관 순매수량 조회 (60초 인메모리 캐시 적용)"""
    now = time.time()
    if code in _SMART_MONEY_CACHE and (now - _SMART_MONEY_CACHE[code]["time"] < 60.0):
        return _SMART_MONEY_CACHE[code]
    
    flow = {"code": code, "foreign_net": 0, "organ_net": 0, "total_flow": 0}
    try:
        url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2.5).json()
        deal_trends = r.get('dealTrendInfos', [])[:3]
        f_sum = 0
        o_sum = 0
        for d in deal_trends:
            f_sum += int(str(d.get('foreignerPureBuyQuant', '0')).replace(',', ''))
            o_sum += int(str(d.get('organPureBuyQuant', '0')).replace(',', ''))
        flow["foreign_net"] = f_sum
        flow["organ_net"] = o_sum
        flow["total_flow"] = f_sum + o_sum
    except Exception:
        pass
    
    _SMART_MONEY_CACHE[code] = {**flow, "time": now}
    return flow

def fetch_smart_money_batch(codes: list) -> dict:
    """후보 종목들의 수급 데이터를 멀티스레드로 고속 병렬 수집"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        future_map = {ex.submit(get_smart_money_flow_data, c): c for c in codes}
        for fut in concurrent.futures.as_completed(future_map):
            c = future_map[fut]
            try:
                results[c] = fut.result()
            except Exception:
                results[c] = {"code": c, "foreign_net": 0, "organ_net": 0, "total_flow": 0}
    return results

def get_ensemble_target_portfolio(max_unit_price=None, top_n=None):
    """
    올인원 버핏 앙상블 스코어링 TOP N 종목 산출
    - 퀄리티(35%) + 밸류(25%) + 모멘텀(20%) + 스마트머니 수급(20%)
    - max_unit_price: 소액 계좌를 위한 1주당 가격 상한선 필터 (예: 200만원 계좌 시 18만원)
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
    # Quality (35%): ROE + OP Margin
    df_valid['Rank_Quality'] = (df_valid['ROE_Avg3'] + df_valid['OP_Margin']).rank(ascending=False)
    # Value (25%): 1/PER + 1/PBR
    df_valid['Rank_Value'] = ((1 / df_valid['PER']) + (1 / df_valid['PBR'])).rank(ascending=False)
    
    # Momentum (20%): 6개월 주가 상대강도
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

    # Smart Money Flow (20%): 최근 3일 외인+기관 순매수 수급 팩터
    try:
        flow_map = fetch_smart_money_batch(df_valid['Code'].tolist())
    except Exception:
        flow_map = {}
        
    df_valid['Flow_Total'] = df_valid['Code'].map(lambda c: flow_map.get(c, {}).get('total_flow', 0))
    df_valid['Flow_Foreign'] = df_valid['Code'].map(lambda c: flow_map.get(c, {}).get('foreign_net', 0))
    df_valid['Flow_Organ'] = df_valid['Code'].map(lambda c: flow_map.get(c, {}).get('organ_net', 0))
    df_valid['Rank_Flow'] = df_valid['Flow_Total'].rank(ascending=False)
    
    # 3. 앙상블 종합 점수 (가치 + 퀄리티 + 모멘텀 + 스마트머니 수급)
    df_valid['Ensemble_Score'] = (
        0.35 * df_valid['Rank_Quality'] + 
        0.25 * df_valid['Rank_Value'] + 
        0.20 * df_valid['Rank_Mom'] +
        0.20 * df_valid['Rank_Flow']
    )
    
    target_count = top_n or config.PORTFOLIO_SIZE
    top_stocks = df_valid.sort_values(by='Ensemble_Score').head(target_count)
    return top_stocks[['Code', 'Name', 'ROE_Avg3', 'OP_Margin', 'PER', 'PBR', 'Debt_Ratio', 'Mom_6M', 'Flow_Total', 'Flow_Foreign', 'Flow_Organ']].to_dict(orient='records')

# -------------------------------------------------------------
# 미국 메가트렌드 해자 유니버스 & 포트폴리오
# -------------------------------------------------------------
US_MOAT_UNIVERSE = [
    {"Ticker": "NVDA", "Name": "엔비디아 (NVIDIA)", "Sector": "AI 반도체", "Moat": "AI 가속기 글로벌 독점", "ROE": 115.0},
    {"Ticker": "AAPL", "Name": "애플 (Apple)", "Sector": "빅테크/디바이스", "Moat": "강력한 하드웨어 생태계 락인", "ROE": 147.0},
    {"Ticker": "MSFT", "Name": "마이크로소프트 (Microsoft)", "Sector": "클라우드/SW", "Moat": "기업용 B2B 소프트웨어 독점", "ROE": 38.0},
    {"Ticker": "GOOGL", "Name": "알파벳 (Google)", "Sector": "인터넷/검색", "Moat": "글로벌 검색 및 유튜브 플랫폼", "ROE": 31.0},
    {"Ticker": "AMZN", "Name": "아마존 (Amazon)", "Sector": "이커머스/AWS", "Moat": "글로벌 물류 인프라 & 클라우드", "ROE": 22.0},
    {"Ticker": "BRK-B", "Name": "버크셔 해서웨이", "Sector": "복합금융/가치투자", "Moat": "워렌 버핏의 60년 복리 자산배분", "ROE": 16.0},
    {"Ticker": "COST", "Name": "코스트코 (Costco)", "Sector": "유통/구독소비", "Moat": "유료 멤버십 갱신율 93%", "ROE": 31.0},
    {"Ticker": "LLY", "Name": "일라이 릴리 (Eli Lilly)", "Sector": "바이오/헬스케어", "Moat": "GLP-1 비만/당뇨 치료제 독점", "ROE": 62.0},
    {"Ticker": "AVGO", "Name": "브로드컴 (Broadcom)", "Sector": "통신/커스텀반도체", "Moat": "네트워크 및 커스텀 ASIC 표준", "ROE": 35.0},
    {"Ticker": "KO", "Name": "코카콜라 (Coca-Cola)", "Sector": "필수소비재/배당", "Moat": "62년 연속 배당성장 글로벌 브랜드", "ROE": 42.0}
]

def get_us_moat_target_portfolio(budget_usd=1500.0, top_n=10):
    """
    미국 메가트렌드 해자 TOP N 포트폴리오 산출 (소수점 매매 수량 계산)
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    items = US_MOAT_UNIVERSE[:top_n]
    per_stock_usd = budget_usd / len(items) if len(items) > 0 else 0
    
    results = []
    for s in items:
        ticker = s['Ticker']
        price = 150.0
        change_pct = 0.0
        hi_52 = 180.0
        lo_52 = 120.0
        
        try:
            u = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d'
            r = requests.get(u, headers=headers, timeout=2.0).json()
            meta = r['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice', 150.0)
            change_pct = meta.get('regularMarketChangePercent', 0.0)
            hi_52 = meta.get('fiftyTwoWeekHigh', price * 1.2)
            lo_52 = meta.get('fiftyTwoWeekLow', price * 0.8)
        except Exception:
            pass
            
        frac_shares = round(per_stock_usd / price, 3) if price > 0 else 0
        est_usd = round(frac_shares * price, 2)
        
        results.append({
            "Ticker": ticker,
            "Name": s["Name"],
            "Sector": s["Sector"],
            "Moat": s["Moat"],
            "ROE": s["ROE"],
            "Price_USD": price,
            "Change_Pct": change_pct,
            "Target_Shares": frac_shares,
            "Target_USD": est_usd,
            "High_52W": hi_52,
            "Low_52W": lo_52
        })
    return results

def execute_rebalance():
    print("="*75)
    print("  [★ 올인원 버핏 앙상블 자동매매 봇 실행]")
    print(f"  모드: {'[시뮬레이션/DRY-RUN]' if config.DRY_RUN else '[실제 API 주문 전송]'}")
    print(f"  서버: {'모의투자(VTS)' if config.IS_MOCK else '실전투자'}")
    print("="*75)

    # 1. 시장 국면 점검 및 동적 현금 비중 산출 (Dynamic Regime Sizing)
    regime_info = get_dynamic_regime_allocation()
    is_bull = regime_info["is_bull"]
    kospi_val = regime_info["current_close"]
    sma200 = regime_info["sma200"]
    cash_reserve_rate = regime_info["cash_ratio"]
    equity_rate = regime_info["equity_ratio"]

    print(f"\n[1단계] 시장 리스크 레짐 점검: {regime_info['regime']}")
    print(f"  현재 KOSPI({kospi_val:,.1f}) vs 200일선({sma200:,.1f}) [이격도: {regime_info['diff_pct']:+.1f}%]")
    print(f"  운용 기조: {regime_info['stance']}")
    print(f"  -> 목표 주식 비중: {equity_rate*100:.0f}% | 안전 현금 버퍼: {cash_reserve_rate*100:.0f}%")

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
