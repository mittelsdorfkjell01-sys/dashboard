"""P0.4: a missing gate-evidence table must fail loudly, never activate silently."""

from __future__ import annotations

import uuid

import pytest

import app.weather.sector_activation as sa


def test_require_gate_evidence_table_raises_when_absent(monkeypatch):
    monkeypatch.setattr(sa, "gate_evidence_table_exists", lambda db: False)
    with pytest.raises(sa.GateEvidenceUnavailable):
        sa.require_gate_evidence_table(object())


def test_require_gate_evidence_table_passes_when_present(monkeypatch):
    monkeypatch.setattr(sa, "gate_evidence_table_exists", lambda db: True)
    sa.require_gate_evidence_table(object())  # does not raise


def test_activation_refuses_without_the_gate_evidence_table(monkeypatch):
    # The guard is the first thing activation does, so no spot/profile/DB work
    # happens — a candidate can never be activated when the proof store is absent.
    monkeypatch.setattr(sa, "gate_evidence_table_exists", lambda db: False)
    with pytest.raises(sa.GateEvidenceUnavailable):
        sa.activate_spot_sectors(
            object(), uuid.uuid4(), 2, actor="test", gate_run_id=uuid.uuid4()
        )


def test_gate_results_refuse_without_the_gate_evidence_table(monkeypatch):
    monkeypatch.setattr(sa, "gate_evidence_table_exists", lambda db: False)
    with pytest.raises(sa.GateEvidenceUnavailable):
        sa.candidate_gate_results(object(), uuid.uuid4())
