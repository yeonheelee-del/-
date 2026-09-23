"""파이프라인 — 전체 자동 편집 워크플로우를 오케스트레이션."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import Config
from .core.audio import extract_audio
from .core.loudness import measure_loudness
from .core.models import EditDecision, LoudnessInfo, SubtitleSegment
from .core.probe import probe
from .core.silence import detect_silence
from .editing.edl import create_edit_decision
from .export.fcp_xml import generate_fcp_xml
from .export.report import format_console_report, write_report_json
from .subtitle.srt_writer import write_srt
from .subtitle.transcribe import transcribe

logger = logging.getLogger(__name__)
console = Console()


def run_pipeline(
    input_path: Path,
    config: Config,
    output_dir: Path | None = None,
    skip_subtitle: bool = False,
) -> EditDecision:
    """전체 자동 편집 파이프라인 실행.

    Args:
        input_path: 입력 영상 파일 경로.
        config: 설정 객체.
        output_dir: 출력 디렉토리 (None이면 입력 파일과 같은 위치).
        skip_subtitle: 자막 생성 건너뛰기.

    Returns:
        EditDecision 결과 객체.
    """
    input_path = Path(input_path).resolve()
    if output_dir is None:
        output_dir = config.output_dir or input_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        # ── Step 1: 메타데이터 분석 ──
        task = progress.add_task("1/5  영상 분석 중...", total=None)
        meta = probe(input_path)
        progress.update(task, description="1/5  영상 분석 ✓")
        progress.remove_task(task)
        console.print(
            f"  [dim]→ {meta.width}x{meta.height} @ {meta.fps:.2f}fps, "
            f"{meta.duration_seconds:.1f}초[/dim]"
        )

        # ── Step 2: 무음 감지 (자동 캘리브레이션 포함) ──
        if config.silence.aggressive:
            task = progress.add_task("2/5  오디오 분석 + 2-패스 무음 감지 중...", total=None)
        elif config.silence.auto_calibrate:
            task = progress.add_task("2/5  오디오 분석 + 무음 감지 중...", total=None)
        else:
            task = progress.add_task("2/5  무음 감지 중...", total=None)

        silent_segments, actual_threshold = detect_silence(
            input_path,
            threshold_db=config.silence.threshold_db,
            min_duration=config.silence.min_duration,
            duration_seconds=meta.duration_seconds,
            auto_calibrate=config.silence.auto_calibrate,
            aggressive=config.silence.aggressive,
        )
        progress.update(task, description="2/5  무음 감지 ✓")
        progress.remove_task(task)
        if config.silence.auto_calibrate:
            console.print(f"  [dim]→ 자동 임계값: {actual_threshold}dB[/dim]")
        console.print(f"  [dim]→ {len(silent_segments)}개 무음 구간 발견[/dim]")

        # ── Step 3: 음량 분석 ──
        task = progress.add_task("3/5  음량 분석 중...", total=None)
        loudness: LoudnessInfo | None = None
        try:
            loudness = measure_loudness(
                input_path,
                target_lufs=config.loudness.target_lufs,
            )
            progress.update(task, description="3/5  음량 분석 ✓")
            console.print(
                f"  [dim]→ 현재 {loudness.input_i:.1f} LUFS, "
                f"목표 {loudness.target_i:.1f} LUFS "
                f"(게인 {loudness.gain_db:+.1f}dB)[/dim]"
            )
        except Exception as e:
            progress.update(task, description="3/5  음량 분석 ⚠")
            console.print(f"  [yellow]→ 음량 분석 실패: {e}[/yellow]")
        progress.remove_task(task)

        # ── Step 4: 자막 생성 ──
        subtitles: list[SubtitleSegment] = []
        if not skip_subtitle:
            task = progress.add_task("4/5  자막 생성 중 (시간이 걸릴 수 있습니다)...", total=None)
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    wav_path = Path(tmpdir) / "audio.wav"
                    extract_audio(input_path, wav_path)
                    subtitles = transcribe(
                        wav_path,
                        model_name=config.subtitle.whisper_model,
                        language=config.subtitle.language,
                        max_line_length=config.subtitle.max_line_length,
                    )
                progress.update(task, description="4/5  자막 생성 ✓")
                console.print(f"  [dim]→ {len(subtitles)}개 자막 세그먼트[/dim]")
            except Exception as e:
                progress.update(task, description="4/5  자막 생성 ⚠")
                console.print(f"  [yellow]→ 자막 생성 실패: {e}[/yellow]")
            progress.remove_task(task)
        else:
            console.print("  [dim]4/5  자막 생성 건너뜀[/dim]")

        # ── Step 5: 편집 결정 및 내보내기 ──
        task = progress.add_task("5/5  내보내기 중...", total=None)

        edit_decision = create_edit_decision(
            project_meta=meta,
            silent_segments=silent_segments,
            loudness=loudness,
            subtitles=subtitles,
            padding=config.silence.padding,
            min_clip_length=config.editing.min_clip_length,
            merge_gap=config.editing.merge_gap,
        )

        # XML 내보내기
        xml_path = output_dir / f"{stem}_auto_edit.xml"
        generate_fcp_xml(edit_decision, xml_path)

        # SRT 내보내기
        output_files: list[str] = [str(xml_path)]

        if config.export.include_srt and edit_decision.subtitles:
            srt_orig = output_dir / f"{stem}_original.srt"
            write_srt(
                edit_decision.subtitles, srt_orig,
                use_bom=config.export.srt_bom,
                max_line_length=config.subtitle.max_line_length,
            )
            output_files.append(str(srt_orig))

            if edit_decision.subtitles_edited:
                srt_edit = output_dir / f"{stem}_edited.srt"
                write_srt(
                    edit_decision.subtitles_edited, srt_edit,
                    use_bom=config.export.srt_bom,
                    max_line_length=config.subtitle.max_line_length,
                )
                output_files.append(str(srt_edit))

        # JSON 리포트
        report_path = output_dir / f"{stem}_report.json"
        write_report_json(edit_decision, report_path)
        output_files.append(str(report_path))

        progress.update(task, description="5/5  내보내기 ✓")
        progress.remove_task(task)

    # 결과 출력
    console.print(format_console_report(edit_decision))

    console.print("[bold green]출력 파일:[/bold green]")
    for f in output_files:
        console.print(f"  📄 {f}")

    console.print()
    console.print(
        "[bold]Premiere Pro에서 File > Import로 XML 파일을 열면 "
        "편집된 타임라인이 적용됩니다.[/bold]"
    )

    return edit_decision
