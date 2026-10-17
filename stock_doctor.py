# ==========================================================
# 5대 전문 부서 원클릭 종목 건강검진기 (한국 & 미국 글로벌 통합)
# ==========================================================
import requests
import json
import os
import config
from gemini_client import GeminiClient
from agents import get_live_macro_indicators

POPULAR_US_STOCKS = [
    {"Ticker": "AAPL", "Name": "애플 (Apple)"},
    {"Ticker": "NVDA", "Name": "엔비디아 (NVIDIA)"},
    {"Ticker": "MSFT", "Name": "마이크로소프트 (Microsoft)"},
    {"Ticker": "GOOGL", "Name": "알파벳/구글 (Google)"},
    {"Ticker": "AMZN", "Name": "아마존 (Amazon)"},
    {"Ticker": "META", "Name": "메타 (Meta/Facebook)"},
    {"Ticker": "TSLA", "Name": "테슬라 (Tesla)"},
    {"Ticker": "BRK-B", "Name": "버크셔 해서웨이 (Berkshire Hathaway)"},
    {"Ticker": "KO", "Name": "코카콜라 (Coca-Cola)"},
    {"Ticker": "OXY", "Name": "옥시덴탈 (Occidental - 버핏 에너지주)"},
    {"Ticker": "COST", "Name": "코스트코 (Costco)"},
    {"Ticker": "LLY", "Name": "일라이 릴리 (Eli Lilly - 비만치료제)"},
    {"Ticker": "TSM", "Name": "TSMC (대만 파운드리)"},
    {"Ticker": "AVGO", "Name": "브로드컴 (Broadcom)"},
    {"Ticker": "JNJ", "Name": "존슨앤존슨 (Johnson & Johnson)"}
]

# ----------------------------------------------------------
# 1. 한국 주식 (KOSPI / KOSDAQ)
# ----------------------------------------------------------
def get_stock_doctor_data(code: str) -> dict:
    """
    네이버 증권 API로부터 한국 종목의 실시간 시세, 밸류에이션, 수급 동향을 추출합니다.
    """
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
    except Exception as e:
        return {"error": f"데이터 수신 실패: {str(e)}"}

    total_infos = {item['code']: item['value'] for item in res.get('totalInfos', [])}
    deal_trends = res.get('dealTrendInfos', [])[:3]

    # 수급 요약 (최근 3일 합산)
    foreign_net_sum = 0
    organ_net_sum = 0
    for d in deal_trends:
        try:
            foreign_net_sum += int(d.get('foreignerPureBuyQuant', '0').replace(',', ''))
            organ_net_sum += int(d.get('organPureBuyQuant', '0').replace(',', ''))
        except:
            pass

    return {
        "market": "KR",
        "code": code,
        "name": res.get("stockName", code),
        "price": total_infos.get("lastClosePrice", "0"),
        "current_price": int(str(total_infos.get("lastClosePrice", "0")).replace(',', '')) if str(total_infos.get("lastClosePrice", "0")).replace(',', '').isdigit() else 0,
        "per": total_infos.get("per", "N/A"),
        "cns_per": total_infos.get("cnsPer", "N/A"),
        "pbr": total_infos.get("pbr", "N/A"),
        "eps": total_infos.get("eps", "N/A"),
        "marcap": total_infos.get("marketValue", "N/A"),
        "foreign_rate": total_infos.get("foreignRate", "N/A"),
        "dividend_yield": total_infos.get("dividendYieldRatio", "0.0%"),
        "high_52w": total_infos.get("highPriceOf52Weeks", "N/A"),
        "low_52w": total_infos.get("lowPriceOf52Weeks", "N/A"),
        "foreign_net_sum": foreign_net_sum,
        "organ_net_sum": organ_net_sum,
        "deal_trends": deal_trends
    }

def diagnose_stock_with_ai(stock_data: dict, api_key=None) -> str:
    """
    5대 가상 전문 부서의 시각으로 한국 종목을 다각적 심의하여 종합 건강 진단서를 발급합니다.
    """
    client = GeminiClient(api_key=api_key)
    macro_data = get_live_macro_indicators()

    deals_summary = []
    for d in stock_data.get("deal_trends", []):
        deals_summary.append(
            f"- 일자 {d.get('bizdate')}: 종가 {d.get('closePrice')}원 | 외인 순매수 {d.get('foreignerPureBuyQuant')}주 | 기관 순매수 {d.get('organPureBuyQuant')}주"
        )
    deals_text = "\n".join(deals_summary) if deals_summary else "최근 수급 데이터 없음"

    prompt = f"""
[분석 대상 한국 종목 데이터]
- 종목명: {stock_data.get('name')} ({stock_data.get('code')})
- 현재가: {stock_data.get('price')} 원
- 시가총액: {stock_data.get('marcap')}
- PER: {stock_data.get('per')} (추정 PER: {stock_data.get('cns_per')}) | PBR: {stock_data.get('pbr')} | 배당수익률: {stock_data.get('dividend_yield')}
- 52주 최고가: {stock_data.get('high_52w')} 원 | 52주 최저가: {stock_data.get('low_52w')} 원
- 외국인 지분율: {stock_data.get('foreign_rate')}
- 최근 3일 수급 동향:
{deals_text}

[현재 글로벌 매크로 환경]
- 원/달러 환율: {macro_data.get('USDKRW')} 원 | 미국 나스닥: {macro_data.get('NASDAQ')} pt

위 종목을 5대 전문 부서(매크로 전략실, 리서치센터, 리스크 검증 레드팀, 수급·테크니컬 퀀트팀, 최고투자책임자 CIO)의 시각에서 철저히 교차 검증하여 [원클릭 종목 종합 건강 진단서]를 작성해주세요.

다음 서식을 준수하여 완결된 문장으로 작성해주세요:

### 🏆 5대 부서 종합 건강 평점: [0~100점] / 등급: [S / A / B / C / D]
- **한 줄 최종 처방:** (예: "가치주의 함정 주의 - 매수 보류" 또는 "실적과 수급이 뒷받침되는 강력 매수 추천")

---
### 1. 🌐 매크로 전략실 진단
- 환율 및 글로벌 거시 환경이 본 종목 비즈니스 모델에 미치는 영향

### 2. 📊 펀더멘털 리서치센터 진단 (버핏 해자 & 밸류)
- PER, PBR, 배당수익률, 비즈니스 경쟁력 평가

### 3. 🩸 리스크 검증 레드팀 (악마의 대변인 비판)
- 찰리 멍거식 역발상: 이 종목이 폭락할 수 있는 치명적 결함, 실적 피크아웃, 밸류 트랩 가능성 고발

### 4. 📈 수급 & 테크니컬 퀀트 진단
- 외국인/기관 스마트머니 자금 흐름, 52주 가격 위치 대비 진입 타이밍 진단

### 5. 🛡️ CIO 최종 처방전 및 행동 요령
- 200만 원 소액 계좌 투자자를 위한 구체적 행동 지침 (지금 매수 vs 관망 vs 손절/비중축소)
"""
    system_instruction = """당신은 고객의 자산을 엄격하게 보호하는 5대 전문 부서 합동 투자심의위원회입니다.
근거 없는 장밋빛 낙관론을 철저히 배제하고, 워렌 버핏과 찰리 멍거의 가치투자 및 리스크 관리 원칙에 따라 냉철하고 정확하게 진단서를 발급합니다."""

    return client.generate(prompt, system_instruction=system_instruction, max_output_tokens=3000)

# ----------------------------------------------------------
# 2. 미국 주식 (S&P 500 / NASDAQ / 글로벌)
# ----------------------------------------------------------
def get_us_stock_data(ticker: str) -> dict:
    """
    Yahoo Finance 및 네이버 해외증권 API를 통해 미국 종목의 실시간 시세 및 월가 컨센서스를 추출합니다.
    """
    clean_ticker = ticker.upper().strip().replace('.', '-')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # 1. Yahoo Finance Chart
    url_yahoo = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_ticker}?interval=1d&range=5d"
    try:
        r_yahoo = requests.get(url_yahoo, headers=headers, timeout=5).json()
        meta = r_yahoo['chart']['result'][0]['meta']
    except Exception as e:
        return {"error": f"미국 시세 수신 실패 ({clean_ticker}): {str(e)}"}

    # 2. Naver Overseas Consensus
    naver_ticker = clean_ticker.replace('-', '.')
    naver_candidates = [f"{naver_ticker}.O", f"{naver_ticker}.N", naver_ticker]
    cns_data = {}
    summary_text = ""
    
    for nt in naver_candidates:
        u_nav = f"https://api.stock.naver.com/stock/{nt}/integration"
        try:
            r_nav = requests.get(u_nav, headers=headers, timeout=2).json()
            cns = r_nav.get("consensusInfo", {})
            if cns:
                cns_data = cns
                summary_text = r_nav.get("summaries", {}).get("summary", "")
                break
        except:
            pass

    price_usd = meta.get("regularMarketPrice", 0)
    change_pct = meta.get("regularMarketChangePercent", 0)
    hi_52 = meta.get("fiftyTwoWeekHigh", 0)
    lo_52 = meta.get("fiftyTwoWeekLow", 0)
    company_name = meta.get("longName", clean_ticker)

    # 환율 조회하여 원화 환산 가격 계산
    macro_data = get_live_macro_indicators()
    fx_str = macro_data.get('USDKRW', '1,350').replace(',', '')
    try:
        fx_val = float(fx_str)
    except:
        fx_val = 1350.0
    price_krw = int(price_usd * fx_val)

    return {
        "market": "US",
        "ticker": clean_ticker,
        "name": company_name,
        "currency": meta.get("currency", "USD"),
        "price_usd": price_usd,
        "current_price": price_usd,
        "price_krw": price_krw,
        "change_pct": change_pct,
        "high_52w": hi_52,
        "low_52w": lo_52,
        "target_price": cns_data.get("priceTargetMean", 0),
        "target_mean": cns_data.get("priceTargetMean", "N/A"),
        "target_high": cns_data.get("priceTargetHigh", "N/A"),
        "target_low": cns_data.get("priceTargetLow", "N/A"),
        "recomm_mean": cns_data.get("recommMean", "N/A"),
        "summary": summary_text,
        "exchange": meta.get("fullExchangeName", "US Market")
    }

def diagnose_us_stock_with_ai(stock_data: dict, api_key=None) -> str:
    """
    5대 가상 전문 부서의 시각으로 미국 종목을 다각적 심의하여 글로벌 종합 건강 진단서를 발급합니다.
    """
    client = GeminiClient(api_key=api_key)
    macro_data = get_live_macro_indicators()

    prompt = f"""
[분석 대상 미국 종목 데이터]
- 종목명: {stock_data.get('name')} (티커: {stock_data.get('ticker')}) | 거래소: {stock_data.get('exchange')}
- 실시간 주가: ${stock_data.get('price_usd'):,.2f} USD (원화 환산 약 {stock_data.get('price_krw'):,} 원)
- 오늘 등락률: {stock_data.get('change_pct'):+.2f}%
- 52주 최고가: ${stock_data.get('high_52w'):,.2f} | 52주 최저가: ${stock_data.get('low_52w'):,.2f}
- 월가 애널리스트 목표주가 평균: ${stock_data.get('target_mean')} (최고 ${stock_data.get('target_high')} / 최저 ${stock_data.get('target_low')})
- 월가 투자의견 종합 평점: {stock_data.get('recomm_mean')} / 5.0 (4.0 이상: 매수 우위)
- 기업 비즈니스 개요: {stock_data.get('summary') if stock_data.get('summary') else '글로벌 대표 우량주'}

[현재 글로벌 매크로 환경]
- 원/달러 환율: {macro_data.get('USDKRW')} 원 | 미국 나스닥 지수: {macro_data.get('NASDAQ')} pt

위 미국 주식을 5대 전문 부서(매크로 전략실, 리서치센터, 리스크 검증 레드팀, 월가 수급·퀀트팀, 최고투자책임자 CIO)의 시각에서 철저히 교차 검증하여 [🇺🇸 미국 주식 원클릭 종합 건강 진단서]를 작성해주세요.

다음 서식을 준수하여 완결된 문장으로 작성해주세요:

### 🏆 5대 부서 종합 건강 평점: [0~100점] / 등급: [S / A / B / C / D]
- **한 줄 최종 처방:** (예: "독보적 AI 해자 보유 - 적극 분할 매수" 또는 "밸류에이션 고평가 주의 - 조정 시 매수")

---
### 1. 🌐 글로벌 매크로 & 통화(달러) 환경 진단
- 미국 금리, 달러 환율({macro_data.get('USDKRW')}원) 환경이 본 기업 실적 및 한국 투자자 환차익에 미치는 영향

### 2. 📊 펀더멘털 리서치센터 진단 (워렌 버핏 해자 & Moat)
- 글로벌 시장 독점력, 잉여현금흐름(FCF), 브랜드 파워, 주주환원(자사주 매입/배당) 평가

### 3. 🩸 리스크 검증 레드팀 (월가 공매도 펀드 시각)
- 찰리 멍거식 역발상: 빅테크 반독점 규제, AI CAPEX 버블론, 중국 리스크, 최악의 하락 시나리오(Bear Case) 고발

### 4. 📈 월가 수급 & 테크니컬 퀀트 진단
- 월가 목표주가(${stock_data.get('target_mean')}) 대비 현재가 괴리율, 52주 가격 밴드 내 매수 타이밍 진단

### 5. 🛡️ CIO 최종 처방전 및 200만 원 계좌 맞춤 가이드
- 소액 계좌(200만 원) 투자자를 위한 구체적 행동 지침 (소수점 매매 비중 배정, 적정 진입 단가)
"""
    system_instruction = """당신은 글로벌 탑티어 헤지펀드의 5대 전문 부서 합동 투자심의위원회입니다.
워렌 버핏과 찰리 멍거의 가치투자 원칙에 입각하여, 과장된 기술주 거품을 경계하고 진짜 지속 가능한 해자를 지닌 기업인지 냉정하게 검증합니다."""

    return client.generate(prompt, system_instruction=system_instruction, max_output_tokens=3000)
