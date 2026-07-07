"""
range_test.py — Field range / link-quality sweep.

Walk one node away from another while this tool periodically samples the link
(RSSI, SNR), correlates it with GPS distance (haversine), runs a quick PDR
burst at each waypoint, applies the pass/fail spec, and emits an HTML report
with a link-quality-vs-distance plot.

This is the headline deliverable of the project: a measured characterization of
how far the mesh actually reaches — the exact report an R&D test engineer
produces for a radio's datasheet range claim.

Usage:
    python -m tools.range_test --port COM5 --peer "!a1b2c3d4"
    python -m tools.range_test --simulate            # desk demo, no hardware
"""

from __future__ import annotations

import sys
import time
import logging
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src.mesh_node import MeshNode, MockNode, haversine_m  # noqa: E402
from src.test_report import FieldReport, Sample, generate  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("range_test")


def load_config() -> dict:
    with open(ROOT / "config" / "test_config.yaml") as f:
        return yaml.safe_load(f)


def quick_pdr(node, peer_id, n=5, interval=2.0) -> float:
    """Small PDR burst used at each waypoint to gauge reliability."""
    got = 0
    for i in range(n):
        tag = f"RT-{int(time.time())}-{i}"
        node.send_text(tag)
        rec = node.wait_for(lambda r: r.text and tag in r.text, timeout_s=interval)
        if rec is not None:
            got += 1
        time.sleep(0.5)
    return 100.0 * got / n


def verdict(rssi, snr, pdr, specs) -> str:
    if rssi is None or snr is None:
        return "N/A"
    ok = (rssi >= specs["min_rssi_dbm"]
          and snr >= specs["min_snr_db"]
          and (pdr is None or pdr >= specs["pdr_pass_pct"]))
    return "PASS" if ok else "FAIL"


def main() -> int:
    ap = argparse.ArgumentParser(description="Mesh field range test")
    ap.add_argument("--port", help="Local node serial port")
    ap.add_argument("--peer", help="Peer node id (!xxxxxxxx)")
    ap.add_argument("--simulate", action="store_true", help="No-hardware demo")
    ap.add_argument("--out", default="logs/range.csv")
    args = ap.parse_args()

    cfg = load_config()
    specs = cfg["specs"]
    interval = cfg["range_test"]["sample_interval_s"]
    duration = cfg["range_test"]["duration_s"]
    peer_id = args.peer or cfg["nodes"]["peer"]["node_id"]

    if not args.simulate and not args.port:
        ap.error("--port required (or use --simulate)")

    node = MockNode(peer_id=peer_id) if args.simulate else MeshNode(port=args.port)
    node.connect()

    report = FieldReport(
        title="Meshtastic Mesh — Range & Link-Quality Characterization",
        bench=cfg["bench"], specs=specs,
    )

    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    csv_f = out_csv.open("w", encoding="utf-8")
    csv_f.write("elapsed_s,distance_m,rssi_dbm,snr_db,pdr_pct,verdict\n")

    # Local position reference (for haversine vs the moving peer).
    me = next((n for n in node.neighbors() if n.node_id == node.my_node_id()), None)

    log.info("Range test started — move the peer node away. Ctrl-C to stop early.")
    t_start = time.time()
    sim_dist = 50.0
    try:
        while time.time() - t_start < duration:
            elapsed = time.time() - t_start

            if args.simulate:
                node.set_distance(sim_dist)

            peer = node.neighbor(peer_id)
            rssi = snr = dist = None
            if peer is not None:
                snr = peer.snr_db
                # Distance from GPS if both fixes exist; else use sim value.
                if me and me.lat and peer.lat:
                    dist = haversine_m(me.lat, me.lon, peer.lat, peer.lon)
                elif args.simulate:
                    dist = sim_dist
                # RSSI comes off received packets; grab the latest if present.
                recent = [r for r in node.rx_log() if r.from_id == peer_id and r.rssi_dbm]
                rssi = recent[-1].rssi_dbm if recent else (
                    node._model_link()[0] if args.simulate else None)

            pdr = quick_pdr(node, peer_id, n=5, interval=2.0)
            v = verdict(rssi, snr, pdr, specs)

            report.samples.append(Sample(elapsed, dist, rssi, snr, pdr, v))
            csv_f.write(f"{elapsed:.0f},{dist},{rssi},{snr},{pdr:.1f},{v}\n")
            csv_f.flush()
            log.info("t=%4.0fs  d=%s m  RSSI=%s  SNR=%s  PDR=%.0f%%  -> %s",
                     elapsed, _fmt(dist), _fmt(rssi), _fmt(snr), pdr, v)

            if args.simulate:
                sim_dist += 150.0  # auto-walk the mock peer outward

            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Stopped by user.")
    finally:
        node.close()
        csv_f.close()
        html = generate(report, cfg["paths"]["report_dir"])
        log.info("CSV : %s", out_csv)
        log.info("HTML: %s", html)
        log.info("Summary: %d PASS / %d FAIL of %d samples",
                 report.pass_count, report.fail_count, len(report.samples))
    return 0


def _fmt(v):
    return f"{v:.1f}" if isinstance(v, (int, float)) else "—"


if __name__ == "__main__":
    raise SystemExit(main())
