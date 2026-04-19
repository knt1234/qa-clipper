---
name: qa-clipper
description: YouTubeまたはローカルの動画から質疑応答（Q&A）を自動検出し、1問1答形式の切り抜きMP4を生成するスキル。Whisper（ローカル無料）で文字起こし、Claude Haiku APIでQ&A境界を検出、ffmpegで切り出す。
---

# Q&Aクリッパー

## 概要

質問会・勉強会・インタビュー動画から、1問1答形式の切り抜き動画を自動生成する。

- **文字起こし**: Whisper large-v3（ローカル・無料）
- **Q&A検出**: Claude Haiku API（10分動画で約13〜26円）
- **動画編集**: ffmpeg
- **前後の余白**: 3秒（YouTube Studioでトリミング調整を前提）

## セットアップ（初回のみ）

```bash
# 依存ライブラリ
pip3 install openai-whisper anthropic ffmpeg-python torch tqdm yt-dlp

# ffmpeg / yt-dlp
brew install ffmpeg

# APIキー（~/.zshenvに追記で永続化）
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshenv
```

## 使い方

### YouTube URLから処理

```bash
cd "/Users/Kenta/Claude Code/video_editor"
python3 main.py "https://youtu.be/XXXX" --mode qa --output ./output
```

### ローカルファイルから処理

```bash
python3 main.py \
  --skip-dl \
  --video "/path/to/video.mp4" \
  --mode qa \
  --output ./output
```

### 限定公開動画（Chromeのログインを使用）

```bash
python3 main.py "https://youtu.be/XXXX" --mode qa --cookies-from-browser chrome
```

### 文字起こし・解析を再利用（2回目以降は高速）

```bash
python3 main.py \
  --skip-dl \
  --video "/path/to/video.mp4" \
  --transcript ./output/transcript.json \
  --analysis ./output/analysis.json \
  --mode qa
```

## 出力ファイル

```
output/
├── transcript.json        ← 文字起こし（再利用可）
├── analysis.json          ← Q&A検出結果（再利用可）
└── qa/
    ├── 001_タイトル.mp4
    ├── 002_タイトル.mp4
    └── ...
```

## 注意事項

- クリップは**前後3秒の余白付き**で生成される
- 短すぎる場合は修正不可のため、長めに設定している
- 長い分はYouTube Studioのトリミング・カット機能で調整する
- Whisper large-v3のダウンロードは初回のみ（約3GB）
- 10分動画の処理時間の目安：文字起こし10〜20分 + Claude解析1分以内

## オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--mode` | `both` | `filler` / `qa` / `both` |
| `--output` | `./output` | 出力フォルダ |
| `--model` | `large-v3` | Whisperモデル名 |
| `--ai-model` | `claude-haiku-4-5-20251001` | Claude AIモデル |
| `--skip-dl` | - | ダウンロードをスキップ |
| `--video` | - | ローカル動画パス |
| `--transcript` | - | 既存の文字起こしJSONを再利用 |
| `--analysis` | - | 既存の解析JSONを再利用 |
| `--cookies-from-browser` | - | 限定公開動画用（chrome/firefox/safari） |
