from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from .dashboard import build_dashboard
from .raw import source_index
from .report import write_summary
from .statistics import augment_summary_file


PUBLICATION_SCHEMA = "aios-bench/publication/v1"
DERIVED_FILES = ("summary.json", "dashboard.html")
ANALYSIS_IMPLEMENTATION_FILES = (
    "raw.py",
    "report.py",
    "statistics.py",
    "landscapes.py",
    "horizon.py",
    "horizon_analysis.py",
    "dashboard.py",
    "publication.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def analysis_implementation_index() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    files = [
        {
            "path": name,
            "sha256": _sha256(root / name),
            "bytes": (root / name).stat().st_size,
        }
        for name in ANALYSIS_IMPLEMENTATION_FILES
    ]
    return {
        "schema": "aios-bench/analysis-implementation/v1",
        "files": files,
        "digest": _canonical_sha256(files),
    }


def _output_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def render_derived(raw_root: Path, output_dir: Path) -> dict[str, Path]:
    """Regenerate all publishable derived artifacts from local raw inputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard = build_dashboard(raw_root, output_dir=output_dir)
    summary = write_summary(raw_root, output_dir=output_dir)
    augment_summary_file(summary, raw_root)
    return {"summary.json": summary, "dashboard.html": dashboard}


def build_publication_manifest(raw_root: Path, published_root: Path) -> dict[str, Any]:
    sources = source_index(raw_root)
    summary_path = published_root / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    outputs = {
        name: _output_record(published_root / name)
        for name in DERIVED_FILES
    }
    return {
        "schema": PUBLICATION_SCHEMA,
        "source": sources,
        "analysis_implementation": analysis_implementation_index(),
        "analysis_schema": summary.get("analysis_schema"),
        "selected_suite": summary.get("selected_suite"),
        "selected_suite_revision": summary.get("selected_suite_revision"),
        "raw_attempt_count": summary.get("raw_attempt_count"),
        "outputs": outputs,
    }


def write_publication_manifest(raw_root: Path, published_root: Path) -> Path:
    manifest = build_publication_manifest(raw_root, published_root)
    path = published_root / "publication.json"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def verify_publication(raw_root: Path, published_root: Path) -> dict[str, Any]:
    """Verify source snapshot, analysis code, output seals and regeneration."""
    errors: list[str] = []
    manifest_path = published_root / "publication.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "schema": "aios-bench/publication-verification/v1",
            "ok": False,
            "errors": ["publication.json is missing"],
        }
    except json.JSONDecodeError as exc:
        return {
            "schema": "aios-bench/publication-verification/v1",
            "ok": False,
            "errors": [f"publication.json is invalid: {exc}"],
        }

    if not isinstance(manifest, dict) or manifest.get("schema") != PUBLICATION_SCHEMA:
        errors.append("publication schema mismatch")

    current_source = source_index(raw_root)
    sealed_source = manifest.get("source") if isinstance(manifest, dict) else None
    if not isinstance(sealed_source, dict):
        errors.append("publication source index is missing")
    else:
        if sealed_source.get("digest") != current_source.get("digest"):
            errors.append("raw source digest changed since publication")
        if sealed_source.get("files") != current_source.get("files"):
            errors.append("raw source file index changed since publication")

    current_implementation = analysis_implementation_index()
    sealed_implementation = manifest.get("analysis_implementation") if isinstance(manifest, dict) else None
    if not isinstance(sealed_implementation, dict):
        errors.append("analysis implementation fingerprint is missing")
    elif sealed_implementation.get("digest") != current_implementation.get("digest"):
        errors.append("analysis implementation changed since publication")

    sealed_outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    if not isinstance(sealed_outputs, dict):
        sealed_outputs = {}
        errors.append("publication output seals are missing")

    actual_hashes: dict[str, str | None] = {}
    for name in DERIVED_FILES:
        path = published_root / name
        if not path.is_file():
            errors.append(f"published output is missing: {name}")
            actual_hashes[name] = None
            continue
        actual = _sha256(path)
        actual_hashes[name] = actual
        sealed = sealed_outputs.get(name)
        if not isinstance(sealed, dict) or sealed.get("sha256") != actual:
            errors.append(f"published output hash mismatch: {name}")

    regenerated_hashes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="aios-bench-verify-") as temporary:
        regenerated = render_derived(raw_root, Path(temporary))
        for name, path in regenerated.items():
            digest = _sha256(path)
            regenerated_hashes[name] = digest
            if actual_hashes.get(name) is not None and actual_hashes[name] != digest:
                errors.append(f"published output is not reproducible from raw inputs: {name}")

    summary_path = published_root / "summary.json"
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"published summary is invalid: {exc}")
        else:
            if summary.get("raw_source_digest") != current_source.get("digest"):
                errors.append("summary raw_source_digest does not match current raw source")
            if summary.get("raw_source_file_count") != current_source.get("file_count"):
                errors.append("summary raw_source_file_count does not match current raw source")

    return {
        "schema": "aios-bench/publication-verification/v1",
        "ok": not errors,
        "errors": errors,
        "source_digest": current_source.get("digest"),
        "analysis_implementation_digest": current_implementation.get("digest"),
        "published_hashes": actual_hashes,
        "regenerated_hashes": regenerated_hashes,
    }
