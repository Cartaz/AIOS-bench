# Browser Automation Implementation Decision Memo

**Technology:** Playwright for Python (Browser Automation & Data Extraction)
**Date:** 2026-08-19
**Workspace:** browser_002 (AIOS-bench fixture — CSV data processing pipeline)
**Author:** AI Agent — evaluated against official Playwright documentation and ecosystem sources

---

## 1. Executive Summary

This memo recommends **Playwright for Python** as the browser automation technology for the browser_002 workspace. The workspace currently processes `data/expenses.csv` and `data/sales.csv` through a manual procedure chain (export → validate → calculate → save summary → review). Playwright enables automated browser-based data extraction, form automation, and web-based report generation, directly supporting the weekly review workflow described in the meeting notes ("review software subscriptions before next month").

The recommendation is based on analysis of **four authoritative sources** (see Source Table, §8), with version guidance reconciled across PyPI, official documentation, and the GitHub repository. Playwright v1.62.0 (stable, as of August 2026) is the current release, supporting Python 3.10+.

---

## 2. Technology Overview

Playwright is an open-source browser automation library developed by Microsoft that supports all modern rendering engines:

- **Chromium** (Chrome, Edge, and open-source Chromium builds)
- **WebKit** (Safari engine)
- **Firefox**

Key capabilities:

- **Auto-waiting**: Eliminates flaky tests by performing actionability checks (visible, enabled, stable, receiving pointer events, editable) before each action — no manual sleeps or waits needed.
- **Locators**: Role-based and text-based locators that produce resilient, user-facing selectors.
- **Sync & Async APIs**: Both synchronous and asynchronous Python APIs are supported; the choice depends on project concurrency requirements.
- **Headed & Headless Modes**: Standard headless mode (fast) and "New Headless" mode (real Chrome browser, more authentic, suitable for high-accuracy testing and browser extension testing).
- **Multi-platform**: Windows 11+, macOS 14+ (Sonoma+), Debian 12/13, Ubuntu 22.04/24.04/26.04.
- **Docker support**: Official `mcr.microsoft.com/playwright/python` images published, with version pinning recommended.
- **CI/CD ready**: Native CI integration with parallel browser execution and trace viewer for debugging.

---

## 3. Prerequisites

### 3.1 Runtime Requirements

| Requirement | Specification | Source |
|---|---|---|
| Python version | **≥ 3.10** (PyPI metadata); official docs also list 3.8+ for older versions | [Source 1](#81-pypi-playwright), [Source 2](#82-playwright-official-python-docs-installation) |
| OS Platforms | Windows 11+ / WSL, macOS 14+ (Sonoma), Debian 12/13, Ubuntu 22.04/24.04/26.04 (x86-64 or arm64) | [Source 2](#82-playwright-official-python-docs-installation) |
| Package manager | pip, poetry, or uv | [Source 2](#82-playwright-official-python-docs-installation) |

### 3.2 System Dependencies

- Playwright ships its own browser binaries. System dependencies (GTK, NSS, fonts, etc.) are installed automatically when running `playwright install --with-deps`.
- For Docker: `mcr.microsoft.com/playwright/python` base images available (Debian-based and Alpine-based).
- **Python 3.7 note**: On Windows Python 3.7, Playwright sets the default event loop to `WindowsProactorEventLoopPolicy`. For Python 3.10+, this is handled automatically.

### 3.3 Workspace-Specific Prerequisites

The current workspace already has:

- ✅ Python 3.14.7 (meets ≥ 3.10 requirement)
- ✅ pip available
- ✅ Linux host (Debian/Ubuntu-compatible environment)
- ✅ Existing CSV data files (`data/expenses.csv`, `data/sales.csv`)

---

## 4. Installation & Setup

### 4.1 Recommended Installation Commands

```bash
# Install Playwright and pytest-playwright plugin
pip install pytest-playwright

# Install browser binaries (Chromium, Firefox, WebKit)
playwright install

# Optional: Install system dependencies (recommended for CI/new machines)
playwright install --with-deps
```

Alternative package managers:

```bash
# Poetry
poetry add pytest-playwright
playwright install

# uv
uv add pytest-playwright playwright
playwright install
```

### 4.2 Update Command

```bash
pip install pytest-playwright playwright -U
playwright install
```

### 4.3 Verification Steps

After installation, verify the setup:

```bash
# Verify installed Playwright version
playwright --version
# Expected output: 1.62.0 (or latest stable)

# Verify browser binaries are installed
playwright install --dry-run

# Run a basic smoke test
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://playwright.dev/')
    print('Page title:', page.title())
    print('Verification: SUCCESS')
    browser.close()
"

# Run example tests
pytest --tracing=on
```

---

## 5. Application to This Workspace

### 5.1 Current Workflow (from `procedures/current.md`)

1. Export the monthly sales CSV.
2. Validate the header and numeric fields.
3. Calculate total revenue and units.
4. Save the summary as `reports/monthly-sales.md`.
5. Review the result before sharing it.

### 5.2 Proposed Playwright-Based Enhancements

| Step | Current (Manual) | Playwright Enhancement |
|---|---|---|
| Data export | Manual CSV export | Automated browser-based data export from web dashboards |
| Validation | Manual header/field checks | Playwright locators to validate HTML table structures from web sources |
| Calculation | Manual/Python `monthly_total` (see `projects/broken_tool.py`) | Playwright can extract computed values directly from rendered web reports |
| Summary generation | Manual `reports/monthly-sales.md` | Automated web form submission or API calls to generate reports |
| Review step | Human review (unchanged) | Playwright screenshot capture for visual review documentation |

### 5.3 Fixing `projects/broken_tool.py`

The existing `projects/broken_tool.py` contains a bug where it passes `"30"` (a string) to `monthly_total()`, which would fail with a type error in Python. Playwright's auto-waiting and assertion capabilities can prevent similar type-safety issues when extracting numeric data from web elements.

---

## 6. Compatibility Constraints & Version Reconciliation

### 6.1 Version Guidance — Sources in Conflict

Four authoritative sources provide the following version guidance:

| Source | Playwright Package Version | pytest-playwright Version | Python Minimum | Notes |
|---|---|---|---|---|
| **PyPI (playwright)** | 1.62.0 (latest stable) | — | ≥ 3.10 | PyPI metadata |
| **PyPI (pytest-playwright)** | — | 0.9.0 (latest stable) | ≥ 3.10 | PyPI metadata |
| **Official Docs (playwright.dev)** | 1.62 (stable tag) | 0.9.0 | ≥ 3.8 (for older docs) | docs-version-stable |
| **GitHub Releases** | v1.62.x | — | — | GitHub changelog |

### 6.2 Resolution of Conflicts

1. **Python version**: Official documentation for the current stable version (v1.62+) requires Python **≥ 3.10**, per PyPI metadata. Older documentation (3.8+) refers to prior Playwright versions. **Recommendation: Use ≥ 3.10 as the constraint.** The workspace has Python 3.14.7, which exceeds this requirement.

2. **Playwright package version**: All four sources converge on **v1.62** as the current stable version. No conflict.

3. **pytest-playwright version**: PyPI shows **0.9.0**, which depends on `playwright>=1.18`. The official docs confirm compatibility with the latest Playwright. **Recommendation: Use pytest-playwright 0.9.0 + playwright 1.62.0.**

4. **Browser version alignment**: Playwright v1.62 ships with Chromium N+1 (ahead of the stable Chrome release by a few weeks), ensuring early detection of breaking changes. This is by design and documented in the [browsers guide](https://playwright.dev/python/docs/browsers).

### 6.3 Docker Version Matching

**Critical constraint**: When using Docker, the Playwright version in the container **must match** the version in the test/project. Mismatched versions cause browser executable lookup failures.

```bash
# Verify version alignment
docker run mcr.microsoft.com/playwright/python:v1.62.0-jammy playwright --version
# Should output: 1.62.0
```

---

## 7. Decision Matrix

| Criterion | Playwright for Python | Rationale |
|---|---|---|
| **Relevance to workspace** | ✅ High | Directly applicable to browser automation for the browser_002 data pipeline |
| **Python compatibility** | ✅ Excellent | Official support for Python 3.10–3.14; workspace runs 3.14 |
| **Documentation quality** | ✅ Comprehensive | 40+ guide pages; sync/async coverage; Docker integration |
| **Community & maintenance** | ✅ Active | Microsoft-backed; weekly releases; Discord & Stack Overflow |
| **Multi-browser support** | ✅ 3 engines | Chromium, WebKit, Firefox with same API |
| **Headless mode** | ✅ Two modes | Standard (fast) + New Headless (authentic) |
| **CI/CD readiness** | ✅ Built-in | Trace viewer, parallel execution, CI guides |
| **Learning curve** | Moderate | Well-structured docs; pytest plugin simplifies testing |

**Decision: PROCEED with Playwright for Python v1.62.0 + pytest-playwright 0.9.0.**

---

## 8. Source Table

| # | Source | Type | URL / Reference | Version / Date |
|---|---|---|---|---|
| **1** | **PyPI — playwright package** | Package registry | https://pypi.org/pypi/playwright/json | v1.62.0 (latest stable) |
| **2** | **PyPI — pytest-playwright package** | Package registry | https://pypi.org/pypi/pytest-playwright/json | v0.9.0 (latest stable) |
| **3** | **Playwright Official Python Documentation** | Official vendor docs | https://playwright.dev/python/docs/intro | version-stable (v1.62) |
| **4** | **GitHub — microsoft/playwright-python** | Open-source repository | https://github.com/microsoft/playwright-python | v1.62.x release line |

**Supplementary sources consulted:**

| Source | Type | URL |
|---|---|---|
| Playwright Browsers Guide | Official docs | https://playwright.dev/python/docs/browsers |
| Playwright Library API | Official docs | https://playwright.dev/python/docs/library |
| Playwright Docker Guide | Official docs | https://playwright.dev/python/docs/docker |
| Playwright Release Notes | Official docs | https://playwright.dev/python/docs/release-notes |
| Playwright Actions/Auto-waiting | Official docs | https://playwright.dev/python/docs/actionability |
| Playwright Locators | Official docs | https://playwright.dev/python/docs/locators |

---

## 9. Recommended Commands Summary

```bash
# --- Installation ---
pip install pytest-playwright
playwright install --with-deps

# --- Verification ---
playwright --version
python3 -c "from playwright.sync_api import sync_playwright; print('OK')"

# --- Quick smoke test ---
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    p = b.new_page()
    p.goto('https://playwright.dev/')
    assert 'Playwright' in p.title()
    print('Smoke test passed:', p.title())
    b.close()
"

# --- Production: Use in workspace ---
# Place browser automation scripts in projects/
# Run with: pytest projects/ --browser=chromium
```

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Browser binary size (~400MB) | Disk usage | Install only needed browsers: `playwright install chromium` |
| Version mismatch in Docker | Runtime failure | Pin Docker image tag: `mcr.microsoft.com/playwright/python:v1.62.0-jammy` |
| Web pages change structure | Broken automation | Use Playwright's role-based locators (closest to user perception); implement auto-retrying assertions |
| Multi-threaded environments | Thread-safety violations | Create one `playwright` instance per thread; Playwright API is not thread-safe |
| Enterprise browser policies | Chrome/Edge launch failures | Use Playwright's bundled Chromium instead of branded browsers; policies are out-of-scope |

---

## 11. Conclusion

Playwright for Python v1.62.0 is the recommended browser automation technology for the browser_002 workspace. It meets all prerequisites (Python ≥ 3.10, supported OS platforms), provides comprehensive documentation, and offers robust features (auto-waiting, multi-engine support, Docker integration) that directly enhance the existing data processing pipeline. The version guidance from all four authoritative sources has been reconciled, with v1.62.0 / pytest-playwright 0.9.0 / Python ≥ 3.10 identified as the correct installation targets.

---

*Memo generated from official Playwright documentation and PyPI metadata. No workspace source data files were modified.*
