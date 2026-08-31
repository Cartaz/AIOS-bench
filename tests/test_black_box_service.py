from concurrent.futures import ThreadPoolExecutor
import time
from pathlib import Path

from core.benchmark import black_box_service
from core.benchmark.black_box_service import BlackBoxInputError, BlackBoxReferenceService
from core.benchmark.parametric import materialize_variant


def test_probe_budget_is_atomic_across_concurrent_requests(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("black_box_reconstruction", workspace, seed=91)
    log_path = tmp_path / "probes.jsonl"
    service = BlackBoxReferenceService(oracle["reference_spec"], 2, log_path)
    original = black_box_service.reference_transform

    def slow_transform(spec, record):
        time.sleep(0.01)
        return original(spec, record)

    monkeypatch.setattr(black_box_service, "reference_transform", slow_transform)
    record = {
        "region": "eu",
        "plan": "plus",
        "units": 37,
        "priority": 3,
        "active": True,
        "tags": ["alpha"],
    }

    def probe() -> bool:
        try:
            service.probe(record)
        except BlackBoxInputError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        successes = list(executor.map(lambda _: probe(), range(8)))

    assert sum(successes) == 2
    assert service.probes_used == 2
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2
    assert service.contract()["probes_remaining"] == 0
