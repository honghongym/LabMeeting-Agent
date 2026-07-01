import type { LLMProviderMode, MeetingType, ReportResponse, TaskDraftResponse, TaskStatusResponse } from "./types";

const API_BASE = "http://localhost:8000/api";

export async function createTask(payload: {
  lab_id: string;
  project_id: string;
  meeting_type: MeetingType;
  llm_provider: LLMProviderMode;
  meeting_date: string;
  raw_transcript: string;
  speaker_mapping: Record<string, string>;
}): Promise<{ task_id: string; task_status: string; llm_provider: LLMProviderMode }> {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return ensureOk(res);
}

export async function getStatus(taskId: string): Promise<TaskStatusResponse> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/status`);
  return ensureOk(res);
}

export async function getDraft(taskId: string): Promise<TaskDraftResponse> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/draft`);
  return ensureOk(res);
}

export async function confirmTask(taskId: string, confirmedResult: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed_result: confirmedResult, edits: [], edited_by: "user_advisor" })
  });
  return ensureOk(res);
}

export async function getReport(taskId: string, role: "advisor" | "student"): Promise<ReportResponse> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/report?role=${role}`);
  return ensureOk(res);
}

async function ensureOk<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}
