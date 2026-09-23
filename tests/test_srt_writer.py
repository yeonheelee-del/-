"""SRT 작성기 테스트."""

from pathlib import Path

from premiere_auto_edit.core.models import SubtitleSegment
from premiere_auto_edit.subtitle.srt_writer import write_srt, _format_timestamp, _wrap_text


def test_format_timestamp():
    """타임스탬프 형식 변환."""
    assert _format_timestamp(0) == "00:00:00,000"
    assert _format_timestamp(1.5) == "00:00:01,500"
    assert _format_timestamp(61.234) == "00:01:01,234"
    assert _format_timestamp(3661.999) == "01:01:01,999"


def test_format_timestamp_negative():
    """음수는 0으로 처리."""
    assert _format_timestamp(-1.0) == "00:00:00,000"


def test_wrap_text_short():
    """짧은 텍스트는 그대로."""
    assert _wrap_text("짧은 텍스트", 40, 2) == "짧은 텍스트"


def test_wrap_text_long():
    """긴 텍스트는 줄바꿈."""
    text = "이것은 매우 긴 자막 텍스트로 한 줄에 다 들어가지 않아서 줄바꿈이 필요합니다"
    result = _wrap_text(text, 20, 2)
    lines = result.split("\n")
    assert len(lines) <= 2
    assert all(len(line) <= 25 for line in lines)  # 약간의 여유


def test_write_srt_basic(tmp_path):
    """기본 SRT 파일 생성."""
    segments = [
        SubtitleSegment(index=1, start=0.0, end=2.5, text="안녕하세요"),
        SubtitleSegment(index=2, start=3.0, end=5.5, text="테스트입니다"),
    ]
    out = tmp_path / "test.srt"
    write_srt(segments, out, use_bom=False)

    content = out.read_text(encoding="utf-8")
    assert "1\n" in content
    assert "00:00:00,000 --> 00:00:02,500" in content
    assert "안녕하세요" in content
    assert "테스트입니다" in content


def test_write_srt_bom(tmp_path):
    """BOM이 포함된 SRT 파일."""
    segments = [
        SubtitleSegment(index=1, start=0.0, end=1.0, text="BOM 테스트"),
    ]
    out = tmp_path / "bom.srt"
    write_srt(segments, out, use_bom=True)

    raw = out.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM
