"""
test_pdr.py — Packet Delivery Ratio (PDR) test.

PDR is the fundamental reliability metric for any radio link:
    PDR = (packets successfully delivered / packets transmitted) * 100%

We transmit N sequence-numbered packets at a controlled interval (respecting
LoRa duty-cycle limits) and count how many are acknowledged/echoed back. The
result is asserted against the bench spec. This is the same measurement an R&D
engineer runs on a StreamCaster link, just at LoRa data rates.
"""

import time
import logging

import pytest

logger = logging.getLogger(__name__)


class TestPacketDeliveryRatio:

    def test_pdr_meets_spec(self, fresh_node, config):
        count = config["pdr_test"]["packet_count"]
        interval = config["pdr_test"]["interval_s"]
        spec = config["specs"]["pdr_pass_pct"]

        delivered = 0
        per_packet_rtt = []

        logger.info("Starting PDR test: %d packets @ %.1fs interval", count, interval)
        for seq in range(count):
            tag = f"PDR-{seq:04d}"
            t0 = time.time()
            fresh_node.send_text(tag)
            rec = fresh_node.wait_for(
                lambda r: r.text and tag in r.text,
                timeout_s=interval,
            )
            if rec is not None:
                delivered += 1
                per_packet_rtt.append(time.time() - t0)
            # Pace the next transmission (avoid hammering the duty cycle).
            time.sleep(max(0.0, interval - (time.time() - t0)))

        pdr = 100.0 * delivered / count
        avg_rtt = sum(per_packet_rtt) / len(per_packet_rtt) if per_packet_rtt else float("nan")
        logger.info("PDR result: %.1f%% (%d/%d), avg RTT %.2fs",
                    pdr, delivered, count, avg_rtt)

        assert pdr >= spec, f"PDR {pdr:.1f}% below spec {spec:.1f}%"
