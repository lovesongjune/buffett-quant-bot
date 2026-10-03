# ==========================================================
# 가상 AI 증권사: 5대 전문 부서 멀티 에이전트 투자심의위원회
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

def _format_candidates(candidates):
    cands_summary = []
    for i, s in enumerate(candidates, 1):
        cands_summary.append(
            f"{i}. {s['Name']}({s['Code']}) | ROE 3년평균: {s['ROE_Avg3']:.1f}% | 영업이익률: {s['OP_Margin']:.1f}% | "
            f"PER: {s['PER']:.1f} | PBR: {s['PBR']:.2f} | 부채비율: {s['Debt_Ratio']:.1f}% | 6M추세: {s.get('Mom_6M', 0)*100:+.1f}%"
        )
    return "\n".join(cands_summary)

class MacroStrategistAgent:
    """🌐 1. 글로벌 거시경제 & 시황 전략가 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 월가와 여의도 탑티어 증권사의 [글로벌 매크로 수석 이코노미스트 / 시황 전략가]입니다.
KOSPI, KOSDAQ, 미국 나스닥, 환율, 금리 등의 거시경제 지표를 종합하여 냉철하게 시장 국면을 진단하고, 
투자심의위원회에 '권장 주식/현금 비중'과 '글로벌 거시 리스크 및 기회 요인'을 명확히 브리핑해야 합니다."""

    def analyze(self, is_bull, kospi_val, sma200, macro_data):
        prompt = f"""
[실시간 시장 데이터 브리핑]
- KOSPI 현재 지수: {kospi_val:,.1f} pt
- KOSPI 200일선 (생명선): {sma200:,.1f} pt
- 200일선 대비 국면: {"200일선 상회 (기술적 강세장)" if is_bull else "200일선 하회 (경계/약세장)"}
- 원/달러 환율: {macro_data.get('USDKRW')} 원
- 미국 나스닥 지수: {macro_data.get('NASDAQ')} pt ({macro_data.get('NASDAQ_COMP')})

위 지표를 바탕으로 [글로벌 매크로 시황 진단 보고서]를 작성해주세요:
1. 시장 국면 총평 (강세장 / 중립 / 약세장 판단 및 핵심 근거)
2. 글로벌 거시 리스크 및 기회 요인 (환율 변동성, 미 증시 추세가 한국 증시에 미치는 영향)
3. 권장 자산배분 비중 (예: 주식 70% : 현금 30% 등 명확한 비율 및 이유 제시)

전문적이고 날카로운 최고 이코노미스트의 어조로 완결된 문장으로 서술해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

class EquityAnalystAgent:
    """📊 2. 기업분석 & 펀더멘털 리서치센터장 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 여의도 최고의 [기업분석 & 컨센서스 리서치센터장]입니다.
워렌 버핏의 가치투자 철학(높은 3년 평균 ROE, 영업이익률, 해자, 합리적 밸류에이션)을 기반으로,
제시된 10개 우량주 후보의 재무 건전성과 비즈니스 경쟁력을 분석하여 투자심의위원회에 펀더멘털 리포트를 제출해야 합니다."""

    def analyze(self, candidates):
        cands_text = _format_candidates(candidates)
        prompt = f"""
[선별된 버핏 퀀트 TOP 10 후보 기업 재무 지표]
{cands_text}

위 10개 기업 리스트를 분석하여 [기업 펀더멘털 & 밸류에이션 종합 리포트]를 작성해주세요:
1. 10개 기업의 산업군 분산도 및 해자(Moat) 총평 (성장주/가치주/경기방어주의 균형 평가)
2. 가장 독보적인 펀더멘털을 지닌 핵심 Top 3 주도주 심층 분석 (ROE, 영업이익률, 밸류에이션 근거)
3. 펀더멘털 관점에서 점검이 필요한 기업 코멘트

실제 증권사 리서치센터장의 신뢰감 있고 통찰력 있는 문체로 완결된 문장으로 작성해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

class RiskRedTeamAgent:
    """🩸 3. 리스크 검증 레드팀 (Devil's Advocate / 공매도 펀드 시각) 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 글로벌 롱숏 헤지펀드의 [공매도·리스크 검증 레드팀장 (Devil's Advocate)]입니다.
찰리 멍거의 'Invert, always invert(역발상하라, 항상 반대로 뒤집어 생각하라)' 원칙에 따라,
모두가 매수를 외칠 때 '이 주식이 폭락할 수 있는 치명적 결함과 지뢰'를 집요하게 파헤치는 악마의 대변인 역할을 수행합니다.
리서치센터의 낙관적 편향을 무자비하게 비판하여 투자자의 소중한 원금을 지키는 것이 유일한 임무입니다."""

    def challenge(self, candidates, equity_report):
        cands_text = _format_candidates(candidates)
        prompt = f"""
[선별된 버핏 퀀트 TOP 10 후보 기업]
{cands_text}

[리서치센터의 펀더멘털 분석 내용]
{equity_report}

위 10개 종목에 대해 '공매도 펀드 및 악마의 대변인' 관점에서 [리스크 검증 레드팀 보고서]를 작성해주세요:
1. ⚠️ 잠재 지뢰 종목 경고: 10개 종목 중 '실적 피크아웃(정점 통과 후 하락)' 또는 '가치주의 함정(Value Trap, 싸 보이지만 계속 하락)'에 빠질 위험이 가장 큰 종목 2~3개 지목 및 치명적 취약점 폭로
2. 📉 최악의 침체 시나리오 (Bear Case): 환율 급등이나 글로벌 경기 침체 발생 시 가장 치명적인 타격을 입을 산업군 경고
3. 🩸 10개 기업 위험도 분류: 10개 기업을 [안전(Low Risk) / 관찰(Medium Risk) / 경계(High Risk)]로 가차 없이 분류

칭찬은 일체 배제하고 냉철하고 신랄한 리스크 감별사의 어조로 완결된 문장으로 서술해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

class TechnicalFlowQuantAgent:
    """📈 4. 수급 & 테크니컬 퀀트팀 (Smart Money Flow & Momentum Lab) 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 시장 자금 흐름과 가격 모멘텀을 전문 추적하는 [수급 & 테크니컬 퀀트 헤드]입니다.
'아무리 좋은 기업이라도 수급과 모멘텀이 따르지 않으면 주가는 움직이지 않는다'는 원칙을 가집니다.
10개 종목의 6개월 수익률 모멘텀, 이평선 추세, 외국인·기관 스마트머니의 수급 쏠림을 분석하여 최적의 진입 시점과 우선순위를 도출합니다."""

    def analyze_flows(self, candidates, macro_data):
        cands_text = _format_candidates(candidates)
        prompt = f"""
[10개 후보 기업의 모멘텀 및 밸류 지표]
{cands_text}

[매크로 환경]
- 환율: {macro_data.get('USDKRW')} 원 | 나스닥: {macro_data.get('NASDAQ')} pt

위 데이터를 기반으로 [수급 & 테크니컬 퀀트 전략 보고서]를 작성해주세요:
1. 🚀 모멘텀 주도주 식별: 6개월 추세와 모멘텀이 가장 강하게 살아있는 TOP 3 종목과 추세 지속력 분석
2. 📊 기술적 저평가 반등 후보: 주가는 눌려있으나 바닥 지지선 구축 후 기술적 반등(Turnaround) 잠재력이 높은 종목
3. ⏱️ 최적 진입 타이밍 & 분할 매수 가이드: 현재 시장 상황에서 즉시 우선 매수할 종목과 눌림목 조정을 기다려야 할 종목 구분

정량적 데이터에 기반한 실전 퀀트 트레이더의 날카롭고 직관적인 어조로 완결된 문장으로 서술해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

class CIOAgent:
    """🛡️ 5. 최고투자책임자(CIO) & 투자심의위원장 에이전트"""
    def __init__(self, client: GeminiClient):
        self.client = client
        self.role = """당신은 고객의 소중한 자산을 총괄 운용하는 [투자심의위원장 겸 최고투자책임자(CIO)]입니다.
워렌 버핏처럼 원금 보존을 최우선으로 하며, 4대 전문 부서(매크로 전략실, 리서치센터, 레드팀, 수급퀀트팀)의 격론을 종합 심의하여
'전재산 200만 원'이라는 소액 계좌에 가장 안전하고도 복리 수익을 극대화할 수 있는 최종 투자 의결서를 작성합니다."""

    def deliberate(self, macro_report, equity_report, risk_report, flow_report, budget_val, targets):
        prompt = f"""
[1. 🌐 매크로 전략실 보고서]
{macro_report}

[2. 📊 기업분석 리서치센터 보고서]
{equity_report}

[3. 🩸 리스크 검증 레드팀 보고서 (공매도·비판 시각)]
{risk_report}

[4. 📈 수급 & 테크니컬 퀀트팀 보고서 (모멘텀·타이밍)]
{flow_report}

[5. 계좌 제약 조건]
- 총 운용 자금: {budget_val:,} 원 (소중한 200만 원 종자돈)
- 포트폴리오 크기: 10개 대형 우량주 분산
- 1주당 단가: 종목당 배정액(약 19만 원) 이하로 최적 분할

위 4개 전문 부서의 격론을 종합 심의하여 [투자심의위원회 최종 의결서]를 작성해주세요:
1. 🏛️ 4대 부서 격론 종합 및 교차 검증 (리서치센터의 낙관론 vs 레드팀의 비판 vs 수급팀의 타이밍 대조 평가)
2. 📋 10개 종목 다각적 컨센서스 스코어카드 (각 종목별 합의 종합 점수 100점 만점 및 투자 등급: Strong Buy / Buy / Neutral / Underweight 제시)
3. 🛡️ 200만 원 계좌 최종 자산배분 승인 및 리스크 관리 지침 (주식 비중 vs 현금 버퍼 비중 확정)
4. 💬 고객(투자자)에게 전하는 CIO의 당부의 한마디 (단기 변동성에 흔들리지 않는 워렌 버핏식 원금 보존 마인드셋)

품격 있고 든든하며 신뢰감을 주는 최고투자책임자의 어조로 작성해주시고, 문장이 도중에 끊기지 않도록 끝까지 완결된 문장으로 서술해주세요.
"""
        return self.client.generate(prompt, system_instruction=self.role)

def run_investment_committee(budget_val, candidates, is_bull, kospi_val, sma200, api_key=None):
    """
    5개 전문 부서 AI 에이전트가 유기적으로 회의를 진행하고 종합 회의록을 반환합니다.
    """
    client = GeminiClient(api_key=api_key)
    macro_data = get_live_macro_indicators()
    
    macro_agent = MacroStrategistAgent(client)
    equity_agent = EquityAnalystAgent(client)
    risk_agent = RiskRedTeamAgent(client)
    flow_agent = TechnicalFlowQuantAgent(client)
    cio_agent = CIOAgent(client)
    
    # 1. 매크로 시황 진단
    macro_report = macro_agent.analyze(is_bull, kospi_val, sma200, macro_data)
    
    # 2. 펀더멘털 리서치센터 분석
    equity_report = equity_agent.analyze(candidates)
    
    # 3. 리스크 검증 레드팀 (Devil's Advocate) 비판 심의
    risk_report = risk_agent.challenge(candidates, equity_report)
    
    # 4. 수급 & 테크니컬 퀀트 모멘텀 진단
    flow_report = flow_agent.analyze_flows(candidates, macro_data)
    
    # 5. CIO 종합 심의 및 최종 의결서 작성
    cio_memo = cio_agent.deliberate(macro_report, equity_report, risk_report, flow_report, budget_val, candidates)
    
    return {
        "macro_report": macro_report,
        "equity_report": equity_report,
        "risk_report": risk_report,
        "flow_report": flow_report,
        "cio_memo": cio_memo,
        "macro_data": macro_data
    }
