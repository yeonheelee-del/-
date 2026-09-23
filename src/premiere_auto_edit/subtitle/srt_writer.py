"""SRT 자막 파일 생성."""

from __future__ import annotations

from pathlib import Path

from ..core.models import SubtitleSegment


def _format_timestamp(seconds: float) -> str:
    """초를 SRT 타임스탬프 형식으로 변환 (HH:MM:SS,mmm)."""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(
    segments: list[SubtitleSegment],
    output_path: Path,
    use_bom: bool = True,
    max_line_length: int = 40,
    max_lines: int = 2,
) -> Path:
    """SubtitleSegment 리스트를 SRT 파일로 저장.

    Args:
        segments: 자막 세그먼트 리스트.
        output_path: 출력 SRT 파일 경로.
        use_bom: UTF-8 BOM 추가 여부 (한국어 호환용).
        max_line_length: 한 줄 최대 글자 수.
        max_lines: 최대 줄 수.

    Returns:
        생성된 SRT 파일 경로.
    """
    lines: list[str] = []

    for i, seg in enumerate(segments, 1):
        # 인덱스
        lines.append(str(i))
        # 타임스탬프
        lines.append(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
        # 텍스트 (줄바꿈 처리)
        text = _wrap_text(seg.text, max_line_length, max_lines)
        lines.append(text)
        # 빈 줄 구분
        lines.append("")

    content = "\n".join(lines)

    encoding = "utf-8-sig" if use_bom else "utf-8"
    output_path.write_text(content, encoding=encoding)

    return output_path


def _wrap_text(text: str, max_length: int, max_lines: int) -> str:
    """텍스트를 최대 길이에 맞춰 줄바꿈."""
    if len(text) <= max_length:
        return text

    words = text.split()
    wrapped_lines: list[str] = []
    current = ""

    for word in words:
        if current and len(current) + 1 + len(word) > max_length:
            wrapped_lines.append(current)
            current = word
            if len(wrapped_lines) >= max_lines:
                break
        else:
            current = f"{current} {word}".strip() if current else word

    if current and len(wrapped_lines) < max_lines:
        wrapped_lines.append(current)

    return "\n".join(wrapped_lines)
