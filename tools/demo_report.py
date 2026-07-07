"""Generate a sample range report from synthetic data (portfolio demo / smoke test)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml
from src.test_report import FieldReport, Sample, generate

cfg = yaml.safe_load(open(ROOT / "config" / "test_config.yaml"))
rows = [
    (0,   50,   -78, 10.5, 100, "PASS"),
    (60,  250,  -94,  6.2, 100, "PASS"),
    (120, 600,  -108, 1.0,  98, "PASS"),
    (180, 1100, -118, -7.5, 71, "FAIL"),
]
rep = FieldReport(
    "Meshtastic Mesh - Range & Link-Quality Characterization",
    cfg["bench"], cfg["specs"], [Sample(*r) for r in rows],
)
out = generate(rep, str(ROOT / cfg["paths"]["report_dir"]))
print("Report:", out)
print(f"Result: {rep.pass_count} PASS / {rep.fail_count} FAIL")
