import type {
  AgentNode,
  ApprovalEntry,
  DashboardEvent,
  DashboardSnapshot,
  HermesPanel,
  ConceptCard
} from "./contract";

const agents: AgentNode[] = [
  {
    id: "root-orchestrator",
    label: "Root Orchestrator",
    type: "orchestrator",
    status: "running",
    currentTask: "Preparing the baseline reproduction plan",
    lastUpdated: "2026-05-08T22:14:10Z",
    outputTargetIds: ["paper-understanding", "environment-detective"],
    contextVariables: ["paper_claim_map", "artifact_inventory"]
  },
  {
    id: "paper-understanding",
    label: "Paper Understanding",
    type: "builder",
    status: "completed",
    parentId: "root-orchestrator",
    currentTask: "Claims extracted from MixMatch",
    lastUpdated: "2026-05-08T22:13:10Z",
    outputTargetIds: ["root-orchestrator"],
    contextVariables: ["claim_map", "ambiguity_log"]
  },
  {
    id: "environment-detective",
    label: "Environment Detective",
    type: "builder",
    status: "waiting",
    parentId: "root-orchestrator",
    currentTask: "Waiting on CUDA compatibility evidence",
    lastUpdated: "2026-05-08T22:14:40Z",
    outputTargetIds: ["baseline-runner"],
    contextVariables: []
  },
  {
    id: "supervisor-verifier",
    label: "Supervisor Verifier",
    type: "supervisor",
    status: "idle",
    parentId: "root-orchestrator",
    currentTask: "Awaiting baseline artifacts",
    lastUpdated: "2026-05-08T22:12:15Z",
    outputTargetIds: ["improvement-orchestrator"],
    contextVariables: ["verification_policy"]
  }
];

const pendingApproval: ApprovalEntry = {
  id: "approval-dataset-substitute",
  title: "Dataset substitution requested",
  owner: "Root Orchestrator",
  detail: "Original benchmark mirror timed out. Approve fallback download?",
  status: "pending",
  timestamp: "2026-05-08T22:15:30Z"
};

const initialHermesPanel: HermesPanel = {
  title: "Hermes Verification",
  summary: "Hermes is checking whether the current narrative is grounded before it is treated as trustworthy.",
  overallStatus: "checking",
  checks: [
    {
      id: "hermes-claim",
      label: "Claim grounded in paper",
      detail: "The extracted concept is linked to a primary source section.",
      status: "verified",
      evidenceLabel: "Paper section 3.2"
    },
    {
      id: "hermes-impl",
      label: "Implementation matches concept",
      detail: "Waiting for implementation evidence from the builder agents.",
      status: "checking"
    },
    {
      id: "hermes-artifacts",
      label: "Artifacts support result",
      detail: "No baseline artifacts available yet.",
      status: "pending"
    },
    {
      id: "hermes-publish",
      label: "UI claim safe to publish",
      detail: "Hermes will only mark the story publishable after evidence is complete.",
      status: "caveat"
    }
  ]
};

const initialConceptCard: ConceptCard = {
  id: "concept-mixmatch-core",
  title: "Consistency Regularization",
  interpretation: "The pipeline is translating the paper's semi-supervised consistency idea into a runnable training flow.",
  status: "active",
  implementedSurface: "Pending implementation surface",
  artifactHint: "Validation artifact will attach after the first baseline run.",
  metricHint: "Baseline metric: top-1 accuracy",
  milestones: [
    {
      id: "concept-extracted",
      label: "Extracted",
      detail: "Core concept recovered from the paper text.",
      status: "done"
    },
    {
      id: "concept-interpreted",
      label: "Interpreted",
      detail: "Mapped into an executable training concept.",
      status: "done"
    },
    {
      id: "concept-implemented",
      label: "Implemented",
      detail: "Implementation target not published yet.",
      status: "active"
    },
    {
      id: "concept-validated",
      label: "Validated",
      detail: "Validation waits on baseline artifacts.",
      status: "pending"
    },
    {
      id: "concept-improved",
      label: "Improved",
      detail: "Improvement analysis unlocks after verification.",
      status: "pending"
    }
  ]
};

export const initialDashboardSnapshot: DashboardSnapshot = {
  agents,
  reasoning: [
    {
      id: "reasoning-claim-map",
      agentId: "paper-understanding",
      agentLabel: "Paper Understanding",
      title: "Method fidelity anchored to the paper",
      detail: "Recovered the algorithm stages and linked the core claim to the original method section.",
      stepType: "paper_parse",
      timestamp: "2026-05-08T22:13:10Z",
      citations: [
        {
          id: "cite-paper-method",
          label: "Paper section 3.2",
          sourceType: "paper",
          excerpt: "Consistency regularization and MixUp combine during training.",
          trustLevel: "primary"
        }
      ]
    }
  ],
  messages: [
    {
      id: "message-claims-to-root",
      fromAgentId: "paper-understanding",
      toAgentId: "root-orchestrator",
      summary: "Claim map delivered",
      detail: "Structured claims, datasets, and unresolved ambiguities have been published.",
      timestamp: "2026-05-08T22:13:14Z"
    }
  ],
  citations: [
    {
      id: "cite-paper-method",
      label: "Paper section 3.2",
      sourceType: "paper",
      excerpt: "Consistency regularization and MixUp combine during training.",
      trustLevel: "primary"
    }
  ],
  approvals: [pendingApproval],
  progress: [
    {
      stage: "plan",
      status: "passed",
      detail: "Scope and claims locked for the MVP run."
    },
    {
      stage: "baseline",
      status: "running",
      detail: "Environment inference is in progress."
    },
    {
      stage: "improvement",
      status: "pending",
      detail: "Improvement agents unlock after baseline verification."
    }
  ],
  dataPanels: [
    {
      id: "claims",
      title: "Claim Map",
      summary: "3 core claims extracted with 2 open ambiguities.",
      items: [
        "Primary dataset fixed to CIFAR-10.",
        "Baseline metric is top-1 accuracy.",
        "One augmentation detail still requires repo corroboration."
      ]
    },
    {
      id: "assumptions",
      title: "Assumption Ledger",
      summary: "1 medium-risk assumption awaiting verification review.",
      items: [
        "Fallback repo issue suggests CUDA 11.3 compatibility.",
        "No substitute dataset approved yet."
      ]
    },
    {
      id: "artifacts",
      title: "Artifact Watch",
      summary: "Docker spec drafted, run logs pending.",
      items: [
        "Environment spec checkpoint saved.",
        "Metrics and plots panels will populate after the first baseline run."
      ]
    }
  ],
  hermesPanel: initialHermesPanel,
  conceptCard: initialConceptCard
};

export const mockDashboardEvents: DashboardEvent[] = [
  {
    event: "agent_started",
    timestamp: "2026-05-08T22:14:45Z",
    agent: {
      ...agents[2],
      status: "running",
      currentTask: "Reconciling CUDA and PyTorch requirements",
      lastUpdated: "2026-05-08T22:14:45Z"
    }
  },
  {
    event: "agent_reasoning_step",
    timestamp: "2026-05-08T22:15:03Z",
    agentId: "environment-detective",
    agentLabel: "Environment Detective",
    stepType: "rlm_query",
    title: "CUDA version cross-check",
    detail: "Issue tracker evidence points to CUDA 11.3 working while CUDA 12 fails.",
    citations: [
      {
        id: "cite-issue-14",
        label: "GitHub issue #14",
        sourceType: "repo_issue",
        excerpt: "CUDA 11.3 confirmed working, CUDA 12 fails.",
        trustLevel: "secondary"
      }
    ]
  },
  {
    event: "rlm_query_executed",
    timestamp: "2026-05-08T22:15:05Z",
    agentId: "environment-detective",
    agentLabel: "Environment Detective",
    query: "What CUDA version is discussed in the issue history?",
    result: "CUDA 11.3 is the strongest supported hint in the available evidence.",
    citations: [
      {
        id: "cite-issue-14",
        label: "GitHub issue #14",
        sourceType: "repo_issue",
        excerpt: "CUDA 11.3 confirmed working, CUDA 12 fails.",
        trustLevel: "secondary"
      }
    ]
  },
  {
    event: "shared_state_updated",
    timestamp: "2026-05-08T22:15:11Z",
    agentId: "environment-detective",
    changeType: "message",
    title: "Environment recommendation delivered",
    detail: "Publishing environment candidate back to the orchestrator with supporting evidence.",
    fromAgentId: "environment-detective",
    toAgentId: "root-orchestrator"
  },
  {
    event: "context_enrichment",
    timestamp: "2026-05-08T22:15:15Z",
    agentId: "environment-detective",
    variableName: "environment_candidate_v1",
    summary: "Draft Docker and package constraints added to shared context."
  },
  {
    event: "verification_gate_result",
    timestamp: "2026-05-08T22:15:20Z",
    stage: "baseline",
    status: "caveat",
    detail: "Baseline can proceed, but dataset fallback requires approval."
  },
  {
    event: "hermes_check_updated",
    timestamp: "2026-05-08T22:15:24Z",
    panel: {
      ...initialHermesPanel,
      overallStatus: "caveat",
      checks: initialHermesPanel.checks.map((check) =>
        check.id === "hermes-impl"
          ? {
              ...check,
              status: "caveat",
              detail: "Implementation target exists, but the artifact proof is still incomplete.",
              evidenceLabel: "Environment candidate v1"
            }
          : check
      )
    }
  },
  {
    event: "concept_card_updated",
    timestamp: "2026-05-08T22:15:26Z",
    card: {
      ...initialConceptCard,
      implementedSurface: "trainer.py -> consistency loss branch",
      milestones: initialConceptCard.milestones.map((milestone) =>
        milestone.id === "concept-implemented"
          ? {
              ...milestone,
              detail: "Trainer implementation target has been identified.",
              status: "done"
            }
          : milestone.id === "concept-validated"
            ? {
                ...milestone,
                detail: "Validation is now waiting on run artifacts.",
                status: "active"
              }
            : milestone
      )
    }
  },
  {
    event: "approval_requested",
    timestamp: "2026-05-08T22:15:30Z",
    approval: pendingApproval
  }
];
