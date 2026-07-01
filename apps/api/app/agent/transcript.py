from __future__ import annotations

from dataclasses import dataclass
import re


TRANSCRIPT_LINE_RE = re.compile(
    r"^\[(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\]\s*(?P<speaker>[^:：]+)[:：]\s*(?P<content>.+)$"
)


@dataclass(frozen=True)
class TranscriptTurn:
    timestamp: str
    timestamp_seconds: int
    speaker_label: str
    content: str
    raw_line: str


def parse_timestamp(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"Unsupported timestamp: {value}")


def parse_transcript(text: str) -> list[TranscriptTurn]:
    turns: list[TranscriptTurn] = []
    invalid_lines: list[int] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        match = TRANSCRIPT_LINE_RE.match(line)
        if not match:
            invalid_lines.append(line_no)
            continue

        timestamp = match.group("ts")
        turns.append(
            TranscriptTurn(
                timestamp=timestamp,
                timestamp_seconds=parse_timestamp(timestamp),
                speaker_label=match.group("speaker").strip(),
                content=match.group("content").strip(),
                raw_line=line,
            )
        )

    if invalid_lines:
        joined = ", ".join(str(line_no) for line_no in invalid_lines[:8])
        raise ValueError(f"Transcript contains invalid lines: {joined}")
    if not turns:
        raise ValueError("Transcript does not contain any parseable turns")

    return turns

