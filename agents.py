# ==========================================================
# 가상 AI 증권사: 멀티 에이전트 투자심의위원회 (Multi-Agent Committee)
# ==========================================================
import json
import requests
from gemini_client import GeminiClient

def get_live_macro_indicators():
    """실시간 거시경제 지표 수집 (환율, 나스닥 등)"""
    indicators = {}
    try:
        # 1. 원/달러 환율
        r_fx = requests.get('https://m.stock.naver.com/api/marketIndex/FX_USDKRW/basic', headers={'User-Agent': 'Mozilla/5.0'}, timeout=3).json()
        indicators['USDKRW'] = r_fx.get('closePrice', '1,350.0')
    except:
        indicators['USDKRW'] = '1,350.0'
        
    try:
        # 2. 미국 나스닥 (NASDAQ)
        r_nasdaq = requests.get('https://m.stock.naver.com/api/index/.IXIC/basic', headers={'User-Agent': 'Mozilla/5.0'}, timeout=3).json()
        indicators['NASDAQ'] = r_nasdaq.get('closePrice', '18,000.0')
        indicators['NASDAQ_COMP'] = r_nasdaq.get('compareToPreviousPrice', {}).get('text', '보합')
    except:
        indicators['NASDAQ'] = '18,000.0'
        indicators['NASDAQ_COMP'] = '보합'
        
    return indicators

class MacroStrategistAgent:
    """🌐 글로벌 거시경제 & 시황 전략가 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 월가와 여의도 탑티어 증권사의 [글로벌 매크로 수석 이코노미스트 / 시황 전략가]입니다.
KOSPI, KOSDAQ, 미국 나스닥, 환율, 금리 등의 거시경제 지표를 종합하여 냉철하게 시장 국면을 진단하고, 
투자심의위원회에 '권장 주식/현금 비중'과 '글로벌 리스크 요인'을 브리핑해야 합니다."""

    def analyze(self, is_bull, kospi_val, sma200, macro_data):
        prompt = f"""
[실시간 시장 데이터 브리핑]
- KOSPI 현재 지수: {kospi_val:,.1f} pt
- KOSPI 200일선 (생명선): {sma200:,.1f} pt
- 200일선 대비 국면: {"200일선 상회 (기술적 강세장)" if is_bull else "200일선 하회 (경계/약세장)"}
- 원/달러 환율: {macro_data.get('USDKRW')} 원
- 미국 나스닥 지수: {macro_data.get('NASDAQ')} pt ({macro_data.get('NASDAQ_COMP')})

위 지표를 바탕으로 [글로벌 매크로 시황 진단 보고서]를 3개 항목으로 작성해주세요:
1. 시장 국면 총평 (강세장 / 중립 / 약세장 판단 및 근거)
2. 글로벌 거시 리스크 및 기회 요인 (환율, 미 증시 영향)
3. 권장 자산배분 비중 (예: 주식 70% : 현금 30% 등 명확한 비율 제시)
전문적이고 날카로운 증권사 리포트 어조로 답변해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

class EquityAnalystAgent:
    """📊 기업분석 & 컨센서스 리서치센터장 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 여의도 최고의 [기업분석 & 컨센서스 리서치센터장]입니다.
워렌 버핏의 가치투자 철학(높은 ROE, 경제적 해자, 합리적 PER/PBR, 안정적 부채비율)을 기반으로,
제시된 10개 우량주 후보의 재무 지표와 비즈니스 경쟁력을 분석하여 투자심의위원회에 추천 보고서를 제출해야 합니다."""

    def analyze(self, candidates):
        cands_summary = []
        for i, s in enumerate(candidates, 1):
            cands_summary.append(
                f"{i}. {s['Name']}({s['Code']}) | ROE 3년평균: {s['ROE_Avg3']:.1f}% | 영업이익률: {s['OP_Margin']:.1f}% | "
                f"PER: {s['PER']:.1f} | PBR: {s['PBR']:.2f} | 부채비율: {s['Debt_Ratio']:.1f}% | 6M추세: {s.get('Mom_6M', 0)*100:+.1f}%"
            )
        cands_text = "\n".join(cands_summary)

        prompt = f"""
[선별된 버핏 퀀트 TOP 10 후보 기업]
{cands_text}

위 10개 기업 리스트를 분석하여 [기업 펀더멘털 & 밸류에이션 종합 리포트]를 작성해주세요:
1. 10개 기업의 산업군 분산도 및 해자(Moat) 총평 (성장주/가치주/방어주의 균형 평가)
2. 특히 주목해야 할 핵심 Top 3 주도주 분석 (선정 이유 및 재무 강점)
3. 투자 시 유의해야 할 잠재 리스크 기업 1~2개 코멘트
실제 증권사 리서치센터장의 신뢰감 있고 통찰력 있는 문체로 작성해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

class CIOAgent:
    """🛡️ 최고투자책임자(CIO) & 투자심의위원장 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 고객의 소중한 자산을 총괄 운용하는 [투자심의위원장 겸 최고투자책임자(CIO)]입니다.
워렌 버핏처럼 원금 보존을 최우선으로 하며, 매크로 전략실 보고서와 리서치센터 분석을 종합 심의하여
'전재산 200만 원'이라는 소액 계좌에 가장 안전하고도 복리 수익을 극대화할 수 있는 최종 투자 의결서를 작성합니다."""

    def deliberate(self, macro_report, equity_report, budget_val, targets):
        prompt = f"""
[1. 매크로 전략실 보고서 요약]
{macro_report[:600]}...

[2. 리서치센터 기업분석 요약]
{equity_report[:600]}...

[3. 계좌 제약 조건]
- 총 운용 자금: {budget_val:,} 원 (소중한 200만 원 종자돈)
- 포트폴리오 크기: 10개 대형 우량주 분산
- 1주당 단가: 종목당 배정액(약 19만 원) 이하로 최적 분할

위 두 부서의 보고서를 심의하여 [투자심의위원회 최종 의결서]를 작성해주세요:
1. 종합 심의 결론 (매크로와 기업 실적의 교차 검증 총평)
2. 포트폴리오 승인 및 리스크 관리 지침 (현금 비중 및 원금 보존 원칙)
3. 고객(투자자)에게 전하는 당부의 한마디 (변동성에 흔들리지 않는 장기 복리 마인드셋)
품격 있고 든든하며 신뢰감을 주는 최고투자책임자의 어조로 작성해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

def run_investment_committee(budget_val, candidates, is_bull, kospi_val, sma200, api_key=None):
    """
    3개 부서 AI 에이전트가 유기적으로 회의를 진행하고 종합 회의록을 반환합니다.
    """
    client = GeminiClient(api_key=api_key)
    macro_data = get_live_macro_indicators()
    
    macro_agent = MacroStrategistAgent(client)
    equity_agent = EquityAnalystAgent(client)
    cio_agent = CIOAgent(client)
    
    # 1. 매크로 진단
    macro_report = macro_agent.analyze(is_bull, kospi_val, sma200, macro_data)
    
    # 2. 기업 분석
    equity_report = equity_agent.analyze(candidates)
    
    # 3. CIO 최종 심의 의결
    cio_memo = cio_agent.deliberate(macro_report, equity_report, budget_val, candidates)
    
    return {
        "macro_report": macro_report,
        "equity_report": equity_report,
        "cio_memo": cio_memo,
        "macro_data": macro_data
    }
