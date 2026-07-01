from __future__ import annotations

from dataclasses import dataclass

from app.agent.transcript import TranscriptTurn


TOPIC_SHIFT_MARKERS = (
    "下一位",
    "接下来",
    "好,我们继续",
    "好，我们继续",
    "请",
    "继续汇报",
    "下一个",
)


@dataclass(frozen=True)
class TranscriptChunk:
    chunk_id: str
    start_time: str
    end_time: str
    primary_speakers: list[str]
    raw_text: str
    turn_count: int
    same_report_group: str | None = None


def _chunk_from_turns(index: int, turns: list[TranscriptTurn], group: str | None = None) -> TranscriptChunk:
    speakers = sorted({turn.speaker_label for turn in turns})
    return TranscriptChunk(
        chunk_id=f"chunk_{index:03d}",
        start_time=turns[0].timestamp,
        end_time=turns[-1].timestamp,
        primary_speakers=speakers,
        raw_text="\n".join(turn.raw_line for turn in turns),
        turn_count=len(turns),
        same_report_group=group,
    )


def chunk_transcript(
    turns: list[TranscriptTurn],
    *,
    min_chars: int = 800,
    max_chars: int = 3000,
    pause_seconds: int = 30,
) -> list[TranscriptChunk]:
    """Split transcript into semantic chunks while preserving speaker units."""
    chunks: list[TranscriptChunk] = []
    current: list[TranscriptTurn] = []
    current_chars = 0
    chunk_index = 1
    same_report_group: str | None = None

    for turn in turns:
        should_cut = False
        if current:
            previous = current[-1]
            speaker_changed = previous.speaker_label != turn.speaker_label
            gap = turn.timestamp_seconds - previous.timestamp_seconds
            marker_hit = any(marker in turn.content for marker in TOPIC_SHIFT_MARKERS)

            if current_chars >= min_chars and (speaker_changed or gap >= pause_seconds or marker_hit):
                should_cut = True
            if current_chars + len(turn.raw_line) > max_chars:
                should_cut = True
                if not speaker_changed:
                    same_report_group = same_report_group or f"report_group_{chunk_index:03d}"

        if should_cut and current:
            chunks.append(_chunk_from_turns(chunk_index, current, same_report_group))
            chunk_index += 1
            current = []
            current_chars = 0

        current.append(turn)
        current_chars += len(turn.raw_line)

    if current:
        chunks.append(_chunk_from_turns(chunk_index, current, same_report_group))

    return _merge_tiny_chunks(chunks, min_chars=min_chars // 3)


def _merge_tiny_chunks(chunks: list[TranscriptChunk], *, min_chars: int) -> list[TranscriptChunk]:
    if len(chunks) <= 1:
        return chunks

    merged: list[TranscriptChunk] = []
    buffer: TranscriptChunk | None = None

    for chunk in chunks:
        if buffer is None:
            buffer = chunk
            continue

        if len(buffer.raw_text) < min_chars:
            combined_turns_text = f"{buffer.raw_text}\n{chunk.raw_text}"
            speakers = sorted(set(buffer.primary_speakers + chunk.primary_speakers))
            buffer = TranscriptChunk(
                chunk_id=buffer.chunk_id,
                start_time=buffer.start_time,
                end_time=chunk.end_time,
                primary_speakers=speakers,
                raw_text=combined_turns_text,
                turn_count=buffer.turn_count + chunk.turn_count,
                same_report_group=buffer.same_report_group or chunk.same_report_group,
            )
        else:
            merged.append(buffer)
            buffer = chunk

    if buffer is not None:
        merged.append(buffer)

    return [
        TranscriptChunk(
            chunk_id=f"chunk_{idx:03d}",
            start_time=chunk.start_time,
            end_time=chunk.end_time,
            primary_speakers=chunk.primary_speakers,
            raw_text=chunk.raw_text,
            turn_count=chunk.turn_count,
            same_report_group=chunk.same_report_group,
        )
        for idx, chunk in enumerate(merged, start=1)
    ]

