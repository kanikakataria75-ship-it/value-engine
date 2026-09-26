"""The frontend's API types must match the backend's response models."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_typescript_types_are_up_to_date():
    spec = importlib.util.spec_from_file_location("generate_ts_types", ROOT / "scripts" / "generate_ts_types.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = module.OUTPUT.read_text(encoding="utf-8")
    assert committed == module.generate(), "Run `python scripts/generate_ts_types.py` and commit the result."
