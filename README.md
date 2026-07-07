# Meshtastic–ATAK Mesh Network Test & Characterization Framework

A Python-based **test automation and RF characterization framework** for a
[Meshtastic](https://meshtastic.org) LoRa mesh network bridged into
[ATAK (Android Team Awareness Kit)](https://www.civtak.org/) for tactical
situational awareness.

This project treats a low-cost LoRa mesh as a **Device Under Test (DUT)** and
applies the same validation methodology used in professional R&D radio test
labs: link characterization, range vs. signal-quality sweeps, packet delivery
ratio (PDR) measurement, multi-hop route validation, and automated reporting.

> **Why this exists:** Anyone can flash Meshtastic firmware and watch messages
> arrive. This framework *quantifies* mesh behavior — turning a hobby mesh into
> a measured, documented, repeatable engineering test bench.

---

## What it demonstrates

| Skill Area | How this project exercises it |
|---|---|
| **MANET / mesh networking** | Multi-hop routing, self-healing topology, neighbor discovery |
| **RF characterization** | RSSI / SNR logging vs. GPS distance, link-budget validation |
| **Embedded systems** | ESP32 / nRF52 LoRa node bring-up and serial/BLE interfacing |
| **Test automation** | `pytest`-based hardware-in-the-loop suite with fixtures |
| **Instrument/DUT abstraction** | Clean Python API wrapper over the Meshtastic device |
| **Data logging & reporting** | CSV telemetry capture + auto-generated HTML test report |
| **Tactical integration** | ATAK Cursor-on-Target (CoT) position-report verification |

---

## System architecture

```
   ┌──────────────┐   LoRa Mesh (915 MHz)   ┌──────────────┐
   │  Node A      │◄───────────────────────►│  Node B      │
   │ ESP32 +      │                          │ ESP32 +      │
   │ LoRa + GPS   │◄──────┐        ┌────────►│ LoRa + GPS   │
   └──────┬───────┘       │        │         └──────────────┘
          │ USB serial    │  relay │ hop
          │               ▼        ▼
          │        ┌──────────────┐
          │        │  Node C      │  (multi-hop relay node)
          │        │ ESP32 + LoRa │
          │        └──────────────┘
          │
   ┌──────▼────────────────────────────────────┐
   │  Test Host (this framework)               │
   │  ┌─────────────────────────────────────┐  │
   │  │ pytest suite  │ range_test.py        │  │
   │  │ mesh_monitor  │ HTML report gen      │  │
   │  └──────────┬──────────────────────────┘  │
   │             │ meshtastic Python API        │
   └─────────────┼──────────────────────────────┘
                 │
          ┌──────▼───────┐   Bluetooth / TCP   ┌──────────────┐
          │ Meshtastic   │────────────────────►│ ATAK (EUD)   │
          │ ATAK plugin  │   CoT position      │ Android tab  │
          └──────────────┘   reports           └──────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for detail.

---

## Hardware (bill of materials)

Minimum viable test bench is **3 nodes** (~$30–45 each):

| Item | Example | Notes |
|---|---|---|
| LoRa node ×3 | Heltec V3 / LilyGO T-Beam | T-Beam includes GPS (needed for range tests) |
| Antennas ×3 | 915 MHz (US) / 868 MHz (EU) | Match your region's ISM band |
| Android device | Any tablet/phone | Runs ATAK + Meshtastic ATAK plugin |
| Test host | Any PC (Win/Linux/Mac) | Runs this framework over USB serial |

> No hardware yet? `tools/mesh_monitor.py --simulate` and the unit tests run
> against a mock node so you can develop and demo the framework without radios.

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/<you>/meshtastic-atak-mesh-test.git
cd meshtastic-atak-mesh-test
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Flash Meshtastic firmware to your nodes (https://flasher.meshtastic.org)
#    Set region, channel, and enable the ATAK plugin module on each node.

# 3. Discover connected nodes
python -m tools.mesh_monitor --list-ports

# 4. Run the live mesh monitor (logs RSSI/SNR/telemetry to CSV)
python -m tools.mesh_monitor --port COM5 --log logs/mesh_live.csv

# 5. Run the automated test suite
pytest -v --html=reports/report.html

# 6. Field range test (walk Node B away from Node A, logging link quality)
python -m tools.range_test --port COM5 --peer "!a1b2c3d4" --out logs/range.csv
```

---

## Test catalog

| Test | File | What it validates |
|---|---|---|
| Link establishment | `tests/test_link.py` | Two nodes associate and exchange messages |
| Packet delivery ratio | `tests/test_pdr.py` | % of N transmitted packets received (per spec) |
| Range / link quality | `tests/test_range.py` | RSSI & SNR stay above threshold at distance |
| Multi-hop routing | `tests/test_link.py` | Traffic relays through an intermediate node |
| ATAK CoT delivery | `src/cot_parser.py` | Position reports decode to valid CoT events |

Full procedures, pass/fail criteria, and equipment list:
[`docs/TEST_PLAN.md`](docs/TEST_PLAN.md).

---

## Sample result (range characterization)

```
Distance (m) | RSSI (dBm) | SNR (dB) | PDR (%) | Verdict
-------------+------------+----------+---------+--------
        50   |    -78     |   10.5   |  100.0  | PASS
       250   |    -94     |    6.2   |  100.0  | PASS
       600   |   -108     |    1.0   |   98.0  | PASS
      1100   |   -118     |   -7.5   |   71.0  | FAIL  (SNR below LoRa floor)
```

The framework correlates these against a computed link budget to confirm the
nodes hit their datasheet-rated range — exactly the kind of report an R&D test
engineer delivers for a radio product.

---

## Repository layout

```
meshtastic-atak-mesh-test/
├── README.md
├── requirements.txt
├── config/test_config.yaml      # bench config: ports, specs, thresholds
├── src/
│   ├── mesh_node.py             # DUT abstraction over the Meshtastic API
│   ├── cot_parser.py            # ATAK Cursor-on-Target decode/validate
│   └── test_report.py           # HTML report generator
├── tests/
│   ├── conftest.py              # pytest fixtures (real + mock node)
│   ├── test_link.py             # link + multi-hop tests
│   ├── test_pdr.py              # packet delivery ratio test
│   └── test_range.py            # range / link-quality test
├── tools/
│   ├── mesh_monitor.py          # live telemetry logger
│   └── range_test.py            # field range-sweep tool
└── docs/
    ├── TEST_PLAN.md             # formal test plan
    └── ARCHITECTURE.md          # design notes
```

---

## License

MIT — see [`LICENSE`](LICENSE).

## Acknowledgements

Built on the [Meshtastic](https://meshtastic.org) open-source project and the
Meshtastic ATAK plugin. Not affiliated with or endorsed by the Meshtastic
project, TAK Product Center, or any government agency.
