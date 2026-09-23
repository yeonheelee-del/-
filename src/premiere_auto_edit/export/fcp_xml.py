"""FCP XML v4 생성 — Premiere Pro에서 임포트할 수 있는 XML 타임라인."""

from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from ..core.models import EditDecision


def generate_fcp_xml(
    edit_decision: EditDecision,
    output_path: Path,
) -> Path:
    """EditDecision을 FCP XML v4 형식으로 내보내기.

    Premiere Pro에서 File > Import로 열 수 있는 XML 파일을 생성합니다.
    비디오와 오디오 트랙 모두 포함됩니다.

    Args:
        edit_decision: 편집 결정 데이터.
        output_path: 출력 XML 파일 경로.

    Returns:
        생성된 XML 파일 경로.
    """
    meta = edit_decision.project_meta
    cut_points = edit_decision.cut_points

    fps = meta.fps
    fps_int = meta.fps_int
    is_ntsc = meta.is_ntsc
    total_frames = meta.seconds_to_frames(meta.duration_seconds)

    # 편집 후 전체 프레임 수
    edited_frames = sum(
        meta.seconds_to_frames(cp.source_duration) for cp in cut_points
    )

    # 소스 파일 경로 (URL 인코딩)
    file_url = "file://localhost/" + urllib.parse.quote(
        str(meta.filepath).lstrip("/"), safe="/:"
    )

    # ── XML 구조 생성 ───────────────────────────────
    xmeml = ET.Element("xmeml", version="4")
    sequence = ET.SubElement(xmeml, "sequence")

    seq_name = meta.filepath.stem + "_auto_edit"
    ET.SubElement(sequence, "name").text = seq_name
    ET.SubElement(sequence, "duration").text = str(edited_frames)

    # Rate
    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = str(fps_int)
    ET.SubElement(rate, "ntsc").text = "TRUE" if is_ntsc else "FALSE"

    # Timecode
    tc = ET.SubElement(sequence, "timecode")
    tc_rate = ET.SubElement(tc, "rate")
    ET.SubElement(tc_rate, "timebase").text = str(fps_int)
    ET.SubElement(tc_rate, "ntsc").text = "TRUE" if is_ntsc else "FALSE"
    ET.SubElement(tc, "string").text = "00:00:00:00"
    ET.SubElement(tc, "frame").text = "0"
    ET.SubElement(tc, "displayformat").text = "NDF"

    # Media
    media = ET.SubElement(sequence, "media")

    # ── 비디오 트랙 ──────────────────────────────
    video = ET.SubElement(media, "video")

    v_format = ET.SubElement(video, "format")
    v_sc = ET.SubElement(v_format, "samplecharacteristics")
    v_rate = ET.SubElement(v_sc, "rate")
    ET.SubElement(v_rate, "timebase").text = str(fps_int)
    ET.SubElement(v_rate, "ntsc").text = "TRUE" if is_ntsc else "FALSE"
    ET.SubElement(v_sc, "width").text = str(meta.width)
    ET.SubElement(v_sc, "height").text = str(meta.height)
    ET.SubElement(v_sc, "anamorphic").text = "FALSE"
    ET.SubElement(v_sc, "pixelaspectratio").text = "square"
    ET.SubElement(v_sc, "fielddominance").text = "none"

    v_track = ET.SubElement(video, "track")

    # File 엘리먼트 (첫 번째 클립에서 정의, 이후 참조)
    file_id = "file-1"

    for i, cp in enumerate(cut_points):
        clip_in = meta.seconds_to_frames(cp.source_in)
        clip_out = meta.seconds_to_frames(cp.source_out)
        tl_start = meta.seconds_to_frames(cp.timeline_in)
        tl_end = meta.seconds_to_frames(cp.timeline_out)

        clip = ET.SubElement(v_track, "clipitem", id=f"v-clip-{i + 1}")
        ET.SubElement(clip, "name").text = meta.filepath.stem
        ET.SubElement(clip, "duration").text = str(total_frames)

        c_rate = ET.SubElement(clip, "rate")
        ET.SubElement(c_rate, "timebase").text = str(fps_int)
        ET.SubElement(c_rate, "ntsc").text = "TRUE" if is_ntsc else "FALSE"

        ET.SubElement(clip, "start").text = str(tl_start)
        ET.SubElement(clip, "end").text = str(tl_end)
        ET.SubElement(clip, "in").text = str(clip_in)
        ET.SubElement(clip, "out").text = str(clip_out)

        if i == 0:
            # 첫 클립에서 파일 정의
            file_elem = ET.SubElement(clip, "file", id=file_id)
            ET.SubElement(file_elem, "name").text = meta.filepath.name
            ET.SubElement(file_elem, "pathurl").text = file_url
            ET.SubElement(file_elem, "duration").text = str(total_frames)

            f_rate = ET.SubElement(file_elem, "rate")
            ET.SubElement(f_rate, "timebase").text = str(fps_int)
            ET.SubElement(f_rate, "ntsc").text = "TRUE" if is_ntsc else "FALSE"

            f_media = ET.SubElement(file_elem, "media")
            f_video = ET.SubElement(f_media, "video")
            f_vsc = ET.SubElement(f_video, "samplecharacteristics")
            f_vr = ET.SubElement(f_vsc, "rate")
            ET.SubElement(f_vr, "timebase").text = str(fps_int)
            ET.SubElement(f_vr, "ntsc").text = "TRUE" if is_ntsc else "FALSE"
            ET.SubElement(f_vsc, "width").text = str(meta.width)
            ET.SubElement(f_vsc, "height").text = str(meta.height)

            f_audio = ET.SubElement(f_media, "audio")
            f_asc = ET.SubElement(f_audio, "samplecharacteristics")
            ET.SubElement(f_asc, "samplerate").text = str(meta.audio_sample_rate)
            ET.SubElement(f_asc, "depth").text = "16"
        else:
            # 이후 클립은 참조
            ET.SubElement(clip, "file", id=file_id)

    # ── 오디오 트랙 ──────────────────────────────
    audio = ET.SubElement(media, "audio")

    a_format = ET.SubElement(audio, "format")
    a_sc = ET.SubElement(a_format, "samplecharacteristics")
    ET.SubElement(a_sc, "samplerate").text = str(meta.audio_sample_rate)
    ET.SubElement(a_sc, "depth").text = "16"

    # 각 오디오 채널에 대해 트랙 생성
    for ch in range(meta.audio_channels):
        a_track = ET.SubElement(audio, "track")

        for i, cp in enumerate(cut_points):
            clip_in = meta.seconds_to_frames(cp.source_in)
            clip_out = meta.seconds_to_frames(cp.source_out)
            tl_start = meta.seconds_to_frames(cp.timeline_in)
            tl_end = meta.seconds_to_frames(cp.timeline_out)

            a_clip = ET.SubElement(
                a_track, "clipitem", id=f"a{ch + 1}-clip-{i + 1}"
            )
            ET.SubElement(a_clip, "name").text = meta.filepath.stem
            ET.SubElement(a_clip, "duration").text = str(total_frames)

            ac_rate = ET.SubElement(a_clip, "rate")
            ET.SubElement(ac_rate, "timebase").text = str(fps_int)
            ET.SubElement(ac_rate, "ntsc").text = "TRUE" if is_ntsc else "FALSE"

            ET.SubElement(a_clip, "start").text = str(tl_start)
            ET.SubElement(a_clip, "end").text = str(tl_end)
            ET.SubElement(a_clip, "in").text = str(clip_in)
            ET.SubElement(a_clip, "out").text = str(clip_out)

            # 오디오도 같은 파일 참조
            ET.SubElement(a_clip, "file", id=file_id)

            # 소스 채널 매핑
            src_track = ET.SubElement(a_clip, "sourcetrack")
            ET.SubElement(src_track, "mediatype").text = "audio"
            ET.SubElement(src_track, "trackindex").text = str(ch + 1)

    # ── XML 출력 ──────────────────────────────────
    tree = ET.ElementTree(xmeml)
    ET.indent(tree, space="  ")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<!DOCTYPE xmeml>\n")
        tree.write(f, encoding="unicode", xml_declaration=False)

    return output_path
