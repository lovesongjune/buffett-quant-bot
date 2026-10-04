# ==========================================================
# 아침 8시 50분 출근길 모바일 30초 데일리 브리핑 시스템
# ==========================================================
import os
import datetime
import requests
import config
from trading_bot import check_market_regime, get_ensemble_target_portfolio
from agents import get_live_macro_indicators

def generate_morning_briefing(budget_val: int = 2000000) -> str:
    """
    출근길 30초 만에 오늘의 시황과 계좌 행동 지침을 파악할 수 있는 브리핑 문구를 생성합니다.
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%Y년 %m월 %d일")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    # 1. 매크로 & 시장 국면
    is_bull, kospi_val, sma200 = check_market_regime()
    macro_data = get_live_macro_indicators()
    fx_rate = macro_data.get('USDKRW', '1,350')
    nasdaq = macro_data.get('NASDAQ', '18,000')

    regime_title = "🟢 강세장 (정상 운용 구간)" if is_bull else "🔴 약세/경계 국면 (현금 30% 방어)"
    action_guide = "정상 보유 및 복리 인내" if is_bull else "보수적 리스크 관리 (추격 매수 금지)"

    # 2. 버핏 퀀트 TOP 10 후보
    target_alloc = int((budget_val * (0.70 if not is_bull else 0.98)) / 10)
    targets = get_ensemble_target_portfolio(max_unit_price=target_alloc)
    top_names = [s['Name'] for s in targets[:5]]

    briefing = f"""🏛️ [버핏 퀀트 AI 가상 증권사] 출근길 모닝 브리핑
📅 일시: {date_str} ({weekday_kr}) 오전 08:50

🌐 [1. 글로벌 야간 시황 30초 요약]
• KOSPI 시장 국면: {regime_title}
  (현재 지수 {kospi_val:,.1f} pt vs 200일선 {sma200:,.1f} pt)
• 원/달러 환율: {fx_rate} 원
• 미국 나스닥: {nasdaq} pt

🎯 [2. 200만 원 계좌 오늘 행동 지침]
• 투자 원칙: 10개 우량주 균등 분산 (종목당 약 {target_alloc:,}원)
• 핵심 주도주: {', '.join(top_names)} 등 10개 종목
• 오늘의 액션: [{action_guide}]

💬 [3. 찰리 멍거의 멘탈 케어 명언]
"주식 시장에서 큰돈을 버는 것은 사고파는 영리함이 아니라, 훌륭한 기업을 발굴하고 지루하게 기다리는 인내심에서 나온다."

오늘도 원금을 철저히 보존하며 장기 복리의 마법을 함께 만드시기 바랍니다! 🚀
"""
    return briefing

def send_telegram_message(text: str, token: str = None, chat_id: str = None) -> dict:
    """텔레그램 봇으로 메시지를 발송합니다."""
    bot_token = token or config.TELEGRAM_TOKEN
    target_chat = chat_id or config.TELEGRAM_CHAT_ID

    if not bot_token or not target_chat:
        return {"success": False, "message": "텔레그램 토큰 또는 Chat ID가 설정되지 않았습니다."}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return {"success": True, "message": "텔레그램 발송 성공"}
        else:
            return {"success": False, "message": f"발송 실패 (코드 {resp.status_code}): {resp.text}"}
    except Exception as e:
        return {"success": False, "message": f"통신 오류: {str(e)}"}

if __name__ == "__main__":
    msg = generate_morning_briefing()
    print(msg)
    if config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
        res = send_telegram_message(msg)
        print("Telegram Result:", res)
