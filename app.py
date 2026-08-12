"""
Top-level entry point launcher for Streamlit Dashboard.
"""
import os
import sys

# Add mna_lbo_engine to sys.path
engine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mna_lbo_engine")
if engine_dir not in sys.path:
    sys.path.insert(0, engine_dir)

# Import app logic
from mna_lbo_engine.app import *
