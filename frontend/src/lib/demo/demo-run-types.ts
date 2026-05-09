import type { LiveDemoPayload } from "./pipeline-dashboard";

export type DemoRunMode = "offline" | "sdk";

export type DemoProvider = "anthropic" | "openai";

export type DemoExecutionMode = "efficient" | "max";

export type DemoSandboxMode = "local" | "docker";

export type DemoRunStatus =
  | "queued"
  | "running"
  | "stopped"
  | "completed"
  | "failed";

export interface LiveDemoRunState {
  projectId: string;
  outputDir: string;
  runMode: DemoRunMode;
  llmProvider?: DemoProvider;
  executionMode?: DemoExecutionMode;
  sandboxMode?: DemoSandboxMode;
  status: DemoRunStatus;
  sourceKind?: "workspace_fixture" | "uploaded_pdf";
  sourceLabel?: string;
  sourceNote?: string;
  startedAt?: string;
  updatedAt?: string;
  completedAt?: string;
  error?: string;
  pid?: number;
  payload: LiveDemoPayload | null;
  log: string;
}
