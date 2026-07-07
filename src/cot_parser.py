"""
cot_parser.py — ATAK Cursor-on-Target (CoT) generation and validation.

The Meshtastic ATAK plugin carries position/identity between the LoRa mesh and
ATAK end-user devices. On the network those are ATAK_PLUGIN packets; in ATAK
they surface as CoT events — an XML schema that every TAK product speaks.

This module:
  1. Builds a CoT XML event from a mesh node's position (what the bridge emits).
  2. Validates a CoT event has the mandatory fields and sane values.

Validating CoT is a real test task: if the bridge emits malformed CoT, friendly
icons never appear on the ATAK map even though the mesh link is perfect — a
classic "good RF, bad application layer" failure that a test engineer must catch.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


@dataclass
class CotEvent:
    uid: str
    callsign: str
    lat: float
    lon: float
    hae: float = 0.0          # height above ellipsoid (m)
    cot_type: str = "a-f-G-U-C"  # friendly-ground-unit-combat (default)
    stale_s: int = 300


def build_cot(ev: CotEvent, now: datetime | None = None) -> str:
    """Serialize a CotEvent to a CoT XML string (UTF-8)."""
    now = now or datetime.now(timezone.utc)
    fmt = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    event = ET.Element("event", {
        "version": "2.0",
        "uid": ev.uid,
        "type": ev.cot_type,
        "how": "m-g",
        "time": fmt(now),
        "start": fmt(now),
        "stale": fmt(now + timedelta(seconds=ev.stale_s)),
    })
    ET.SubElement(event, "point", {
        "lat": f"{ev.lat:.7f}",
        "lon": f"{ev.lon:.7f}",
        "hae": f"{ev.hae:.1f}",
        "ce": "10.0",   # circular error (m)
        "le": "10.0",   # linear error (m)
    })
    detail = ET.SubElement(event, "detail")
    ET.SubElement(detail, "contact", {"callsign": ev.callsign})
    ET.SubElement(detail, "__group", {"name": "Cyan", "role": "Team Member"})
    return ET.tostring(event, encoding="unicode")


# Mandatory CoT structure for a valid position event.
_LATLON_RE = re.compile(r"^-?\d+(\.\d+)?$")


def validate_cot(xml: str) -> tuple[bool, list[str]]:
    """
    Validate a CoT XML string. Returns (is_valid, list_of_problems).
    Empty problem list == valid.
    """
    problems: list[str] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        return False, [f"XML parse error: {e}"]

    if root.tag != "event":
        problems.append(f"root element is <{root.tag}>, expected <event>")

    for attr in ("uid", "type", "time", "start", "stale"):
        if not root.get(attr):
            problems.append(f"missing required event attribute '{attr}'")

    point = root.find("point")
    if point is None:
        problems.append("missing <point> element")
    else:
        lat, lon = point.get("lat"), point.get("lon")
        if not lat or not _LATLON_RE.match(lat) or not (-90 <= float(lat) <= 90):
            problems.append(f"invalid lat: {lat!r}")
        if not lon or not _LATLON_RE.match(lon) or not (-180 <= float(lon) <= 180):
            problems.append(f"invalid lon: {lon!r}")

    detail = root.find("detail")
    if detail is None or detail.find("contact") is None:
        problems.append("missing <detail>/<contact> (no callsign for ATAK)")

    ok = not problems
    if ok:
        logger.debug("CoT valid: uid=%s", root.get("uid"))
    else:
        logger.warning("CoT invalid: %s", "; ".join(problems))
    return ok, problems


def cot_from_node(node_id: str, callsign: str, lat: float, lon: float) -> str:
    """Convenience: build a validated CoT directly from mesh node position."""
    return build_cot(CotEvent(uid=node_id, callsign=callsign, lat=lat, lon=lon))


if __name__ == "__main__":
    # Tiny self-demo.
    xml = cot_from_node("MESH-NODE-B", "BRAVO", 34.0901, -118.4065)
    print(xml)
    print("valid?", validate_cot(xml))
