# ==========================================================
# 미래에셋증권 Open API 및 자동매매 환경 설정 파일
# ==========================================================
import os

# 1. 미래에셋증권 Open API 발급 정보
# (미래에셋증권 개발자 센터 https://developers.miraeasset.com 에서 발급)
APP_KEY = os.getenv("MIRAE_APP_KEY", "YOUR_APP_KEY_HERE")
APP_SECRET = os.getenv("MIRAE_APP_SECRET", "YOUR_APP_SECRET_HERE")

# 계좌번호 (앞 8자리) 및 상품코드 (보통 '01')
ACCOUNT_NO = os.getenv("MIRAE_ACCOUNT_NO", "12345678")
ACCOUNT_CODE = os.getenv("MIRAE_ACCOUNT_CODE", "01")

# 2. 투자 모드 설정
# True: 모의투자 (VTS), False: 실전투자
IS_MOCK = True

# DRY_RUN: True일 경우 실제 주문 API를 호출하지 않고 콘솔에만 시뮬레이션 출력 (안전 테스트 모드)
DRY_RUN = True

# 3. 텔레그램 알림 설정 (선택 사항)
# 텔레그램 BotFather를 통해 발급받은 봇 토큰 및 chat_id
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 4. 전략 기본 파라미터
PORTFOLIO_SIZE = 10       # 보유 종목 수 (버핏 퀀트 TOP 10)
CASH_BUFFER_RATE = 0.02   # 수수료 및 오차 방지를 위해 남겨둘 현금 비율 (2%)
