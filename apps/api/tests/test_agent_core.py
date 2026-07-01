from __future__ import annotations

import pytest

from app.agent.budget import TokenBudgetController
from app.agent.chunking import chunk_transcript
from app.agent.transcript import parse_transcript
from app.agent.validation import assert_no_binary_defense_judgement, validate_confidence_tendency
from app.core.enums import ConfidenceTendency


def test_parse_transcript_extracts_turn_fields() -> None:
    turns = parse_transcript("[00:03:15] 发言人2: 我这周完成了数据预处理")

    assert turns[0].timestamp == "00:03:15"
    assert turns[0].timestamp_seconds == 195
    assert turns[0].speaker_label == "发言人2"
    assert "数据预处理" in turns[0].content


def test_parse_transcript_rejects_invalid_lines() -> None:
    with pytest.raises(ValueError, match="invalid lines"):
        parse_transcript("发言人2: 缺少时间戳")


def test_chunking_respects_speaker_and_size_boundaries() -> None:
    text = "\n".join(
        [
            "[00:00:01] 发言人1: 今天先听张同学汇报项目进展。",
            "[00:00:20] 发言人2: 我这周完成了数据预处理，接下来计划做消融实验。",
            "[00:01:05] 发言人1: 下一位同学继续汇报。",
            "[00:01:40] 发言人3: 我遇到的问题是训练速度偏慢，下周准备定位原因。",
        ]
    )
    chunks = chunk_transcript(parse_transcript(text), min_chars=40, max_chars=110)

    assert len(chunks) >= 2
    assert chunks[0].chunk_id == "chunk_001"
    assert chunks[0].start_time == "00:00:01"
    assert chunks[-1].end_time == "00:01:40"


def test_budget_controller_degrades_before_rejecting() -> None:
    controller = TokenBudgetController(per_call_limit=100, per_task_limit=500)
    decision = controller.check_call("短文本", "历史记忆" * 500)

    assert decision.degraded is True
    assert decision.reason in {"historical_memory_compressed", "chunk_requires_secondary_split"}


def test_confidence_tendency_allows_only_guardrail_enum() -> None:
    assert validate_confidence_tendency("moderate_support") == ConfidenceTendency.MODERATE_SUPPORT
    with pytest.raises(ValueError):
        validate_confidence_tendency("pass")


def test_defense_report_rejects_binary_judgement() -> None:
    with pytest.raises(ValueError, match="banned binary"):
        assert_no_binary_defense_judgement("建议通过")

