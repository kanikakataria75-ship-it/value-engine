"""
AI / LLM Financial Model Copilot.
Generates rigorous, rule-based explanations of model changes without hallucinating.
"""

from typing import Dict, Any

def generate_dcf_explanation(dcf_data: Dict[str, Any]) -> str:
    """Generates an explanation of the DCF model state."""
    price = dcf_data.get("implied_share_price", 0)
    current = dcf_data.get("current_price", 0)
    upside = dcf_data.get("upside_downside_pct", 0)
    spread = dcf_data.get("value_creation_spread", 0) * 100
    wacc = dcf_data.get("wacc", 0) * 100
    term = dcf_data.get("terminal_growth_rate", 0) * 100
    
    explanation = f"The DCF implies a share price of ${price:.2f}, representing a {upside:.1f}% {'premium' if upside > 0 else 'discount'} to the current price of ${current:.2f}. "
    
    if spread > 0:
        explanation += f"The company creates economic value (ROIC exceeds WACC by {spread:.1f}%). "
    else:
        explanation += f"The company destroys economic value (ROIC is below WACC by {abs(spread):.1f}%). "
        
    explanation += f"Terminal value assumes {term:.1f}% growth discounted at a {wacc:.1f}% WACC. "
    
    if (wacc - term) < 2.0:
        explanation += "WARNING: The spread between WACC and Terminal Growth is tight, meaning terminal value constitutes an aggressively large portion of Enterprise Value."
        
    return explanation


def generate_lbo_explanation(lbo_data: Dict[str, Any]) -> str:
    """Generates an explanation of LBO Returns."""
    irr = lbo_data.get("irr", 0) * 100
    moic = lbo_data.get("moic", 0)
    
    attr_ebitda = lbo_data.get("attr_ebitda_growth", 0)
    attr_mult = lbo_data.get("attr_multiple_expansion", 0)
    attr_debt = lbo_data.get("attr_debt_paydown", 0)
    attr_cash = lbo_data.get("attr_cash_generation", 0)
    
    total = attr_ebitda + attr_mult + attr_debt + attr_cash
    
    if total <= 0:
        return "LBO Returns are negative. The sponsor is losing equity value."
        
    explanation = f"The LBO generates a {irr:.1f}% IRR and a {moic:.1f}x MoIC. "
    
    dominant = max([
        (attr_ebitda, "EBITDA Growth"), 
        (attr_mult, "Multiple Expansion"), 
        (attr_debt, "Debt Paydown"), 
        (attr_cash, "Cash Generation")
    ], key=lambda x: x[0])
    
    explanation += f"Value creation is primarily driven by {dominant[1]} ({dominant[0]/total*100:.1f}% of total value created). "
    
    if dominant[1] == "Multiple Expansion":
        explanation += "RELIANCE WARNING: Relying heavily on multiple expansion is risky in high-rate environments."
        
    return explanation
