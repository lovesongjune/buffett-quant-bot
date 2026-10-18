# ==========================================================
# [개선안 2] 텔레그램 양방향 리모컨 & 스마트 머니 관제 모듈
# ==========================================================
import os
import json
import time
import requests
import datetime
import config
from paper_ledger import (
    load_paper_ledger,
    update_paper_ledger_market_values,
    get_stops_monitoring_status,
    execute_risk_management_stops
)
from trading_bot import (
    check_market_regime,
    get_dynamic_regime_allocation,
    get_ensemble_target_portfolio,
    get_us_moat_target_portfolio
)
from stock_doctor import get_stock_doctor_data, get_us_stock_doctor_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OFFSET_FILE = os.path.join(DATA_DIR, 'telegram_offset.json')

def get_last_offset() -> int:
    """텔레그램 메시지 처리 오프셋 로드"""
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("offset", 0)
        except Exception:
            pass
    return 0

def save_last_offset(offset: int):
    """텔레그램 메시지 처리 오프셋 저장"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(OFFSET_FILE, 'w', encoding='utf-8') as f:
            json.dump({"offset": offset, "updated_at": datetime.datetime.now().isoformat()}, f)
    except Exception:
        pass

def send_telegram_reply(chat_id: str, text: str) -> bool:
    """텔레그램 채팅방으로 응답 전송"""
    if not config.TELEGRAM_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram Reply] 전송 실패: {e}")
        return False

def handle_telegram_command(command_text: str) -> str:
    """
    사용자가 보낸 텔레그램 명령어를 분석하고 최적의 서식화된 응답을 생성합니다.
    """
    raw_cmd = command_text.strip()
    parts = raw_cmd.split()
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    # 1. 도움말
    if cmd in ["/start", "/help", "/도움말", "/명령어"]:
        return (
            "🤖 *[AI 버핏 퀀트 시스템 양방향 리모컨]*\n"
            "스마트폰에서 아래 명령어로 실시간 계좌와 수급을 제어하세요:\n\n"
            "📊 `/잔고` : 실시간 총자산, 수익률 및 종목별 PnL 조회\n"
            "🌊 `/수급` : 외인·기관 쌍끌이 스마트머니 TOP 5\n"
            "🛡️ `/스톱` : 손절선(-7%) 및 트레일링 익절선 감시 현황\n"
            "🩺 `/진단 <코드>` : 종목 긴급 건강검진 (예: `/진단 005930`, `/진단 NVDA`)\n"
            "🔄 `/리밸런싱` : 리스크 관리 및 스톱로스 즉시 실행\n"
            "📈 `/시장` : KOSPI 200일선 레짐 및 동적 현금 비중 진단\n"
        )

    # 2. 실시간 잔고 조회
    elif cmd in ["/잔고", "/balance", "/계좌"]:
        res = update_paper_ledger_market_values()
        kr_eval = res.get("kr_evaluated", [])
        us_eval = res.get("us_evaluated", [])

        lines = [
            "📊 *[실전 가상계좌 실시간 잔고 리포트]*",
            f"• 총 평가자산: *{res['total_asset_krw']:,}원*",
            f"• 누적 수익률: *{res['cum_return_pct']:+.2f}%*",
            f"• 안전 예수금: *{res['cash_krw']:,}원*",
            f"• 적용 환율: *{res['fx_rate']:,}원/USD*",
            "\n🇰🇷 *[국내 보유 종목]*"
        ]
        for k in kr_eval:
            lines.append(f"• {k['name']}: {k['current_price']:,}원 ({k['pnl_pct']:+.1f}%)")
        
        lines.append("\n🇺🇸 *[미국 보유 종목]*")
        for u in us_eval:
            lines.append(f"• {u['name']}: ${u['current_price_usd']:.2f} ({u['pnl_pct']:+.1f}%)")

        return "\n".join(lines)

    # 3. 스마트 머니 수급 TOP 5
    elif cmd in ["/수급", "/flow", "/외인기관"]:
        top_stocks = get_ensemble_target_portfolio(top_n=5)
        lines = [
            "🌊 *[스마트 머니 (외인·기관) 쌍끌이 TOP 5]*",
            "재무 퀄리티와 3일 외인+기관 순매수 수급 종합 평가:\n"
        ]
        for i, s in enumerate(top_stocks, 1):
            f_net = s.get('Flow_Foreign', 0)
            o_net = s.get('Flow_Organ', 0)
            lines.append(
                f"*{i}. {s['Name']}* (`{s['Code']}`)\n"
                f"   - 3년 평균 ROE: `{s['ROE_Avg3']}%` | PER: `{s['PER']}`\n"
                f"   - 외인 순매수: `{f_net:+,}주` | 기관: `{o_net:+,}주`"
            )
        return "\n".join(lines)

    # 4. 손절 및 트레일링 익절 감시 현황
    elif cmd in ["/스톱", "/stops", "/리스크"]:
        status_list = get_stops_monitoring_status()
        lines = [
            "🛡️ *[동적 리스크 관리 (손절/트레일링) 감시 현황]*",
            "• 기준: -7% 즉시 손절 / +10% 돌파 후 고점 -8% 반락 시 익절\n"
        ]
        for item in status_list:
            lines.append(
                f"• *{item['name']}* ({item['market']}): {item['risk_status']}\n"
                f"   현재: `{item['current_price']}` | 손절선: `{item['stop_loss_price']}` | 익절선: `{item['trailing_stop_price']}`"
            )
        return "\n".join(lines)

    # 5. 종목 건강검진
    elif cmd in ["/진단", "/doctor", "/진찰"]:
        if not arg:
            return "⚠️ 진단할 종목코드 또는 티커를 입력해주세요.\n예: `/진단 005930` 또는 `/진단 NVDA`"
        
        target = arg.upper().strip()
        if target.isalpha(): # 미국 주식
            data = get_us_stock_doctor_data(target)
            if "error" in data:
                return f"❌ 미국 종목 조회 실패: {data['error']}"
            return (
                f"🩺 *[미국 종목 닥터 진단: {data['name']} ({data['ticker']})]*\n"
                f"• 현재가: `${data['current_price']:.2f}`\n"
                f"• 52주 변동폭: `${data['low_52w']}` ~ `${data['high_52w']}`\n"
                f"• PER: `{data['pe_ratio']}` | ROE: `{data['roe']}%`\n"
                f"• 목표주가: `${data['target_price']}` (애널리스트 투자의견: `{data['recommendation']}`)"
            )
        else: # 한국 주식
            code = target.zfill(6)
            data = get_stock_doctor_data(code)
            if "error" in data:
                return f"❌ 한국 종목 조회 실패: {data['error']}"
            return (
                f"🩺 *[한국 종목 닥터 진단: {data['name']} ({data['code']})]*\n"
                f"• 현재가: `{data['current_price']:,}원`\n"
                f"• PER: `{data['per']}` | PBR: `{data['pbr']}` | 배당수익률: `{data['dividend_yield']}`\n"
                f"• 외인 지분율: `{data['foreign_rate']}`\n"
                f"• 최근 3일 외인 순매수: `{data['foreign_net_sum']:,}주` | 기관: `{data['organ_net_sum']:,}주`"
            )

    # 6. 리밸런싱 및 리스크 스톱 실행
    elif cmd in ["/리밸런싱", "/rebalance", "/실행"]:
        actions = execute_risk_management_stops(send_telegram=False)
        regime = get_dynamic_regime_allocation()
        lines = [
            "🔄 *[리스크 관리 & 포트폴리오 상태 보고]*",
            f"• 시장 국면: *{regime['regime']}*",
            f"• 운용 기조: {regime['stance']}\n"
        ]
        if actions:
            lines.append("🚨 *[긴급 청산 조치 완료]*")
            for a in actions:
                lines.append(f"• {a['desc']}")
        else:
            lines.append("✅ *[이상 없음]*: 손절(-7%) 또는 트레일링 익절 조건에 걸린 종목이 없습니다. 모든 포지션을 안정적으로 유지합니다.")
        return "\n".join(lines)

    # 7. 시장 레짐 진단
    elif cmd in ["/시장", "/market", "/레짐"]:
        regime = get_dynamic_regime_allocation()
        return (
            f"📈 *[KOSPI 200일선 시장 레짐 분석]*\n"
            f"• 국면: *{regime['regime']}*\n"
            f"• 현재 KOSPI: `{regime['current_close']:,.1f}` (200일선: `{regime['sma200']:,.1f}`)\n"
            f"• 이격도: `{regime['diff_pct']:+.1f}%`\n"
            f"• 권장 비중: 주식 `{regime['equity_ratio']*100:.0f}%` / 안전자산·현금 `{regime['cash_ratio']*100:.0f}%`\n"
            f"• 운용 방침: {regime['stance']}"
        )

    else:
        return (
            "❓ 알 수 없는 명령어입니다.\n"
            "`/도움말`을 입력하시면 사용 가능한 명령어 목록을 확인하실 수 있습니다."
        )

def process_telegram_updates(single_run: bool = True) -> list:
    """
    텔레그램 봇의 인박스를 조회하여 새로운 사용자 명령어를 처리하고 답장을 보냅니다.
    """
    if not config.TELEGRAM_TOKEN:
        return []

    offset = get_last_offset()
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 2}
    
    try:
        r = requests.get(url, params=params, timeout=5).json()
    except Exception as e:
        print(f"[Telegram Updates] 조회 오류: {e}")
        return []

    if not r.get("ok"):
        return []

    updates = r.get("result", [])
    handled_logs = []

    for up in updates:
        up_id = up.get("update_id", 0)
        msg = up.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "")

        # 다음 번 폴링을 위해 오프셋 전진
        offset = max(offset, up_id + 1)
        save_last_offset(offset)

        if not text:
            continue

        # 보안 검증: 설정된 관리자 CHAT_ID가 있으면 오직 본인 요청에만 응답
        if config.TELEGRAM_CHAT_ID and chat_id != str(config.TELEGRAM_CHAT_ID):
            send_telegram_reply(chat_id, "⛔ *[접근 제한]*: 등록된 관리자만 퀀트 봇을 제어할 수 있습니다.")
            continue

        # 명령어 처리 및 답장 전송
        reply_text = handle_telegram_command(text)
        send_telegram_reply(chat_id, reply_text)
        handled_logs.append({"cmd": text, "reply": reply_text, "chat_id": chat_id})

    return handled_logs

if __name__ == "__main__":
    print("[Telegram Interactive Controller] 실행 테스트...")
    logs = process_telegram_updates(single_run=True)
    print(f"처리된 메시지 수: {len(logs)}")
    test_reply = handle_telegram_command("/잔고")
    print("\n[샘플 /잔고 응답]:\n", test_reply)
