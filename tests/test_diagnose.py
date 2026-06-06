"""core.diagnose — self-check suite behind /system/diagnose and --diagnose."""
import pytest

from core import diagnose
from core.diagnose import OK, WARN, FAIL, run_diagnostics, format_text


@pytest.fixture()
def report():
    # include_network=False: the suite must come back instantly offline —
    # that's the contract the CLI and tests rely on.
    return run_diagnostics(include_network=False)


def test_report_shape(report):
    assert set(report) == {"app_version", "platform", "checks", "summary"}
    ids = [c["id"] for c in report["checks"]]
    assert len(ids) == len(set(ids)), "check ids must be unique"
    for c in report["checks"]:
        assert c["status"] in (OK, WARN, FAIL)
        assert c["label"] and isinstance(c["detail"], str)


def test_network_check_skippable(report):
    assert "network" not in [c["id"] for c in report["checks"]]


def test_summary_consistent(report):
    s = report["summary"]
    statuses = [c["status"] for c in report["checks"]]
    assert s["passed"] == statuses.count(OK)
    assert s["warnings"] == statuses.count(WARN)
    assert s["failures"] == statuses.count(FAIL)
    assert s["ok"] == (s["failures"] == 0)


def test_core_checks_present(report):
    ids = {c["id"] for c in report["checks"]}
    assert {"python", "device", "ffmpeg", "hf_token", "disk", "data_dir", "ram", "engines"} <= ids


def test_low_disk_fails(monkeypatch):
    class FakeUsage:
        free = 1 * 1024 ** 3  # 1 GB — below the 2 GB fail line
    monkeypatch.setattr(diagnose.shutil, "disk_usage", lambda _p: FakeUsage())
    check = diagnose._check_disk()
    assert check["status"] == FAIL


def test_unwritable_data_dir_fails(monkeypatch, tmp_path):
    missing = tmp_path / "definitely" / "not" / "there"
    monkeypatch.setattr(diagnose, "DATA_DIR", str(missing))
    check = diagnose._check_data_dir()
    assert check["status"] == FAIL
    assert check["hint"]  # actionable hint required on failure


def test_details_are_scrubbed(monkeypatch, tmp_path):
    # A DATA_DIR under the user's home must come out as ~/… in the report.
    import os
    home_dir = os.path.join(os.path.expanduser("~"), ".omnivoice-test-probe")
    monkeypatch.setattr(diagnose, "DATA_DIR", home_dir)
    check = diagnose._check_disk()
    assert os.path.expanduser("~") not in check["detail"]


def test_format_text_ascii_and_exit_signal(report):
    text = format_text(report)
    # ASCII-only: Windows consoles on legacy code pages must not choke.
    text.encode("ascii")
    assert "OmniVoice Studio self-check" in text
    assert ("looks healthy" in text) == report["summary"]["ok"]
