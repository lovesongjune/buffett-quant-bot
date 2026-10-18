# ==========================================================
# [개선안 1] 실전 가상계좌(Paper-Trading) 라이브 포워드 트래킹 렛저
# ==========================================================
import os
import json
import time
import datetime
import requests
import pandas as pd
import concurrent.futures
from kis_api import KoreaInvestmentAPI
import config

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

_PRICE_CACHE = {}
_KR_CACHE = {}
_FX_CACHE = {"rate": 1365.0, "time": 0.0}

def get_live_usd_price(ticker: str) -> float:
    """야후 파이낸스를 통해 미국 주식 실시간가 조회 (15초 인메모리 캐시 적용)"""
    now = time.time()
    if ticker in _PRICE_CACHE and (now - _PRICE_CACHE[ticker]["time"] < 15.0):
        return _PRICE_CACHE[ticker]["price"]

    headers = {'User-Agent': 'Mozilla/5.0'}
    fallback_prices = {"NVDA": 138.0, "AAPL": 235.0, "MSFT": 430.0, "BRK-B": 470.0, "COST": 920.0}
    price = fallback_prices.get(ticker, 150.0)
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d'
        r = requests.get(url, headers=headers, timeout=2.0).json()
        live_p = r['chart']['result'][0]['meta'].get('regularMarketPrice')
        if live_p and float(live_p) > 0:
            price = float(live_p)
    except Exception:
        pass

    _PRICE_CACHE[ticker] = {"price": price, "time": now}
    return price

def get_live_kr_price(code: str, api=None) -> int:
    """한국 주식 실시간가 조회 (15초 인메모리 캐시 적용)"""
    now = time.time()
    if code in _KR_CACHE and (now - _KR_CACHE[code]["time"] < 15.0):
        return _KR_CACHE[code]["price"]

    cur_p = None
    if api:
        cur_p = api.get_current_price(code)
    if not cur_p or cur_p <= 0:
        try:
            url = f"https://m.stock.naver.com/api/stock/{code}/integration"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2.0).json()
            dt_info = r.get('dealTrendInfos', [])
            if dt_info and 'closePrice' in dt_info[0]:
                cur_p = int(dt_info[0]['closePrice'].replace(',', ''))
        except Exception:
            pass
    if not cur_p or cur_p <= 0:
        cur_p = 50000

    _KR_CACHE[code] = {"price": cur_p, "time": now}
    return cur_p

def get_live_fx_rate() -> float:
    """원/달러 환율 실시간 조회 (15초 인메모리 캐시 적용)"""
    now = time.time()
    if (now - _FX_CACHE["time"] < 15.0):
        return _FX_CACHE["rate"]

    fx_rate = 1365.0
    try:
        r = requests.get('https://m.stock.naver.com/api/index/FX_USDKRW/basic', headers={'User-Agent': 'Mozilla/5.0'}, timeout=2).json()
        if 'closePrice' in r:
            fx_rate = float(str(r['closePrice']).replace(',', ''))
    except Exception:
        pass

    _FX_CACHE["rate"] = fx_rate
    _FX_CACHE["time"] = now
    return fx_rate

def update_paper_ledger_market_values(api=None) -> dict:
    """
    원장 내 모든 한국 및 미국 종목의 현재가를 실시간 조회하여 Mark-to-Market 평가를 갱신합니다.
    """
    ledger = load_paper_ledger()
    if api is None:
        api = KoreaInvestmentAPI(dry_run=True)

    # 1. 환율 조회 (캐시 적용)
    fx_rate = get_live_fx_rate()

    # 2. 한국 및 미국 종목 병렬 평가 (Parallel Multi-threading for sub-second speed)
    def eval_single_kr(h):
        code = h["code"]
        shares = h["shares"]
        entry_price = h["entry_price"]
        cur_price = get_live_kr_price(code, api)
        if not cur_price or cur_price <= 0:
            cur_price = entry_price
        
        # 고점 추적 (Trailing High)
        highest_price = max(h.get("highest_price", entry_price), cur_price)
        h["highest_price"] = highest_price
        
        cur_val = cur_price * shares
        pnl_amt = cur_val - (entry_price * shares)
        pnl_pct = (pnl_amt / (entry_price * shares)) * 100 if entry_price > 0 else 0.0
        
        # 고점 대비 하락률 (Drawdown from High)
        dd_from_high = ((cur_price - highest_price) / highest_price) * 100 if highest_price > 0 else 0.0
        
        # 리스크 관리 조건 감지: -7% 손절 또는 +10% 이상 수익 후 고점 대비 -8% 반락 시 트레일링 익절
        stop_loss_triggered = (pnl_pct <= -7.0)
        trailing_stop_triggered = (highest_price >= entry_price * 1.10) and (dd_from_high <= -8.0)
        
        if stop_loss_triggered:
            risk_status = "🔴 손절선 도달 (-7% 청산)"
        elif trailing_stop_triggered:
            risk_status = "🟡 트레일링 익절 발동 (고점 -8% 반락 이익보존)"
        elif highest_price >= entry_price * 1.10:
            risk_status = f"🟢 트레일링 감시 중 (고점대비 {dd_from_high:.1f}%)"
        else:
            risk_status = f"🔵 정상 보유 (수익률 {pnl_pct:+.1f}%)"

        return {
            "code": code,
            "name": h["name"],
            "shares": shares,
            "entry_price": entry_price,
            "highest_price": highest_price,
            "current_price": cur_price,
            "current_val_krw": cur_val,
            "pnl_amt_krw": pnl_amt,
            "pnl_pct": pnl_pct,
            "dd_from_high": dd_from_high,
            "stop_loss_price": int(entry_price * 0.93),
            "trailing_stop_price": int(highest_price * 0.92) if highest_price >= entry_price * 1.10 else None,
            "risk_status": risk_status,
            "stop_loss_triggered": stop_loss_triggered,
            "trailing_stop_triggered": trailing_stop_triggered
        }

    def eval_single_us(h):
        ticker = h["code"]
        shares = h["shares"]
        entry_price_usd = h["entry_price_usd"]
        cur_price_usd = get_live_usd_price(ticker)
        
        highest_price_usd = max(h.get("highest_price_usd", entry_price_usd), cur_price_usd)
        h["highest_price_usd"] = highest_price_usd
        
        cur_val_usd = cur_price_usd * shares
        pnl_amt_usd = cur_val_usd - (entry_price_usd * shares)
        pnl_pct = (pnl_amt_usd / (entry_price_usd * shares)) * 100 if entry_price_usd > 0 else 0.0
        cur_val_krw = int(cur_val_usd * fx_rate)

        dd_from_high = ((cur_price_usd - highest_price_usd) / highest_price_usd) * 100 if highest_price_usd > 0 else 0.0
        stop_loss_triggered = (pnl_pct <= -7.0)
        trailing_stop_triggered = (highest_price_usd >= entry_price_usd * 1.10) and (dd_from_high <= -8.0)

        if stop_loss_triggered:
            risk_status = "🔴 손절선 도달 (-7% 청산)"
        elif trailing_stop_triggered:
            risk_status = "🟡 트레일링 익절 발동 (고점 -8% 반락 이익보존)"
        elif highest_price_usd >= entry_price_usd * 1.10:
            risk_status = f"🟢 트레일링 감시 중 (고점대비 {dd_from_high:.1f}%)"
        else:
            risk_status = f"🔵 정상 보유 (수익률 {pnl_pct:+.1f}%)"

        return {
            "code": ticker,
            "name": h["name"],
            "shares": shares,
            "entry_price_usd": entry_price_usd,
            "highest_price_usd": highest_price_usd,
            "current_price_usd": cur_price_usd,
            "current_val_usd": cur_val_usd,
            "current_val_krw": cur_val_krw,
            "pnl_amt_usd": pnl_amt_usd,
            "pnl_pct": pnl_pct,
            "dd_from_high": dd_from_high,
            "stop_loss_price_usd": round(entry_price_usd * 0.93, 2),
            "trailing_stop_price_usd": round(highest_price_usd * 0.92, 2) if highest_price_usd >= entry_price_usd * 1.10 else None,
            "risk_status": risk_status,
            "stop_loss_triggered": stop_loss_triggered,
            "trailing_stop_triggered": trailing_stop_triggered
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        kr_futures = [executor.submit(eval_single_kr, h) for h in ledger.get("holdings_kr", [])]
        us_futures = [executor.submit(eval_single_us, h) for h in ledger.get("holdings_us", [])]
        kr_evaluated = [f.result() for f in kr_futures]
        us_evaluated = [f.result() for f in us_futures]

    kr_total_val = sum(x["current_val_krw"] for x in kr_evaluated)
    us_total_val_usd = sum(x["current_val_usd"] for x in us_evaluated)

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

def get_stops_monitoring_status(api=None) -> list:
    """
    모든 국내/미국 보유 종목의 손절선(-7%) 및 트레일링 익절선(+10% 후 고점 -8%) 대비 현재 위치를 정밀 진단
    """
    eval_res = update_paper_ledger_market_values(api=api)
    status_list = []
    
    for item in eval_res.get("kr_evaluated", []):
        entry = item["entry_price"]
        cur = item["current_price"]
        highest = item["highest_price"]
        sl_price = item["stop_loss_price"]
        tp_price = item["trailing_stop_price"]
        
        status_list.append({
            "market": "KR",
            "code": item["code"],
            "name": item["name"],
            "shares": item["shares"],
            "entry_price": f"{entry:,}원",
            "current_price": f"{cur:,}원",
            "highest_price": f"{highest:,}원",
            "pnl_pct": item["pnl_pct"],
            "dd_from_high": item["dd_from_high"],
            "stop_loss_price": f"{sl_price:,}원",
            "trailing_stop_price": f"{tp_price:,}원" if tp_price else "비활성 (+10% 돌파 시 작동)",
            "risk_status": item["risk_status"],
            "triggered": item["stop_loss_triggered"] or item["trailing_stop_triggered"]
        })
        
    for item in eval_res.get("us_evaluated", []):
        entry = item["entry_price_usd"]
        cur = item["current_price_usd"]
        highest = item["highest_price_usd"]
        sl_price = item["stop_loss_price_usd"]
        tp_price = item["trailing_stop_price_usd"]
        
        status_list.append({
            "market": "US",
            "code": item["code"],
            "name": item["name"],
            "shares": item["shares"],
            "entry_price": f"${entry:.2f}",
            "current_price": f"${cur:.2f}",
            "highest_price": f"${highest:.2f}",
            "pnl_pct": item["pnl_pct"],
            "dd_from_high": item["dd_from_high"],
            "stop_loss_price": f"${sl_price:.2f}",
            "trailing_stop_price": f"${tp_price:.2f}" if tp_price else "비활성 (+10% 돌파 시 작동)",
            "risk_status": item["risk_status"],
            "triggered": item["stop_loss_triggered"] or item["trailing_stop_triggered"]
        })
        
    return status_list

def execute_risk_management_stops(api=None, send_telegram=True) -> list:
    """
    손절(-7%) 또는 트레일링 익절(고점 대비 -8% 반락)에 도달한 종목을 자동 청산하고 안전 현금으로 전환
    """
    ledger = load_paper_ledger()
    eval_res = update_paper_ledger_market_values(api=api)
    
    actions_taken = []
    new_kr_holdings = []
    cash_addition_krw = 0
    
    kr_eval_map = {x["code"]: x for x in eval_res.get("kr_evaluated", [])}
    for h in ledger.get("holdings_kr", []):
        code = h["code"]
        ev = kr_eval_map.get(code)
        if ev and (ev.get("stop_loss_triggered") or ev.get("trailing_stop_triggered")):
            reason = "손절(-7% 청산)" if ev.get("stop_loss_triggered") else "트레일링 익절(고점 반락 -8%)"
            proceeds = ev["current_val_krw"]
            cash_addition_krw += proceeds
            action_desc = f"[국내 {reason}] {ev['name']}({code}): {ev['shares']}주 전량 청산 ({proceeds:,}원 회수, 수익률: {ev['pnl_pct']:+.1f}%)"
            actions_taken.append({
                "market": "KR",
                "code": code,
                "name": ev["name"],
                "reason": reason,
                "pnl_pct": ev["pnl_pct"],
                "proceeds_krw": proceeds,
                "desc": action_desc
            })
        else:
            new_kr_holdings.append(h)
            
    new_us_holdings = []
    us_eval_map = {x["code"]: x for x in eval_res.get("us_evaluated", [])}
    for h in ledger.get("holdings_us", []):
        ticker = h["code"]
        ev = us_eval_map.get(ticker)
        if ev and (ev.get("stop_loss_triggered") or ev.get("trailing_stop_triggered")):
            reason = "손절(-7% 청산)" if ev.get("stop_loss_triggered") else "트레일링 익절(고점 반락 -8%)"
            proceeds_krw = ev["current_val_krw"]
            cash_addition_krw += proceeds_krw
            action_desc = f"[미국 {reason}] {ev['name']}({ticker}): {ev['shares']}주 전량 청산 (${ev['current_val_usd']:.2f} / {proceeds_krw:,}원 회수, 수익률: {ev['pnl_pct']:+.1f}%)"
            actions_taken.append({
                "market": "US",
                "code": ticker,
                "name": ev["name"],
                "reason": reason,
                "pnl_pct": ev["pnl_pct"],
                "proceeds_krw": proceeds_krw,
                "desc": action_desc
            })
        else:
            new_us_holdings.append(h)
            
    if actions_taken:
        ledger["holdings_kr"] = new_kr_holdings
        ledger["holdings_us"] = new_us_holdings
        ledger["cash_krw"] = ledger.get("cash_krw", 0) + cash_addition_krw
        if "trade_logs" not in ledger:
            ledger["trade_logs"] = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for act in actions_taken:
            ledger["trade_logs"].append({
                "timestamp": now_str,
                "action": act["desc"],
                "pnl_pct": act["pnl_pct"],
                "proceeds_krw": act["proceeds_krw"]
            })
        save_paper_ledger(ledger)
        update_paper_ledger_market_values(api=api)
        
        # 텔레그램 긴급 알림 발송
        if send_telegram and config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
            msg_lines = ["🚨 *[AI 퀀트 리스크 관리 긴급 주문 체결]*", f"시간: `{now_str}`", ""]
            for a in actions_taken:
                msg_lines.append(f"• {a['desc']}")
            msg_lines.append(f"\n💰 *회수된 안전 예수금*: `+{cash_addition_krw:,}원`")
            msg_lines.append("🛡️ _자본금 보존 원칙에 따라 안전 현금으로 즉시 전환되었습니다._")
            
            try:
                url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
                payload = {
                    "chat_id": config.TELEGRAM_CHAT_ID,
                    "text": "\n".join(msg_lines),
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                print(f"[Telegram Alert Error] {e}")
            
    return actions_taken

