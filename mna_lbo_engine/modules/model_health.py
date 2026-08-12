"""
Model Health Center & Deal Quality Engine.
Computes Model Health (VALID, REVIEW REQUIRED, INVALID),
Assumption Risk mapping, and a Deal Quality Score.
"""

from typing import Dict, Any

def evaluate_model_health(
    dcf_res: Dict[str, Any], 
    ma_res: Dict[str, Any], 
    lbo_res: Dict[str, Any],
    data_quality_issues: list
) -> Dict[str, Any]:
    """
    Check critical errors across all modules.
    Returns: status (🟢 VALID, 🟡 REVIEW REQUIRED, 🔴 INVALID) and a list of flags.
    """
    flags = []
    is_invalid = False
    is_warning = False

    # Engine Status Checks
    if dcf_res.get("status") == "INVALID":
        flags.append(f"🔴 DCF Engine: {dcf_res.get('message', 'INVALID')}")
        is_invalid = True
    if ma_res.get("status") == "INVALID":
        flags.append(f"🔴 M&A Engine: {ma_res.get('message', 'INVALID')}")
        is_invalid = True
    if lbo_res.get("status") == "INVALID":
        flags.append(f"🔴 LBO Engine: {lbo_res.get('message', 'INVALID')}")
        is_invalid = True

    # DCF Checks
    if not is_invalid and dcf_res.get("terminal_value", 0) < 0:
        flags.append("🔴 DCF Terminal Value is negative.")
        is_invalid = True
    
    spread = dcf_res.get("value_creation_spread", 0)
    if spread < 0:
        flags.append(f"🟡 DCF ROIC < WACC (Negative Spread: {spread*100:.1f}%).")
        is_warning = True

    # M&A Checks
    if not is_invalid and ma_res.get("is_accretive") is False:
        flags.append("🟡 M&A Deal is Dilutive to EPS.")
        is_warning = True
    
    if not is_invalid and ma_res.get("break_even_pre_tax_synergy", 0) > (ma_res.get("pre_tax_synergies", 0) * 5):
        flags.append("🔴 M&A Break-Even synergy required is highly unrealistic (>5x entered).")
        is_invalid = True

    # LBO Checks
    if not is_invalid and lbo_res.get("sponsor_initial_equity", 0) <= 0:
        flags.append("🔴 LBO Sponsor Initial Equity is zero or negative.")
        is_invalid = True
        
    # Data Quality Checks
    for issue in data_quality_issues:
        if issue["severity"] == "HARD ERROR":
            flags.append(f"🔴 Data: {issue['message']}")
            is_invalid = True
        elif issue["severity"] == "WARNING":
            flags.append(f"🟡 Data: {issue['message']}")
            is_warning = True

    status = "🟢 VALID"
    if is_warning:
        status = "🟡 REVIEW REQUIRED"
    if is_invalid:
        status = "🔴 INVALID"

    return {
        "status": status,
        "flags": flags
    }

def calculate_deal_quality(
    dcf_res: Dict[str, Any], 
    ma_res: Dict[str, Any], 
    lbo_res: Dict[str, Any],
    comps_res: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes a transparent Deal Quality breakdown.
    Refuses to score if any engine is invalid.
    """
    if any(res.get("status") == "INVALID" for res in [dcf_res, ma_res, lbo_res]):
        return {"score": "UNAVAILABLE", "components": ["Model is INVALID."]}
        
    score = 0
    components = []

    # 1. Valuation Attractiveness (Spot vs DCF)
    spot = dcf_res.get("current_price", 0)
    intrinsic = dcf_res.get("implied_share_price", 0)
    if intrinsic > spot * 1.2:
        score += 20
        components.append(f"✅ High Valuation Upside (Intrinsic {intrinsic:.2f} > Spot {spot:.2f}) [+20 pts]")
    elif intrinsic > spot:
        score += 10
        components.append(f"✅ Moderate Valuation Upside [+10 pts]")
    else:
        components.append(f"❌ Valuation Downside (Intrinsic {intrinsic:.2f} < Spot {spot:.2f}) [0 pts]")

    # 2. EPS Accretion
    if ma_res.get("is_accretive", False):
        score += 20
        components.append("✅ Deal is EPS Accretive [+20 pts]")
    else:
        components.append("❌ Deal is EPS Dilutive [0 pts]")

    # 3. LBO Returns
    irr = lbo_res.get("irr", 0)
    if irr >= 0.20:
        score += 20
        components.append(f"✅ Strong LBO Returns (IRR {irr*100:.1f}%) [+20 pts]")
    elif irr >= 0.15:
        score += 10
        components.append(f"✅ Acceptable LBO Returns (IRR {irr*100:.1f}%) [+10 pts]")
    else:
        components.append(f"❌ Poor LBO Returns (IRR {irr*100:.1f}%) [0 pts]")
        
    # 4. Synergy Dependency
    req_syn = ma_res.get("break_even_pre_tax_synergy", 0)
    act_syn = ma_res.get("pre_tax_synergies", 0)
    if req_syn <= 0:
        score += 20
        components.append("✅ Accretive before synergies [+20 pts]")
    elif act_syn >= req_syn:
        score += 10
        components.append("✅ Synergies cover accretion shortfall [+10 pts]")
    else:
        components.append("❌ Heavy synergy dependence for accretion [0 pts]")

    final_score = (score / 80.0) * 100.0

    return {
        "score": final_score,
        "components": components
    }
