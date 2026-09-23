"""오디오 추출 — 영상에서 WAV를 추출 (Whisper 입력용)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def extract_audio(input_path: Path, output_path: Path, sample_rate: int = 16000) -> Path:
    """영상에서 16kHz 모노 WAV를 추출.

    Args:
        input_path: 원본 영상 파일 경로.
        output_path: 출력 WAV 파일 경로.
        sample_rate: 샘플레이트 (Whisper 기본: 16000).

    Returns:
        생성된 WAV 파일 경로.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output_path),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"오디오 추출 실패: {result.stderr.strip()}")

    return output_path
