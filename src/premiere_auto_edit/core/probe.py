"""FFprobe 래퍼 — 영상 메타데이터 추출."""

from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from .models import ProjectMeta


class FFmpegNotFoundError(RuntimeError):
    """FFmpeg/FFprobe가 설치되어 있지 않을 때."""


class InvalidMediaError(ValueError):
    """영상 또는 오디오 스트림이 없을 때."""


def _check_ffmpeg() -> None:
    if shutil.which("ffprobe") is None:
        raise FFmpegNotFoundError(
            "ffprobe를 찾을 수 없습니다. FFmpeg를 설치해 주세요.\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )


def _parse_fps(stream: dict) -> float:
    """r_frame_rate 또는 avg_frame_rate에서 FPS 추출."""
    for key in ("r_frame_rate", "avg_frame_rate"):
        raw = stream.get(key, "0/0")
        if "/" in raw:
            frac = Fraction(raw)
            if frac > 0:
                return float(frac)
        else:
            val = float(raw)
            if val > 0:
                return val
    return 30.0  # fallback


def probe(filepath: Path) -> ProjectMeta:
    """영상 파일을 분석하여 ProjectMeta를 반환."""
    _check_ffmpeg()

    filepath = Path(filepath).resolve()
    if not filepath.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(filepath),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        raise InvalidMediaError(f"ffprobe 실행 실패: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise InvalidMediaError("비디오 스트림이 없습니다.")
    if audio_stream is None:
        raise InvalidMediaError("오디오 스트림이 없습니다.")

    duration = float(fmt.get("duration", 0))
    if duration <= 0:
        duration = float(video_stream.get("duration", 0))

    return ProjectMeta(
        filepath=filepath,
        duration_seconds=duration,
        fps=_parse_fps(video_stream),
        width=int(video_stream.get("width", 1920)),
        height=int(video_stream.get("height", 1080)),
        audio_sample_rate=int(audio_stream.get("sample_rate", 48000)),
        audio_channels=int(audio_stream.get("channels", 2)),
        codec_video=video_stream.get("codec_name", "h264"),
        codec_audio=audio_stream.get("codec_name", "aac"),
    )
