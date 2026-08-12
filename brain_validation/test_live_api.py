import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.alpha_vantage_provider import AlphaVantageProvider

provider = AlphaVantageProvider()

print("PROVIDER:", type(provider).__name__)
print("LIVE API PROVIDER IMPORT: PASS")
