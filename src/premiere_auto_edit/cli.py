"""CLI 인터페이스 — Click 기반 명령어."""

from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .config import Config, load_config
from .pipeline import run_pipeline

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="premiere-auto-edit")
@click.pass_context
def main(ctx: click.Context) -> None:
    """🎬 premiere-auto-edit — 프리미어 프로 자동 편집 도구

    무음 삭제 · 음량 밸런스 · 컷 편집 · 자막 생성을 자동으로 처리합니다.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("input_video", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output-dir", type=click.Path(), default=None, help="출력 디렉토리")
@click.option("-c", "--config", "config_path", type=click.Path(), default=None, help="설정 YAML 파일")
@click.option("--preset", type=click.Choice(["youtube", "podcast", "broadcast"]), help="프리셋")
@click.option("--silence-threshold", type=float, default=None, help="무음 임계값 (dB, 기본: 자동)")
@click.option("--silence-duration", type=float, default=None, help="최소 무음 길이 (초, 기본: 0.3)")
@click.option("--silence-padding", type=float, default=None, help="발화 앞뒤 여유 (초, 기본: 0.12)")
@click.option("--no-auto-calibrate", is_flag=True, default=False, help="자동 음량 분석 끄기 (수동 임계값 사용)")
@click.option("--aggressive", is_flag=True, default=False, help="공격적 모드: 작은 소리도 최대한 삭제")
@click.option("--target-lufs", type=float, default=None, help="목표 음량 (LUFS, 기본: -16)")
@click.option("--whisper-model", type=str, default=None, help="Whisper 모델 (기본: medium)")
@click.option("--language", type=str, default=None, help="언어 코드 (기본: ko)")
@click.option("--no-subtitle", is_flag=True, default=False, help="자막 생성 건너뛰기")
@click.option("-v", "--verbose", is_flag=True, default=False, help="상세 로그 출력")
def auto(
    input_video: str,
    output_dir: str | None,
    config_path: str | None,
    preset: str | None,
    silence_threshold: float | None,
    silence_duration: float | None,
    silence_padding: float | None,
    no_auto_calibrate: bool,
    aggressive: bool,
    target_lufs: float | None,
    whisper_model: str | None,
    language: str | None,
    no_subtitle: bool,
    verbose: bool,
) -> None:
    """전체 자동 편집 파이프라인 실행.

    INPUT_VIDEO: 편집할 영상 파일 경로.

    예시:
        premiere-auto-edit auto my_video.mp4
        premiere-auto-edit auto my_video.mp4 --aggressive --no-subtitle
        premiere-auto-edit auto my_video.mp4 --silence-threshold -25 -o ./output
    """
    _setup_logging(verbose)

    console.print()
    console.print("[bold blue]🎬 premiere-auto-edit[/bold blue]")
    console.print()

    # 설정 구성
    overrides: dict = {}
    if silence_threshold is not None:
        overrides.setdefault("silence", {})["threshold_db"] = silence_threshold
        overrides.setdefault("silence", {})["auto_calibrate"] = False  # 수동 지정 시 자동 끔
    if silence_duration is not None:
        overrides.setdefault("silence", {})["min_duration"] = silence_duration
    if silence_padding is not None:
        overrides.setdefault("silence", {})["padding"] = silence_padding
    if no_auto_calibrate:
        overrides.setdefault("silence", {})["auto_calibrate"] = False
    if aggressive:
        overrides.setdefault("silence", {})["aggressive"] = True
        overrides.setdefault("silence", {})["min_duration"] = 0.2
        overrides.setdefault("silence", {})["padding"] = 0.06
        overrides.setdefault("silence", {})["auto_calibrate"] = True
        overrides.setdefault("editing", {})["min_clip_length"] = 0.15
        overrides.setdefault("editing", {})["merge_gap"] = 0.1
    if target_lufs is not None:
        overrides.setdefault("loudness", {})["target_lufs"] = target_lufs
    if whisper_model is not None:
        overrides.setdefault("subtitle", {})["whisper_model"] = whisper_model
    if language is not None:
        overrides.setdefault("subtitle", {})["language"] = language

    cfg = load_config(
        config_path=Path(config_path) if config_path else None,
        preset=preset,
        overrides=overrides if overrides else None,
    )

    if output_dir:
        cfg.output_dir = Path(output_dir)

    run_pipeline(
        input_path=Path(input_video),
        config=cfg,
        output_dir=cfg.output_dir,
        skip_subtitle=no_subtitle,
    )


@main.command()
@click.argument("input_video", type=click.Path(exists=True, dir_okay=False))
@click.option("--threshold", type=float, default=-40.0, help="무음 임계값 (dB)")
@click.option("--duration", type=float, default=0.5, help="최소 무음 길이 (초)")
@click.option("-v", "--verbose", is_flag=True, default=False)
def silence(input_video: str, threshold: float, duration: float, verbose: bool) -> None:
    """무음 구간만 감지하여 출력."""
    _setup_logging(verbose)
    from .core.probe import probe as probe_fn
    from .core.silence import detect_silence

    meta = probe_fn(Path(input_video))
    segments, used_threshold = detect_silence(
        Path(input_video),
        threshold_db=threshold,
        min_duration=duration,
        duration_seconds=meta.duration_seconds,
    )

    console.print(f"\n[bold]무음 구간 {len(segments)}개 발견[/bold] (임계값: {used_threshold}dB)\n")
    total_silence = 0.0
    for i, seg in enumerate(segments, 1):
        console.print(
            f"  {i:3d}. {seg.start:8.2f}s → {seg.end:8.2f}s  "
            f"({seg.duration:.2f}s)"
        )
        total_silence += seg.duration

    pct = (total_silence / meta.duration_seconds * 100) if meta.duration_seconds > 0 else 0
    console.print(f"\n  합계: {total_silence:.1f}s / {meta.duration_seconds:.1f}s ({pct:.1f}%)\n")


@main.command()
@click.argument("input_video", type=click.Path(exists=True, dir_okay=False))
@click.option("--target", type=float, default=-16.0, help="목표 LUFS")
@click.option("-v", "--verbose", is_flag=True, default=False)
def loudness(input_video: str, target: float, verbose: bool) -> None:
    """음량(LUFS)만 분석하여 출력."""
    _setup_logging(verbose)
    from .core.loudness import measure_loudness

    info = measure_loudness(Path(input_video), target_lufs=target)

    console.print("\n[bold]음량 분석 결과[/bold]\n")
    console.print(f"  현재 음량:     {info.input_i:.1f} LUFS")
    console.print(f"  True Peak:     {info.input_tp:.1f} dBTP")
    console.print(f"  Loudness Range: {info.input_lra:.1f} LU")
    console.print(f"  목표 음량:     {info.target_i:.1f} LUFS")
    console.print(f"  필요 게인:     {info.gain_db:+.1f} dB\n")


@main.command()
@click.argument("input_video", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", type=click.Path(), default=None, help="출력 SRT 파일 경로")
@click.option("--model", type=str, default="medium", help="Whisper 모델 (기본: medium)")
@click.option("--language", type=str, default="ko", help="언어 (기본: ko)")
@click.option("-v", "--verbose", is_flag=True, default=False)
def subtitle(
    input_video: str,
    output: str | None,
    model: str,
    language: str,
    verbose: bool,
) -> None:
    """자막만 생성하여 SRT로 저장."""
    _setup_logging(verbose)

    import tempfile

    from .core.audio import extract_audio
    from .subtitle.srt_writer import write_srt
    from .subtitle.transcribe import transcribe as transcribe_fn

    input_path = Path(input_video)

    console.print(f"\n[bold]자막 생성 중...[/bold] (모델: {model}, 언어: {language})\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "audio.wav"
        extract_audio(input_path, wav_path)
        segments = transcribe_fn(wav_path, model_name=model, language=language)

    if not segments:
        console.print("[red]자막을 생성할 수 없습니다.[/red]")
        return

    out_path = Path(output) if output else input_path.with_suffix(".srt")
    write_srt(segments, out_path)

    console.print(f"[green]✓ {len(segments)}개 자막 저장: {out_path}[/green]\n")


if __name__ == "__main__":
    main()
