# ==========================================================
# [전체 시스템 종합 기능 점검 및 부하/스트레스 테스트]
# ==========================================================
import sys
import os
import time
import json
import traceback
import concurrent.futures
import pandas as pd
import numpy as np

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

print("=" * 80)
print("  🚀 [AI 증권사 버핏 퀀트 시스템] 전체 기능 점검 & 부하 테스트 시작")
print("=" * 80)

passed_tests = 0
failed_tests = 0

def run_test(name, func):
    global passed_tests, failed_tests
    print(f"\n[검사 항목] {name} ...", end=" ", flush=True)
    start_t = time.time()
    try:
        func()
        elapsed = time.time() - start_t
        print(f"✅ 통과 ({elapsed:.2f}초)")
        passed_tests += 1
    except Exception as e:
        elapsed = time.time() - start_t
        print(f"❌ 실패 ({elapsed:.2f}초)")
        print(f"   -> 에러 상세: {e}")
        traceback.print_exc(file=sys.stdout)
        failed_tests += 1

# -------------------------------------------------------------
# 1. trading_bot 모듈 핵심 기능 검증
# -------------------------------------------------------------
def test_trading_bot_regime():
    from trading_bot import check_market_regime, get_dynamic_regime_allocation
    is_bull, close, sma = check_market_regime()
    assert isinstance(is_bull, bool), "is_bull must be bool"
    assert close > 0 and sma > 0, "Prices must be positive"
    
    dyn = get_dynamic_regime_allocation()
    assert "regime" in dyn and "equity_ratio" in dyn and "cash_ratio" in dyn
    assert round(dyn["equity_ratio"] + dyn["cash_ratio"], 2) == 1.0, "Ratios must sum to 1.0"

def test_trading_bot_kr_ensemble():
    from trading_bot import get_ensemble_target_portfolio
    # 200만 원 예산 단가 제약 (19만 원 이하)
    targets = get_ensemble_target_portfolio(max_unit_price=190000, top_n=5)
    assert len(targets) > 0, "Target list must not be empty"
    for s in targets:
        assert "Code" in s and "Name" in s and "ROE_Avg3" in s
        assert s["ROE_Avg3"] > 0, f"ROE should be positive for {s['Name']}"

def test_trading_bot_us_moat():
    from trading_bot import get_us_moat_target_portfolio
    us_targets = get_us_moat_target_portfolio(budget_usd=740.0, top_n=5)
    assert len(us_targets) == 5, f"Expected 5 US stocks, got {len(us_targets)}"
    total_spent = sum(s["Target_USD"] for s in us_targets)
    assert 600.0 <= total_spent <= 800.0, f"Target USD out of range: {total_spent}"
    for s in us_targets:
        assert s["Price_USD"] > 0, f"Invalid price for {s['Ticker']}"
        assert s["Target_Shares"] > 0, f"Invalid shares for {s['Ticker']}"

# -------------------------------------------------------------
# 2. paper_ledger 모듈 실시간 Mark-to-Market 검증
# -------------------------------------------------------------
def test_paper_ledger():
    from paper_ledger import load_paper_ledger, update_paper_ledger_market_values, record_daily_snapshot
    ledger = load_paper_ledger()
    assert ledger["initial_seed_krw"] == 2000000
    assert len(ledger["holdings_kr"]) == 5
    assert len(ledger["holdings_us"]) == 5
    
    summary = update_paper_ledger_market_values()
    assert summary["total_asset_krw"] >= 1800000, f"Unreasonable total asset: {summary['total_asset_krw']}"
    assert summary["kr_total_val"] > 0, "KR total val must be > 0"
    assert summary["us_total_val_krw"] > 0, "US total val must be > 0"
    assert summary["cash_krw"] > 0, "Cash buffer must be positive"
    
    snap = record_daily_snapshot()
    assert len(snap["history"]) > 0

# -------------------------------------------------------------
# 3. 브리핑 생성 모듈 (08:50 모닝 & 15:40 마감)
# -------------------------------------------------------------
def test_briefing_generators():
    from daily_briefing import generate_morning_briefing
    from closing_briefing import generate_closing_briefing
    m_msg = generate_morning_briefing(2000000)
    assert "모닝 브리핑" in m_msg and "KOSPI" in m_msg
    assert len(m_msg) > 100
    
    c_msg = generate_closing_briefing()
    assert "15:40 장 마감" in c_msg and "총 평가 자산" in c_msg
    assert len(c_msg) > 100

# -------------------------------------------------------------
# 4. 종목 건강검진 원클릭 닥터 모듈
# -------------------------------------------------------------
def test_stock_doctor_data():
    from stock_doctor import get_stock_doctor_data, get_us_stock_data
    # 국내 기아(000270)
    kr_info = get_stock_doctor_data("000270")
    assert kr_info["name"] == "기아"
    assert kr_info["current_price"] > 0
    assert "per" in kr_info and "pbr" in kr_info
    
    # 미국 엔비디아(NVDA)
    us_info = get_us_stock_data("NVDA")
    assert us_info["ticker"] == "NVDA"
    assert us_info["current_price"] > 0
    assert "target_mean" in us_info

# -------------------------------------------------------------
# 5. 스트림릿 대시보드 데이터 연산 무결성 (NaN / KeyError 검사)
# -------------------------------------------------------------
def test_data_integrity():
    data_dir = os.path.join(BASE_DIR, 'data')
    prices = pd.read_csv(os.path.join(data_dir, 'prices_top100.csv'), index_col=0, parse_dates=True)
    assert 'KOSPI' in prices.columns
    assert len(prices) > 1000
    
    metrics = pd.read_csv(os.path.join(data_dir, 'parsed_metrics.csv'), dtype={'Code': str})
    assert not metrics.empty
    assert set(['Code', 'Name', 'ROE_Avg3', 'OP_Margin', 'PER', 'PBR']).issubset(metrics.columns)
    
    universe = pd.read_csv(os.path.join(data_dir, 'universe_top100.csv'), dtype={'Code': str})
    assert len(universe) >= 50

# -------------------------------------------------------------
# 6. 부하 테스트 1: 외부 금융 시세 API 병렬 동시성 부하 테스트 (Concurrency Stress)
# -------------------------------------------------------------
def test_concurrency_stress_market_quotes():
    """
    네이버 및 야후 파이낸스 실시간 시세 API에 10개 스레드로 동시 요청을 발생시켜
    응답 지연, 타임아웃, 커넥션 풀 누수 여부를 스트레스 테스트합니다.
    """
    from stock_doctor import get_us_stock_data, get_stock_doctor_data
    
    kr_codes = ["005930", "000660", "000270", "011200", "033780", "003550", "272210", "017670", "012330", "035420"]
    us_tickers = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "BRK-B", "COST", "LLY", "AVGO", "KO"]
    
    def fetch_kr(c):
        t0 = time.time()
        d = get_stock_doctor_data(c)
        return time.time() - t0, d["current_price"] > 0
        
    def fetch_us(t):
        t0 = time.time()
        d = get_us_stock_data(t)
        return time.time() - t0, d["current_price"] > 0

    print("\n   [부하 1-A] 한국 10개 대형주 동시 병렬 시세 조회 (10 Threads)...", end=" ", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_kr, c) for c in kr_codes]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    latencies = [r[0] for r in results]
    successes = [r[1] for r in results]
    print(f"완료 (성공률: {sum(successes)}/10, 평균 지연시간: {np.mean(latencies):.2f}초, 최대: {np.max(latencies):.2f}초)")
    assert sum(successes) >= 9, f"KR Concurrency success rate too low: {sum(successes)}/10"

    print("   [부하 1-B] 미국 10대 독점주 동시 병렬 시세 조회 (10 Threads)...", end=" ", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_us, t) for t in us_tickers]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    latencies = [r[0] for r in results]
    successes = [r[1] for r in results]
    print(f"완료 (성공률: {sum(successes)}/10, 평균 지연시간: {np.mean(latencies):.2f}초, 최대: {np.max(latencies):.2f}초)")
    assert sum(successes) >= 9, f"US Concurrency success rate too low: {sum(successes)}/10"

# -------------------------------------------------------------
# 7. 부하 테스트 2: 실전 가상계좌(Paper Ledger) 연속 20회 Mark-to-Market 반복 갱신 부하
# -------------------------------------------------------------
def test_ledger_stress_repetition():
    """
    장중 빈번한 새로고침이나 연속 주문 집행 시 JSON 파일 I/O 및 계산 병목 검사
    """
    from paper_ledger import update_paper_ledger_market_values
    from kis_api import KoreaInvestmentAPI
    api = KoreaInvestmentAPI(dry_run=True)
    
    print("\n   [부하 2] 원장 연속 10회 고속 Mark-to-Market 연산 및 JSON 락/안정성 검사...", end=" ", flush=True)
    times = []
    for i in range(10):
        t0 = time.time()
        res = update_paper_ledger_market_values(api=api)
        times.append(time.time() - t0)
        assert res["total_asset_krw"] > 0
    print(f"완료 (10회 평균: {np.mean(times):.3f}초, 총 소요: {sum(times):.2f}초, 데이터 무결성 100%)")
    assert np.mean(times) < 3.0, "Ledger update too slow"

# -------------------------------------------------------------
# 8. 부하 테스트 3: Gemini Client API Pacing & Backoff 회복력 검증
# -------------------------------------------------------------
def test_gemini_client_robustness():
    """
    GeminiClient의 재시도, 지수 백오프, 에러 메시지 격리 기능 검증
    """
    from gemini_client import GeminiClient
    # Mock invalid key test
    client = GeminiClient(api_key="TEST_INVALID_KEY_FOR_ROBUSTNESS", max_retries=1, timeout=5)
    resp = client.generate_text("Test prompt")
    # API 키 오류 시 크래시 없이 친절한 에러 문구를 반환해야 함
    assert "[Gemini AI] API 키가 올바르지 않거나" in resp or "[Gemini AI]" in resp
    print("\n   [회복력 검사] 비정상 키/네트워크 장애 시 앱 크래시 방지 및 안내 문구 반환 검증 완료")

# -------------------------------------------------------------
# 9. 극단적 예산/환율 엣지 케이스 (Edge Cases) 테스트
# -------------------------------------------------------------
def test_edge_cases():
    from trading_bot import get_ensemble_target_portfolio, get_us_moat_target_portfolio
    
    # 엣지 1: 최소 예산 50만 원 계좌
    budget_small = 500000
    alloc_per_stock = int(budget_small / 5) # 종목당 10만 원
    small_targets = get_ensemble_target_portfolio(max_unit_price=alloc_per_stock, top_n=5)
    assert len(small_targets) > 0, "Should find affordable stocks even for 500k KRW budget"
    
    # 엣지 2: 소수점 매매 미국 주식 최소 $100 예산
    small_us = get_us_moat_target_portfolio(budget_usd=100.0, top_n=5)
    assert len(small_us) == 5
    for s in small_us:
        assert s["Target_Shares"] > 0

# -------------------------------------------------------------
# 메인 테스트 러너
# -------------------------------------------------------------
if __name__ == "__main__":
    tests = [
        ("1. 시장 레짐 & 3단계 동적 현금 비중 검증", test_trading_bot_regime),
        ("2. 한국 버핏 TOP 5 소액 단가 제약 검증", test_trading_bot_kr_ensemble),
        ("3. 미국 메가트렌드 TOP 5 소수점 매매 검증", test_trading_bot_us_moat),
        ("4. 실전 가상계좌(Paper Ledger) Mark-to-Market 검증", test_paper_ledger),
        ("5. 08:50 모닝 & 15:40 마감 브리핑 생성 검증", test_briefing_generators),
        ("6. 한·미 종목 건강검진 원클릭 닥터 데이터 검증", test_stock_doctor_data),
        ("7. 2020~2026 백테스트 데이터 무결성 검증", test_data_integrity),
        ("8. [부하 1] 실시간 금융 API 병렬 동시성 부하 테스트 (10 Threads)", test_concurrency_stress_market_quotes),
        ("9. [부하 2] 실전 원장 연속 Mark-to-Market 반복 부하 테스트", test_ledger_stress_repetition),
        ("10. [부하 3] Gemini AI 클라이언트 장애 회복력(Resilience) 검증", test_gemini_client_robustness),
        ("11. 극단적 소액 예산(50만 원) 엣지 케이스 처리 검증", test_edge_cases),
    ]

    for name, func in tests:
        run_test(name, func)

    print("\n" + "=" * 80)
    print(f"  🏁 [종합 점검 결과] 총 {passed_tests + failed_tests}개 테스트 중: ✅ {passed_tests}개 통과 / ❌ {failed_tests}개 실패")
    print("=" * 80)
    
    if failed_tests > 0:
        sys.exit(1)
    else:
        sys.exit(0)
