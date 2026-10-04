# ==========================================================
# 5대 전문 부서 원클릭 종목 건강검진기 (Single Stock Deep Doctor)
# ==========================================================
import requests
import json
import os
import config
from gemini_client import GeminiClient
from agents import get_live_macro_indicators

def get_stock_doctor_data(code: str) -> dict:
    """
    네이버 증권 API로부터 종목의 실시간 시세, 밸류에이션, 수급 동향을 추출합니다.
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
        "code": code,
        "name": res.get("stockName", code),
        "price": total_infos.get("lastClosePrice", "0"),
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
    5대 가상 전문 부서의 시각으로 해당 종목을 다각적 심의하여 종합 건강 진단서를 발급합니다.
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
[분석 대상 종목 데이터]
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

    return client.generate(prompt, system_instruction=system_instruction, max_output_tokens=8192)
