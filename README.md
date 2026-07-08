# qa-clipper

Q&A動画を1問1答形式のクリップに自動分割するツール。Claude Codeのスキル `qa-clipper` として使う。

このリポジトリは自分用のバックアップ。運用手順・実行フロー・トラブルシューティングはすべて **[SKILL.md](SKILL.md) が正**。READMEには書かない（二重管理による乖離を防ぐため）。

## スキルとしての実体

`~/.claude/skills/qa-clipper` は、このリポジトリへのシンボリックリンク。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `main.py` | CLIエントリポイント（解析→事前チェック→切り出し→事後検証） |
| `analyzer.py` | Claude解析、終端補正、質問マーカー検出・クロスチェック |
| `transcriber.py` | faster-whisperによる文字起こし |
| `editor.py` | ffmpegでの切り出し、クリップ検証（`qa_report.md`生成） |
| `finalize.py` | 承認後の最終配置（ローカル完成品＋Google Driveバックアップ） |
| `downloader.py` | YouTube動画のダウンロード |
| `references/lessons.md` | 運用の教訓・ふりかえり記録 |
| `references/troubleshooting.md` | トラブルシューティング詳細 |
| `references/design-archive/` | 実装済みの設計書（過去の変更履歴） |

## セットアップ

```bash
pip3 install faster-whisper anthropic ffmpeg-python tqdm yt-dlp
brew install ffmpeg
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshenv
```
