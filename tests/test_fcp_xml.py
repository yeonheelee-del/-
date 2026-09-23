"""FCP XML 생성 테스트."""

import xml.etree.ElementTree as ET
from pathlib import Path

from premiere_auto_edit.core.models import (
    CutPoint,
    EditDecision,
    ProjectMeta,
    SilentSegment,
)
from premiere_auto_edit.export.fcp_xml import generate_fcp_xml


def _make_edit_decision() -> EditDecision:
    """테스트용 EditDecision 생성."""
    meta = ProjectMeta(
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
    return EditDecision(
        source_file=meta.filepath,
        project_meta=meta,
        cut_points=[
            CutPoint(source_in=0.0, source_out=5.0, timeline_in=0.0, timeline_out=5.0),
            CutPoint(source_in=10.0, source_out=30.0, timeline_in=5.0, timeline_out=25.0),
            CutPoint(source_in=35.0, source_out=60.0, timeline_in=25.0, timeline_out=50.0),
        ],
        silent_segments=[
            SilentSegment(start=5.0, end=10.0),
            SilentSegment(start=30.0, end=35.0),
        ],
    )


def test_xml_structure(tmp_path):
    """XML 기본 구조 검증."""
    ed = _make_edit_decision()
    out = tmp_path / "test.xml"
    generate_fcp_xml(ed, out)

    tree = ET.parse(out)
    root = tree.getroot()

    assert root.tag == "xmeml"
    assert root.get("version") == "4"

    seq = root.find("sequence")
    assert seq is not None
    assert seq.find("name").text == "test_video_auto_edit"


def test_clip_count(tmp_path):
    """클립 수가 CutPoint 수와 일치."""
    ed = _make_edit_decision()
    out = tmp_path / "test.xml"
    generate_fcp_xml(ed, out)

    tree = ET.parse(out)
    root = tree.getroot()

    video_track = root.find(".//media/video/track")
    clips = video_track.findall("clipitem")
    assert len(clips) == 3


def test_frame_values(tmp_path):
    """프레임 값이 올바른지 검증."""
    ed = _make_edit_decision()
    out = tmp_path / "test.xml"
    generate_fcp_xml(ed, out)

    tree = ET.parse(out)
    root = tree.getroot()

    video_track = root.find(".//media/video/track")
    first_clip = video_track.findall("clipitem")[0]

    # 30fps, 0~5초 → 0~150 프레임
    assert first_clip.find("start").text == "0"
    assert first_clip.find("end").text == "150"
    assert first_clip.find("in").text == "0"
    assert first_clip.find("out").text == "150"


def test_audio_tracks(tmp_path):
    """오디오 트랙이 채널 수만큼 생성."""
    ed = _make_edit_decision()
    out = tmp_path / "test.xml"
    generate_fcp_xml(ed, out)

    tree = ET.parse(out)
    root = tree.getroot()

    audio = root.find(".//media/audio")
    tracks = audio.findall("track")
    assert len(tracks) == 2  # 스테레오 = 2채널


def test_ntsc_detection(tmp_path):
    """NTSC 감지 (29.97fps)."""
    meta = ProjectMeta(
        filepath=Path("/tmp/ntsc_video.mp4"),
        duration_seconds=10.0,
        fps=29.97,
        width=1920,
        height=1080,
        audio_sample_rate=48000,
        audio_channels=2,
        codec_video="h264",
        codec_audio="aac",
    )
    ed = EditDecision(
        source_file=meta.filepath,
        project_meta=meta,
        cut_points=[
            CutPoint(source_in=0.0, source_out=10.0, timeline_in=0.0, timeline_out=10.0),
        ],
        silent_segments=[],
    )
    out = tmp_path / "ntsc.xml"
    generate_fcp_xml(ed, out)

    tree = ET.parse(out)
    root = tree.getroot()

    rate = root.find(".//sequence/rate")
    assert rate.find("timebase").text == "30"
    assert rate.find("ntsc").text == "TRUE"


def test_file_reference(tmp_path):
    """첫 클립에서 파일 정의, 이후 클립은 참조."""
    ed = _make_edit_decision()
    out = tmp_path / "test.xml"
    generate_fcp_xml(ed, out)

    tree = ET.parse(out)
    root = tree.getroot()

    video_track = root.find(".//media/video/track")
    clips = video_track.findall("clipitem")

    # 첫 클립: file 엘리먼트에 pathurl이 있음
    first_file = clips[0].find("file")
    assert first_file.find("pathurl") is not None

    # 두 번째 클립: file 참조만 (pathurl 없음)
    second_file = clips[1].find("file")
    assert second_file.find("pathurl") is None
    assert second_file.get("id") == "file-1"
