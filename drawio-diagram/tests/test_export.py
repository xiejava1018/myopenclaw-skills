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


def test_export_builds_correct_command(monkeypatch, tmp_path):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()
    monkeypatch.setattr(export.subprocess, "run", fake_run)
    export.export_image("in.drawio", str(tmp_path / "out.png"), fmt="png", scale=2, border=20)
    cmd = captured["cmd"]
    assert cmd[0] == "drawio"
    assert "-x" in cmd and "-f" in cmd and "png" in cmd
    assert "--scale" in cmd and "2" in cmd
    assert "--border" in cmd and "20" in cmd


def test_export_raises_if_drawio_missing(monkeypatch):
    monkeypatch.setattr(export, "drawio_available", lambda: False)
    try:
        export.export_image("in.drawio", "out.png")
        assert False
    except export.ExportError:
        pass


def test_export_raises_on_nonzero_exit(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"
        return R()
    monkeypatch.setattr(export.subprocess, "run", fake_run)
    monkeypatch.setattr(export, "drawio_available", lambda: True)
    try:
        export.export_image("in.drawio", str(tmp_path / "o.png"))
        assert False
    except export.ExportError as e:
        assert "boom" in str(e)
