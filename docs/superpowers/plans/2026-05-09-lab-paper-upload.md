# Lab Paper Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PDF upload support to `/lab` so users can launch offline or SDK runs from an uploaded paper while keeping the existing fixture demo flow.

**Architecture:** Extend the lab demo API and runner to accept an optional uploaded PDF, stage it into the run directory, and route it through the repo's existing paper-ingestion pipeline. Keep the current fixture workflow as the fallback and surface uploaded-paper metadata in the dashboard source summary.

**Tech Stack:** Next.js route handlers, React client state, Node filesystem/process spawning, existing Python ingestion + pipeline services, Vitest

---

### Task 1: Add failing runner tests for uploaded-paper metadata and launch behavior

**Files:**
- Modify: `frontend/src/lib/demo/node-runner.ts`
- Create: `frontend/src/lib/demo/node-runner.test.ts`

- [ ] **Step 1: Write the failing tests**

- [ ] **Step 2: Run the targeted Vitest command and confirm failure**

Run: `npm test -- src/lib/demo/node-runner.test.ts`
Expected: FAIL because uploaded-paper start behavior does not exist yet.

- [ ] **Step 3: Implement the minimal runner support to satisfy the tests**

- [ ] **Step 4: Re-run the targeted Vitest command**

Run: `npm test -- src/lib/demo/node-runner.test.ts`
Expected: PASS

### Task 2: Add failing API tests for multipart upload handling

**Files:**
- Modify: `frontend/src/app/api/demo/route.ts`
- Create: `frontend/src/app/api/demo/route.test.ts`

- [ ] **Step 1: Write the failing tests for multipart upload requests**

- [ ] **Step 2: Run the targeted Vitest command and confirm failure**

Run: `npm test -- src/app/api/demo/route.test.ts`
Expected: FAIL because the route only supports mode-based starts.

- [ ] **Step 3: Implement multipart validation and uploaded-paper runner start**

- [ ] **Step 4: Re-run the targeted Vitest command**

Run: `npm test -- src/app/api/demo/route.test.ts`
Expected: PASS

### Task 3: Add failing UI tests for file selection and uploaded run submission

**Files:**
- Modify: `frontend/src/components/lab/live-demo-client.tsx`
- Create or Modify: `frontend/src/components/lab/live-demo-client.test.tsx`

- [ ] **Step 1: Write failing tests for file selection and upload-triggered fetch**

- [ ] **Step 2: Run the targeted Vitest command and confirm failure**

Run: `npm test -- src/components/lab/live-demo-client.test.tsx`
Expected: FAIL because the upload controls do not exist yet.

- [ ] **Step 3: Implement the upload UI with FormData submission**

- [ ] **Step 4: Re-run the targeted Vitest command**

Run: `npm test -- src/components/lab/live-demo-client.test.tsx`
Expected: PASS

### Task 4: Wire uploaded-paper metadata into dashboard summaries

**Files:**
- Modify: `frontend/src/lib/demo/pipeline-dashboard.ts`
- Modify: `frontend/src/lib/demo/pipeline-dashboard.test.ts`

- [ ] **Step 1: Add a failing dashboard test for uploaded-paper source metadata**

- [ ] **Step 2: Run the targeted Vitest command and confirm failure**

Run: `npm test -- src/lib/demo/pipeline-dashboard.test.ts`
Expected: FAIL because uploaded-paper source labels are not synthesized yet.

- [ ] **Step 3: Implement metadata handling**

- [ ] **Step 4: Re-run the targeted Vitest command**

Run: `npm test -- src/lib/demo/pipeline-dashboard.test.ts`
Expected: PASS

### Task 5: Run focused verification and smoke-check the lab flow

**Files:**
- Verify only

- [ ] **Step 1: Run the combined frontend verification suite**

Run: `npm test -- src/lib/demo/node-runner.test.ts src/app/api/demo/route.test.ts src/components/lab/live-demo-client.test.tsx src/lib/demo/pipeline-dashboard.test.ts src/features/dashboard/dashboard-shell.test.tsx`
Expected: PASS

- [ ] **Step 2: Run the production build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: Start or refresh the lab server and smoke-test `/lab`**

Run: use the existing local frontend server, then open `http://127.0.0.1:3000/lab`
Expected: Upload control appears, fixture buttons still work, uploaded-paper run starts.
