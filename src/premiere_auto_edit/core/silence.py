"""무음 감지 — FFmpeg silencedetect 필터를 사용."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import SilentSegment

# FFmpeg silencedetect 출력 패턴
_RE_SILENCE_START = re.compile(r"silence_start:\s*([\d.e+-]+)")
_RE_SILENCE_END = re.compile(r"silence_end:\s*([\d.e+-]+)")


def detect_silence(
    input_path: Path,
    threshold_db: float = -40.0,
    min_duration: float = 0.5,
    duration_seconds: float | None = None,
) -> list[SilentSegment]:
    """FFmpeg silencedetect로 무음 구간을 감지.

    Args:
        input_path: 영상 또는 오디오 파일 경로.
        threshold_db: 무음 임계값 (dB). 기본 -40dB.
        min_duration: 무음 최소 길이 (초). 기본 0.5s.
        duration_seconds: 영상 전체 길이 (마지막 무음 보정용).

    Returns:
        SilentSegment 리스트 (시간순).
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    stderr = result.stderr

    return parse_silencedetect_output(stderr, duration_seconds)


def parse_silencedetect_output(
    stderr: str,
    duration_seconds: float | None = None,
) -> list[SilentSegment]:
    """FFmpeg silencedetect stderr 출력을 파싱.

    시작만 있고 끝이 없는 경우(영상 끝까지 무음)에도 대응.
    """
    starts: list[float] = []
    ends: list[float] = []

    for line in stderr.splitlines():
        m_start = _RE_SILENCE_START.search(line)
        if m_start:
            starts.append(float(m_start.group(1)))

        m_end = _RE_SILENCE_END.search(line)
        if m_end:
            ends.append(float(m_end.group(1)))

    segments: list[SilentSegment] = []
    for i, start in enumerate(starts):
        if i < len(ends):
            end = ends[i]
        elif duration_seconds is not None:
            # 영상 끝까지 무음인 경우
            end = duration_seconds
        else:
            continue  # 끝을 알 수 없으면 건너뜀

        if end > start:
            segments.append(SilentSegment(start=start, end=end))

    return segments
