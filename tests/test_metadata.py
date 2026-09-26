"""Guard against metadata drift that hassfest/HACS or releases would trip on."""

import json

from conftest import REPO_ROOT

from custom_components.met_tides.const import USER_AGENT


def _manifest() -> dict:
    return json.loads((REPO_ROOT / "manifest.json").read_text())


def test_versions_agree():
    version = _manifest()["version"]
    assert (REPO_ROOT / "VERSION").read_text().strip() == version
    assert f"/{version} " in USER_AGENT
    assert f"## [{version}]" in (REPO_ROOT / "CHANGELOG.md").read_text()


def test_manifest_key_order():
    # hassfest: domain, name, then the remaining keys alphabetically
    keys = list(_manifest())
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])
