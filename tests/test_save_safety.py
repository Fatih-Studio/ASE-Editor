from pathlib import Path

import pytest

from ase_editor import exporter
from ase_editor.parser import parse_scenario_file, parse_scenario_text


SCENARIO_TEXT = "@N:ONE:1234:1:-1:2:3000:220:900:0\nUNKNOWN:café\n"


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("stage", ["serialize", "create", "write", "flush", "fsync", "replace"])
def test_failed_save_preserves_destination_and_cleans_temporary_file(tmp_path, monkeypatch, existing, stage):
    destination = tmp_path / "scenario.txt"
    original = b"Original scenario\r\nKeep these exact bytes\x00\xff"
    if existing:
        destination.write_bytes(original)
    scenario = parse_scenario_text(SCENARIO_TEXT)

    def fail(*args, **kwargs):
        raise OSError(f"injected {stage} failure")

    if stage == "serialize":
        monkeypatch.setattr(exporter, "serialize_scenario", fail)
    elif stage == "create":
        monkeypatch.setattr(exporter.tempfile, "NamedTemporaryFile", fail)
    elif stage in {"fsync", "replace"}:
        monkeypatch.setattr(exporter.os, stage, fail)
    else:
        real_factory = exporter.tempfile.NamedTemporaryFile

        class FailingTemporaryFile:
            def __init__(self, *args, **kwargs):
                self.file = real_factory(*args, **kwargs)
                self.name = self.file.name

            def __enter__(self):
                self.file.__enter__()
                return self

            def __exit__(self, *args):
                return self.file.__exit__(*args)

            def write(self, text):
                if stage == "write":
                    self.file.write(text[:12])
                    self.file.flush()
                    fail()
                return self.file.write(text)

            def flush(self):
                if stage == "flush":
                    fail()
                self.file.flush()

            def fileno(self):
                return self.file.fileno()

        monkeypatch.setattr(exporter.tempfile, "NamedTemporaryFile", FailingTemporaryFile)

    with pytest.raises(OSError, match=f"injected {stage} failure"):
        exporter.write_scenario_file(scenario, destination)

    assert destination.exists() == existing
    if existing:
        assert destination.read_bytes() == original
    assert list(tmp_path.iterdir()) == ([destination] if existing else [])


def test_successful_save_replaces_only_after_complete_synced_write(tmp_path, monkeypatch):
    destination = tmp_path / "scenario.txt"
    destination.write_bytes(b"existing")
    scenario = parse_scenario_text(SCENARIO_TEXT.replace("\n", "\r\n"))
    real_replace = exporter.os.replace
    real_fsync = exporter.os.fsync
    operations = []

    def fsync(fd):
        operations.append("fsync")
        real_fsync(fd)

    def replace(source, target):
        assert Path(source).parent == destination.parent
        assert Path(source) != destination
        assert destination.read_bytes() == b"existing"
        assert Path(source).read_bytes() == SCENARIO_TEXT.encode("utf-8")
        assert operations == ["fsync"]
        operations.append("replace")
        real_replace(source, target)

    monkeypatch.setattr(exporter.os, "fsync", fsync)
    monkeypatch.setattr(exporter.os, "replace", replace)
    exporter.write_scenario_file(scenario, destination)

    assert operations == ["fsync", "replace"]
    assert destination.read_bytes() == SCENARIO_TEXT.encode("utf-8")
    assert parse_scenario_file(destination).aircraft[0].unknown_lines == ["UNKNOWN:café"]
    assert list(tmp_path.iterdir()) == [destination]


def test_utf8_bom_input_is_saved_without_bom(tmp_path):
    destination = tmp_path / "scenario.txt"
    destination.write_bytes(b"\xef\xbb\xbf" + SCENARIO_TEXT.encode("utf-8"))
    scenario = parse_scenario_file(destination)
    exporter.write_scenario_file(scenario, destination)
    assert destination.read_bytes() == SCENARIO_TEXT.encode("utf-8")
