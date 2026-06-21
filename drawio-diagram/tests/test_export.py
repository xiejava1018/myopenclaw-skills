import importlib
export = importlib.import_module("export")  # scripts/export.py


def test_drawio_available_true_when_which_returns_path(monkeypatch):
    monkeypatch.setattr(export.shutil, "which", lambda name: "/opt/homebrew/bin/drawio")
    assert export.drawio_available() is True


def test_drawio_available_false_when_missing(monkeypatch):
    monkeypatch.setattr(export.shutil, "which", lambda name: None)
    assert export.drawio_available() is False


def test_check_status_returns_dict(monkeypatch):
    monkeypatch.setattr(export, "drawio_available", lambda: True)
    monkeypatch.setattr(export, "drawio_version", lambda: "30.0.2")
    status = export.check_status()
    assert status["available"] is True
    assert status["version"] == "30.0.2"
    assert "drawio" in status["install_hint"]
