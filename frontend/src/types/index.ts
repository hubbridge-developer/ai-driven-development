export interface Workflow {
  id: string;
  workflow_id: string;
  status: 'running' | 'waiting_approval' | 'waiting_code_approval' | 'completed' | 'cancelled' | 'failed' | 'error';
  current_agent: string;
  user_request: string;
  state_snapshot: Record<string, unknown>;
  token_usage: Record<string, unknown>;
  error: string;
  created_at: string;
  updated_at: string;
  specs: GeneratedSpec[];
}

export interface GeneratedSpec {
  id: string;
  spec_id: string;
  namespace: string;
  content: string;
  version: number;
  indexed_at: string | null;
  created_at: string;
}

export interface ValidationResult {
  check: string;
  is_valid: boolean;
  message: string;
}

export interface RelatedSpec {
  spec_id: string;
  score: number;
  match_type: string;
}

export interface SpecDetail {
  spec_id: string;
  generated_spec: string;
  low_confidence_sections: string[];
  duplicate_warning: string | null;
  consistency_warnings: string[];
  validation_results: ValidationResult[];
  request_classification: string;
  extends_spec: string | null;
  related_specs: RelatedSpec[];
  identified_namespaces: string[];
  spec_pr_url: string | null;
  spec_pr_number: number | null;
}

export interface CodeDetail {
  spec_id: string;
  implementation_summary: string;
  generated_files: GeneratedFile[];
  generated_tests: GeneratedTest[];
  code_pr_url: string | null;
  code_pr_numbers: { repo: string; pr_number: number; pr_url: string; files: string[] }[];
  code_approval_status: string;
  code_rejection_feedback: string;
  affected_files: { path: string; action: string; reason: string }[];
  target_repositories: Record<string, unknown>[];
}

export interface GeneratedFile {
  path: string;
  action: string;
  content: string;
  language?: string;
}

export interface GeneratedTest {
  path: string;
  content: string;
  test_type: string;
}

export interface Namespace {
  id: string;
  name: string;
  description: string;
  owners: string[];
  stack_config: Record<string, string>;
  next_spec_sequence: number;
  created_at: string;
  updated_at: string;
}

export interface WsMessage {
  workflow_id: string;
  current_agent: string;
  status: string;
  spec_id?: string;
  message?: string;
  sub_step?: string;
  detail?: string;
  model?: string;
  duplicate_warning?: string | null;
  low_confidence_sections?: string[];
}

export interface PipelineStage {
  key: string;
  label: string;
  subSteps: string[];
}

export const PIPELINE_STAGES: PipelineStage[] = [
  {
    key: 'spec_discovery',
    label: 'Spec Discovery',
    subSteps: [
      'LLM Request Parsing',
      'Namespace Resolution',
      'LLM Query Expansion',
      'Qdrant Dual-Vector Search',
      'Related Spec Enrichment',
    ],
  },
  {
    key: 'spec_generator',
    label: 'Spec Generation',
    subSteps: [
      'Template Selection',
      'LLM Spec Generation',
      'Consistency Check (Qdrant)',
    ],
  },
  {
    key: 'spec_validator',
    label: 'Spec Validation',
    subSteps: [
      'XML Well-formedness',
      'Required Sections Check',
      'Header Fields Check',
      'Format Version Match',
      'Cross-reference Validation',
    ],
  },
  {
    key: 'spec_approval_gate',
    label: 'Approval Gate',
    subSteps: [
      'Persist State',
      'Human Review',
    ],
  },
  {
    key: 'spec_publisher',
    label: 'Spec Publisher',
    subSteps: [
      'Save to Database',
      'GitHub Publish (Branch / Commit / PR)',
      'LLM Summary for Indexing',
      'Qdrant Vector Indexing',
    ],
  },
  {
    key: 'namespace_resolver',
    label: 'Namespace Resolver',
    subSteps: [
      'Load Repositories',
      'Scan Repository',
      'Analyze Impact',
      'Build Code Context',
    ],
  },
  {
    key: 'code_developer',
    label: 'Code Developer',
    subSteps: [
      'Revision Feedback',
      'Task Planning',
      'Code Writing',
      'Test Writing',
      'Integration Check',
      'Retry Code Writing',
      'Lint & Format',
      'Test Execution',
      'Test Repair',
    ],
  },
  {
    key: 'code_publisher',
    label: 'Code Publisher',
    subSteps: [
      'Create Branch',
      'Atomic Commit',
      'Open Pull Request',
      'Save to Database',
    ],
  },
  {
    key: 'code_approval_gate',
    label: 'Code Approval',
    subSteps: [
      'Persist State',
      'Human Review',
    ],
  },
  {
    key: 'code_review_handoff',
    label: 'Code Review & Merge',
    subSteps: [
      'Check PR Status',
      'Squash Merge',
      'Finalize',
    ],
  },
];
