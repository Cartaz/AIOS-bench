from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import AGENTS

PROFILE_SCHEMA = "aios-bench/doctor-profile/v1"
DEFAULT_PROFILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "aios-bench" / "profile.json"


@dataclass(frozen=True)
class InstallRecipe:
    command: tuple[str, ...] | None
    shell: str | None
    docs: str
    note: str = ""


@dataclass(frozen=True)
class HarnessDoctorSpec:
    name: str
    executable: str | None
    install: Callable[[], InstallRecipe]
    config_hint: str


def _linux_id() -> str:
    try:
        values = {}
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
        return values.get("ID", "").lower()
    except OSError:
        return ""


def _npm_recipe(package: str, docs: str, note: str = "") -> InstallRecipe:
    return InstallRecipe(("npm", "install", "-g", package), None, docs, note)


def _pi_recipe() -> InstallRecipe:
    return _npm_recipe(
        "@mariozechner/pi-coding-agent",
        "https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent",
    )


def _opencode_recipe() -> InstallRecipe:
    if platform.system() == "Linux" and _linux_id() in {"arch", "cachyos", "endeavouros", "manjaro"}:
        return InstallRecipe(
            ("sudo", "pacman", "-S", "--needed", "opencode"),
            None,
            "https://opencode.ai/docs/",
            "Arch-family stable package; AUR users may prefer opencode-bin.",
        )
    return _npm_recipe("opencode-ai", "https://opencode.ai/docs/")


def _goose_recipe() -> InstallRecipe:
    return InstallRecipe(
        None,
        "curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | bash",
        "https://block.github.io/goose/",
        "Official Goose CLI installer.",
    )


def _letta_recipe() -> InstallRecipe:
    return _npm_recipe("@letta-ai/letta-code", "https://github.com/letta-ai/letta-code")


def _hermes_recipe() -> InstallRecipe:
    return InstallRecipe(
        None,
        "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser",
        "https://hermes-agent.nousresearch.com/docs/",
        "Uses the official installer and skips browser bootstrap; AIOS-bench enables only its pinned harness surface.",
    )


def _claude_recipe() -> InstallRecipe:
    return _npm_recipe(
        "@anthropic-ai/claude-code",
        "https://code.claude.com/docs/",
        "Claude Code may also offer a native installer; npm remains a portable CLI path.",
    )


def _agentzero_recipe() -> InstallRecipe:
    return InstallRecipe(
        None,
        None,
        "https://github.com/frdel/agent-zero",
        "Agent Zero is a service integration in AIOS-bench. Install/start the service separately, then configure its URL/project bridge.",
    )


SPECS: dict[str, HarnessDoctorSpec] = {
    "hermes": HarnessDoctorSpec("hermes", "hermes", _hermes_recipe, "Configure a local/custom provider in Hermes, then set AIOS_BENCH_HERMES_PROVIDER if needed."),
    "piagent": HarnessDoctorSpec("piagent", "pi", _pi_recipe, "Configure your local model/provider in Pi and verify that the benchmark --model identifier resolves there."),
    "opencode": HarnessDoctorSpec("opencode", "opencode", _opencode_recipe, "Configure an OpenAI-compatible custom provider in OpenCode and use the same model id passed to --model."),
    "goose": HarnessDoctorSpec("goose", "goose", _goose_recipe, "Configure the local provider used by Goose and set AIOS_BENCH_GOOSE_PROVIDER when the provider id is not implicit."),
    "letta": HarnessDoctorSpec("letta", "letta", _letta_recipe, "Use Letta /connect for the local provider and ensure the requested --model is selectable."),
    "agentzero": HarnessDoctorSpec("agentzero", None, _agentzero_recipe, "Set AIOS_BENCH_AGENTZERO_URL plus the project/root/model attestation variables required by the Agent Zero adapter."),
    "claude": HarnessDoctorSpec("claude", "claude", _claude_recipe, "Provide an Anthropic-compatible gateway via AIOS_BENCH_CLAUDE_BASE_URL (or ANTHROPIC_BASE_URL)."),
}


def _probe(executable: str | None) -> tuple[bool, str | None, str | None]:
    if not executable:
        return False, None, None
    path = shutil.which(executable)
    if not path:
        return False, None, None
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=4, check=False)
        output = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
        version = output[0][:200] if output else None
    except (OSError, subprocess.SubprocessError):
        version = None
    return True, path, version


def _agentzero_ready() -> bool:
    return bool(os.environ.get("AIOS_BENCH_AGENTZERO_URL") or os.environ.get("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT"))


def inspect() -> dict:
    harnesses = []
    for name in AGENTS:
        spec = SPECS[name]
        if name == "agentzero":
            installed = _agentzero_ready()
            path = "external-service" if installed else None
            version = os.environ.get("AIOS_BENCH_AGENTZERO_REVISION") or None
        else:
            installed, path, version = _probe(spec.executable)
        harnesses.append({
            "name": name,
            "display_name": AGENTS[name].display_name,
            "installed": installed,
            "path": path,
            "version": version,
            "docs": spec.install().docs,
            "config_hint": spec.config_hint,
        })
    return {
        "schema": "aios-bench/doctor-report/v1",
        "system": {
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "distribution": _linux_id() or None,
            "python": platform.python_version(),
            "node": shutil.which("node"),
            "npm": shutil.which("npm"),
            "bubblewrap": shutil.which("bwrap"),
        },
        "harnesses": harnesses,
        "ready": all(item["installed"] for item in harnesses),
    }


def load_profile(path: Path = DEFAULT_PROFILE) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def apply_profile_environment(path: Path = DEFAULT_PROFILE) -> dict:
    profile = load_profile(path)
    environment = profile.get("environment") if isinstance(profile.get("environment"), dict) else {}
    for key, value in environment.items():
        if isinstance(key, str) and isinstance(value, str) and value and key not in os.environ:
            os.environ[key] = value
    return profile


def write_profile(*, model: str, openai_url: str, anthropic_url: str, path: Path = DEFAULT_PROFILE) -> Path:
    environment: dict[str, str] = {}
    if openai_url:
        environment["AIOS_BENCH_ENDPOINT"] = openai_url.rstrip("/")
    if anthropic_url:
        environment["AIOS_BENCH_CLAUDE_BASE_URL"] = anthropic_url.rstrip("/")
    value = {
        "schema": PROFILE_SCHEMA,
        "model": model.strip(),
        "openai_compatible_url": openai_url.strip(),
        "anthropic_compatible_url": anthropic_url.strip(),
        "environment": environment,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def _yes_no(prompt: str, default: bool = True, input_fn=input) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input_fn(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "s", "si", "sì"}


def _run_install(recipe: InstallRecipe) -> bool:
    if recipe.command:
        try:
            return subprocess.run(list(recipe.command), check=False).returncode == 0
        except OSError:
            return False
    if recipe.shell:
        try:
            return subprocess.run(recipe.shell, shell=True, executable="/bin/bash", check=False).returncode == 0
        except OSError:
            return False
    return False


def render_report(report: dict) -> str:
    system = report["system"]
    lines = [
        "AIOS-bench Doctor",
        "",
        f"System: {system['platform']} {system['release']} ({system['machine']})",
        f"Python: {system['python']} | Node: {'yes' if system['node'] else 'no'} | npm: {'yes' if system['npm'] else 'no'} | bwrap: {'yes' if system['bubblewrap'] else 'no'}",
        "",
        "Harnesses:",
    ]
    for item in report["harnesses"]:
        mark = "OK" if item["installed"] else "MISSING"
        detail = item["version"] or item["path"] or "not detected"
        lines.append(f"  {mark:7} {item['display_name']:<14} {detail}")
    installed = sum(bool(item["installed"]) for item in report["harnesses"])
    lines += ["", f"Ready: {installed}/{len(report['harnesses'])} harnesses detected"]
    return "\n".join(lines)


def run_wizard(*, setup: bool, repair: bool, check_only: bool, input_fn=input) -> int:
    report = inspect()
    print(render_report(report))
    if check_only or (not setup and not repair):
        return 0 if report["ready"] else 1

    missing = [item for item in report["harnesses"] if not item["installed"]]
    if missing and _yes_no("Install or guide setup for missing harnesses?", True, input_fn):
        for item in missing:
            spec = SPECS[item["name"]]
            recipe = spec.install()
            print(f"\n{item['display_name']}")
            print(f"  Docs: {recipe.docs}")
            if recipe.note:
                print(f"  Note: {recipe.note}")
            if recipe.command:
                printable = " ".join(recipe.command)
                print(f"  Install: {printable}")
                if _yes_no("  Run this command now?", True, input_fn):
                    print("  Result:", "OK" if _run_install(recipe) else "FAILED")
            elif recipe.shell:
                print(f"  Install: {recipe.shell}")
                if _yes_no("  Run the official installer now?", False, input_fn):
                    print("  Result:", "OK" if _run_install(recipe) else "FAILED")
            else:
                print("  Installation is intentionally manual for this service-backed harness.")
            print(f"  Configure: {spec.config_hint}")

    current = load_profile()
    default_model = str(current.get("model") or "")
    default_openai = str(current.get("openai_compatible_url") or os.environ.get("AIOS_BENCH_ENDPOINT", ""))
    default_anthropic = str(current.get("anthropic_compatible_url") or os.environ.get("AIOS_BENCH_CLAUDE_BASE_URL", os.environ.get("ANTHROPIC_BASE_URL", "")))
    if _yes_no("Create/update the isolated AIOS-bench local-model profile?", True, input_fn):
        model = input_fn(f"Model id [{default_model or 'unknown'}]: ").strip() or default_model
        openai_url = input_fn(f"OpenAI-compatible URL [{default_openai}]: ").strip() or default_openai
        anthropic_url = input_fn(f"Anthropic-compatible URL [{default_anthropic}]: ").strip() or default_anthropic
        path = write_profile(model=model, openai_url=openai_url, anthropic_url=anthropic_url)
        print(f"Profile: {path}")

    final = inspect()
    print("\n" + render_report(final))
    profile = load_profile()
    model = profile.get("model") or "<model>"
    print(f"\nNext: aiosbench --all --model {model} smoke")
    return 0 if final["ready"] else 1
