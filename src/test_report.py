"""
test_report.py — Generate a standalone HTML report from mesh test results.

Pytest produces its own report via pytest-html; this module is for the *field*
tools (range_test / mesh_monitor) which run outside pytest and still need a
shareable engineering deliverable with a link-quality plot.
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Sample:
    elapsed_s: float
    distance_m: float | None
    rssi_dbm: float | None
    snr_db: float | None
    pdr_pct: float | None
    verdict: str  # PASS / FAIL / N/A


@dataclass
class FieldReport:
    title: str
    bench: dict
    specs: dict
    samples: list[Sample] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for s in self.samples if s.verdict == "PASS")

    @property
    def fail_count(self) -> int:
        return sum(1 for s in self.samples if s.verdict == "FAIL")


def _plot(report: FieldReport, out_png: Path) -> bool:
    """Plot link quality vs distance. Returns False if matplotlib unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        logger.warning("matplotlib not available; skipping plot")
        return False

    pts = [s for s in report.samples if s.distance_m is not None]
    if not pts:
        return False
    x = [s.distance_m for s in pts]
    rssi = [s.rssi_dbm for s in pts]
    snr = [s.snr_db for s in pts]

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(x, rssi, "o-", color="#1565C0", label="RSSI (dBm)")
    ax1.set_xlabel("Distance (m)")
    ax1.set_ylabel("RSSI (dBm)", color="#1565C0")
    ax1.axhline(report.specs.get("min_rssi_dbm", -115), ls="--",
                color="#1565C0", alpha=0.4)

    ax2 = ax1.twinx()
    ax2.plot(x, snr, "s-", color="#C62828", label="SNR (dB)")
    ax2.set_ylabel("SNR (dB)", color="#C62828")
    ax2.axhline(report.specs.get("min_snr_db", -10), ls="--",
                color="#C62828", alpha=0.4)

    plt.title("Mesh Link Quality vs. Distance")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    return True


_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
 body{{font-family:'Segoe UI',Arial,sans-serif;margin:36px;background:#f5f7fa;color:#222}}
 .hdr{{background:#1A2744;color:#fff;padding:20px 24px;border-radius:8px}}
 .hdr h1{{margin:0 0 6px 0}}
 .cards{{display:flex;gap:16px;margin:20px 0}}
 .card{{background:#fff;border-radius:8px;padding:14px 18px;flex:1;text-align:center;
        box-shadow:0 1px 4px rgba(0,0,0,.1)}}
 .card .v{{font-size:1.9em;font-weight:700}} .pass{{color:#2e7d32}} .fail{{color:#c62828}}
 table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;
        box-shadow:0 1px 4px rgba(0,0,0,.1)}}
 th{{background:#2c3e50;color:#fff;padding:10px;text-align:left}} td{{padding:8px 10px;border-bottom:1px solid #eee}}
 .b-PASS{{background:#d5f5e3;color:#1e8449;padding:2px 9px;border-radius:11px;font-weight:700}}
 .b-FAIL{{background:#fadbd8;color:#922b21;padding:2px 9px;border-radius:11px;font-weight:700}}
 img{{max-width:100%;border-radius:8px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
</style></head><body>
 <div class="hdr"><h1>{title}</h1><div>{bench} &middot; generated {ts}</div></div>
 <div class="cards">
  <div class="card"><div class="v">{total}</div><div>Samples</div></div>
  <div class="card"><div class="v pass">{passed}</div><div>Pass</div></div>
  <div class="card"><div class="v fail">{failed}</div><div>Fail</div></div>
 </div>
 {plot}
 <table><tr><th>t (s)</th><th>Distance (m)</th><th>RSSI (dBm)</th>
 <th>SNR (dB)</th><th>PDR (%)</th><th>Verdict</th></tr>{rows}</table>
</body></html>"""


def generate(report: FieldReport, out_dir: str = "reports") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    png = out / f"link_quality_{stamp}.png"
    have_plot = _plot(report, png)

    rows = ""
    for s in report.samples:
        cell = lambda v, f="{:.1f}": (f.format(v) if isinstance(v, (int, float)) else "—")
        rows += (
            f"<tr><td>{s.elapsed_s:.0f}</td><td>{cell(s.distance_m)}</td>"
            f"<td>{cell(s.rssi_dbm)}</td><td>{cell(s.snr_db)}</td>"
            f"<td>{cell(s.pdr_pct)}</td>"
            f"<td><span class='b-{s.verdict}'>{s.verdict}</span></td></tr>"
        )

    html = _HTML.format(
        title=report.title,
        bench=report.bench.get("channel_name", "mesh"),
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total=len(report.samples), passed=report.pass_count, failed=report.fail_count,
        plot=(f"<img src='{png.name}'>" if have_plot else ""),
        rows=rows,
    )
    out_html = out / f"field_report_{stamp}.html"
    out_html.write_text(html, encoding="utf-8")
    logger.info("Report written: %s", out_html)
    return out_html
