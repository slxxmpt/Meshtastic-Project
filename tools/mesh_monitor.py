"""
mesh_monitor.py — Live mesh telemetry logger.

Connects to a Meshtastic node and streams every received packet to the console
and a CSV, capturing the link-quality metadata (RSSI, SNR, hop limit) that an
RF test engineer needs. Think of it as a software logic analyzer for the mesh.

Usage:
    python -m tools.mesh_monitor --list-ports
    python -m tools.mesh_monitor --port COM5 --log logs/mesh_live.csv
    python -m tools.mesh_monitor --simulate          # no hardware
"""

from __future__ import annotations

import sys
import csv
import time
import signal
import logging
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mesh_node import MeshNode, MockNode, RxRecord  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("mesh_monitor")


def list_ports() -> None:
    try:
        from serial.tools import list_ports as lp
    except Exception:
        print("pyserial not installed; run: pip install -r requirements.txt")
        return
    ports = list(lp.comports())
    if not ports:
        print("No serial ports found. Is a node plugged in?")
        return
    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device:12} {p.description}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Live Meshtastic mesh monitor")
    ap.add_argument("--port", help="Serial port of the local node (e.g. COM5)")
    ap.add_argument("--log", default="logs/mesh_live.csv", help="CSV output path")
    ap.add_argument("--simulate", action="store_true", help="Use mock node")
    ap.add_argument("--list-ports", action="store_true", help="List serial ports")
    args = ap.parse_args()

    if args.list_ports:
        list_ports()
        return 0

    if not args.simulate and not args.port:
        ap.error("--port is required (or use --simulate / --list-ports)")

    out = Path(args.log)
    out.parent.mkdir(parents=True, exist_ok=True)
    csv_file = out.open("w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow(["timestamp", "from", "to", "portnum",
                     "rssi_dbm", "snr_db", "hop_limit", "payload_len", "text"])

    def on_rx(rec: RxRecord) -> None:
        writer.writerow([f"{rec.timestamp:.3f}", rec.from_id, rec.to_id,
                         rec.portnum, rec.rssi_dbm, rec.snr_db,
                         rec.hop_limit, rec.payload_len, rec.text or ""])
        csv_file.flush()
        log.info("RX %-16s %-18s RSSI=%-6s SNR=%-5s hops=%s %s",
                 rec.from_id, rec.portnum, rec.rssi_dbm, rec.snr_db,
                 rec.hop_limit, (rec.text or "")[:40])

    node = MockNode() if args.simulate else MeshNode(port=args.port)
    node.on_receive(on_rx)
    node.connect()
    log.info("Monitoring mesh — logging to %s (Ctrl-C to stop)", out)

    running = {"go": True}
    signal.signal(signal.SIGINT, lambda *_: running.update(go=False))

    try:
        tick = 0
        while running["go"]:
            time.sleep(1.0)
            tick += 1
            if args.simulate and tick % 5 == 0:
                node.send_text(f"sim-beacon-{tick}")  # generate mock traffic
            if tick % 30 == 0:
                neigh = node.neighbors()
                log.info("Mesh has %d node(s): %s", len(neigh),
                         ", ".join(n.node_id for n in neigh))
    finally:
        node.close()
        csv_file.close()
        log.info("Stopped. Log saved to %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
