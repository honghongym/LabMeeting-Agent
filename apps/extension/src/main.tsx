import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Loader2,
  MessageSquareText,
  Play,
  RotateCw,
  Settings,
  Sparkles,
  UserRound,
  UsersRound
} from "lucide-react";
import { confirmTask, createTask, getDraft, getReport, getStatus } from "./api";
import type { MeetingType, ReportResponse, TaskDraftResponse, TaskStatusResponse } from "./types";
import "./styles.css";

type ViewKey = "input" | "draft" | "report";
type RoleKey = "advisor" | "student";

const sampleTranscript = `[00:00:03] 发言人1: 今天我们先听张同学汇报项目进展。
[00:00:15] 发言人2: 我这周主要完成了数据预处理部分，实现了三种归一化方法的对比。
[00:01:10] 发言人1: 第二种方法效果具体怎么样？下周需要把实验日志整理成表格。
[00:01:35] 发言人2: 第二种方法在验证集上提升了大概3个百分点，但训练速度有点慢。
[00:02:20] 发言人2: 下周计划完成消融实验，并把慢的问题定位到数据加载还是模型结构。
[00:03:05] 发言人3: 我这周读了《Retrieval Augmented Generation for Knowledge Intensive NLP》，准备把里面的检索模块用于会议记忆。
[00:03:44] 发言人1: 这个方向可以继续，但要注意和组内已有文献精读做区分。`;

const meetingTypeLabels: Record<MeetingType, string> = {
  project_report: "项目汇报",
  literature_review: "文献精读",
  proposal_defense: "开题答辩",
  midterm_defense: "中期答辩",
  final_defense: "毕业答辩"
};

const statusLabels: Record<string, string> = {
  queued: "排队中",
  segmenting: "分段中",
  extracting: "抽取中",
  reducing: "聚合中",
  awaiting_confirmation: "待确认",
  confirmed: "已归档",
  failed: "失败"
};

function App() {
  const [view, setView] = useState<ViewKey>("input");
  const [meetingType, setMeetingType] = useState<MeetingType>("project_report");
  const [transcript, setTranscript] = useState(sampleTranscript);
  const [speakerMapping, setSpeakerMapping] = useState("发言人1=李老师\n发言人2=张同学\n发言人3=王同学");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [draft, setDraft] = useState<TaskDraftResponse | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [role, setRole] = useState<RoleKey>("advisor");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const mapping = useMemo(() => parseMapping(speakerMapping), [speakerMapping]);
  const taskReady = status?.task_status === "awaiting_confirmation";
  const confirmed = status?.task_status === "confirmed";
  const draftResult = draft?.draft_result ?? null;

  useEffect(() => {
    if (!taskId || taskReady || confirmed || status?.task_status === "failed") {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await getStatus(taskId);
        setStatus(next);
        if (next.task_status === "awaiting_confirmation") {
          setDraft(await getDraft(taskId));
          setView("draft");
        }
      } catch (err) {
        setError(readError(err));
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [confirmed, taskId, taskReady, status?.task_status]);

  async function submit() {
    setBusy(true);
    setError(null);
    setDraft(null);
    setReport(null);
    setShowRaw(false);
    try {
      const res = await createTask({
        lab_id: "lab_demo",
        project_id: "project_agent",
        meeting_type: meetingType,
        meeting_date: new Date().toISOString().slice(0, 10),
        raw_transcript: transcript,
        speaker_mapping: mapping
      });
      setTaskId(res.task_id);
      setStatus(await getStatus(res.task_id));
      setView("draft");
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(false);
    }
  }

  async function refreshTask() {
    if (!taskId) return;
    setBusy(true);
    try {
      const next = await getStatus(taskId);
      setStatus(next);
      if (next.task_status === "awaiting_confirmation") {
        setDraft(await getDraft(taskId));
      }
      if (next.task_status === "confirmed") {
        setReport(await getReport(taskId, role));
      }
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDraft() {
    if (!taskId || !draftResult) return;
    setBusy(true);
    setError(null);
    try {
      await confirmTask(taskId, draftResult);
      const next = await getStatus(taskId);
      setStatus(next);
      setReport(await getReport(taskId, role));
      setView("report");
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadReport(nextRole: RoleKey) {
    setRole(nextRole);
    if (!taskId || !confirmed) return;
    try {
      setReport(await getReport(taskId, nextRole));
    } catch (err) {
      setError(readError(err));
    }
  }

  return (
    <main className="appShell">
      <header className="appHeader">
        <div className="brand">
          <div className="brandMark">
            <Sparkles size={16} strokeWidth={2} />
          </div>
          <div>
            <h1>组会纪要 Agent</h1>
            <p>{meetingTypeLabels[meetingType]} · 长周期记忆</p>
          </div>
        </div>
        <button className="iconButton" title="设置">
          <Settings size={17} />
        </button>
      </header>

      <section className="statusStrip">
        <div>
          <span className={`statusDot ${status?.task_status ?? "idle"}`} />
          {status ? statusLabels[status.task_status] ?? status.task_status : "待提交"}
        </div>
        <span>{status?.token_consumed ? `${status.token_consumed} tokens` : "Mock 模式"}</span>
      </section>

      <nav className="tabs">
        <button className={view === "input" ? "active" : ""} onClick={() => setView("input")}>
          <FileText size={15} /> 输入
        </button>
        <button className={view === "draft" ? "active" : ""} onClick={() => setView("draft")}>
          <ClipboardCheck size={15} /> 草稿
        </button>
        <button className={view === "report" ? "active" : ""} onClick={() => setView("report")} disabled={!confirmed}>
          <BookOpen size={15} /> 报告
        </button>
      </nav>

      <section className="bodyScroll">
        {view === "input" && (
          <InputView
            busy={busy}
            meetingType={meetingType}
            setMeetingType={setMeetingType}
            speakerMapping={speakerMapping}
            setSpeakerMapping={setSpeakerMapping}
            transcript={transcript}
            setTranscript={setTranscript}
            onSubmit={submit}
          />
        )}

        {view === "draft" && (
          <DraftView
            busy={busy}
            draft={draftResult}
            status={status}
            showRaw={showRaw}
            onConfirm={confirmDraft}
            onRefresh={refreshTask}
            setShowRaw={setShowRaw}
          />
        )}

        {view === "report" && (
          <ReportView
            confirmed={confirmed}
            report={report}
            role={role}
            showRaw={showRaw}
            onRoleChange={loadReport}
            setShowRaw={setShowRaw}
          />
        )}

        {error && (
          <div className="callout errorCallout">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}
      </section>

      <footer className="footer">
        <span>API: localhost:8000</span>
        <button className="textButton" onClick={refreshTask} disabled={!taskId || busy}>
          {busy ? <Loader2 className="spin" size={14} /> : <RotateCw size={14} />}
          刷新
        </button>
      </footer>
    </main>
  );
}

function InputView(props: {
  busy: boolean;
  meetingType: MeetingType;
  setMeetingType: (value: MeetingType) => void;
  speakerMapping: string;
  setSpeakerMapping: (value: string) => void;
  transcript: string;
  setTranscript: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="stack">
      <section className="card compact">
        <div className="sectionTitle">
          <span>会议配置</span>
          <span className="pill">Demo Lab</span>
        </div>
        <label className="fieldLabel">
          类型
          <select value={props.meetingType} onChange={(event) => props.setMeetingType(event.target.value as MeetingType)}>
            {Object.entries(meetingTypeLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="fieldLabel">
          说话人映射
          <textarea
            className="mappingBox"
            value={props.speakerMapping}
            onChange={(event) => props.setSpeakerMapping(event.target.value)}
          />
        </label>
      </section>

      <section className="card compact">
        <div className="sectionTitle">
          <span>转录文本</span>
          <span className="hint">{props.transcript.split("\n").filter(Boolean).length} 行</span>
        </div>
        <textarea
          className="transcriptBox"
          value={props.transcript}
          onChange={(event) => props.setTranscript(event.target.value)}
        />
      </section>

      <button className="primaryButton" onClick={props.onSubmit} disabled={props.busy || props.transcript.trim().length < 20}>
        {props.busy ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
        提交 Agent 任务
      </button>
    </div>
  );
}

function DraftView(props: {
  busy: boolean;
  draft: Record<string, unknown> | null;
  status: TaskStatusResponse | null;
  showRaw: boolean;
  onConfirm: () => void;
  onRefresh: () => void;
  setShowRaw: (value: boolean) => void;
}) {
  if (!props.draft) {
    return (
      <div className="emptyState">
        <Loader2 className={props.status && props.status.task_status !== "failed" ? "spin" : ""} size={24} />
        <h2>{props.status ? statusLabels[props.status.task_status] ?? props.status.task_status : "等待任务"}</h2>
        <p>{props.status?.progress_message ?? "提交转录后，Agent 会在这里生成可确认的结构化草稿。"}</p>
        <ProgressBar value={props.status?.progress_percent ?? 0} />
        <button className="secondaryButton" onClick={props.onRefresh}>
          <RotateCw size={15} /> 刷新状态
        </button>
      </div>
    );
  }

  return (
    <div className="stack">
      <DraftSummary draft={props.draft} />
      <button className="primaryButton" onClick={props.onConfirm} disabled={props.busy}>
        {props.busy ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />}
        确认并写入长期记忆
      </button>
      <RawToggle showRaw={props.showRaw} setShowRaw={props.setShowRaw} value={props.draft} />
    </div>
  );
}

function DraftSummary({ draft }: { draft: Record<string, unknown> }) {
  const meetingType = String(draft.meeting_type ?? "");
  if (meetingType === "literature_review") {
    return <LiteratureDraft draft={draft} />;
  }
  if (meetingType.includes("defense")) {
    return <DefenseDraft draft={draft} />;
  }
  return <ProjectDraft draft={draft} />;
}

function ProjectDraft({ draft }: { draft: Record<string, unknown> }) {
  const reports = arrayOfRecords(draft.per_student_reports);
  const summary = recordOf(draft.project_level_summary);
  return (
    <div className="stack">
      <section className="card">
        <div className="sectionTitle">
          <span>项目摘要</span>
          <span className="pill emerald">待确认</span>
        </div>
        <p className="leadText">{text(summary.overall_progress_note, "已按学生聚合本次组会内容。")}</p>
        <MetricGrid
          metrics={[
            ["学生", reports.length],
            ["计划", countNested(reports, "next_week_plan")],
            ["阻塞", countNested(reports, "current_blockers")]
          ]}
        />
      </section>
      {reports.map((item, index) => (
        <section className="card" key={`${text(item.display_name, "student")}-${index}`}>
          <div className="personHeader">
            <div className="avatar">
              <UserRound size={16} />
            </div>
            <div>
              <h3>{text(item.display_name, "未命名成员")}</h3>
              <p>{arrayOfRecords(item.previous_commitments_review).length} 条历史承诺待核对</p>
            </div>
          </div>
          <MiniList title="本周完成" items={arrayOfRecords(item.this_week_completed).map((v) => text(v.description))} />
          <MiniList title="下周计划" items={arrayOfRecords(item.next_week_plan).map((v) => text(v.description))} accent />
          <MiniList title="当前阻塞" items={arrayOfRecords(item.current_blockers).map((v) => text(v.description))} tone="warning" />
          <MiniList title="导师反馈" items={arrayOfRecords(item.advisor_feedback).map((v) => text(v.feedback_content))} />
        </section>
      ))}
    </div>
  );
}

function LiteratureDraft({ draft }: { draft: Record<string, unknown> }) {
  const info = recordOf(draft.literature_info);
  const assessment = recordOf(draft.comprehension_assessment);
  return (
    <div className="stack">
      <section className="card">
        <div className="sectionTitle">
          <span>文献卡片</span>
          <span className="pill violet">精读</span>
        </div>
        <h3>{text(info.title, "未命名文献")}</h3>
        <p className="leadText">{text(info.core_method_summary, "已提取核心方法摘要。")}</p>
        <MiniList title="创新点" items={arrayOfText(info.innovation_points)} accent />
        <div className="insightBox">{text(draft.duplication_insight, "未发现明显重复精读记录。")}</div>
      </section>
      <section className="card">
        <div className="sectionTitle">
          <span>理解深度</span>
          <span className="pill">{text(assessment.depth_indicator, "moderate")}</span>
        </div>
        <MiniList
          title="问答证据"
          items={arrayOfRecords(assessment.supporting_evidence).map((item) => text(item.qa_exchange_summary))}
        />
      </section>
    </div>
  );
}

function DefenseDraft({ draft }: { draft: Record<string, unknown> }) {
  const candidate = recordOf(draft.candidate);
  const dimensions = arrayOfRecords(draft.evaluation_dimensions);
  return (
    <div className="stack">
      <section className="card">
        <div className="personHeader">
          <div className="avatar">
            <UserRound size={16} />
          </div>
          <div>
            <h3>{text(candidate.display_name, "答辩学生")}</h3>
            <p>{text(candidate.degree_type, "master")} · {text(candidate.enrollment_year, "2024")}</p>
          </div>
        </div>
      </section>
      {dimensions.map((dimension, index) => (
        <section className="card" key={`${text(dimension.dimension_name)}-${index}`}>
          <div className="sectionTitle">
            <span>{text(dimension.dimension_name, "评估维度")}</span>
            <span className="pill">{tendencyLabel(text(dimension.confidence_tendency))}</span>
          </div>
          <p className="leadText">{text(dimension.note, "等待导师确认。")}</p>
          <MiniList
            title="证据"
            items={arrayOfRecords(dimension.evidence_excerpts).map((item) => text(item.content_summary))}
            accent
          />
        </section>
      ))}
    </div>
  );
}

function ReportView(props: {
  confirmed: boolean;
  report: ReportResponse | null;
  role: RoleKey;
  showRaw: boolean;
  onRoleChange: (role: RoleKey) => void;
  setShowRaw: (value: boolean) => void;
}) {
  if (!props.confirmed) {
    return (
      <div className="emptyState">
        <BookOpen size={24} />
        <h2>报告尚未生成</h2>
        <p>确认草稿并写入长期记忆后，可查看导师视图和学生视图。</p>
      </div>
    );
  }

  const value = props.report?.report ?? {};
  return (
    <div className="stack">
      <div className="roleSwitch">
        <button className={props.role === "advisor" ? "active" : ""} onClick={() => props.onRoleChange("advisor")}>
          <UsersRound size={15} /> 导师
        </button>
        <button className={props.role === "student" ? "active" : ""} onClick={() => props.onRoleChange("student")}>
          <UserRound size={15} /> 学生
        </button>
      </div>
      <StructuredReport value={value} />
      <RawToggle showRaw={props.showRaw} setShowRaw={props.setShowRaw} value={value} />
    </div>
  );
}

function StructuredReport({ value }: { value: Record<string, unknown> }) {
  const title = text(value.title, "角色化报告");
  const matrix = arrayOfRecords(value.student_matrix);
  const sections = arrayOfRecords(value.sections);
  const dimensions = arrayOfRecords(value.evaluation_dimensions);
  const qa = arrayOfRecords(value.qa_log ?? value.qa_session_log);
  const literature = recordOf(value.literature);

  return (
    <div className="stack">
      <section className="card">
        <div className="sectionTitle">
          <span>{title}</span>
          <span className="pill emerald">已归档</span>
        </div>
        {text(recordOf(value.summary).overall_progress_note, "") && (
          <p className="leadText">{text(recordOf(value.summary).overall_progress_note)}</p>
        )}
        {text(literature.title, "") && (
          <>
            <h3>{text(literature.title)}</h3>
            <p className="leadText">{text(literature.core_method_summary)}</p>
          </>
        )}
      </section>

      {matrix.map((item, index) => (
        <section className="card" key={`${text(item.display_name, "member")}-${index}`}>
          <div className="personHeader">
            <div className="avatar"><UserRound size={16} /></div>
            <div>
              <h3>{text(item.display_name, "成员")}</h3>
              <p>{arrayOfRecords(item.next_week_plan).length} 个下周计划</p>
            </div>
          </div>
          <MiniList title="下周计划" items={arrayOfRecords(item.next_week_plan).map((v) => text(v.description))} accent />
          <MiniList title="阻塞点" items={arrayOfRecords(item.current_blockers).map((v) => text(v.description))} tone="warning" />
        </section>
      ))}

      {sections.map((section, index) => (
        <section className="card" key={`${text(section.heading)}-${index}`}>
          <div className="sectionTitle">
            <span>{text(section.heading, "任务")}</span>
          </div>
          <MiniList title="" items={arrayOfRecords(section.items).map((item) => text(item.description ?? item.feedback_content))} accent />
        </section>
      ))}

      {dimensions.map((dimension, index) => (
        <section className="card" key={`${text(dimension.dimension_name)}-${index}`}>
          <div className="sectionTitle">
            <span>{text(dimension.dimension_name, "评估维度")}</span>
            <span className="pill">{text(dimension.display_tendency, tendencyLabel(text(dimension.confidence_tendency)))}</span>
          </div>
          <p className="leadText">{text(dimension.note)}</p>
        </section>
      ))}

      {qa.length > 0 && (
        <section className="card">
          <div className="sectionTitle">
            <span>问答记录</span>
            <span className="pill">{qa.length}</span>
          </div>
          {qa.slice(0, 5).map((item, index) => (
            <div className="qaItem" key={index}>
              <MessageSquareText size={15} />
              <div>
                <strong>{text(item.question, "问题")}</strong>
                <p>{text(item.response_summary ?? item.candidate_response_summary, "已记录回答摘要")}</p>
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function MiniList({
  title,
  items,
  accent,
  tone
}: {
  title: string;
  items: string[];
  accent?: boolean;
  tone?: "warning";
}) {
  const filtered = items.filter(Boolean);
  if (!filtered.length) return null;
  return (
    <div className="miniList">
      {title && <h4>{title}</h4>}
      {filtered.slice(0, 4).map((item, index) => (
        <div className={`miniItem ${accent ? "accent" : ""} ${tone ?? ""}`} key={`${item}-${index}`}>
          <Check size={13} />
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

function MetricGrid({ metrics }: { metrics: Array<[string, string | number]> }) {
  return (
    <div className="metricGrid">
      {metrics.map(([label, value]) => (
        <div key={label}>
          <strong>{value}</strong>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="progressTrack">
      <div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

function RawToggle({
  showRaw,
  setShowRaw,
  value
}: {
  showRaw: boolean;
  setShowRaw: (value: boolean) => void;
  value: unknown;
}) {
  return (
    <section className="rawPanel">
      <button className="secondaryButton full" onClick={() => setShowRaw(!showRaw)}>
        {showRaw ? "隐藏原始 JSON" : "查看原始 JSON"}
        <ArrowRight size={14} />
      </button>
      {showRaw && <pre>{JSON.stringify(value, null, 2)}</pre>}
    </section>
  );
}

function parseMapping(input: string): Record<string, string> {
  return Object.fromEntries(
    input
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, value] = line.split("=");
        return [key.trim(), value?.trim() ?? key.trim()];
      })
  );
}

function recordOf(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function arrayOfRecords(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(recordOf) : [];
}

function arrayOfText(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)).filter(Boolean) : [];
}

function countNested(records: Array<Record<string, unknown>>, key: string): number {
  return records.reduce((sum, item) => sum + arrayOfRecords(item[key]).length, 0);
}

function tendencyLabel(value: string): string {
  const labels: Record<string, string> = {
    strong_support: "证据支持充分",
    moderate_support: "证据部分支持",
    insufficient_evidence: "证据尚不充分",
    concern_raised: "存在疑虑需关注"
  };
  return labels[value] ?? value;
}

function text(value: unknown, fallback = ""): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") return value || fallback;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function readError(err: unknown): string {
  return err instanceof Error ? err.message : "未知错误";
}

createRoot(document.getElementById("root")!).render(<App />);
