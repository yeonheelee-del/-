# 🎬 premiere-auto-edit

프리미어 프로 자동 편집 도구 — 무음 삭제, 음량 밸런스, 컷 편집, 자막 생성을 자동으로 처리합니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🔇 **무음 삭제** | FFmpeg silencedetect로 무음 구간을 감지하고 자동으로 컷 포인트 생성 |
| 🔊 **음량 밸런스** | LUFS 기반 라우드니스 분석 및 게인 조정값 제공 |
| ✂️ **컷 편집** | 무음 기반 자동 EDL 생성 → Premiere Pro XML 타임라인으로 출력 |
| 📝 **자막 생성** | Whisper 한국어 음성 인식 → SRT 자막 파일 생성 |

## 사용 흐름

```
영상 파일 → premiere-auto-edit → Premiere Pro에서 XML Import → 편집 완료!
```

1. CLI로 영상 파일을 분석
2. 무음 구간 감지 + 음량 분석 + 자막 생성
3. Premiere Pro용 XML 타임라인 + SRT 자막 파일 출력
4. Premiere Pro에서 `File > Import`로 XML을 열면 편집된 타임라인이 적용됩니다

## 설치

### 필수 요건
- Python 3.10+
- FFmpeg

```bash
# FFmpeg 설치
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows: https://ffmpeg.org/download.html
```

### 패키지 설치
```bash
pip install -e .
```

## 사용법

### 전체 자동 편집 (추천)
```bash
# 기본 설정으로 실행
premiere-auto-edit auto my_video.mp4

# YouTube 프리셋 + 자막 없이
premiere-auto-edit auto my_video.mp4 --preset youtube --no-subtitle

# 설정 커스텀
premiere-auto-edit auto my_video.mp4 \
    --silence-threshold -35 \
    --target-lufs -14 \
    --whisper-model large-v3 \
    -o ./output
```

### 개별 기능 사용
```bash
# 무음 구간만 확인
premiere-auto-edit silence my_video.mp4

# 음량만 분석
premiere-auto-edit loudness my_video.mp4

# 자막만 생성
premiere-auto-edit subtitle my_video.mp4
```

### 설정 파일 사용
```bash
premiere-auto-edit auto my_video.mp4 -c config.yaml
```

`config.example.yaml`을 참고하여 설정 파일을 작성할 수 있습니다.

## 출력 파일

| 파일 | 설명 |
|------|------|
| `{name}_auto_edit.xml` | Premiere Pro 임포트용 FCP XML (편집된 타임라인) |
| `{name}_original.srt` | 원본 타임라인 기준 한국어 자막 |
| `{name}_edited.srt` | 편집 후 타임라인 기준 한국어 자막 |
| `{name}_report.json` | 편집 결과 리포트 (JSON) |

## 기본 설정값

토킹헤드/인터뷰 촬영에 최적화된 기본값입니다.

| 설정 | 기본값 | 설명 |
|------|--------|------|
| 무음 임계값 | -40dB | 실내 녹화 기준. 시끄러운 환경은 -35 ~ -30 |
| 최소 무음 길이 | 0.5초 | 자연스러운 발화 간 쉼은 유지 |
| 패딩 | 0.15초 | 한국어 받침 발음을 위한 여유 |
| 목표 음량 | -16 LUFS | YouTube/팟캐스트 표준 |
| Whisper 모델 | medium | 한국어 정확도/속도 균형 |
| 최소 클립 길이 | 0.3초 | 너무 짧은 클립 방지 |

## 프리셋

| 프리셋 | 목표 LUFS | 용도 |
|--------|-----------|------|
| `youtube` | -14 | YouTube 업로드 |
| `podcast` | -16 | 팟캐스트 |
| `broadcast` | -24 | 방송 표준 |

## 개발

```bash
# 개발 의존성 설치
pip install -e ".[dev]"

# 테스트 실행
pytest tests/ -v
```

## 라이선스

MIT
