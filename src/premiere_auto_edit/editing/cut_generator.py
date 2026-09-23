"""컷 편집 생성 — 무음 구간을 기반으로 유지할 구간(CutPoint)을 계산."""

from __future__ import annotations

from ..core.models import CutPoint, SilentSegment


def generate_cut_points(
    silent_segments: list[SilentSegment],
    total_duration: float,
    padding: float = 0.15,
    min_clip_length: float = 0.3,
    merge_gap: float = 0.2,
) -> list[CutPoint]:
    """무음 구간에서 유지(keep) 구간 리스트를 생성.

    알고리즘:
    1. 전체 영상을 하나의 keep 구간으로 시작
    2. 각 무음 구간을 패딩 적용 후 제거
    3. 너무 짧은 클립 제거
    4. 가까운 클립 병합
    5. 타임라인 위치 재계산

    Args:
        silent_segments: 감지된 무음 구간 리스트.
        total_duration: 영상 전체 길이 (초).
        padding: 발화 앞뒤 여유 (초).
        min_clip_length: 최소 클립 길이 (초).
        merge_gap: 이보다 가까운 클립은 병합 (초).

    Returns:
        타임라인순 CutPoint 리스트.
    """
    if not silent_segments:
        return [CutPoint(
            source_in=0.0,
            source_out=total_duration,
            timeline_in=0.0,
            timeline_out=total_duration,
        )]

    # 1. 무음 구간을 패딩 적용한 컷 영역으로 변환
    cut_regions: list[tuple[float, float]] = []
    for seg in sorted(silent_segments, key=lambda s: s.start):
        cut_start = seg.start + padding
        cut_end = seg.end - padding
        if cut_end > cut_start:
            cut_regions.append((cut_start, cut_end))

    # 2. 컷 영역을 병합 (겹치는 영역 통합)
    merged_cuts: list[tuple[float, float]] = []
    for start, end in cut_regions:
        if merged_cuts and start <= merged_cuts[-1][1]:
            merged_cuts[-1] = (merged_cuts[-1][0], max(merged_cuts[-1][1], end))
        else:
            merged_cuts.append((start, end))

    # 3. 유지 구간 추출 (전체 - 컷 = keep)
    keep_segments: list[tuple[float, float]] = []
    prev_end = 0.0
    for cut_start, cut_end in merged_cuts:
        if cut_start > prev_end:
            keep_segments.append((prev_end, cut_start))
        prev_end = cut_end
    if prev_end < total_duration:
        keep_segments.append((prev_end, total_duration))

    # 4. 최소 길이 필터
    keep_segments = [(s, e) for s, e in keep_segments if (e - s) >= min_clip_length]

    # 5. 가까운 클립 병합
    if keep_segments:
        merged_keeps: list[tuple[float, float]] = [keep_segments[0]]
        for s, e in keep_segments[1:]:
            prev_s, prev_e = merged_keeps[-1]
            if s - prev_e <= merge_gap:
                merged_keeps[-1] = (prev_s, e)
            else:
                merged_keeps.append((s, e))
        keep_segments = merged_keeps

    # 6. 타임라인 위치 계산
    cut_points: list[CutPoint] = []
    timeline_pos = 0.0
    for source_in, source_out in keep_segments:
        duration = source_out - source_in
        cut_points.append(CutPoint(
            source_in=source_in,
            source_out=source_out,
            timeline_in=timeline_pos,
            timeline_out=timeline_pos + duration,
        ))
        timeline_pos += duration

    return cut_points
