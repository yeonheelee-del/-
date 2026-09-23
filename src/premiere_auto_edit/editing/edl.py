"""EDL (Edit Decision List) — 편집 결정 요약 및 검증."""

from __future__ import annotations

from pathlib import Path

from ..core.models import (
    CutPoint,
    EditDecision,
    LoudnessInfo,
    ProjectMeta,
    SilentSegment,
    SubtitleSegment,
)
from .cut_generator import generate_cut_points


def create_edit_decision(
    project_meta: ProjectMeta,
    silent_segments: list[SilentSegment],
    loudness: LoudnessInfo | None = None,
    subtitles: list[SubtitleSegment] | None = None,
    padding: float = 0.15,
    min_clip_length: float = 0.3,
    merge_gap: float = 0.2,
) -> EditDecision:
    """전체 편집 결정을 생성.

    Args:
        project_meta: 영상 메타데이터.
        silent_segments: 감지된 무음 구간.
        loudness: LUFS 측정 결과.
        subtitles: 원본 타임라인 자막.
        padding: 발화 앞뒤 여유.
        min_clip_length: 최소 클립 길이.
        merge_gap: 클립 병합 기준 간격.

    Returns:
        EditDecision 객체.
    """
    cut_points = generate_cut_points(
        silent_segments=silent_segments,
        total_duration=project_meta.duration_seconds,
        padding=padding,
        min_clip_length=min_clip_length,
        merge_gap=merge_gap,
    )

    _validate_cut_points(cut_points, project_meta.duration_seconds)

    # 자막을 편집 타임라인에 맞춰 재배치
    subtitles_edited: list[SubtitleSegment] = []
    if subtitles:
        subtitles_edited = retime_subtitles(subtitles, cut_points)

    return EditDecision(
        source_file=project_meta.filepath,
        project_meta=project_meta,
        cut_points=cut_points,
        silent_segments=silent_segments,
        loudness=loudness,
        subtitles=subtitles or [],
        subtitles_edited=subtitles_edited,
    )


def _validate_cut_points(cut_points: list[CutPoint], total_duration: float) -> None:
    """컷 포인트의 일관성 검증."""
    for i, cp in enumerate(cut_points):
        if cp.source_out <= cp.source_in:
            raise ValueError(f"클립 {i}: source_out({cp.source_out}) <= source_in({cp.source_in})")
        if cp.source_in < 0:
            raise ValueError(f"클립 {i}: source_in이 음수입니다 ({cp.source_in})")
        if cp.source_out > total_duration + 0.1:  # 약간의 허용
            raise ValueError(
                f"클립 {i}: source_out({cp.source_out})이 "
                f"전체 길이({total_duration})를 초과합니다"
            )

    # 겹침 검사
    for i in range(len(cut_points) - 1):
        if cut_points[i].source_out > cut_points[i + 1].source_in + 0.001:
            raise ValueError(
                f"클립 {i}와 {i + 1}이 겹칩니다: "
                f"{cut_points[i].source_out} > {cut_points[i + 1].source_in}"
            )


def retime_subtitles(
    subtitles: list[SubtitleSegment],
    cut_points: list[CutPoint],
) -> list[SubtitleSegment]:
    """원본 자막을 편집 타임라인에 맞춰 재배치.

    무음 삭제 후 타임라인에서 각 자막의 새 위치를 계산.
    잘린 구간에 속한 자막은 제거.
    """
    retimed: list[SubtitleSegment] = []
    idx = 1

    for sub in subtitles:
        new_start = _map_time(sub.start, cut_points)
        new_end = _map_time(sub.end, cut_points)

        if new_start is not None and new_end is not None and new_end > new_start:
            retimed.append(SubtitleSegment(
                index=idx,
                start=new_start,
                end=new_end,
                text=sub.text,
            ))
            idx += 1

    return retimed


def _map_time(t: float, cut_points: list[CutPoint]) -> float | None:
    """원본 시간을 편집 타임라인 시간으로 매핑.

    잘린 영역에 속하면 None 반환.
    """
    for cp in cut_points:
        if cp.source_in <= t <= cp.source_out:
            offset = t - cp.source_in
            return cp.timeline_in + offset

    # 가장 가까운 클립의 경계에 맞춤
    for cp in cut_points:
        if t < cp.source_in:
            return cp.timeline_in
    if cut_points:
        return cut_points[-1].timeline_out

    return None
