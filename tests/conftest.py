"""테스트 공통 픽스처."""

import pytest

from premiere_auto_edit.core.models import ProjectMeta, SilentSegment, SubtitleSegment
from pathlib import Path


@pytest.fixture
def sample_meta() -> ProjectMeta:
    """테스트용 영상 메타데이터."""
    return ProjectMeta(
        filepath=Path("/tmp/test_video.mp4"),
        duration_seconds=60.0,
        fps=30.0,
        width=1920,
        height=1080,
        audio_sample_rate=48000,
        audio_channels=2,
        codec_video="h264",
        codec_audio="aac",
    )


@pytest.fixture
def sample_silent_segments() -> list[SilentSegment]:
    """테스트용 무음 구간."""
    return [
        SilentSegment(start=5.0, end=8.0),
        SilentSegment(start=15.0, end=17.5),
        SilentSegment(start=30.0, end=35.0),
        SilentSegment(start=50.0, end=52.0),
    ]


@pytest.fixture
def sample_subtitles() -> list[SubtitleSegment]:
    """테스트용 자막 데이터."""
    return [
        SubtitleSegment(index=1, start=0.5, end=4.5, text="안녕하세요, 오늘 이야기할 내용은"),
        SubtitleSegment(index=2, start=8.5, end=14.0, text="프리미어 프로 자동 편집에 대한 것입니다"),
        SubtitleSegment(index=3, start=18.0, end=29.0, text="무음 구간을 자동으로 감지하고 삭제합니다"),
        SubtitleSegment(index=4, start=36.0, end=49.0, text="이렇게 하면 편집 시간을 크게 절약할 수 있습니다"),
        SubtitleSegment(index=5, start=53.0, end=59.0, text="감사합니다"),
    ]
