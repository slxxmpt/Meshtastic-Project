# Test Plan — Meshtastic–ATAK Mesh Network

**Document ID:** MESH-TP-001
**Revision:** 1.0
**DUT:** 3-node Meshtastic LoRa mesh (ESP32/nRF52), ATAK plugin enabled

---

## 1. Objectives

Validate that a low-cost LoRa mesh meets baseline tactical-comms requirements:
reliable message delivery, acceptable link quality vs. range, correct multi-hop
routing, and valid ATAK Cursor-on-Target (CoT) position reporting.

## 2. Test equipment

| Item | Qty | Purpose | Cal/Setup note |
|---|---|---|---|
| LoRa node (T-Beam, GPS) | 3 | DUT mesh + relay | Same region/channel/preset |
| Android device w/ ATAK + plugin | 1 | CoT end-user device | Paired via BLE to a node |
| Test host running this framework | 1 | Stimulus + logging | USB serial to local node |
| Tape measure / GPS | 1 | Ground-truth distance | For range correlation |

## 3. Configuration

- All nodes: region per `config.bench.region`, channel `TestNet`, preset `LongFast`.
- ATAK plugin module enabled on each node; position broadcast interval set.
- Pass/fail thresholds defined in `config/test_config.yaml › specs`.

## 4. Test cases

| ID | Title | Procedure (summary) | Pass criteria |
|---|---|---|---|
| TC-01 | Node identity | Query local node id | Returns valid `!xxxxxxxx` |
| TC-02 | Peer discovery | Read mesh node DB | Peer appears within 15 s |
| TC-03 | Round-trip echo | Send tagged msg, await echo | RTT ≤ `max_link_latency_s` |
| TC-04 | Packet Delivery Ratio | Send N packets, count echoes | PDR ≥ `pdr_pass_pct` |
| TC-05 | Link quality floor | Read peer SNR | SNR ≥ `min_snr_db` |
| TC-06 | Multi-hop routing | Force traffic via relay | `hopsAway` ≤ `max_hops_expected` |
| TC-07 | Range characterization | Sweep distance, log RSSI/SNR/PDR | Meets floor to rated range |
| TC-08 | CoT validity | Build CoT from node position | Passes `validate_cot()` |
| TC-09 | CoT negative test | Feed malformed CoT | Validator rejects it |

## 5. Execution

```bash
pytest -v --html=reports/report.html          # TC-01..TC-06, TC-08, TC-09
python -m tools.range_test --port COM5 --peer "!a1b2c3d4"   # TC-07
```

## 6. Reporting

- `pytest-html` report → `reports/report.html`
- Field range report (with plot) → `reports/field_report_*.html`
- Raw telemetry → `logs/*.csv`

## 7. Risks / assumptions

- LoRa duty-cycle limits constrain packet rate; PDR interval respects this.
- SNR/RSSI are firmware-reported, not lab-instrument grade — adequate for
  relative characterization, not absolute calibration.
- Range results depend on terrain, antenna height, and RF environment; each
  run records conditions for traceability.

## 8. Traceability

| Requirement | Verified by |
|---|---|
| Reliable delivery | TC-03, TC-04 |
| Usable link margin | TC-05, TC-07 |
| Self-healing multi-hop mesh | TC-06 |
| ATAK situational-awareness integration | TC-08, TC-09 |
