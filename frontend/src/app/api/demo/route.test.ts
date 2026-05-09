// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const startDemoRun = vi.fn();
const loadDemoRun = vi.fn();
const stopDemoRun = vi.fn();

vi.mock("@/lib/demo/node-runner", () => ({
  startDemoRun,
  loadDemoRun,
  stopDemoRun
}));

describe("POST /api/demo", () => {
  beforeEach(() => {
    startDemoRun.mockReset();
    loadDemoRun.mockReset();
    stopDemoRun.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts an uploaded-paper run from multipart form data", async () => {
    startDemoRun.mockResolvedValue({
      projectId: "prj_upload",
      outputDir: "runs/prj_upload",
      runMode: "sdk",
      status: "queued",
      payload: null,
      log: ""
    });

    const { POST } = await import("./route");
    const formData = new FormData();
    formData.set("mode", "sdk");
    formData.set(
      "paper",
      new File([new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])], "paper.pdf", {
        type: "application/pdf"
      })
    );

    const response = await POST(
      new Request("http://localhost:3000/api/demo", {
        method: "POST",
        body: formData
      })
    );

    expect(response.status).toBe(202);
    expect(startDemoRun).toHaveBeenCalledWith("sdk", "anthropic", "efficient", "local", {
      uploadedPaper: expect.objectContaining({
        fileName: "paper.pdf"
      })
    });
  });

  it("rejects multipart requests without a pdf file", async () => {
    const { POST } = await import("./route");
    const formData = new FormData();
    formData.set("mode", "offline");

    const response = await POST(
      new Request("http://localhost:3000/api/demo", {
        method: "POST",
        body: formData
      })
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: "Upload a PDF before starting a lab run."
    });
    expect(startDemoRun).not.toHaveBeenCalled();
  });
});
