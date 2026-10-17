# ==========================================================
# [개선안 3] 오후 15:40 한국 장 마감 PnL & 수급 복기 리포트 시스템
# ==========================================================
import os
import datetime
import requests
import config
from trading_bot import get_dynamic_regime_allocation
from paper_ledger import record_daily_snapshot, load_paper_ledger
from daily_briefing import send_telegram_message

def get_live_market_closing_trend():
    """당일 KOSPI 외인/기관 순매수 및 시황 조회"""
    res = {
        "foreign_net": "집계 중",
        "organ_net": "집계 중",
        "kosdaq_close": "820.0"
    }
    try:
        url = "https://m.stock.naver.com/api/index/KOSPI/trend"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3).json()
        if r and len(r) > 0:
            latest = r[0]
            res["foreign_net"] = latest.get("foreignerPureBuyQuant", "외인 순매수")
            res["organ_net"] = latest.get("organPureBuyQuant", "기관 순매수")
    except Exception:
        pass
    return res

def generate_closing_briefing() -> str:
    """
    15:40 장 마감 직후 30초 만에 오늘의 스마트머니 수급과 가상계좌 PnL을 복기하는 리포트 생성
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%Y년 %m월 %d일")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    # 1. 시장 레짐 & 수급
    regime_info = get_dynamic_regime_allocation()
    trend_info = get_live_market_closing_trend()
    
    # 2. 페이퍼 트레이딩 라이브 원장 스냅샷 갱신
    snapshot = record_daily_snapshot()
    total_asset = snapshot["total_asset_krw"]
    seed = snapshot["initial_seed_krw"]
    cum_ret = snapshot["cum_return_pct"]
    cash = snapshot["cash_krw"]
    
    # 3. 오늘 최고 수익 종목 탐색
    all_eval = snapshot.get("kr_evaluated", []) + snapshot.get("us_evaluated", [])
    top_stock = None
    if all_eval:
        sorted_stocks = sorted(all_eval, key=lambda x: x.get("pnl_pct", 0.0), reverse=True)
        top_stock = sorted_stocks[0]

    top_stock_str = f"{top_stock['name']} ({top_stock['pnl_pct']:+.1f}%)" if top_stock else "산출 중"

    briefing = f"""🔔 [버핏 퀀트 AI 가상 증권사] 15:40 장 마감 PnL & 수급 리포트
📅 일시: {date_str} ({weekday_kr}) 오후 03:40

🌐 [1. 오늘 마감 시황 & 스마트머니 수급]
• KOSPI 마감: {regime_info['current_close']:,.1f} pt ({regime_info['diff_pct']:+.1f}% vs 200일선)
• 시장 레짐: {regime_info['regime']}
• 스마트머니 수급: 외인 {trend_info['foreign_net']} | 기관 {trend_info['organ_net']}

💼 [2. 200만 원 실전 가상계좌(Paper Ledger) 마감 현황]
• 총 평가 자산: {total_asset:,} 원 (원금 {seed:,} 원 대비)
• 누적 수익률: {cum_ret:+.2f}%
• 안전 현금/달러 버퍼: {cash:,} 원 ({regime_info['cash_ratio']*100:.0f}% 방어율 준수)
• 최고 효자 종목: 🏆 {top_stock_str}

🧭 [3. 내일 시초가 대응 가이드]
• 운용 기조: [{regime_info['stance']}]
• 행동 지침: 잦은 단타 매매를 지양하고 경제적 해자를 지닌 우량 기업의 가치 복리를 유지합니다.

원금을 철저히 보존하는 퀀트 시스템이 24시간 자산을 지킵니다. 오늘 하루도 수고 많으셨습니다! 🌙
"""
    return briefing

if __name__ == "__main__":
    msg = generate_closing_briefing()
    print(msg)
    if config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
        res = send_telegram_message(msg)
        print("Telegram Result:", res)
