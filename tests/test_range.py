"""
test_range.py — Link-quality and CoT-integration tests.

Two concerns validated here:
  1. The current link to the peer meets the RSSI/SNR floor in the spec.
  2. Position data from the mesh produces a *valid* ATAK CoT event — catching
     the "good RF but nothing shows on the ATAK map" application-layer failure.
"""

import time
import logging

import pytest

from src.cot_parser import cot_from_node, validate_cot

logger = logging.getLogger(__name__)


class TestLinkQuality:

    def test_peer_link_above_floor(self, node, config):
        """Peer's reported SNR must be above the configured decode floor."""
        peer_id = config["nodes"]["peer"]["node_id"]
        min_snr = config["specs"]["min_snr_db"]

        peer = node.neighbor(peer_id)
        if peer is None or peer.snr_db is None:
            pytest.skip("peer SNR not yet available")

        logger.info("Peer %s SNR = %.1f dB (floor %.1f dB)",
                    peer_id, peer.snr_db, min_snr)
        assert peer.snr_db >= min_snr, (
            f"link SNR {peer.snr_db:.1f} dB below floor {min_snr:.1f} dB"
        )


class TestAtakCotIntegration:

    def test_position_produces_valid_cot(self, node, config):
        """
        Take a mesh node's GPS position and confirm it serializes to a valid
        CoT event ATAK can render.
        """
        # Find any neighbor with a position fix (mock always has one).
        fixed = next((n for n in node.neighbors()
                      if n.lat is not None and n.lon is not None), None)
        if fixed is None:
            pytest.skip("no neighbor has a GPS fix to build CoT from")

        xml = cot_from_node(fixed.node_id, fixed.short_name or "MESH",
                            fixed.lat, fixed.lon)
        ok, problems = validate_cot(xml)
        logger.info("CoT for %s valid=%s", fixed.node_id, ok)
        assert ok, f"CoT invalid: {problems}"

    def test_malformed_cot_is_rejected(self):
        """Negative test: the validator must reject obviously bad CoT."""
        bad = "<event version='2.0'><detail/></event>"  # no uid/type/point
        ok, problems = validate_cot(bad)
        assert not ok and problems, "validator accepted malformed CoT"
