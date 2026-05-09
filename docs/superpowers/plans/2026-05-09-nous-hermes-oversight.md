# Nous Hermes Oversight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real backend oversight layer powered by Nous Hermes that audits pipeline outputs, traces, and artifacts, then records bounded interventions without replacing the existing agents.

**Architecture:** Introduce a new `backend/hermes_audit/` service package with stable models, payload builders, storage, and a Nous Hermes client adapter. Thread that service through the orchestrator so major steps and checkpoints emit audit reports and optional bounded interventions while preserving the current pipeline structure.

**Tech Stack:** Python 3.11, Pydantic v2, Claude Agent SDK, optional Nous Hermes Python runtime (`run_agent.AIAgent`), pytest

---

### Task 1: Add Hermes audit domain models and storage

**Files:**
- Create: `backend/hermes_audit/__init__.py`
- Create: `backend/hermes_audit/models.py`
- Create: `backend/hermes_audit/storage.py`
- Test: `tests/test_hermes_audit_models.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement minimal models and storage**
- [ ] **Step 4: Run tests to verify they pass**

### Task 2: Add Nous Hermes payload building and client/service adapter

**Files:**
- Create: `backend/hermes_audit/payloads.py`
- Create: `backend/hermes_audit/client.py`
- Create: `backend/hermes_audit/service.py`
- Modify: `pyproject.toml`
- Test: `tests/test_hermes_audit_service.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement payload builder, client abstraction, and service**
- [ ] **Step 4: Run tests to verify they pass**

### Task 3: Thread Hermes oversight through the orchestrator

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Modify: `backend/agents/pipeline.py`
- Modify: `backend/agents/__init__.py`
- Test: `tests/test_issue22_orchestrator.py`
- Test: `tests/test_hermes_audit_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrator integration tests**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement step/checkpoint audit hooks and bounded intervention handling**
- [ ] **Step 4: Run tests to verify they pass**

### Task 4: Run regression verification

**Files:**
- Test: `tests/test_issue27_verification.py`
- Test: `tests/test_issue29_e2e_pipeline.py`

- [ ] **Step 1: Run targeted regression suites**
- [ ] **Step 2: Fix any integration regressions**
- [ ] **Step 3: Re-run targeted suites and confirm green**
