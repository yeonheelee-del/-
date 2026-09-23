"""무음 감지 파서 테스트."""

from premiere_auto_edit.core.models import SilentSegment
from premiere_auto_edit.core.silence import merge_segments, parse_silencedetect_output


SAMPLE_FFMPEG_OUTPUT = """
[silencedetect @ 0x55a1b2c3d4e5] silence_start: 5.000
[silencedetect @ 0x55a1b2c3d4e5] silence_end: 8.000 | silence_duration: 3.000
[silencedetect @ 0x55a1b2c3d4e5] silence_start: 15.000
[silencedetect @ 0x55a1b2c3d4e5] silence_end: 17.500 | silence_duration: 2.500
[silencedetect @ 0x55a1b2c3d4e5] silence_start: 30.000
[silencedetect @ 0x55a1b2c3d4e5] silence_end: 35.000 | silence_duration: 5.000
"""


def test_parse_basic():
    """기본 파싱: 시작과 끝이 쌍으로 매칭."""
    segments = parse_silencedetect_output(SAMPLE_FFMPEG_OUTPUT)
    assert len(segments) == 3
    assert segments[0].start == 5.0
    assert segments[0].end == 8.0
    assert abs(segments[0].duration - 3.0) < 0.001


def test_parse_empty():
    """무음이 없는 경우."""
    segments = parse_silencedetect_output("No silence detected")
    assert segments == []


def test_parse_silence_at_end():
    """영상 끝까지 무음 (end 없이 start만 있는 경우)."""
    stderr = """
[silencedetect @ 0x1234] silence_start: 50.000
"""
    segments = parse_silencedetect_output(stderr, duration_seconds=60.0)
    assert len(segments) == 1
    assert segments[0].start == 50.0
    assert segments[0].end == 60.0


def test_parse_silence_at_end_no_duration():
    """영상 끝까지 무음인데 total duration도 모르는 경우."""
    stderr = """
[silencedetect @ 0x1234] silence_start: 50.000
"""
    segments = parse_silencedetect_output(stderr, duration_seconds=None)
    assert segments == []  # 끝을 모르면 건너뜀


def test_parse_mixed_output():
    """다른 FFmpeg 출력과 섞여 있는 경우."""
    stderr = """
frame=   30 fps=0.0 q=-0.0 size=N/A time=00:00:01.00 bitrate=N/A
[silencedetect @ 0x1234] silence_start: 1.500
frame=   90 fps=0.0 q=-0.0 size=N/A time=00:00:03.00 bitrate=N/A
[silencedetect @ 0x1234] silence_end: 3.200 | silence_duration: 1.700
video:0kB audio:192kB subtitle:0kB other streams:0kB
"""
    segments = parse_silencedetect_output(stderr)
    assert len(segments) == 1
    assert segments[0].start == 1.5
    assert segments[0].end == 3.2


def test_merge_segments_overlap():
    """겹치는 무음 구간 병합."""
    segs = [
        SilentSegment(start=1.0, end=3.0),
        SilentSegment(start=2.5, end=5.0),
        SilentSegment(start=8.0, end=10.0),
    ]
    merged = merge_segments(segs, merge_gap=0.0)
    assert len(merged) == 2
    assert merged[0].start == 1.0
    assert merged[0].end == 5.0
    assert merged[1].start == 8.0
    assert merged[1].end == 10.0


def test_merge_segments_gap():
    """가까운 무음 구간 병합 (merge_gap 이내)."""
    segs = [
        SilentSegment(start=1.0, end=3.0),
        SilentSegment(start=3.2, end=5.0),
    ]
    merged = merge_segments(segs, merge_gap=0.3)
    assert len(merged) == 1
    assert merged[0].start == 1.0
    assert merged[0].end == 5.0


def test_merge_segments_empty():
    """빈 리스트 병합."""
    assert merge_segments([]) == []


def test_merge_segments_unsorted():
    """정렬되지 않은 입력도 처리."""
    segs = [
        SilentSegment(start=5.0, end=7.0),
        SilentSegment(start=1.0, end=3.0),
    ]
    merged = merge_segments(segs, merge_gap=0.0)
    assert len(merged) == 2
    assert merged[0].start == 1.0
    assert merged[1].start == 5.0
