export type MeetingType =
  | "project_report"
  | "literature_review"
  | "proposal_defense"
  | "midterm_defense"
  | "final_defense";

export type LLMProviderMode = "mock" | "tongyi";

export type TaskStatus =
  | "queued"
  | "segmenting"
  | "extracting"
  | "reducing"
  | "awaiting_confirmation"
  | "confirmed"
  | "failed";

export interface TaskStatusResponse {
  task_id: string;
  task_status: TaskStatus;
  total_chunks: number;
  completed_chunks: number;
  progress_percent: number;
  progress_message?: string;
  token_consumed: number;
  degraded_reason?: string;
  error_message?: string;
}

export interface TaskDraftResponse {
  task_id: string;
  task_status: TaskStatus;
  draft_result: Record<string, unknown> | null;
}

export interface ReportResponse {
  task_id: string;
  role: string;
  meeting_type: MeetingType;
  report: Record<string, unknown>;
}
