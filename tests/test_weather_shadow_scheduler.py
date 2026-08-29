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
    assert "vars.WEATHER_SHADOW_ENABLED" in workflow
    assert "secrets.NEON_API_KEY" in workflow
    assert "vars.NEON_PROJECT_ID" in workflow
    assert "secrets.REDIS_URL" in workflow
    assert "python -m scripts.neon_transfer_guard" in workflow
    assert workflow.count("steps.neon_quota.outputs.allow_shadow == 'true'") == 4


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
