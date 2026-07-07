"""
test_link.py — Link establishment, round-trip, and multi-hop routing tests.

These validate the bottom of the stack first (can two nodes hear each other?),
then work up to routing (does traffic relay through an intermediate node?) —
the same bottom-up isolation order a test engineer uses to debug a dead link.
"""

import time
import logging

import pytest

logger = logging.getLogger(__name__)


class TestLinkEstablishment:

    def test_node_reports_identity(self, node):
        """DUT must return a well-formed Meshtastic node id (!xxxxxxxx)."""
        nid = node.my_node_id()
        logger.info("DUT node id: %s", nid)
        assert nid.startswith("!") and len(nid) == 9

    def test_peer_is_in_mesh(self, node, config):
        """The configured peer node must be discoverable in the mesh table."""
        peer_id = config["nodes"]["peer"]["node_id"]
        # Give the mesh a moment to populate the node DB.
        deadline = time.time() + 15
        found = None
        while time.time() < deadline and found is None:
            found = node.neighbor(peer_id)
            time.sleep(1.0)
        assert found is not None, f"peer {peer_id} not seen in mesh"
        logger.info("Peer %s found (SNR=%s dB)", peer_id, found.snr_db)

    def test_round_trip_echo(self, fresh_node, config):
        """
        Send a tagged message; expect a reply within the latency spec.
        (With real hardware, configure the peer to echo, or run a companion
        responder. The MockNode echoes automatically.)
        """
        max_latency = config["specs"]["max_link_latency_s"]
        tag = f"PING-{int(time.time())}"

        t0 = time.time()
        fresh_node.send_text(tag)
        rec = fresh_node.wait_for(
            lambda r: r.text and tag in r.text, timeout_s=max_latency
        )
        rtt = time.time() - t0

        assert rec is not None, f"no echo within {max_latency}s"
        logger.info("Round-trip OK in %.2fs (RSSI=%s SNR=%s)",
                    rtt, rec.rssi_dbm, rec.snr_db)
        assert rtt <= max_latency


class TestMultiHopRouting:

    def test_relay_hop_count_within_spec(self, node, config):
        """
        For any neighbor reachable via relay, hopsAway must be within the
        expected maximum — proves the routing layer resolves multi-hop paths.
        """
        max_hops = config["specs"]["max_hops_expected"]
        neighbors = node.neighbors()
        if not neighbors:
            pytest.skip("no neighbors visible to evaluate routing")

        for n in neighbors:
            if n.hops_away is None:
                continue
            logger.info("Node %s is %d hop(s) away", n.node_id, n.hops_away)
            assert n.hops_away <= max_hops, (
                f"{n.node_id} is {n.hops_away} hops away (max {max_hops})"
            )
