# ==========================================================
# 한국투자증권 (KIS Developers) Open API 및 자동매매 환경 설정
# ==========================================================
import os

# 1. 한국투자증권 Open API 발급 정보
# (한국투자증권 개발자 포털 https://apiportal.koreainvestment.com 에서 발급)
KIS_APP_KEY = os.getenv("KIS_APP_KEY", os.getenv("APP_KEY", "YOUR_KIS_APP_KEY_HERE"))
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", os.getenv("APP_SECRET", "YOUR_KIS_APP_SECRET_HERE"))

# 모의투자 계좌번호 (앞 8자리) 및 상품코드 ('01')
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", os.getenv("ACCOUNT_NO", "12345678"))
KIS_ACCOUNT_CODE = os.getenv("KIS_ACCOUNT_CODE", os.getenv("ACCOUNT_CODE", "01"))

# 2. 투자 모드 설정
# True: 모의투자 (VTS), False: 실전투자
IS_MOCK = True

# DRY_RUN: True일 경우 실제 주문 API를 호출하지 않고 콘솔에만 시뮬레이션 출력 (안전 테스트 모드)
# 모의투자 AppKey/Secret을 입력하고 실제 모의 주문을 넣으려면 False로 변경하세요.
DRY_RUN = True

# 3. 텔레그램 알림 설정 (선택 사항)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 4. 전략 기본 파라미터
PORTFOLIO_SIZE = 10       # 보유 종목 수 (버핏 퀀트 TOP 10)
CASH_BUFFER_RATE = 0.02   # 수수료 및 오차 방지를 위해 남겨둘 현금 비율 (2%)
