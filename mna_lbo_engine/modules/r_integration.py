import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict

R_ANALYTICS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "r_analytics", "valuation_risk")

def is_r_available() -> bool:
    return shutil.which("Rscript") is not None

def call_r_script(script_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    if not is_r_available():
        return {
            "status": "UNAVAILABLE",
            "message": "R is not installed or Rscript is not in PATH."
        }
    
    script_path = os.path.join(R_ANALYTICS_DIR, script_name)
    if not os.path.exists(script_path):
        return {
            "status": "UNAVAILABLE",
            "message": f"R script {script_name} not found."
        }
        
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(input_data, f)
            input_file = f.name
            
        result = subprocess.run(
            ["Rscript", script_path, input_file],
            capture_output=True,
            text=True,
            check=False
        )
        
        os.remove(input_file)
        
        if result.returncode != 0:
            return {
                "status": "UNAVAILABLE",
                "message": f"R execution failed: {result.stderr.strip()}"
            }
            
        try:
            output = json.loads(result.stdout)
            return output
        except json.JSONDecodeError:
            return {
                "status": "UNAVAILABLE",
                "message": f"R script returned invalid JSON: {result.stdout.strip()[:200]}"
            }
            
    except Exception as e:
        return {
            "status": "UNAVAILABLE",
            "message": f"Internal integration error: {str(e)}"
        }
