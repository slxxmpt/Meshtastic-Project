# Architecture

## Layered design

The framework follows the same abstraction discipline used in professional RF
test automation: test logic never talks to hardware directly.

```
┌──────────────────────────────────────────────┐
│ TEST / TOOL LAYER                             │
│  pytest cases · range_test · mesh_monitor     │
├──────────────────────────────────────────────┤
│ DUT ABSTRACTION                               │
│  MeshNode  (real)   /   MockNode (simulated)  │
│  - connect/close, send_text, neighbors,       │
│    wait_for, rx_log                            │
├──────────────────────────────────────────────┤
│ TRANSPORT                                     │
│  meshtastic Python API  (serial / BLE / TCP)  │
├──────────────────────────────────────────────┤
│ PHYSICAL MESH                                 │
│  ESP32/nRF52 LoRa nodes · ATAK plugin · ATAK  │
└──────────────────────────────────────────────┘
```

Swapping `MeshNode` for `MockNode` lets the entire suite run with no radios —
so the framework is developable, testable, and demoable anywhere, then points
at real hardware by changing one fixture option (`--mock`).

## Key modules

- **`src/mesh_node.py`** — the DUT wrapper. Normalizes every received packet
  into an `RxRecord` carrying the RF metadata (RSSI, SNR, hop limit) that the
  tests assert on. Includes a log-distance path-loss model in `MockNode` so
  range sweeps produce believable curves offline.
- **`src/cot_parser.py`** — builds and validates ATAK CoT XML. Decouples the
  application-layer (does ATAK get a usable icon?) from the RF layer (did the
  bits arrive?), so failures are attributed to the right layer.
- **`src/test_report.py`** — turns field-test samples into a shareable HTML
  report with a link-quality-vs-distance plot.

## Why the mock matters (engineering judgment)

A reviewer might ask, "how do I know your tests work without your radios?"
The `MockNode` answers that: `pytest --mock` exercises every code path with a
deterministic link model. It also documents the *expected* physics — the model
encodes how SNR should fall with distance, which is itself a statement of the
acceptance criteria.

## Extending

- Add a `ThroughputTest` that times bulk transfer for an effective-bitrate
  metric.
- Add temperature logging (nodes report `deviceMetrics`) for an environmental
  characterization run.
- Replace firmware-reported RSSI with a calibrated spectrum-analyzer capture
  for absolute (vs. relative) power measurement.
