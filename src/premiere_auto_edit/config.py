"""설정 관리 — YAML 파일 + CLI 인자 + 기본값 병합."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── 기본값 (토킹헤드 / 인터뷰 기준) ──────────────────────────


@dataclass
class SilenceConfig:
    threshold_db: float = -30.0
    min_duration: float = 0.3
    padding: float = 0.10
    auto_calibrate: bool = True
    aggressive: bool = False


@dataclass
class LoudnessConfig:
    target_lufs: float = -16.0
    true_peak: float = -1.5
    lra: float = 11.0


@dataclass
class SubtitleConfig:
    whisper_model: str = "medium"
    language: str = "ko"
    max_line_length: int = 40
    max_lines: int = 2


@dataclass
class EditingConfig:
    min_clip_length: float = 0.3
    merge_gap: float = 0.2


@dataclass
class ExportConfig:
    include_srt: bool = True
    srt_bom: bool = True


PRESETS: dict[str, dict[str, Any]] = {
    "youtube": {"loudness": {"target_lufs": -14.0}},
    "podcast": {"loudness": {"target_lufs": -16.0}},
    "broadcast": {"loudness": {"target_lufs": -24.0}},
}


@dataclass
class Config:
    silence: SilenceConfig = field(default_factory=SilenceConfig)
    loudness: LoudnessConfig = field(default_factory=LoudnessConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    editing: EditingConfig = field(default_factory=EditingConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    output_dir: Path | None = None
    preset: str | None = None


# ── 로더 ──────────────────────────────────────────────────────


def _deep_merge(base: dict, override: dict) -> dict:
    """딕셔너리를 재귀적으로 병합."""
    merged = base.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _apply_dict(cfg: Config, data: dict) -> None:
    """딕셔너리를 Config 객체에 적용."""
    for section_name in ("silence", "loudness", "subtitle", "editing", "export"):
        if section_name in data:
            section = getattr(cfg, section_name)
            for k, v in data[section_name].items():
                if hasattr(section, k):
                    setattr(section, k, v)


def load_config(
    config_path: Path | None = None,
    preset: str | None = None,
    overrides: dict | None = None,
) -> Config:
    """설정 로드: 기본값 → YAML → preset → CLI overrides 순서로 병합."""
    cfg = Config()

    # YAML 파일
    if config_path and config_path.exists():
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f) or {}
        _apply_dict(cfg, yaml_data)

    # 프리셋
    effective_preset = preset or cfg.preset
    if effective_preset and effective_preset in PRESETS:
        _apply_dict(cfg, PRESETS[effective_preset])
        cfg.preset = effective_preset

    # CLI 오버라이드
    if overrides:
        _apply_dict(cfg, overrides)

    return cfg
