"""음성 인식 — Whisper를 사용한 한국어 자막 생성."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.models import SubtitleSegment

logger = logging.getLogger(__name__)


def transcribe(
    audio_path: Path,
    model_name: str = "medium",
    language: str = "ko",
    max_line_length: int = 40,
) -> list[SubtitleSegment]:
    """Whisper로 오디오를 텍스트로 변환.

    Args:
        audio_path: WAV 오디오 파일 경로.
        model_name: Whisper 모델 크기 (tiny/base/small/medium/large-v3).
        language: 언어 코드.
        max_line_length: 자막 한 줄 최대 글자 수.

    Returns:
        SubtitleSegment 리스트.
    """
    try:
        import whisper
    except ImportError:
        logger.warning(
            "openai-whisper가 설치되어 있지 않습니다. "
            "자막 생성을 건너뜁니다.\n"
            "설치: pip install openai-whisper"
        )
        return []

    logger.info("Whisper 모델 로딩 중: %s", model_name)
    model = whisper.load_model(model_name)

    logger.info("음성 인식 중 (언어: %s)...", language)
    result = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        verbose=False,
    )

    segments: list[SubtitleSegment] = []
    idx = 1

    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue

        start = float(seg.get("start", 0))
        end = float(seg.get("end", 0))

        # 너무 긴 자막은 분할
        if len(text) > max_line_length * 2:
            split_segments = _split_long_segment(idx, start, end, text, max_line_length)
            segments.extend(split_segments)
            idx += len(split_segments)
        else:
            segments.append(SubtitleSegment(index=idx, start=start, end=end, text=text))
            idx += 1

    logger.info("인식 완료: %d개 자막 세그먼트", len(segments))
    return segments


def _split_long_segment(
    start_idx: int,
    start: float,
    end: float,
    text: str,
    max_length: int,
) -> list[SubtitleSegment]:
    """긴 자막 세그먼트를 적절한 길이로 분할."""
    # 한국어는 공백(어절) 기준으로 분할
    words = text.split()
    if len(words) <= 1:
        return [SubtitleSegment(index=start_idx, start=start, end=end, text=text)]

    chunks: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_length:
            chunks.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        chunks.append(current)

    if not chunks:
        return [SubtitleSegment(index=start_idx, start=start, end=end, text=text)]

    total_duration = end - start
    segments: list[SubtitleSegment] = []
    for i, chunk in enumerate(chunks):
        # 글자 수 비율로 시간 배분
        ratio_start = sum(len(c) for c in chunks[:i]) / sum(len(c) for c in chunks)
        ratio_end = sum(len(c) for c in chunks[: i + 1]) / sum(len(c) for c in chunks)

        seg_start = start + total_duration * ratio_start
        seg_end = start + total_duration * ratio_end

        segments.append(SubtitleSegment(
            index=start_idx + i,
            start=seg_start,
            end=seg_end,
            text=chunk,
        ))

    return segments
