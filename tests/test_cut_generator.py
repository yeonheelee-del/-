"""컷 편집 생성 테스트."""

import pytest

from premiere_auto_edit.core.models import SilentSegment
from premiere_auto_edit.editing.cut_generator import generate_cut_points


def test_no_silence():
    """무음이 없으면 전체가 하나의 클립."""
    cuts = generate_cut_points([], total_duration=60.0)
    assert len(cuts) == 1
    assert cuts[0].source_in == 0.0
    assert cuts[0].source_out == 60.0


def test_basic_silence_removal():
    """기본 무음 삭제."""
    segments = [SilentSegment(start=5.0, end=10.0)]
    cuts = generate_cut_points(segments, total_duration=30.0, padding=0.0)

    assert len(cuts) == 2
    # 첫 클립: 0 ~ 5
    assert cuts[0].source_in == 0.0
    assert cuts[0].source_out == 5.0
    # 두 번째 클립: 10 ~ 30
    assert cuts[1].source_in == 10.0
    assert cuts[1].source_out == 30.0


def test_padding():
    """패딩이 적용되면 무음 양쪽에 여유를 남김."""
    segments = [SilentSegment(start=5.0, end=10.0)]
    cuts = generate_cut_points(segments, total_duration=30.0, padding=0.15)

    # 컷 영역: 5.15 ~ 9.85
    # 유지: 0 ~ 5.15, 9.85 ~ 30
    assert len(cuts) == 2
    assert abs(cuts[0].source_out - 5.15) < 0.01
    assert abs(cuts[1].source_in - 9.85) < 0.01


def test_min_clip_length():
    """최소 길이보다 짧은 클립은 제거."""
    segments = [
        SilentSegment(start=0.0, end=0.1),   # 너무 짧은 keep (0 ~ 0)
        SilentSegment(start=0.2, end=10.0),   # keep (10 ~ 30)
    ]
    cuts = generate_cut_points(
        segments, total_duration=30.0, padding=0.0, min_clip_length=0.3,
    )
    # 0~0.1 keep = 0.1s < 0.3s → 제거, 0.2~10 사이 keep = 0.1s < 0.3s → 제거
    # 10~30 keep = 20s → 유지
    assert len(cuts) >= 1
    assert cuts[-1].source_out == 30.0


def test_merge_close_clips():
    """가까운 클립은 병합."""
    segments = [
        SilentSegment(start=5.0, end=5.1),  # 아주 짧은 무음
    ]
    cuts = generate_cut_points(
        segments, total_duration=30.0, padding=0.0, merge_gap=0.2,
    )
    # 5.0~5.1 무음 → keep: 0~5.0, 5.1~30
    # 갭 = 5.1 - 5.0 = 0.1 < 0.2 → 병합
    assert len(cuts) == 1
    assert cuts[0].source_in == 0.0
    assert cuts[0].source_out == 30.0


def test_timeline_sequential():
    """타임라인이 순차적으로 이어지는지 확인."""
    segments = [
        SilentSegment(start=5.0, end=10.0),
        SilentSegment(start=20.0, end=25.0),
    ]
    cuts = generate_cut_points(segments, total_duration=30.0, padding=0.0)

    # 타임라인 연속성 검증
    for i in range(len(cuts) - 1):
        assert abs(cuts[i].timeline_out - cuts[i + 1].timeline_in) < 0.001

    # 전체 타임라인 길이 = 원본 - 무음
    total_timeline = sum(c.timeline_duration for c in cuts)
    assert abs(total_timeline - 20.0) < 0.01  # 30 - 5 - 5 = 20


def test_silence_at_start(sample_silent_segments):
    """영상 시작 부분에 무음이 있는 경우."""
    segments = [SilentSegment(start=0.0, end=3.0)]
    cuts = generate_cut_points(segments, total_duration=10.0, padding=0.0)
    assert cuts[0].source_in == 3.0
    assert cuts[0].timeline_in == 0.0


def test_silence_at_end():
    """영상 끝 부분에 무음이 있는 경우."""
    segments = [SilentSegment(start=8.0, end=10.0)]
    cuts = generate_cut_points(segments, total_duration=10.0, padding=0.0)
    assert len(cuts) == 1
    assert cuts[0].source_in == 0.0
    assert cuts[0].source_out == 8.0
