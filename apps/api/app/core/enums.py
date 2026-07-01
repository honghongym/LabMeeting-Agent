from enum import Enum


class MeetingType(str, Enum):
    PROJECT_REPORT = "project_report"
    LITERATURE_REVIEW = "literature_review"
    PROPOSAL_DEFENSE = "proposal_defense"
    MIDTERM_DEFENSE = "midterm_defense"
    FINAL_DEFENSE = "final_defense"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    SEGMENTING = "segmenting"
    EXTRACTING = "extracting"
    REDUCING = "reducing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class ConfidenceTendency(str, Enum):
    STRONG_SUPPORT = "strong_support"
    MODERATE_SUPPORT = "moderate_support"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONCERN_RAISED = "concern_raised"


CONFIDENCE_LABELS = {
    ConfidenceTendency.STRONG_SUPPORT: "证据支持充分",
    ConfidenceTendency.MODERATE_SUPPORT: "证据部分支持",
    ConfidenceTendency.INSUFFICIENT_EVIDENCE: "证据尚不充分",
    ConfidenceTendency.CONCERN_RAISED: "存在疑虑需关注",
}

