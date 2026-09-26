"""Shared fixtures.

The integration lives at the repository root (HACS ``content_in_root``), but
Home Assistant only loads custom integrations from a ``custom_components``
package. Expose the repo as ``custom_components.met_tides`` via a symlink in a
temp dir before anything imports it.
"""

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_shim = Path(tempfile.mkdtemp(prefix="met_tides_shim_"))
(_shim / "custom_components").mkdir()
(_shim / "custom_components" / "met_tides").symlink_to(REPO_ROOT, target_is_directory=True)
sys.path.insert(0, str(_shim))

FIXTURES = Path(__file__).parent / "fixtures"

from tide_helpers import make_forecast  # noqa: E402


@pytest.fixture
def forecast_start() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def forecast_text(forecast_start) -> str:
    return make_forecast(forecast_start)


@pytest.fixture
def harbors_xml() -> str:
    return (FIXTURES / "available.xml").read_text()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return
