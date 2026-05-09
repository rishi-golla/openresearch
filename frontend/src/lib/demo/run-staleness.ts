import type { DemoRunStatus } from "./demo-run-types";

export interface DemoRunStatusLike {
  status: DemoRunStatus;
  updatedAt: string;
}

const QUEUED_STALE_MS = 15_000;
const RUNNING_STALE_MS = 120_000;

export function isStaleDemoRun(
  status: DemoRunStatusLike,
  now = Date.now()
): boolean {
  const updatedAt = Date.parse(status.updatedAt);
  if (Number.isNaN(updatedAt)) {
    return false;
  }

  const ageMs = now - updatedAt;
  if (status.status === "queued") {
    return ageMs > QUEUED_STALE_MS;
  }
  if (status.status === "running") {
    return ageMs > RUNNING_STALE_MS;
  }
  return false;
}

export function summarizeRunFailure(log: string): string {
  const trimmed = log.trim();
  if (!trimmed) {
    return "Demo runner stopped updating before completion";
  }

  const lines = trimmed.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const tracebackLine = [...lines].reverse().find((line) => /error|exception/i.test(line));
  return tracebackLine ?? lines.at(-1) ?? "Demo runner stopped updating before completion";
}
