# Effective Configuration Report

## Reference Chain

The following chain of indirect references was followed to discover the effective runtime configuration:

1. **`README.md`** — The top-level workspace README states: *"For the current runtime configuration, follow the reference chain: `docs/README.md`."*
2. **`docs/README.md`** — This file says: *"See `config/app.yaml` for the effective runtime configuration."*
3. **`config/app.yaml`** — The actual configuration file containing the effective settings.

**Full reference chain:**
`README.md` → `docs/README.md` → `config/app.yaml`

## Effective Settings (from `config/app.yaml`)

| Setting  | Value      |
|----------|------------|
| `port`   | `8081`     |
| `env`    | `production` |

## Consumer Code

The configuration file is consumed by **`tools/run_server.py`**, which loads it via:

```python
from pathlib import Path
import yaml
CONFIG = Path(__file__).parents[1] / 'config' / 'app.yaml'

def effective_config():
    return yaml.safe_load(CONFIG.read_text())
```

The `run_server.py` module reads `config/app.yaml` using `yaml.safe_load()` and exposes the parsed configuration through the `effective_config()` function. This is the primary consumer of the configuration settings.

A secondary consumer, **`projects/report_tool.py`**, is a standalone CSV-to-JSON report tool that does not read the config file.

## Summary

The workspace's effective runtime configuration is minimal: the application runs on **port 8081** in the **production** environment. The configuration is loaded programmatically by `tools/run_server.py` from `config/app.yaml`, which is the terminal node in the reference chain originating from `README.md`.
