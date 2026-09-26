import os
import sys
from types import SimpleNamespace

import pytest

from ase_editor import __main__ as entrypoint


@pytest.mark.parametrize("contents,existing,expected", [
    ('FLIGHTPLANDB_API_KEY="file-test-key"\n', None, "file-test-key"),
    ("FLIGHTPLANDB_API_KEY=file-test-key\n", "environment-test-key", "environment-test-key"),
    ("FLIGHTPLANDB_API_KEY=\n", None, ""),
    (None, None, None),
])
def test_startup_loads_project_env_before_ui_from_any_directory(monkeypatch, tmp_path, contents, existing, expected):
    project = tmp_path / "project"
    package = project / "ase_editor"
    package.mkdir(parents=True)
    monkeypatch.setattr(entrypoint, "__file__", str(package / "__main__.py"))
    monkeypatch.delenv("FLIGHTPLANDB_API_KEY", raising=False)
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    if existing is not None:
        monkeypatch.setenv("FLIGHTPLANDB_API_KEY", existing)
    if contents is not None:
        # Accept Windows editors that save a UTF-8 byte order mark.
        (project / ".env").write_text(contents, encoding="utf-8-sig")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".env").write_text("FLIGHTPLANDB_API_KEY=wrong-location\n", encoding="utf-8")
    monkeypatch.chdir(elsewhere)
    seen = []
    def run():
        seen.append(os.environ.get("FLIGHTPLANDB_API_KEY"))
        return 0
    monkeypatch.setitem(sys.modules, "ase_editor.ui", SimpleNamespace(run=run))
    assert entrypoint.main() == 0
    assert seen == [expected]
