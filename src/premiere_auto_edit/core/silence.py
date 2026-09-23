"""무음 감지 — FFmpeg silencedetect + 자동 음량 캘리브레이션."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .models import SilentSegment

# FFmpeg silencedetect 출력 패턴
_RE_SILENCE_START = re.compile(r"silence_start:\s*([\d.e+-]+)")
_RE_SILENCE_END = re.compile(r"silence_end:\s*([\d.e+-]+)")


def analyze_audio_levels(input_path: Path) -> dict:
    """오디오 레벨을 분석하여 평균 음량과 노이즈 플로어를 측정.

    FFmpeg astats 필터로 전체 오디오의 RMS 레벨을 구간별로 분석합니다.
    """
    # 1초 단위로 RMS 레벨 측정
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )

    # RMS 값들 파싱
    rms_values: list[float] = []
    rms_re = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+)")

    output = result.stdout + result.stderr
    for line in output.splitlines():
        m = rms_re.search(line)
        if m:
            val = float(m.group(1))
            if val > -100:  # -inf 제외
                rms_values.append(val)

    if not rms_values:
        return {"mean_rms": -30.0, "noise_floor": -50.0, "speech_level": -20.0}

    # 정렬하여 분석
    rms_values.sort()
    total = len(rms_values)

    # 하위 20% = 노이즈 플로어 (조용한 구간)
    noise_floor_idx = max(1, int(total * 0.2))
    noise_floor = sum(rms_values[:noise_floor_idx]) / noise_floor_idx

    # 상위 30% = 발화 레벨 (말하는 구간)
    speech_start_idx = max(0, int(total * 0.7))
    speech_values = rms_values[speech_start_idx:]
    speech_level = sum(speech_values) / len(speech_values) if speech_values else -20.0

    # 전체 평균
    mean_rms = sum(rms_values) / total

    return {
        "mean_rms": round(mean_rms, 1),
        "noise_floor": round(noise_floor, 1),
        "speech_level": round(speech_level, 1),
    }


def auto_threshold(input_path: Path) -> float:
    """오디오를 분석하여 최적의 무음 임계값을 자동 계산.

    발화 레벨과 노이즈 플로어의 중간값을 기준으로 설정합니다.
    작은 목소리(웅얼거림, 숨소리)도 잡히도록 발화 레벨에 가깝게 설정.
    """
    levels = analyze_audio_levels(input_path)

    noise_floor = levels["noise_floor"]
    speech_level = levels["speech_level"]

    # 발화 레벨과 노이즈 플로어의 60:40 지점
    # → 발화 쪽에 가까워서 작은 소리도 무음으로 판정
    threshold = noise_floor + (speech_level - noise_floor) * 0.6

    # 안전 범위 클램프: -50dB ~ -20dB
    threshold = max(-50.0, min(-20.0, threshold))

    return round(threshold, 1)


def detect_silence(
    input_path: Path,
    threshold_db: float = -30.0,
    min_duration: float = 0.3,
    duration_seconds: float | None = None,
    auto_calibrate: bool = True,
) -> tuple[list[SilentSegment], float]:
    """FFmpeg silencedetect로 무음 구간을 감지.

    Args:
        input_path: 영상 또는 오디오 파일 경로.
        threshold_db: 무음 임계값 (dB). 기본 -30dB.
        min_duration: 무음 최소 길이 (초). 기본 0.3s.
        duration_seconds: 영상 전체 길이 (마지막 무음 보정용).
        auto_calibrate: True이면 오디오를 분석하여 임계값을 자동 설정.

    Returns:
        (SilentSegment 리스트, 실제 사용된 임계값) 튜플.
    """
    if auto_calibrate:
        threshold_db = auto_threshold(input_path)

    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    stderr = result.stderr

    return parse_silencedetect_output(stderr, duration_seconds), threshold_db


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
            end = duration_seconds
        else:
            continue

        if end > start:
            segments.append(SilentSegment(start=start, end=end))

    return segments
