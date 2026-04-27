# Public Multi-Source Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the public refresh pipeline from one source to two public trend-editorial sources with source selection, source-level reporting, and source-specific parsing boundaries.

**Architecture:** Keep the existing refresh chain intact, but add a dedicated source-selection layer, expand the registry contract with reporting metadata, move source-specific provenance hints to adapter-produced snapshot sections, and add one new heterogeneous adapter while reusing the Who What Wear path for the second homologous source.

**Tech Stack:** Python 3 standard library, JSON fixtures, `unittest`, existing refresh / ingestion modules, PowerShell git workflow.

---

## File Map

- Modify: `data/refresh/dress/source_registry.json`
  - Add the second Who What Wear source, the Marie Claire source, and registry metadata fields.
- Modify: `temu_y2_women/public_source_registry.py`
  - Validate new registry fields and expose selected enabled sources.
- Modify: `temu_y2_women/public_signal_refresh.py`
  - Add source selection, run-id update, and source-level reporting.
- Modify: `temu_y2_women/public_signal_refresh_cli.py`
  - Add repeated `--source-id`.
- Modify: `temu_y2_women/public_source_adapter.py`
  - Register new adapter ids.
- Modify: `temu_y2_women/canonical_signal_builder.py`
  - Move provenance derivation to snapshot section metadata instead of hard-coded single-source constants.
- Modify: `temu_y2_women/public_source_adapters/whowhatwear_editorial.py`
  - Generalize for the second Who What Wear source profile.
- Create: `temu_y2_women/public_source_adapters/marieclaire_editorial.py`
  - Parse the heterogeneous editorial source into snapshot sections.
- Create or update: `tests/test_public_source_registry.py`
- Create or update: `tests/test_public_source_adapter.py`
- Create or update: `tests/test_canonical_signal_builder.py`
- Create or update: `tests/test_public_signal_refresh.py`
- Create or update: `tests/test_public_signal_refresh_cli.py`
- Create fixtures under:
  - `tests/fixtures/public_sources/dress/*.html`
  - `tests/fixtures/public_sources/dress/expected-*.json`
  - `tests/fixtures/public_refresh/dress/expected-*.json`

### Task 1: Expand the registry contract and source-selection boundary

**Files:**
- Modify: `data/refresh/dress/source_registry.json`
- Modify: `temu_y2_women/public_source_registry.py`
- Modify: `tests/test_public_source_registry.py`

- [ ] **Step 1: Write the failing registry tests**
- [ ] **Step 2: Run `python -m unittest tests.test_public_source_registry -v` and confirm the new selection/metadata expectations fail**
- [ ] **Step 3: Implement `priority` / `weight` validation and add a focused source-selection helper that can fail closed on unknown or disabled `source_id`**
- [ ] **Step 4: Update the registry fixture to include the second Who What Wear source and the Marie Claire source**
- [ ] **Step 5: Re-run `python -m unittest tests.test_public_source_registry -v` until green**

### Task 2: Add the second Who What Wear source and Marie Claire adapter coverage

**Files:**
- Modify: `temu_y2_women/public_source_adapter.py`
- Modify: `temu_y2_women/public_source_adapters/whowhatwear_editorial.py`
- Create: `temu_y2_women/public_source_adapters/marieclaire_editorial.py`
- Modify: `tests/test_public_source_adapter.py`
- Create/update fixtures in `tests/fixtures/public_sources/dress/`

- [ ] **Step 1: Write failing adapter tests for the second Who What Wear source and the new Marie Claire source**
- [ ] **Step 2: Run `python -m unittest tests.test_public_source_adapter -v` and verify the new adapter expectations fail**
- [ ] **Step 3: Refactor the Who What Wear adapter so section rules can differ by source id without duplicating the whole parser**
- [ ] **Step 4: Implement the Marie Claire editorial adapter and register its adapter id**
- [ ] **Step 5: Re-run `python -m unittest tests.test_public_source_adapter -v` until green**

### Task 3: Move canonical provenance to source-driven section metadata

**Files:**
- Modify: `temu_y2_women/canonical_signal_builder.py`
- Modify: `tests/test_canonical_signal_builder.py`
- Update fixture payloads under `tests/fixtures/public_sources/dress/`

- [ ] **Step 1: Write failing canonical-builder tests that assert multi-source provenance is taken from snapshot section metadata**
- [ ] **Step 2: Run `python -m unittest tests.test_canonical_signal_builder -v` and verify the provenance assertions fail**
- [ ] **Step 3: Implement the minimal canonical-builder change so `confidence`, `adapter_version`, `warnings`, `matched_keywords`, and `excerpt_anchor` come from section metadata while preserving the existing bundle contract**
- [ ] **Step 4: Refresh the expected canonical-signal and signal-bundle fixtures**
- [ ] **Step 5: Re-run `python -m unittest tests.test_canonical_signal_builder -v` until green**

### Task 4: Extend refresh orchestration and report contracts

**Files:**
- Modify: `temu_y2_women/public_signal_refresh.py`
- Modify: `tests/test_public_signal_refresh.py`
- Update fixture payloads under `tests/fixtures/public_refresh/dress/`

- [ ] **Step 1: Write failing refresh tests for all-source runs, selected-source runs, and source-level report details**
- [ ] **Step 2: Run `python -m unittest tests.test_public_signal_refresh -v` and confirm the new report/selection expectations fail**
- [ ] **Step 3: Implement source selection, stable multi-source run id generation, and `source_details` reporting without changing the staged artifact list**
- [ ] **Step 4: Refresh expected `refresh_report.json` and other staged artifact fixtures for both all-source and single-source runs**
- [ ] **Step 5: Re-run `python -m unittest tests.test_public_signal_refresh -v` until green**

### Task 5: Extend CLI coverage and run regression verification

**Files:**
- Modify: `temu_y2_women/public_signal_refresh_cli.py`
- Modify: `tests/test_public_signal_refresh_cli.py`

- [ ] **Step 1: Write failing CLI tests for repeated `--source-id`, selected-source forwarding, and invalid source failure**
- [ ] **Step 2: Run `python -m unittest tests.test_public_signal_refresh_cli -v` and verify the new CLI expectations fail**
- [ ] **Step 3: Implement repeated `--source-id` parsing and result forwarding**
- [ ] **Step 4: Re-run the focused CLI suite until green**
- [ ] **Step 5: Run end-to-end regression**

```bash
python -m unittest tests.test_public_signal_refresh_cli tests.test_public_signal_refresh tests.test_canonical_signal_builder tests.test_public_source_adapter tests.test_signal_ingestion tests.test_public_source_registry -v
python -m py_compile temu_y2_women\public_source_registry.py temu_y2_women\public_signal_refresh.py temu_y2_women\public_signal_refresh_cli.py temu_y2_women\public_source_adapter.py temu_y2_women\public_source_adapters\whowhatwear_editorial.py temu_y2_women\public_source_adapters\marieclaire_editorial.py temu_y2_women\canonical_signal_builder.py
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

- [ ] **Step 6: Review `git diff --stat` and prepare the branch for PR-only shipping**
