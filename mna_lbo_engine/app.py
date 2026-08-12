import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from config import (
    CORPORATE_TAX_RATE,
    DEFAULT_WACC,
    TERMINAL_GROWTH_RATE,
    DEFAULT_REV_GROWTH,
    DEFAULT_EBITDA_MARGIN,
    SENIOR_DEBT_INTEREST,
    PRESET_FINANCIALS,
)
from modules.data_loader import FinancialDataLoader
from modules.dcf_engine import run_dcf
from modules.ma_engine import run_ma_model
from modules.lbo_engine import run_lbo_model
from modules.comps_engine import run_trading_comps, run_transaction_comps
from modules.excel_exporter import ExcelReportExporter
from modules.data_quality_engine import run_data_quality_checks
from modules.model_health import evaluate_model_health, calculate_deal_quality
from modules.risk_engine import run_dcf_monte_carlo, run_stress_test
from modules.copilot_engine import generate_dcf_explanation, generate_lbo_explanation

st.set_page_config(page_title="ValuEngine V2 | Deal Workspace", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .reportview-container { background: #f4f5f7; }
    h1, h2, h3 { color: #1e293b; font-family: 'Inter', sans-serif; font-weight: 600; }
    .stMetric { background-color: #ffffff; padding: 12px; border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border-left: 3px solid #0f172a; }
    .css-1d391kg { padding-top: 1rem; }
    .badge-live { background-color: #059669; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-demo { background-color: #d97706; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-unavail { background-color: #dc2626; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT (Strict Isolation) ---
def init_or_reset_state(ticker_t="AAPL", ticker_a="MSFT", force_reset=False):
    if force_reset or 'deal_id' not in st.session_state:
        st.session_state.deal_id = f"{ticker_t}_{ticker_a}"
        st.session_state.target_ticker = ticker_t
        st.session_state.acquirer_ticker = ticker_a
        st.session_state.target_data = PRESET_FINANCIALS.get(ticker_t, PRESET_FINANCIALS["AAPL"])
        st.session_state.acquirer_data = PRESET_FINANCIALS.get(ticker_a, PRESET_FINANCIALS["MSFT"])
        st.session_state.is_demo_t = True
        st.session_state.is_demo_a = True

        # Flush stale assumptions
        for k in list(st.session_state.keys()):
            if k.startswith("assump_"):
                del st.session_state[k]

init_or_reset_state()

@st.cache_data(ttl=3600)
def fetch_data(ticker): return FinancialDataLoader().fetch_company_financials(ticker)

# --- NAVIGATION WORKFLOW ---
st.sidebar.title("Workflow")
workflow_step = st.sidebar.radio("Navigation", [
    "1. Deal Setup",
    "2. Data Validation",
    "3. Valuation",
    "4. Deal Structure",
    "5. Returns",
    "6. Risk & Review",
    "7. Export"
])

# --- GLOBAL VARIABLES & DATA PREP ---
t_data = st.session_state.target_data
a_data = st.session_state.acquirer_data
currency_t = t_data.get("currency", "USD")
currency_a = a_data.get("currency", "USD")

# UI State variables for inline assumptions
wacc = st.sidebar.number_input("WACC (%)", value=8.5, step=0.1) / 100
term_growth = st.sidebar.number_input("Terminal Growth (%)", value=2.5, step=0.1) / 100
offer_prem = st.sidebar.number_input("M&A Premium (%)", value=25.0, step=1.0) / 100
syn_rev = st.sidebar.number_input("Revenue Synergies ($M)", value=500.0) * 1e6
syn_cost = st.sidebar.number_input("Cost Synergies ($M)", value=200.0) * 1e6
lbo_entry = st.sidebar.number_input("LBO Entry (x)", value=10.0, step=0.5)

# --- DATA VALIDATION GATE ---
dq_issues = run_data_quality_checks(t_data)
a_dq_issues = run_data_quality_checks(a_data)

is_fatal_t = any(i["severity"] == "HARD ERROR" for i in dq_issues)
is_fatal_a = any(i["severity"] == "HARD ERROR" for i in a_dq_issues)

# --- ENGINE EXECUTION (STRICT KWARGS) ---
dcf_res = run_dcf(
    financials=t_data,
    revenue_growth_rate=0.07,
    ebitda_margin=0.25,
    wacc=wacc,
    terminal_growth_rate=term_growth,
    projection_years=5,
    tax_rate=CORPORATE_TAX_RATE,
    mid_year_convention=False
) if not is_fatal_t else {"status": "INVALID", "message": "Fatal data quality issue prevented DCF execution."}

ma_res = run_ma_model(
    acquirer_data=a_data,
    target_data=t_data,
    offer_premium_pct=offer_prem,
    pct_cash=0.5,
    pct_stock=0.5,
    debt_interest_rate=SENIOR_DEBT_INTEREST,
    revenue_synergies=syn_rev,
    incremental_margin=0.20,
    cost_synergies=syn_cost,
    integration_costs=50e6,
    tax_rate=CORPORATE_TAX_RATE
) if not (is_fatal_t or is_fatal_a) else {"status": "INVALID", "message": "Fatal data quality issue in Target or Acquirer prevented M&A execution."}

lbo_res = run_lbo_model(
    target_data=t_data,
    entry_multiple=lbo_entry,
    senior_debt_pct=0.4,
    sub_debt_pct=0.2,
    senior_rate=SENIOR_DEBT_INTEREST,
    sub_rate=0.09,
    exit_multiple=11.0,
    revenue_growth=0.07,
    ebitda_margin=0.25,
    projection_years=5,
    tax_rate=CORPORATE_TAX_RATE
) if not is_fatal_t else {"status": "INVALID", "message": "Fatal data quality issue prevented LBO execution."}

comps_res = run_trading_comps(
    target_data=t_data, 
    peers_data=[PRESET_FINANCIALS["MSFT"], PRESET_FINANCIALS["NVDA"]]
) if not is_fatal_t else {"status": "INVALID", "message": "Fatal data quality issue prevented Comps execution."}

tx_comps_res = run_transaction_comps(
    target_data=t_data, 
    transactions=[] # Explicitly pass empty to show unavailable
) if not is_fatal_t else {"status": "INVALID", "message": "Fatal data quality issue prevented Transaction Comps execution."}

health_res = evaluate_model_health(
    dcf_res=dcf_res, 
    ma_res=ma_res, 
    lbo_res=lbo_res, 
    data_quality_issues=dq_issues
)
dq_score = calculate_deal_quality(
    dcf_res=dcf_res, 
    ma_res=ma_res, 
    lbo_res=lbo_res, 
    comps_res=comps_res
) if health_res["status"] != "🔴 INVALID" else {"score": "UNAVAILABLE", "components": ["Model is INVALID."]}

# --- UI RENDER ---

if workflow_step == "1. Deal Setup":
    st.title("Target × Acquirer | Transaction Analysis")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Target")
        tt = st.text_input("Ticker", st.session_state.target_ticker, key="t_tick").upper()
        if st.button("Load Target"):
            if tt != st.session_state.target_ticker:
                init_or_reset_state(ticker_t=tt, ticker_a=st.session_state.acquirer_ticker, force_reset=True)
                st.rerun()
            
        if st.session_state.is_demo_t:
            st.markdown("<span class='badge-demo'>DEMONSTRATION DATA (NOT LIVE MARKET DATA)</span>", unsafe_allow_html=True)
            st.warning("Live API provider not configured. Using verified cached fallback.")
    with c2:
        st.subheader("Acquirer")
        aa = st.text_input("Ticker", st.session_state.acquirer_ticker, key="a_tick").upper()
        if st.button("Load Acquirer"):
            if aa != st.session_state.acquirer_ticker:
                init_or_reset_state(ticker_t=st.session_state.target_ticker, ticker_a=aa, force_reset=True)
                st.rerun()

        if st.session_state.is_demo_a:
            st.markdown("<span class='badge-demo'>DEMONSTRATION DATA</span>", unsafe_allow_html=True)

elif workflow_step == "2. Data Validation":
    st.title("Data Validation & Provenance")
    st.write(f"**Target Provenance:** {t_data.get('_provenance', 'UNKNOWN')}")
    st.write(f"**Currency:** {currency_t} | **Units:** Millions (internally normalized to absolute)")
    
    if dq_issues:
        for i in dq_issues:
            if i['severity'] == 'HARD ERROR': st.error(f"**{i['metric']}**: {i['message']}")
            else: st.warning(f"**{i['metric']}**: {i['message']}")
    else:
        st.success("All accounting identities validate correctly.")

elif workflow_step == "3. Valuation":
    st.title("Valuation Workspace")
    if dcf_res.get("status") == "INVALID":
        st.error(f"MODEL INVALID: {dcf_res.get('message')}")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("DCF Intrinsic", f"{currency_t} {dcf_res['implied_share_price']:.2f}")
        c2.metric("Trading Comps Median", f"{currency_t} {comps_res.get('implied_share_price_median', 0):.2f}")
        
        tc_price = tx_comps_res.get('implied_share_price_median')
        if not tc_price:
            c3.metric("Transaction Comps", "UNAVAILABLE")
        else:
            c3.metric("Transaction Comps Median", f"{currency_t} {tc_price:.2f}")
            
        st.subheader("Copilot Explainer")
        st.info(generate_dcf_explanation(dcf_res))

elif workflow_step == "4. Deal Structure":
    st.title("M&A Deal Structure")
    if ma_res.get("status") == "INVALID":
        st.error(f"MODEL INVALID: {ma_res.get('message')}")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Offer Premium", f"{offer_prem*100:.1f}%")
        c2.metric("Pro-Forma EPS Change", f"{currency_a} {ma_res['eps_change_dollar']:.2f}")
        c3.metric("Break-Even Pre-Tax Synergy", f"{currency_t} {ma_res['break_even_pre_tax_synergy']/1e6:.1f}M")
        
        if ma_res["break_even_pre_tax_synergy"] <= 0:
            st.success("The transaction is accretive without requiring synergies.")

elif workflow_step == "5. Returns":
    st.title("LBO Returns")
    if lbo_res.get("status") == "INVALID":
        st.error(f"MODEL INVALID: {lbo_res.get('message')}")
    else:
        c1, c2 = st.columns(2)
        c1.metric("IRR", f"{lbo_res['irr']*100:.1f}%")
        c2.metric("MoIC", f"{lbo_res['moic']:.1f}x")
        
        st.subheader("Returns Attribution Copilot")
        st.info(generate_lbo_explanation(lbo_res))

elif workflow_step == "6. Risk & Review":
    st.title("Risk & Stress Testing")
    
    st.subheader("Model Status")
    if health_res["status"] == "🟢 VALID": st.success("VALID")
    elif health_res["status"] == "🟡 REVIEW REQUIRED": st.warning("REVIEW REQUIRED")
    else: st.error("INVALID")
    for flag in health_res["flags"]: st.write("- " + flag)
        
    st.subheader("DCF Monte Carlo Uncertainty")
    if dcf_res.get("status") != "INVALID":
        mc = run_dcf_monte_carlo(
            dcf_func=run_dcf, 
            financials=t_data, 
            base_rev_growth=0.07, 
            base_ebitda_margin=0.25, 
            base_wacc=wacc, 
            base_term_growth=term_growth, 
            tax_rate=CORPORATE_TAX_RATE, 
            mid_year_convention=False, 
            iterations=200
        )
        if mc.get("status") == "VALID":
            c1, c2, c3 = st.columns(3)
            c1.metric("10th Percentile", f"{currency_t} {mc['p10']:.2f}")
            c2.metric("Median", f"{currency_t} {mc['median']:.2f}")
            c3.metric("90th Percentile", f"{currency_t} {mc['p90']:.2f}")
            st.caption("This represents model uncertainty under the selected assumptions. It is a statistical projection, not a prediction.")
        else:
            st.error("Monte Carlo Simulation Invalidated by Constraints.")
            
    st.markdown("---")
    st.subheader("FINANCIAL MODEL COPILOT")
    st.button("Ask the Model (AI Copilot coming soon...)")
    st.caption("This assistant will eventually explain validated model outputs and assumptions natively. (LLM integration deferred)")

elif workflow_step == "7. Export":
    st.title("Audit-Ready Export")
    if st.button("Generate Excel File"):
        exporter = ExcelReportExporter()
        path = exporter.export_full_model(dcf_res, ma_res, lbo_res, "Final_Audit_Model.xlsx")
        with open(path, "rb") as f:
            st.download_button("Download Workstation Export", f, file_name=path)
