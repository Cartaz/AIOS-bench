# Task catalog layout

The canonical active Frontier catalogs are:

- `frontier_v3/` — frozen/static Frontier v3 tasks.
- `frontier_v4/` — seeded parametric Frontier v4 tasks.
- `specs/` — benchmark-owned acceptance/specification material used by the active evaluators.

The root-level category JSON files (`autonomy.json`, `browser.json`, `coding.json`, `knowledge.json`, `learning.json`, `long_horizon.json`, `memory.json`, `subagents.json`, `tool_use.json`) and `frontier_v2.json` are historical catalog assets retained for provenance. Current `load_tasks()` calls always target an explicit active suite directory; the desktop exposes only the registered Frontier suites and does not merge these root-level files into current runs.

Do not edit a historical root-level catalog to change current benchmark behavior. Changes to an active suite belong in its versioned directory and will change that suite's semantic fingerprint.
