// Temporary frontend-local mirror of the PRD event contract until issue #8
// lands a shared package that both the backend and frontend can import.

export type AgentType =
  | "orchestrator"
  | "builder"
  | "verifier"
  | "improvement"
  | "supervisor";

export type AgentStatus = "idle" | "running" | "waiting" | "completed" | "failed";

export type TrustLevel =
  | "primary"
  | "strong_secondary"
  | "secondary"
  | "weak";

export type PipelineStage = "plan" | "baseline" | "improvement";

export type ProgressStatus = "pending" | "running" | "passed" | "failed" | "caveat";

export type ApprovalStatus = "pending" | "approved" | "rejected";
export type HermesCheckStatus =
  | "pending"
  | "checking"
  | "verified"
  | "caveat"
  | "unsupported";
export type ConceptMilestoneStatus = "pending" | "active" | "done";

export interface Citation {
  id: string;
  label: string;
  sourceType: string;
  excerpt: string;
  trustLevel: TrustLevel;
}

export interface AgentNode {
  id: string;
  label: string;
  type: AgentType;
  status: AgentStatus;
  parentId?: string;
  currentTask: string;
  lastUpdated: string;
  outputTargetIds: string[];
  contextVariables: string[];
}

export interface ReasoningEntry {
  id: string;
  agentId: string;
  agentLabel: string;
  title: string;
  detail: string;
  stepType: string;
  timestamp: string;
  citations: Citation[];
}

export interface MessageEntry {
  id: string;
  fromAgentId: string;
  toAgentId: string;
  summary: string;
  detail: string;
  timestamp: string;
}

export interface ApprovalEntry {
  id: string;
  title: string;
  owner: string;
  detail: string;
  status: ApprovalStatus;
  timestamp: string;
}

export interface ProgressEntry {
  stage: PipelineStage;
  status: ProgressStatus;
  detail: string;
}

export interface DataPanel {
  id: string;
  title: string;
  summary: string;
  items: string[];
}

export interface HermesCheckItem {
  id: string;
  label: string;
  detail: string;
  status: HermesCheckStatus;
  evidenceLabel?: string;
}

export interface HermesPanel {
  title: string;
  summary: string;
  overallStatus: HermesCheckStatus;
  checks: HermesCheckItem[];
}

export interface ConceptMilestone {
  id: string;
  label: string;
  detail: string;
  status: ConceptMilestoneStatus;
}

export interface ConceptCard {
  id: string;
  title: string;
  interpretation: string;
  status: "planned" | "active" | "validated" | "improved";
  implementedSurface: string;
  artifactHint: string;
  metricHint: string;
  improvementHint?: string;
  milestones: ConceptMilestone[];
}

export interface DashboardSnapshot {
  agents: AgentNode[];
  reasoning: ReasoningEntry[];
  messages: MessageEntry[];
  citations: Citation[];
  approvals: ApprovalEntry[];
  progress: ProgressEntry[];
  dataPanels: DataPanel[];
  hermesPanel: HermesPanel | null;
  conceptCard: ConceptCard | null;
}

interface BaseDashboardEvent {
  event: string;
  timestamp: string;
  agentId?: string;
}

export interface AgentLifecycleEvent extends BaseDashboardEvent {
  event: "agent_started" | "agent_completed" | "agent_failed";
  agent: AgentNode;
}

export interface AgentReasoningStepEvent extends BaseDashboardEvent {
  event: "agent_reasoning_step";
  agentId: string;
  agentLabel: string;
  stepType: string;
  title: string;
  detail: string;
  citations: Citation[];
}

export interface QueryExecutedEvent extends BaseDashboardEvent {
  event: "rlm_query_executed" | "semantic_search_executed";
  agentId: string;
  agentLabel: string;
  query: string;
  result: string;
  citations: Citation[];
}

export interface SharedStateUpdatedEvent extends BaseDashboardEvent {
  event: "shared_state_updated";
  agentId: string;
  changeType: "message" | "assumption" | "decision" | "ledger_entry";
  title: string;
  detail: string;
  fromAgentId?: string;
  toAgentId?: string;
}

export interface VerificationGateResultEvent extends BaseDashboardEvent {
  event: "verification_gate_result";
  stage: PipelineStage;
  status: ProgressStatus;
  detail: string;
}

export interface ApprovalRequestedEvent extends BaseDashboardEvent {
  event: "approval_requested";
  approval: ApprovalEntry;
}

export interface ApprovalResolvedEvent extends BaseDashboardEvent {
  event: "approval_resolved";
  approvalId: string;
  status: Exclude<ApprovalStatus, "pending">;
  detail: string;
}

export interface ContextEnrichmentEvent extends BaseDashboardEvent {
  event: "context_enrichment";
  agentId: string;
  variableName: string;
  summary: string;
}

export interface HermesCheckUpdatedEvent extends BaseDashboardEvent {
  event: "hermes_check_updated";
  panel: HermesPanel;
}

export interface ConceptCardUpdatedEvent extends BaseDashboardEvent {
  event: "concept_card_updated";
  card: ConceptCard;
}

export type DashboardEvent =
  | AgentLifecycleEvent
  | AgentReasoningStepEvent
  | QueryExecutedEvent
  | SharedStateUpdatedEvent
  | VerificationGateResultEvent
  | ApprovalRequestedEvent
  | ApprovalResolvedEvent
  | ContextEnrichmentEvent
  | HermesCheckUpdatedEvent
  | ConceptCardUpdatedEvent;

export type DashboardEventListener = (event: DashboardEvent) => void;

export interface DashboardEventAdapter {
  getSnapshot(): DashboardSnapshot;
  subscribe(listener: DashboardEventListener): () => void;
  flush(): Promise<void>;
}
