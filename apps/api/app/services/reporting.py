from __future__ import annotations

from typing import Any

from app.core.enums import CONFIDENCE_LABELS, ConfidenceTendency, MeetingType
from app.agent.validation import assert_no_binary_defense_judgement


def build_report(*, confirmed_result: dict[str, Any], meeting_type: MeetingType, role: str) -> dict[str, Any]:
    if meeting_type == MeetingType.LITERATURE_REVIEW:
        report = _literature_report(confirmed_result, role)
    elif meeting_type in {MeetingType.PROPOSAL_DEFENSE, MeetingType.MIDTERM_DEFENSE, MeetingType.FINAL_DEFENSE}:
        report = _defense_report(confirmed_result, role)
        assert_no_binary_defense_judgement(str(report))
    else:
        report = _project_report(confirmed_result, role)
    return report


def _project_report(result: dict[str, Any], role: str) -> dict[str, Any]:
    if role == "student":
        first_student = (result.get("per_student_reports") or [{}])[0]
        return {
            "title": f"{first_student.get('display_name', '学生')}的组会任务卡片",
            "sections": [
                {"heading": "本周完成", "items": first_student.get("this_week_completed", [])},
                {"heading": "当前阻塞", "items": first_student.get("current_blockers", [])},
                {"heading": "下周计划", "items": first_student.get("next_week_plan", [])},
                {"heading": "导师反馈", "items": first_student.get("advisor_feedback", [])},
            ],
        }
    return {
        "title": "导师视图 - 项目进展矩阵",
        "summary": result.get("project_level_summary", {}),
        "student_matrix": result.get("per_student_reports", []),
        "participants": result.get("participants", []),
    }


def _literature_report(result: dict[str, Any], role: str) -> dict[str, Any]:
    info = result.get("literature_info", {})
    if role == "student":
        return {
            "title": "学生视图 - 文献阅读记录",
            "literature": info,
            "comprehension_assessment": result.get("comprehension_assessment", {}),
            "qa_log": result.get("advisor_qa_log", []),
        }
    return {
        "title": "导师视图 - 文献方法总结",
        "literature": info,
        "duplication_insight": result.get("duplication_insight"),
        "qa_log": result.get("advisor_qa_log", []),
    }


def _defense_report(result: dict[str, Any], role: str) -> dict[str, Any]:
    dimensions = []
    for dimension in result.get("evaluation_dimensions", []):
        tendency = ConfidenceTendency(dimension.get("confidence_tendency"))
        dimensions.append({**dimension, "display_tendency": CONFIDENCE_LABELS[tendency]})

    if role == "student":
        return {
            "title": "学生视图 - 答辩问答与改进提示",
            "candidate": result.get("candidate", {}),
            "qa_session_log": result.get("qa_session_log", []),
            "comparison_with_history": result.get("comparison_with_history", {}),
        }
    return {
        "title": "导师视图 - 答辩评估报告",
        "candidate": result.get("candidate", {}),
        "evaluation_dimensions": dimensions,
        "comparison_with_history": result.get("comparison_with_history", {}),
        "wording_guardrail": "本报告仅呈现证据与倾向性评估，不输出二元裁定。",
    }

