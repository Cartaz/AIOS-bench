from __future__ import annotations

import pytest

from core.benchmark import doctor


def test_doctor_inspection_stops_between_bounded_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []
    cancelled = False

    def probe(executable: str | None):
        nonlocal cancelled
        calls.append(executable)
        cancelled = True
        return True, f"/bin/{executable}", "1.0"

    monkeypatch.setattr(doctor, "_probe", probe)
    monkeypatch.setattr(doctor, "_agentzero_ready", lambda: False)

    with pytest.raises(RuntimeError, match="Doctor inspection cancelled"):
        doctor.inspect(lambda: cancelled)

    assert len(calls) == 1
