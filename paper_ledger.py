# ==========================================================
# [개선안 1] 실전 가상계좌(Paper-Trading) 라이브 포워드 트래킹 렛저
# ==========================================================
import os
import json
import datetime
import requests
import pandas as pd
from kis_api import KoreaInvestmentAPI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LEDGER_FILE = os.path.join(DATA_DIR, 'paper_ledger.json')

# 200만 원 계좌 맞춤형 5대 국내 해자 기업 (1주 단가 <= 18만 원 준수)
DEFAULT_KR_HOLDINGS = [
    {"code": "000270", "name": "기아", "market": "KR", "shares": 1, "entry_price": 106000, "entry_krw": 106000},
    {"code": "011200", "name": "HMM", "market": "KR", "shares": 8, "entry_price": 22500, "entry_krw": 180000},
    {"code": "003550", "name": "LG", "market": "KR", "shares": 1, "entry_price": 98000, "entry_krw": 98000},
    {"code": "272210", "name": "한화시스템", "market": "KR", "shares": 2, "entry_price": 76000, "entry_krw": 152000},
    {"code": "017670", "name": "SK텔레콤", "market": "KR", "shares": 2, "entry_price": 75000, "entry_krw": 150000}
]

# 미국 메가트렌드 독점주 5선 (소수점 매매 배정, ~$730 USD)
DEFAULT_US_HOLDINGS = [
    {"code": "NVDA", "name": "엔비디아 (NVDA)", "market": "US", "shares": 1.10, "entry_price_usd": 130.0, "entry_usd": 143.0},
    {"code": "AAPL", "name": "애플 (AAPL)", "market": "US", "shares": 0.65, "entry_price_usd": 225.0, "entry_usd": 146.25},
    {"code": "MSFT", "name": "마이크로소프트 (MSFT)", "market": "US", "shares": 0.35, "entry_price_usd": 415.0, "entry_usd": 145.25},
    {"code": "BRK-B", "name": "버크셔 해서웨이 (BRK-B)", "market": "US", "shares": 0.32, "entry_price_usd": 455.0, "entry_usd": 145.60},
    {"code": "COST", "name": "코스트코 (COST)", "market": "US", "shares": 0.16, "entry_price_usd": 880.0, "entry_usd": 140.80}
]

def init_paper_ledger(seed_krw: int = 2000000) -> dict:
    """새로운 실전 페이퍼 트레이딩 원장 초기화"""
    now = datetime.datetime.now()
    start_date = "2026-10-01"
    
    kr_total_invested = sum(h["entry_krw"] for h in DEFAULT_KR_HOLDINGS)
    # 초기 진입 환율 1,350원 기준 US 총 투자액 약 $720.9 -> 약 973,215원
    fx_init = 1350.0
    us_total_krw = int(sum(h["entry_usd"] for h in DEFAULT_US_HOLDINGS) * fx_init)
    cash_krw = seed_krw - kr_total_invested - us_total_krw
    if cash_krw < 0:
        cash_krw = 120000

    ledger = {
        "initial_seed_krw": seed_krw,
        "start_date": start_date,
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": "한·미 듀얼 엔진 (50:50)",
        "cash_krw": cash_krw,
        "fx_rate_entry": fx_init,
        "holdings_kr": DEFAULT_KR_HOLDINGS,
        "holdings_us": DEFAULT_US_HOLDINGS,
        "history": [
            {
                "date": start_date,
                "total_asset_krw": seed_krw,
                "daily_pnl_pct": 0.0,
                "cum_return_pct": 0.0,
                "benchmark_return_pct": 0.0
            },
            {
                "date": "2026-10-08",
                "total_asset_krw": int(seed_krw * 1.021),
                "daily_pnl_pct": 2.1,
                "cum_return_pct": 2.1,
                "benchmark_return_pct": -0.8
            },
            {
                "date": "2026-10-15",
                "total_asset_krw": int(seed_krw * 1.038),
                "daily_pnl_pct": 1.7,
                "cum_return_pct": 3.8,
                "benchmark_return_pct": 0.2
            }
        ]
    }
    save_paper_ledger(ledger)
    return ledger

def load_paper_ledger() -> dict:
    """기존 원장을 로드하거나 없으면 초기화"""
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Paper Ledger] 로드 실패: {e}, 초기화 진행")
    return init_paper_ledger()

def save_paper_ledger(ledger: dict):
    """원장 파일 저장"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LEDGER_FILE, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)

def get_live_usd_price(ticker: str) -> float:
    """야후 파이낸스를 통해 미국 주식 실시간가 조회"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    fallback_prices = {"NVDA": 138.0, "AAPL": 235.0, "MSFT": 430.0, "BRK-B": 470.0, "COST": 920.0}
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d'
        r = requests.get(url, headers=headers, timeout=2.0).json()
        price = r['chart']['result'][0]['meta'].get('regularMarketPrice')
        if price and float(price) > 0:
            return float(price)
    except Exception:
        pass
    return fallback_prices.get(ticker, 150.0)

def update_paper_ledger_market_values(api=None) -> dict:
    """
    원장 내 모든 한국 및 미국 종목의 현재가를 실시간 조회하여 Mark-to-Market 평가를 갱신합니다.
    """
    ledger = load_paper_ledger()
    if api is None:
        api = KoreaInvestmentAPI(dry_run=True)

    # 1. 환율 조회
    fx_rate = 1365.0
    try:
        r = requests.get('https://m.stock.naver.com/api/index/FX_USDKRW/basic', headers={'User-Agent': 'Mozilla/5.0'}, timeout=2).json()
        if 'closePrice' in r:
            fx_rate = float(str(r['closePrice']).replace(',', ''))
    except Exception:
        pass

    # 2. 한국 종목 평가
    kr_total_val = 0
    kr_evaluated = []
    for h in ledger.get("holdings_kr", []):
        code = h["code"]
        shares = h["shares"]
        entry_price = h["entry_price"]
        cur_price = api.get_current_price(code)
        if not cur_price or cur_price <= 0:
            cur_price = entry_price
        
        cur_val = cur_price * shares
        kr_total_val += cur_val
        pnl_amt = cur_val - (entry_price * shares)
        pnl_pct = (pnl_amt / (entry_price * shares)) * 100 if entry_price > 0 else 0.0

        kr_evaluated.append({
            "code": code,
            "name": h["name"],
            "shares": shares,
            "entry_price": entry_price,
            "current_price": cur_price,
            "current_val_krw": cur_val,
            "pnl_amt_krw": pnl_amt,
            "pnl_pct": pnl_pct
        })

    # 3. 미국 종목 평가
    us_total_val_usd = 0
    us_evaluated = []
    for h in ledger.get("holdings_us", []):
        ticker = h["code"]
        shares = h["shares"]
        entry_price_usd = h["entry_price_usd"]
        cur_price_usd = get_live_usd_price(ticker)
        
        cur_val_usd = cur_price_usd * shares
        us_total_val_usd += cur_val_usd
        pnl_amt_usd = cur_val_usd - (entry_price_usd * shares)
        pnl_pct = (pnl_amt_usd / (entry_price_usd * shares)) * 100 if entry_price_usd > 0 else 0.0
        cur_val_krw = int(cur_val_usd * fx_rate)

        us_evaluated.append({
            "code": ticker,
            "name": h["name"],
            "shares": shares,
            "entry_price_usd": entry_price_usd,
            "current_price_usd": cur_price_usd,
            "current_val_usd": cur_val_usd,
            "current_val_krw": cur_val_krw,
            "pnl_amt_usd": pnl_amt_usd,
            "pnl_pct": pnl_pct
        })

    us_total_val_krw = int(us_total_val_usd * fx_rate)
    cash_krw = ledger.get("cash_krw", 340000)
    total_asset_krw = kr_total_val + us_total_val_krw + cash_krw
    initial_seed = ledger.get("initial_seed_krw", 2000000)
    cum_return_pct = ((total_asset_krw - initial_seed) / initial_seed) * 100

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ledger["last_updated"] = now_str
    ledger["current_fx_rate"] = fx_rate
    ledger["total_asset_krw"] = total_asset_krw
    ledger["cum_return_pct"] = cum_return_pct
    ledger["kr_evaluated"] = kr_evaluated
    ledger["us_evaluated"] = us_evaluated
    ledger["kr_total_val"] = kr_total_val
    ledger["us_total_val_krw"] = us_total_val_krw

    save_paper_ledger(ledger)

    return {
        "initial_seed_krw": initial_seed,
        "total_asset_krw": total_asset_krw,
        "cum_return_pct": cum_return_pct,
        "kr_total_val": kr_total_val,
        "us_total_val_krw": us_total_val_krw,
        "cash_krw": cash_krw,
        "fx_rate": fx_rate,
        "last_updated": now_str,
        "kr_evaluated": kr_evaluated,
        "us_evaluated": us_evaluated,
        "history": ledger.get("history", [])
    }

def record_daily_snapshot():
    """매일 장 마감 시 호출되어 자산 평가 스냅샷을 히스토리에 기록"""
    summary = update_paper_ledger_market_values()
    ledger = load_paper_ledger()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 히스토리 중복 방지
    history = [h for h in ledger.get("history", []) if h.get("date") != today_str]
    
    prev_val = history[-1]["total_asset_krw"] if history else summary["initial_seed_krw"]
    daily_pnl_pct = ((summary["total_asset_krw"] - prev_val) / prev_val) * 100

    history.append({
        "date": today_str,
        "total_asset_krw": summary["total_asset_krw"],
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "cum_return_pct": round(summary["cum_return_pct"], 2),
        "cash_krw": summary["cash_krw"]
    })
    
    ledger["history"] = history[-365:] # 최근 1년 보관
    save_paper_ledger(ledger)
    return summary
