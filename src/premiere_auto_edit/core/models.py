"""데이터 모델 — 프로젝트 전체에서 사용하는 데이터 클래스."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectMeta:
    """영상 파일의 메타데이터."""

    filepath: Path
    duration_seconds: float
    fps: float
    width: int
    height: int
    audio_sample_rate: int
    audio_channels: int
    codec_video: str
    codec_audio: str

    @property
    def fps_int(self) -> int:
        """NTSC 대응 — 정수 timebase (29.97 → 30, 23.976 → 24)."""
        return round(self.fps)

    @property
    def is_ntsc(self) -> bool:
        """29.97, 23.976, 59.94 등 드롭 프레임 여부."""
        frac = self.fps - int(self.fps)
        return 0.9 < frac < 1.0 or (0.96 < (self.fps / round(self.fps)) < 1.0 and frac > 0.01)

    def seconds_to_frames(self, seconds: float) -> int:
        """초를 프레임 수로 변환."""
        return int(round(seconds * self.fps))


@dataclass
class SilentSegment:
    """감지된 무음 구간."""

    start: float  # 초
    end: float  # 초

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class CutPoint:
    """최종 타임라인에 남길 구간 (keep segment)."""

    source_in: float  # 원본 시작 (초)
    source_out: float  # 원본 끝 (초)
    timeline_in: float = 0.0  # 편집 타임라인 시작
    timeline_out: float = 0.0  # 편집 타임라인 끝

    @property
    def source_duration(self) -> float:
        return self.source_out - self.source_in

    @property
    def timeline_duration(self) -> float:
        return self.timeline_out - self.timeline_in


@dataclass
class LoudnessInfo:
    """LUFS 측정 결과."""

    input_i: float  # Integrated loudness (LUFS)
    input_tp: float  # True peak (dBTP)
    input_lra: float  # Loudness range (LU)
    input_thresh: float  # Threshold (LUFS)
    target_i: float  # 목표 LUFS
    gain_db: float  # 필요한 게인 조정 (dB)


@dataclass
class SubtitleSegment:
    """자막 한 줄."""

    index: int
    start: float  # 초
    end: float  # 초
    text: str


@dataclass
class EditDecision:
    """전체 편집 결정 — 파이프라인의 최종 결과물."""

    source_file: Path
    project_meta: ProjectMeta
    cut_points: list[CutPoint] = field(default_factory=list)
    silent_segments: list[SilentSegment] = field(default_factory=list)
    loudness: LoudnessInfo | None = None
    subtitles: list[SubtitleSegment] = field(default_factory=list)
    subtitles_edited: list[SubtitleSegment] = field(default_factory=list)

    @property
    def total_removed_seconds(self) -> float:
        kept = sum(cp.source_duration for cp in self.cut_points)
        return self.project_meta.duration_seconds - kept

    @property
    def edited_duration(self) -> float:
        if not self.cut_points:
            return self.project_meta.duration_seconds
        return sum(cp.source_duration for cp in self.cut_points)
