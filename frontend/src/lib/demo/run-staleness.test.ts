import { describe, expect, it } from "vitest";

import { isStaleDemoRun, summarizeRunFailure } from "./run-staleness";

describe("isStaleDemoRun", () => {
  it("marks old queued runs as stale", () => {
    const now = Date.UTC(2026, 4, 9, 22, 0, 0);
    expect(
      isStaleDemoRun(
        {
          status: "queued",
          updatedAt: new Date(now - 20_000).toISOString()
        },
        now
      )
    ).toBe(true);
  });

  it("keeps fresh running runs active", () => {
    const now = Date.UTC(2026, 4, 9, 22, 0, 0);
    expect(
      isStaleDemoRun(
        {
          status: "running",
          updatedAt: new Date(now - 30_000).toISOString()
        },
        now
      )
    ).toBe(false);
  });
});

describe("summarizeRunFailure", () => {
  it("extracts the most useful error line from the runner log", () => {
    const summary = summarizeRunFailure(`Traceback...\nSystemError: broken env\nmore text`);
    expect(summary).toContain("SystemError");
  });
});
