"""
conftest.py — pytest fixtures for the mesh test bench.

Hardware-in-the-loop tests need careful setup/teardown: connect to the node
once per session, restore a clean state before each test, always close the
serial port even on failure. These fixtures encapsulate that.

Run against real hardware:   pytest -v
Run against the mock node:   pytest -v --mock      (no radios required)
"""

import sys
import logging
from pathlib import Path

import pytest
import yaml

# Make src/ importable without installing the package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mesh_node import MeshNode, MockNode  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--mock", action="store_true", default=False,
                     help="Run against the simulated MockNode (no hardware).")


@pytest.fixture(scope="session")
def config():
    cfg_path = ROOT / "config" / "test_config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session", autouse=True)
def _logging(config):
    log_dir = ROOT / config["paths"]["log_dir"]
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "pytest_run.log"),
            logging.StreamHandler(),
        ],
    )


@pytest.fixture(scope="session")
def node(request, config):
    """Connected node under test — real or mock depending on --mock."""
    use_mock = request.config.getoption("--mock")
    if use_mock:
        peer = config["nodes"]["peer"]["node_id"]
        dut = MockNode(name="MOCK", peer_id=peer)
    else:
        port = config["nodes"]["local"]["port"]
        dut = MeshNode(port=port, name=config["nodes"]["local"]["name"])
    dut.connect()
    yield dut
    dut.close()


@pytest.fixture(scope="function")
def fresh_node(node):
    """Clear the capture log before each test so assertions are isolated."""
    node.clear_rx_log()
    yield node
    node.clear_rx_log()
