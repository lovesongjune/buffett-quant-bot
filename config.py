# ==========================================================
# 한국투자증권 & 미래에셋 & Gemini AI 자동매매 환경 설정
# ==========================================================
import os

# .env 파일이 존재할 경우 자동 로드 (보안 보호)
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

_load_env()

# Streamlit Cloud Secrets 지원
try:
    import streamlit as st
    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# 1. Google Gemini AI API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 2. 한국투자증권 (KIS Developers) Open API 발급 정보
KIS_APP_KEY = os.getenv("KIS_APP_KEY", os.getenv("APP_KEY", "YOUR_KIS_APP_KEY_HERE"))
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", os.getenv("APP_SECRET", "YOUR_KIS_APP_SECRET_HERE"))
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", os.getenv("ACCOUNT_NO", "12345678"))
KIS_ACCOUNT_CODE = os.getenv("KIS_ACCOUNT_CODE", os.getenv("ACCOUNT_CODE", "01"))

# 3. 미래에셋증권 Open API 발급 정보 (호환용)
MIRAE_APP_KEY = os.getenv("MIRAE_APP_KEY", "YOUR_MIRAE_APP_KEY_HERE")
MIRAE_APP_SECRET = os.getenv("MIRAE_APP_SECRET", "YOUR_MIRAE_APP_SECRET_HERE")
MIRAE_ACCOUNT_NO = os.getenv("MIRAE_ACCOUNT_NO", "12345678")
MIRAE_ACCOUNT_CODE = os.getenv("MIRAE_ACCOUNT_CODE", "01")

# 4. 투자 모드 설정
IS_MOCK = True  # True: 모의투자, False: 실전투자
DRY_RUN = True  # True: 시뮬레이션 모드, False: 실제 증권사 주문 전송

# 5. 텔레그램 알림 설정 (선택 사항)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 6. 전략 기본 파라미터
PORTFOLIO_SIZE = 10       # 보유 종목 수 (버핏 퀀트 TOP 10)
CASH_BUFFER_RATE = 0.02   # 수수료 및 오차 방지를 위해 남겨둘 현금 비율 (2%)
