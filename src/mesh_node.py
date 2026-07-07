"""
mesh_node.py — Device Under Test (DUT) abstraction for a Meshtastic LoRa node.

This wraps the raw Meshtastic Python API in a clean, test-friendly interface —
the same abstraction-layer pattern used in professional RF test automation
(separate the *what* of a test from the *how* of talking to the device).

A real Meshtastic node is reached over USB serial; the same class also supports
a built-in MockNode so the framework can be developed and demoed without radios.

References:
  - Meshtastic Python API: https://python.meshtastic.org/
  - Packet metadata (rxRssi, rxSnr, hopLimit) is attached by firmware to every
    received packet — this is the gold an RF test engineer logs.
"""

from __future__ import annotations

import math
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# ─── Data models ────────────────────────────────────────────────────────────
@dataclass
class RxRecord:
    """One received packet, with the link-quality metadata we care about."""
    timestamp: float
    from_id: str
    to_id: str
    portnum: str
    rssi_dbm: Optional[float]
    snr_db: Optional[float]
    hop_limit: Optional[int]
    payload_len: int
    text: Optional[str] = None


@dataclass
class NodeInfo:
    node_id: str
    long_name: str
    short_name: str
    snr_db: Optional[float] = None
    last_heard: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    battery_pct: Optional[int] = None
    hops_away: Optional[int] = None


# ─── Real device ────────────────────────────────────────────────────────────
class MeshNode:
    """Test wrapper around a physical Meshtastic node on a serial port."""

    def __init__(self, port: str, name: str = "DUT"):
        self.port = port
        self.name = name
        self._iface = None
        self._rx_log: list[RxRecord] = []
        self._rx_lock = threading.Lock()
        self._on_rx: Optional[Callable[[RxRecord], None]] = None

    # -- lifecycle ----------------------------------------------------------
    def connect(self) -> None:
        # Imported lazily so the framework still imports without the lib/hardware.
        import meshtastic.serial_interface
        from pubsub import pub

        self._iface = meshtastic.serial_interface.SerialInterface(self.port)
        pub.subscribe(self._handle_receive, "meshtastic.receive")
        time.sleep(2.0)  # allow node info to populate
        my = self.my_node_id()
        logger.info("Connected to %s on %s (id=%s)", self.name, self.port, my)

    def close(self) -> None:
        if self._iface is not None:
            self._iface.close()
            self._iface = None
            logger.info("Closed %s on %s", self.name, self.port)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # -- identity / status --------------------------------------------------
    def my_node_id(self) -> str:
        node = self._iface.getNode("^local")
        num = node.nodeNum
        return f"!{num:08x}"

    def neighbors(self) -> list[NodeInfo]:
        """Return all nodes currently known to the mesh."""
        out: list[NodeInfo] = []
        for n in self._iface.nodes.values():
            user = n.get("user", {})
            pos = n.get("position", {})
            metrics = n.get("deviceMetrics", {})
            out.append(NodeInfo(
                node_id=user.get("id", "?"),
                long_name=user.get("longName", "?"),
                short_name=user.get("shortName", "?"),
                snr_db=n.get("snr"),
                last_heard=n.get("lastHeard"),
                lat=pos.get("latitude"),
                lon=pos.get("longitude"),
                battery_pct=metrics.get("batteryLevel"),
                hops_away=n.get("hopsAway"),
            ))
        return out

    def neighbor(self, node_id: str) -> Optional[NodeInfo]:
        for n in self.neighbors():
            if n.node_id == node_id:
                return n
        return None

    # -- transmit -----------------------------------------------------------
    def send_text(self, text: str, dest: str = "^all") -> None:
        logger.debug("TX -> %s: %r", dest, text)
        self._iface.sendText(text, destinationId=dest)

    # -- receive ------------------------------------------------------------
    def on_receive(self, callback: Callable[[RxRecord], None]) -> None:
        """Register a callback fired for every received packet."""
        self._on_rx = callback

    def _handle_receive(self, packet, interface=None) -> None:
        try:
            decoded = packet.get("decoded", {}) or {}
            payload = decoded.get("payload", b"") or b""
            rec = RxRecord(
                timestamp=time.time(),
                from_id=self._fmt_id(packet.get("from")),
                to_id=self._fmt_id(packet.get("to")),
                portnum=str(decoded.get("portnum", "UNKNOWN")),
                rssi_dbm=packet.get("rxRssi"),
                snr_db=packet.get("rxSnr"),
                hop_limit=packet.get("hopLimit"),
                payload_len=len(payload),
                text=decoded.get("text"),
            )
        except Exception:  # defensive: never let a bad packet kill the listener
            logger.exception("Failed to parse received packet")
            return

        with self._rx_lock:
            self._rx_log.append(rec)
        if self._on_rx:
            self._on_rx(rec)

    @staticmethod
    def _fmt_id(num) -> str:
        if isinstance(num, int):
            return f"!{num:08x}"
        return str(num)

    # -- captured log -------------------------------------------------------
    def rx_log(self) -> list[RxRecord]:
        with self._rx_lock:
            return list(self._rx_log)

    def clear_rx_log(self) -> None:
        with self._rx_lock:
            self._rx_log.clear()

    def wait_for(self, predicate: Callable[[RxRecord], bool],
                 timeout_s: float = 10.0) -> Optional[RxRecord]:
        """Block until a packet matching `predicate` arrives, or timeout."""
        deadline = time.time() + timeout_s
        seen = 0
        while time.time() < deadline:
            log = self.rx_log()
            for rec in log[seen:]:
                if predicate(rec):
                    return rec
            seen = len(log)
            time.sleep(0.2)
        return None


# ─── RF helper ──────────────────────────────────────────────────────────────
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points, in meters."""
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# ─── Mock device (no hardware needed) ───────────────────────────────────────
class MockNode(MeshNode):
    """
    Simulated node for developing/demoing the framework without radios.

    Models link quality with a simple log-distance path-loss model so range
    sweeps and PDR tests produce realistic-looking data.
    """

    def __init__(self, name: str = "MOCK", peer_id: str = "!a1b2c3d4"):
        super().__init__(port="MOCK", name=name)
        self._peer_id = peer_id
        self._distance_m = 50.0  # tests can move the peer

    def connect(self) -> None:
        logger.info("Connected to MOCK node %s (no hardware)", self.name)

    def close(self) -> None:
        logger.info("Closed MOCK node %s", self.name)

    def my_node_id(self) -> str:
        return "!0badf00d"

    def set_distance(self, meters: float) -> None:
        self._distance_m = meters

    def _model_link(self) -> tuple[float, float]:
        """Return (rssi_dbm, snr_db) for current distance via path-loss model."""
        # FSPL-ish at 915 MHz + LoRa processing; tuned to give a believable curve.
        d = max(self._distance_m, 1.0)
        rssi = -40.0 - 20.0 * math.log10(d)       # -40 dBm at 1 m reference
        snr = 12.0 - 7.0 * math.log10(d / 50.0)   # ~12 dB close, drops with range
        return round(rssi, 1), round(snr, 1)

    def neighbors(self) -> list[NodeInfo]:
        rssi, snr = self._model_link()
        return [NodeInfo(
            node_id=self._peer_id, long_name="Mock-Peer", short_name="MP",
            snr_db=snr, last_heard=time.time(),
            lat=34.0 + self._distance_m / 111_000.0, lon=-118.0,
            battery_pct=88, hops_away=0,
        )]

    def send_text(self, text: str, dest: str = "^all") -> None:
        # Simulate a reply: delivered only if the modeled link is good enough.
        rssi, snr = self._model_link()
        delivered = snr > -8.0  # crude LoRa decode threshold
        if delivered:
            rec = RxRecord(
                timestamp=time.time(), from_id=self._peer_id,
                to_id=self.my_node_id(), portnum="TEXT_MESSAGE_APP",
                rssi_dbm=rssi, snr_db=snr, hop_limit=2,
                payload_len=len(text.encode()), text=f"echo:{text}",
            )
            with self._rx_lock:
                self._rx_log.append(rec)
            if self._on_rx:
                self._on_rx(rec)
