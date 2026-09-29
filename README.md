# 📈 Buffett Quant Auto Trading Bot (올인원 버핏 앙상블 자동매매 봇)

미래에셋증권 Open API와 연동하여 워렌 버핏 퀄리티 밸류 + 조엘 그린블랫 마법공식 + 상대강도 모멘텀을 결합한 앙상블 퀀트 자동매매 시스템입니다.

---

## 🎯 전략 개요

1. **대형 우량주 안전판:** 코스피 시총 상위 60위 대형주 유니버스 (슬리피지 0%, 상장폐지 위험 0%)
2. **버핏 퀄리티 팩터 (40%):** 3년 평균 ROE + 영업이익률 순위 (경제적 해자)
3. **마법공식 밸류 팩터 (30%):** 1/PER + 1/PBR 순위 (안전마진)
4. **상대강도 모멘텀 (30%):** 6개월 주가 추세 순위 (가치 함정 회피 및 주도주 포획)
5. **시장 국면 리스크 관리:** KOSPI 200일선 하회 시 현금 30% 방어 버퍼 자동 확보
6. **소액 계좌(200만 원) 최적화:** 1주당 단가 필터를 적용하여 10개 종목에 고르게 분산 투자

---

## 📂 프로젝트 구조

* `config.py`: 환경 변수 및 계좌/API 설정
* `mirae_api.py`: 미래에셋증권 Open API (OAuth 2.0 REST) 클라이언트
* `trading_bot.py`: 자동매매 실행 메인 엔진
* `run_backtest.py`: 2020~2026 과거 6년 백테스트 시뮬레이터
* `analyze_stability.py`: 전략별 안정성, 낙폭(MDD), 샤프/소르티노 지수 정밀 분석기
* `.github/workflows/rebalance.yml`: GitHub Actions 정기 자동 실행 워크플로우

---

## ⚙️ 실행 방법

### 로컬 실행
```bash
pip install -r requirements.txt
python trading_bot.py
```

### GitHub Actions 자동화
저장소 `Settings -> Secrets and variables -> Actions`에 아래 Secrets를 등록하면 스케줄에 맞춰 완전 무료로 자동 실행됩니다:
* `MIRAE_APP_KEY`: 미래에셋 Open API AppKey
* `MIRAE_APP_SECRET`: 미래에셋 Open API AppSecret
* `MIRAE_ACCOUNT_NO`: 계좌번호 8자리
* `MIRAE_ACCOUNT_CODE`: 상품코드 (`01`)
* `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`: (선택) 텔레그램 알림용
