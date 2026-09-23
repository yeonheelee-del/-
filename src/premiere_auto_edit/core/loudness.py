"""음량 분석 — LUFS 기반 라우드니스 측정."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .models import LoudnessInfo


def measure_loudness(
    input_path: Path,
    target_lufs: float = -16.0,
) -> LoudnessInfo:
    """FFmpeg loudnorm 필터로 LUFS를 측정 (1-pass 분석).

    Args:
        input_path: 영상 또는 오디오 파일 경로.
        target_lufs: 목표 LUFS 값.

    Returns:
        LoudnessInfo 측정 결과.
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", f"loudnorm=I={target_lufs}:print_format=json",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    loudness_data = _parse_loudnorm_json(result.stderr)

    input_i = float(loudness_data.get("input_i", -70))
    input_tp = float(loudness_data.get("input_tp", -70))
    input_lra = float(loudness_data.get("input_lra", 0))
    input_thresh = float(loudness_data.get("input_thresh", -70))

    gain_db = target_lufs - input_i

    return LoudnessInfo(
        input_i=input_i,
        input_tp=input_tp,
        input_lra=input_lra,
        input_thresh=input_thresh,
        target_i=target_lufs,
        gain_db=gain_db,
    )


def _parse_loudnorm_json(stderr: str) -> dict:
    """FFmpeg loudnorm 출력에서 JSON 블록을 추출."""
    # loudnorm은 stderr 마지막에 JSON을 출력
    # { 로 시작하고 } 로 끝나는 블록을 찾음
    json_match = re.search(
        r"\{[^{}]*\"input_i\"[^{}]*\}",
        stderr,
        re.DOTALL,
    )
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # 대안: 줄 단위로 JSON 블록 찾기
    lines = stderr.strip().splitlines()
    json_lines: list[str] = []
    in_json = False
    for line in lines:
        stripped = line.strip()
        if stripped == "{":
            in_json = True
            json_lines = [stripped]
        elif in_json:
            json_lines.append(stripped)
            if stripped == "}":
                try:
                    return json.loads("\n".join(json_lines))
                except json.JSONDecodeError:
                    json_lines = []
                    in_json = False

    raise RuntimeError("loudnorm JSON 출력을 파싱할 수 없습니다.")
