from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_contract_is_post_only_and_bounded():
    workflow = (ROOT / ".github/workflows/weather-shadow.yml").read_text(
        encoding="utf-8"
    )
    assert 'cron: "41 */6 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "timeout-minutes: 15" in workflow
    assert "--request POST" in workflow
    assert "--max-time 30" in workflow
    assert "secrets.WEATHER_SHADOW_CRON_SECRET" in workflow
    assert "vars.WEATHER_SHADOW_ENDPOINT" in workflow


def test_scheduler_does_not_embed_an_authorization_value():
    workflow = (ROOT / ".github/workflows/weather-shadow.yml").read_text(
        encoding="utf-8"
    )
    authorization_lines = [
        line for line in workflow.splitlines() if "Authorization:" in line
    ]
    assert [line.strip() for line in authorization_lines] == [
        '--header "Authorization: Bearer ${WEATHER_SHADOW_CRON_SECRET}" \\'
    ]
