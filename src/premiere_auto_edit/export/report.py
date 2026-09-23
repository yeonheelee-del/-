"""리포트 생성 — 편집 결과 요약을 JSON과 콘솔로 출력."""

from __future__ import annotations

import json
from pathlib import Path

from ..core.models import EditDecision


def _format_time(seconds: float) -> str:
    """초를 HH:MM:SS 형식으로 변환."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def generate_report(edit_decision: EditDecision) -> dict:
    """편집 결과를 딕셔너리로 요약."""
    meta = edit_decision.project_meta
    total = meta.duration_seconds
    edited = edit_decision.edited_duration
    removed = edit_decision.total_removed_seconds
    pct = (removed / total * 100) if total > 0 else 0

    report = {
        "input": {
            "file": str(meta.filepath.name),
            "duration": _format_time(total),
            "duration_seconds": round(total, 1),
            "resolution": f"{meta.width}x{meta.height}",
            "fps": meta.fps,
            "codec_video": meta.codec_video,
            "codec_audio": meta.codec_audio,
        },
        "silence": {
            "segments_found": len(edit_decision.silent_segments),
            "total_silence": _format_time(
                sum(s.duration for s in edit_decision.silent_segments)
            ),
            "total_silence_seconds": round(
                sum(s.duration for s in edit_decision.silent_segments), 1
            ),
        },
        "editing": {
            "clip_count": len(edit_decision.cut_points),
            "edited_duration": _format_time(edited),
            "edited_duration_seconds": round(edited, 1),
            "removed_duration": _format_time(removed),
            "removed_duration_seconds": round(removed, 1),
            "removed_percent": round(pct, 1),
        },
    }

    if edit_decision.loudness:
        ld = edit_decision.loudness
        report["loudness"] = {
            "input_lufs": ld.input_i,
            "target_lufs": ld.target_i,
            "gain_db": round(ld.gain_db, 1),
            "true_peak_dbtp": ld.input_tp,
            "loudness_range_lu": ld.input_lra,
        }

    if edit_decision.subtitles:
        report["subtitles"] = {
            "segments_original": len(edit_decision.subtitles),
            "segments_edited": len(edit_decision.subtitles_edited),
            "language": "ko",
        }

    return report


def write_report_json(edit_decision: EditDecision, output_path: Path) -> Path:
    """편집 리포트를 JSON 파일로 저장."""
    report = generate_report(edit_decision)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def format_console_report(edit_decision: EditDecision) -> str:
    """콘솔 출력용 리포트 문자열 생성."""
    report = generate_report(edit_decision)
    inp = report["input"]
    sil = report["silence"]
    edt = report["editing"]

    lines = [
        "",
        "═══ premiere-auto-edit 결과 ═══",
        "",
        f"  입력:     {inp['file']}",
        f"  길이:     {inp['duration']} ({inp['duration_seconds']}초)",
        f"  해상도:   {inp['resolution']} @ {inp['fps']}fps",
        "",
        "  ── 무음 감지 ──",
        f"  감지:     {sil['segments_found']}개 구간",
        f"  무음합계: {sil['total_silence']} ({sil['total_silence_seconds']}초)",
        "",
        "  ── 컷 편집 ──",
        f"  클립:     {edt['clip_count']}개",
        f"  편집후:   {edt['edited_duration']} ({edt['edited_duration_seconds']}초)",
        f"  삭제:     {edt['removed_duration']} ({edt['removed_percent']}%)",
    ]

    if "loudness" in report:
        ld = report["loudness"]
        lines += [
            "",
            "  ── 음량 분석 ──",
            f"  현재:     {ld['input_lufs']} LUFS",
            f"  목표:     {ld['target_lufs']} LUFS",
            f"  게인:     {ld['gain_db']:+.1f} dB",
        ]

    if "subtitles" in report:
        sub = report["subtitles"]
        lines += [
            "",
            "  ── 자막 ──",
            f"  원본:     {sub['segments_original']}개 세그먼트",
            f"  편집후:   {sub['segments_edited']}개 세그먼트",
        ]

    lines += ["", "═" * 32, ""]
    return "\n".join(lines)
