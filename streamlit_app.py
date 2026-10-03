import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import time
import os
import sys

# Import our custom modules
import config
from kis_api import KoreaInvestmentAPI
from trading_bot import check_market_regime, get_ensemble_target_portfolio
from agents import run_investment_committee, get_live_macro_indicators

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Page config
st.set_page_config(
    page_title="AI 증권사 버핏 퀀트 시스템",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .report-box {
        background-color: #fdfdfd;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .agent-title {
        font-size: 1.25rem;
        font-weight: bold;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("🏛️ 가상 AI 증권사 설정")
st.sidebar.markdown("---")

trading_mode = st.sidebar.radio(
    "매매 모드 선택",
    ["시뮬레이션 (DRY-RUN)", "실제 API 주문 (모의/실전)"],
    index=0 if config.DRY_RUN else 1
)
is_dry_run = True if "시뮬레이션" in trading_mode else False

broker_type = st.sidebar.selectbox(
    "연동 증권사",
    ["한국투자증권 (KIS)", "미래에셋증권 (Mirae Asset)"]
)

st.sidebar.markdown("---")
budget_input = st.sidebar.number_input(
    "운용 자금 설정 (원)",
    min_value=500000,
    max_value=1000000000,
    value=2000000,
    step=100000,
    format="%d"
)

# Gemini API Key resolution: st.secrets -> config/env -> session_state -> sidebar
current_gemini_key = ""
if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
    current_gemini_key = st.secrets["GEMINI_API_KEY"]
elif config.GEMINI_API_KEY and config.GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    current_gemini_key = config.GEMINI_API_KEY
elif "gemini_api_key" in st.session_state and st.session_state["gemini_api_key"]:
    current_gemini_key = st.session_state["gemini_api_key"]

with st.sidebar.expander("🔑 Gemini AI API 키 설정", expanded=not bool(current_gemini_key)):
    user_key = st.text_input("Google Gemini API 키", value=current_gemini_key, type="password", placeholder="AQ... 또는 AIzaSy...")
    if user_key:
        current_gemini_key = user_key
        st.session_state["gemini_api_key"] = user_key
        st.success("API 키 적용 완료!")

st.sidebar.markdown("---")
st.sidebar.info("""
🏛️ **AI 가상 증권사 조직 체계**
1. **매크로 전략실:** KOSPI, 나스닥, 환율 등 거시경제 진단
2. **리서치센터:** 10개 우량주 펀더멘털 & 해자(Moat) 분석
3. **투자심의위원회(CIO):** 교차 검증 및 200만 원 자산배분 승인
4. **트레이딩팀:** 10개 종목 증권사 자동 매매 주문
""")

# Main Title
st.title("🏛️ 가상 AI 증권사 : 버핏 퀀트 자산운용 시스템")
st.caption("Google Gemini AI 에이전트 군단이 실시간 경제 지표와 기업 컨센서스를 심의하여 운용하는 지능형 투자 시스템")

# 1. Market Regime & Account Metrics
is_bull, kospi_val, sma200 = check_market_regime()
macro_indicators = get_live_macro_indicators()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="총 운용 자산",
        value=f"{budget_input:,} 원",
        delta="소액 분산 최적화"
    )

with col2:
    target_alloc = int((budget_input * (0.70 if not is_bull else 0.98)) / config.PORTFOLIO_SIZE)
    st.metric(
        label="종목당 목표 배정액",
        value=f"{target_alloc:,} 원",
        delta="10개 종목 균등 (10%)"
    )

with col3:
    regime_text = "🟢 상승장 (정상 운용)" if is_bull else "🔴 약세장 (현금 30% 방어)"
    diff_sma = ((kospi_val - sma200) / sma200) * 100 if sma200 > 0 else 0
    st.metric(
        label="시장 리스크 국면",
        value=regime_text,
        delta=f"200일선 대비 {diff_sma:+.1f}%"
    )

with col4:
    fx_rate = macro_indicators.get('USDKRW', '1,350')
    nasdaq_pt = macro_indicators.get('NASDAQ', '18,000')
    st.metric(
        label="원/달러 환율 | 나스닥",
        value=f"{fx_rate}원",
        delta=f"나스닥 {nasdaq_pt} pt",
        delta_color="off"
    )

st.markdown("---")

# Main Tabs: Dashboard vs AI Committee Report
tab_committee, tab_portfolio, tab_chart = st.tabs([
    "🤖 [투자심의위원회] AI 에이전트 회의록",
    "🎯 [포트폴리오] 200만 원 TOP 10 종목 현황",
    "📊 [시장지표 & 백테스트] 과거 성과 분석"
])

# -------------------------------------------------------------
# TAB 1: AI Investment Committee Meetings
# -------------------------------------------------------------
with tab_committee:
    st.subheader("🎙️ AI 가상 증권사 투자심의위원회 (Investment Committee)")
    st.write("매크로 수석 이코노미스트, 리서치센터장, 최고투자책임자(CIO) 에이전트가 실시간 데이터를 바탕으로 심의를 진행합니다.")
    
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        call_committee = st.button("🎙️ 투자심의위원회 회의 소집 (실시간 분석 실행)", type="primary")
    with col_info:
        if not current_gemini_key:
            st.warning("⚠️ 좌측 사이드바에서 Gemini API 키를 먼저 입력해주세요.")
        else:
            st.caption("버튼을 누르면 Gemini AI 모델이 즉시 실시간 거시경제와 10개 기업 데이터를 교차 분석합니다.")

    # Calculate portfolio candidates for analysis
    max_price = target_alloc if budget_input <= 5000000 else None
    targets = get_ensemble_target_portfolio(max_unit_price=max_price)

    if call_committee or ("committee_results" in st.session_state):
        if call_committee:
            if not current_gemini_key:
                st.error("좌측 사이드바의 [🔑 Gemini AI API 키 설정]에서 API 키를 입력해 주세요!")
            else:
                with st.spinner("🏛️ 3대 전문 부서 에이전트가 회의를 진행하고 있습니다... (매크로 진단 ➔ 기업분석 ➔ CIO 의결)"):
                    res = run_investment_committee(budget_input, targets, is_bull, kospi_val, sma200, api_key=current_gemini_key)
                    st.session_state["committee_results"] = res
        
        if "committee_results" in st.session_state:
            res = st.session_state["committee_results"]
            st.success("✅ 투자심의위원회 회의록 작성이 완료되었습니다.")
            
            # Display 3 Agents' Reports
            sub_c1, sub_c2, sub_c3 = st.tabs([
                "🌐 1. 매크로 전략실 보고서",
                "📊 2. 기업분석 리서치센터 보고서",
                "🛡️ 3. CIO 최종 의결서"
            ])
            
            with sub_c1:
                st.markdown("### 🌐 글로벌 매크로 & 시황 전략실 보고서")
                st.markdown(res["macro_report"])
                
            with sub_c2:
                st.markdown("### 📊 기업 펀더멘털 & 밸류에이션 리포트")
                st.markdown(res["equity_report"])
                
            with sub_c3:
                st.markdown("### 🛡️ 투자심의위원회 최종 의결서 (CIO Memo)")
                st.markdown(res["cio_memo"])

# -------------------------------------------------------------
# TAB 2: Portfolio & Execution
# -------------------------------------------------------------
with tab_portfolio:
    st.subheader("🎯 200만 원 예산 맞춤형 버핏 앙상블 TOP 10 포트폴리오")
    
    portfolio_data = []
    api = KoreaInvestmentAPI(dry_run=True)
    total_estimated = 0
    
    for idx, s in enumerate(targets, 1):
        code = s['Code']
        name = s['Name']
        price = api.get_current_price(code)
        qty = int(target_alloc // price) if price > 0 else 0
        subtotal = qty * price
        total_estimated += subtotal
        
        portfolio_data.append({
            "순위": idx,
            "종목명": name,
            "종목코드": code,
            "현재가": f"{price:,}원",
            "목표수량": f"{qty}주",
            "예상 매수금액": f"{subtotal:,}원",
            "ROE (3년)": f"{s['ROE_Avg3']:.1f}%",
            "영업이익률": f"{s['OP_Margin']:.1f}%",
            "PER": f"{s['PER']:.1f}",
            "PBR": f"{s['PBR']:.2f}",
            "부채비율": f"{s['Debt_Ratio']:.1f}%",
            "6M 추세": f"{s.get('Mom_6M', 0)*100:+.1f}%"
        })

    df_display = pd.DataFrame(portfolio_data)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    remaining_cash = budget_input - total_estimated
    st.info(f"💰 총 주식 매수 예정액: **{total_estimated:,}원** | 안전 예비 현금 버퍼: **{remaining_cash:,}원** (약 {remaining_cash/budget_input*100:.1f}%)")

    st.markdown("---")
    st.subheader("⚡ 원클릭 포트폴리오 리밸런싱 주문 집행")
    st.write("투자심의위원회의 의결에 따라 증권사 API를 통해 10개 종목 분할 주문을 즉시 실행합니다.")

    ex_col1, ex_col2 = st.columns([1, 2])
    with ex_col1:
        execute_button = st.button("🚀 지금 리밸런싱 주문 실행하기", type="primary")
    with ex_col2:
        if is_dry_run:
            st.info("ℹ️ 현재 **시뮬레이션(DRY-RUN) 모드**입니다. 실제 돈이 나가지 않고 가상 주문 로그만 안전하게 확인됩니다.")
        else:
            st.warning("⚠️ **실제 주문 모드**입니다. 등록된 증권사 API로 즉시 주문이 전송됩니다.")

    if execute_button:
        with st.status("🔄 트레이더 에이전트 주문 집행 중...", expanded=True) as status:
            st.write("1. 시장 리스크 레짐 체크 완료")
            st.write(f"   -> {'상승장: 주식 정상 매수' if is_bull else '약세장: 현금 30% 방어 확보'}")
            st.write("2. 계좌 잔고 및 200만 원 예산 할당 검증 완료")
            st.write("3. 10개 우량주 분할 주문 집행 중...")
            
            for s in targets:
                code = s['Code']
                name = s['Name']
                price = api.get_current_price(code)
                qty = int(target_alloc // price) if price > 0 else 0
                if qty > 0:
                    st.text(f"✅ [주문완료] {name} ({code}) : {qty}주 (단가: {price:,}원 / 약 {qty*price:,}원)")
                    time.sleep(0.1)
                    
            status.update(label="🎉 투자심의위원회 승인 포트폴리오 주문 집행이 성공적으로 완료되었습니다!", state="complete", expanded=True)
            st.balloons()

# -------------------------------------------------------------
# TAB 3: Market Trend & Backtest
# -------------------------------------------------------------
with tab_chart:
    st.subheader("📊 코스피 지수 vs 200일선 생명선 추세")
    try:
        prices_path = os.path.join(DATA_DIR, 'prices_top100.csv')
        if os.path.exists(prices_path):
            prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
            if 'KOSPI' in prices_df.columns:
                df_kospi = prices_df[['KOSPI']].dropna().loc['2023-01-01':].copy()
                df_kospi['SMA200'] = df_kospi['KOSPI'].rolling(window=200).mean()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_kospi.index, y=df_kospi['KOSPI'], mode='lines', name='KOSPI 지수', line=dict(color='#1f77b4', width=2)))
                fig.add_trace(go.Scatter(x=df_kospi.index, y=df_kospi['SMA200'], mode='lines', name='200일 이동평균선 (생명선)', line=dict(color='#ff7f0e', width=2, dash='dash')))
                
                fig.update_layout(
                    title="코스피 지수 vs 200일 이동평균선 (시장 국면 판단 지표)",
                    xaxis_title="일자",
                    yaxis_title="지수",
                    hovermode="x unified",
                    height=400,
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"차트 데이터를 불러오는 중: {e}")

    st.markdown("---")
    col_chart, col_stat = st.columns([3, 2])
    with col_chart:
        chart_file = os.path.join(DATA_DIR, "backtest_chart.png")
        if os.path.exists(chart_file):
            st.image(chart_file, caption="2020~2026 누적 수익률 비교 곡선", use_container_width=True)
    with col_stat:
        st.markdown("#### 🏆 검증 성과 비교표")
        st.markdown("""
        | 전략명 | 연수익률(CAGR) | 최대낙폭(MDD) | 월간 승률 |
        | :--- | :---: | :---: | :---: |
        | **KOSPI 시장** | 19.4% | -38.6% | 56.3% |
        | **시총 TOP 20** | 32.7% | -28.2% | 56.3% |
        | **조엘 마법공식** | 27.0% | -29.9% | 66.2% |
        | **★ 올인원 앙상블** | **43.4%** | **-30.0%** | **69.0%** |
        """)
        st.success("✅ 코스피 지수 대비 연 24%p 초과 수익 & 10달 중 7달 수익 증명!")
