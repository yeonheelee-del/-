"""무음 감지 — FFmpeg silencedetect + RMS 에너지 분석 2-패스 방식."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import SilentSegment

_RE_SILENCE_START = re.compile(r"silence_start:\s*([\d.e+-]+)")
_RE_SILENCE_END = re.compile(r"silence_end:\s*([\d.e+-]+)")


def analyze_audio_levels(input_path: Path) -> dict:
    """1초 단위 RMS 레벨을 측정하여 노이즈 플로어/발화 레벨/백분위를 반환."""
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

    rms_values: list[float] = []
    rms_re = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+)")

    output = result.stdout + result.stderr
    for line in output.splitlines():
        m = rms_re.search(line)
        if m:
            val = float(m.group(1))
            if val > -100:
                rms_values.append(val)

    if not rms_values:
        return {
            "mean_rms": -30.0,
            "noise_floor": -50.0,
            "speech_level": -20.0,
            "p10": -50.0,
            "p25": -40.0,
            "p50": -30.0,
            "p75": -25.0,
            "rms_per_second": [],
        }

    rms_values.sort()
    total = len(rms_values)

    def percentile(p: float) -> float:
        idx = min(int(total * p / 100), total - 1)
        return rms_values[idx]

    noise_floor_idx = max(1, int(total * 0.15))
    noise_floor = sum(rms_values[:noise_floor_idx]) / noise_floor_idx

    speech_start_idx = max(0, int(total * 0.75))
    speech_values = rms_values[speech_start_idx:]
    speech_level = sum(speech_values) / len(speech_values) if speech_values else -20.0

    mean_rms = sum(rms_values) / total

    return {
        "mean_rms": round(mean_rms, 1),
        "noise_floor": round(noise_floor, 1),
        "speech_level": round(speech_level, 1),
        "p10": round(percentile(10), 1),
        "p25": round(percentile(25), 1),
        "p50": round(percentile(50), 1),
        "p75": round(percentile(75), 1),
        "rms_per_second": rms_values,
    }


def auto_threshold(input_path: Path, aggressive: bool = False) -> float:
    """오디오 분석으로 최적의 무음 임계값을 계산.

    aggressive=True이면 발화 레벨에 더 가깝게 설정하여
    작은 목소리/웅얼거림/숨소리까지 무음으로 판정.
    """
    levels = analyze_audio_levels(input_path)

    noise_floor = levels["noise_floor"]
    speech_level = levels["speech_level"]
    gap = speech_level - noise_floor

    if aggressive:
        threshold = noise_floor + gap * 0.7
    else:
        threshold = noise_floor + gap * 0.55

    threshold = max(-50.0, min(-20.0, threshold))
    return round(threshold, 1)


def detect_low_energy_segments(
    input_path: Path,
    speech_threshold_db: float,
    min_duration: float = 0.3,
) -> list[SilentSegment]:
    """RMS 에너지가 발화 레벨보다 낮은 구간을 감지.

    silencedetect가 놓치는 웅얼거림, 숨소리, 작은 잡음 구간을 잡아냅니다.
    0.5초 단위로 분석하여 더 세밀하게 감지합니다.
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", "astats=metadata=1:reset=0.5,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )

    rms_re = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+)")
    rms_values: list[float] = []

    output = result.stdout + result.stderr
    for line in output.splitlines():
        m = rms_re.search(line)
        if m:
            val = float(m.group(1))
            rms_values.append(val if val > -100 else -100.0)

    if not rms_values:
        return []

    window = 0.5
    segments: list[SilentSegment] = []
    seg_start: float | None = None

    for i, rms in enumerate(rms_values):
        t = i * window
        if rms < speech_threshold_db:
            if seg_start is None:
                seg_start = t
        else:
            if seg_start is not None:
                seg_end = t
                if (seg_end - seg_start) >= min_duration:
                    segments.append(SilentSegment(start=seg_start, end=seg_end))
                seg_start = None

    if seg_start is not None:
        seg_end = len(rms_values) * window
        if (seg_end - seg_start) >= min_duration:
            segments.append(SilentSegment(start=seg_start, end=seg_end))

    return segments


def merge_segments(
    segments: list[SilentSegment],
    merge_gap: float = 0.3,
) -> list[SilentSegment]:
    """겹치거나 가까운 무음 구간을 병합."""
    if not segments:
        return []

    sorted_segs = sorted(segments, key=lambda s: s.start)
    merged = [SilentSegment(start=sorted_segs[0].start, end=sorted_segs[0].end)]

    for seg in sorted_segs[1:]:
        if seg.start <= merged[-1].end + merge_gap:
            merged[-1] = SilentSegment(
                start=merged[-1].start,
                end=max(merged[-1].end, seg.end),
            )
        else:
            merged.append(SilentSegment(start=seg.start, end=seg.end))

    return merged


def detect_silence(
    input_path: Path,
    threshold_db: float = -30.0,
    min_duration: float = 0.3,
    duration_seconds: float | None = None,
    auto_calibrate: bool = True,
    aggressive: bool = False,
) -> tuple[list[SilentSegment], float]:
    """2-패스 무음 감지.

    패스 1: FFmpeg silencedetect (기본 무음 감지)
    패스 2: RMS 에너지 분석 (저음량 구간 추가 감지) — aggressive 모드에서 활성화

    Args:
        input_path: 영상/오디오 파일 경로.
        threshold_db: 무음 임계값 (dB).
        min_duration: 무음 최소 길이 (초).
        duration_seconds: 영상 전체 길이.
        auto_calibrate: 자동 임계값 설정.
        aggressive: 공격적 모드 (2-패스 + 높은 임계값).

    Returns:
        (SilentSegment 리스트, 실제 사용된 임계값) 튜플.
    """
    if auto_calibrate:
        threshold_db = auto_threshold(input_path, aggressive=aggressive)

    # 패스 1: silencedetect
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
    segments = parse_silencedetect_output(result.stderr, duration_seconds)

    # 패스 2: 저음량 구간 추가 감지 (aggressive 모드)
    if aggressive:
        levels = analyze_audio_levels(input_path)
        speech_level = levels["speech_level"]
        noise_floor = levels["noise_floor"]
        low_energy_threshold = noise_floor + (speech_level - noise_floor) * 0.45

        low_energy = detect_low_energy_segments(
            input_path,
            speech_threshold_db=low_energy_threshold,
            min_duration=min_duration,
        )

        if low_energy:
            segments = merge_segments(segments + low_energy)

    return segments, threshold_db


def parse_silencedetect_output(
    stderr: str,
    duration_seconds: float | None = None,
) -> list[SilentSegment]:
    """FFmpeg silencedetect stderr 출력을 파싱."""
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
