import io
import json

from scripts import neon_transfer_guard as guard


def test_transfer_thresholds_are_exact():
    assert guard.transfer_level(guard.WARNING_BYTES - 1) == "ok"
    assert guard.transfer_level(guard.WARNING_BYTES) == "warning"
    assert guard.transfer_level(guard.CRITICAL_BYTES) == "critical"
    assert guard.transfer_level(guard.BLOCK_BYTES - 1) == "critical"
    assert guard.transfer_level(guard.BLOCK_BYTES) == "blocked"


def test_project_detail_transfer_parser_uses_read_only_get():
    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def opener(request, timeout):
        seen["method"] = request.get_method()
        seen["timeout"] = timeout
        return Response(json.dumps({"project": {"data_transfer_bytes": 123}}).encode())

    assert guard.fetch_project_transfer("secret", "project-1", opener=opener) == 123
    assert seen == {"method": "GET", "timeout": 15}


def test_missing_monitor_configuration_blocks_shadow(monkeypatch, tmp_path):
    output = tmp_path / "output.txt"
    monkeypatch.delenv("NEON_API_KEY", raising=False)
    monkeypatch.delenv("NEON_PROJECT_ID", raising=False)
    assert guard.main(["--github-output", str(output)]) == 0
    values = output.read_text(encoding="utf-8")
    assert "configured=false" in values
    assert "allow_shadow=false" in values


def test_block_threshold_fails_without_leaking_key(monkeypatch, tmp_path, capsys):
    output = tmp_path / "output.txt"
    monkeypatch.setenv("NEON_API_KEY", "do-not-print-this")
    monkeypatch.setenv("NEON_PROJECT_ID", "project-1")
    monkeypatch.setattr(guard, "fetch_project_transfer", lambda *args: guard.BLOCK_BYTES)
    assert guard.main(["--github-output", str(output)]) == 2
    combined = capsys.readouterr().out + output.read_text(encoding="utf-8")
    assert "allow_shadow=false" in combined
    assert "do-not-print-this" not in combined
