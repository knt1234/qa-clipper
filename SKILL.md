---
name: qa-clipper
description: YouTubeまたはローカルの動画から質疑応答（Q&A）を自動検出し、1問1答形式の切り抜きMP4を生成するスキル。faster-whisper（ローカル無料）で文字起こし、Claude Haiku APIでQ&A境界を検出、ffmpegで切り出す。
---

# Q&Aクリッパー

## 概要

質問会・勉強会・インタビュー動画から、1問1答形式の切り抜き動画を自動生成する。

- **文字起こし**: faster-whisper large-v3-turbo（ローカル・無料。CTranslate2はMacでGPU非対応のためCPU実行。turbo+vad_filter+全コア使用で実測は動画の長さの約1.05倍）
- **Q&A検出**: Claude Haiku API（10分動画で約13〜26円）
- **動画編集**: ffmpeg（再エンコード方式で正確に切り出し）
- **余白**: なし（質問の話し始め〜回答の話し終わりでぴったり切る）

## 実行フロー（Claude Code経由で実行する場合は必ずこの順で進める）

1. **解析**: 文字起こし → Claude解析 → 3段階の終端自動補正（`validate_qa_pairs`→`snap_answer_endings`→`refine_endings_by_silence`。経緯は[references/lessons.md](references/lessons.md)）→ `qa_list.md`（Q&A一覧）を生成
2. **事前チェック**: `detect_question_markers`／`cross_check_qa_pairs` でAI検出結果とルールベースの定型句検出を突き合わせる。警告（検出漏れ／結合の疑い）が出たら**切り出しに進まない**。`analysis.json` を修正するか再解析し、警告ゼロを確認する（CLI単体実行では`--force`で無視も可・非推奨）
3. **事前レビュー**: `qa_list.md` の内容（タイトル・時間・質問の冒頭、警告があれば⚠️セクションも）をチャットでユーザーに提示し、確認を取る
4. **切り出し**: ユーザーOKが出たら再エンコード方式で切り出しを実行する
5. **事後検証**: `verify_clips` を実行し `qa_report.md` を生成する（詳細は下記「事後検証」参照）
6. **事後レビュー**: `qa_report.md` の表を提示し、**最終OKをもらって初めて完成**。⚠️があれば原因を修正して4に戻る
7. **ふりかえり記録**: 完了報告の前にセッションの指摘・確認事項を整理し記録する。手順とテンプレートは [references/lessons.md](references/lessons.md) 冒頭の「このファイルの書き方」を参照。SKILL.mdに仕様を追加した場合は `verify_clips` の仕様準拠チェック項目も必ずセットで追加する
8. **最終配置（承認後）**: 完成承認後、`finalize.py` でローカル完成品配置＋GDriveバックアップ＋作業フォルダ削除を行う（下記「最終配置とバックアップ」参照）。実行前にファイル操作の内容を提示し、**⑥とは別にもう一段の承認を得る**（無断でファイルを動かさない）

`--review` フラグで切り出し前に一時停止してqa_list.mdを確認できる（単体実行時向け）。Claude Code経由ではフラグの有無に関わらず上記を人間の確認込みで進める。

## 事後検証（qa_report.md、詳細は [references/troubleshooting.md](references/troubleshooting.md)）

`verify_clips`（editor.py）が4系統（A.ファイル健全性 / B.境界検査 / C.カバレッジ検査 / D.仕様準拠チェック）を検証し「✅ 合格」または「⚠️ 要確認N件」を出す。Cは参考情報で合否に含めない。⚠️は自動失格ではなく確認のトリガー。**Dが照合する約束事項は下記「注意事項」の記述そのもの。注意事項を変更したら `verify_clips` 内 `compliance_rows` も同時に更新すること。**

## 最終配置とバックアップ

完成物だけをローカルに残し、それ以外（audio.wav・JSON・レポート含む一式）はGoogle Driveにバックアップする運用（動画編集プロジェクト共通）。

| 種別 | パス | 内容 |
|---|---|---|
| ローカル完成品 | `/Users/Kenta/Documents/動画編集_完成品/QA_{動画名}/` | クリップMP4のみ |
| GDriveバックアップ | `.../動画編集_中間ファイル/qa_{動画名}/` | output フォルダ一式（クリップ+音声+JSON+レポート） |
| 作業フォルダ | `output_{動画名}_{日付}/` | 検証通過後に削除 |

```bash
python3 finalize.py --output "output_xxx_20260707"
```

安全順序（コピー→検証→削除）を厳守し、`qa_report.md` が「✅ 合格」でないと実行しない。`--keep-local`（削除スキップ）、`--yes`（確認省略）、`--force`（⚠️があっても続行。**ユーザー承認必須**、無条件バイパスにしない）。GDrive未マウント時は中止する。

## セットアップ（初回のみ）

```bash
# 依存ライブラリ
pip3 install faster-whisper anthropic ffmpeg-python tqdm yt-dlp

# ffmpeg / yt-dlp
brew install ffmpeg

# APIキー（~/.zshenvに追記で永続化）
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshenv
```

## 使い方

```bash
cd "/Users/Kenta/Claude Code/video_editor"

# ローカルファイルから処理（主な用途）。--output省略時は output_{動画名}_{日付} が自動生成される
python3 main.py --skip-dl --video "/path/to/video.mp4" --mode qa --review

# YouTube URLから処理
python3 main.py "https://youtu.be/XXXX" --mode qa --review

# 限定公開動画（Chromeのログインを使用）
python3 main.py "https://youtu.be/XXXX" --mode qa --cookies-from-browser chrome

# 文字起こし・解析を再利用（2回目以降は高速）
python3 main.py --skip-dl --video "/path/to/video.mp4" \
  --transcript ./output_xxx/transcript.json --analysis ./output_xxx/analysis.json --mode qa

# グループコンサル形式（講師が受講生を指名して対話する動画。指名〜次の指名で1クリップ）
python3 main.py --skip-dl --video "/path/to/video.mp4" --mode group-consult --review

# 動画全体を1本として扱う（区切り検出なし、タイトルだけAI生成）
python3 main.py --skip-dl --video "/path/to/video.mp4" --mode whole
```

## 出力ファイル

`finalize.py` 実行前は作業フォルダ `output_{動画名}_{日付}/` に `transcript.json`（文字起こし）・`analysis.json`（Q&A検出結果）・`qa_list.md`（事前レビュー用一覧）・`qa_report.md`（事後検証レポート）・`qa/001_タイトル.mp4...`（クリップ）が揃う。

`finalize.py` 実行後（承認後）は `Documents/動画編集_完成品/QA_{動画名}/` にクリップのみ、`GDrive/動画編集_中間ファイル/qa_{動画名}/` に上記一式のバックアップが残り、作業フォルダは削除される（詳細は「最終配置とバックアップ」参照）。

## 完了時チェックリスト

- [ ] `qa_report.md` の総合判定を確認し、表をそのままユーザーに提示する。⚠️は原因を切り分け、実際の問題なら修正して再切り出し・再検証する
- [ ] ユーザーから最終OKをもらって初めて完成とする（生成できた時点では完成ではない）
- [ ] 完了報告の前にセッションの指摘事項を整理・記録する（実行フロー⑦参照）

## 注意事項

- クリップは**再エンコード方式**で切り出す（`-c copy` は使わない）。キーフレーム単位のズレを避けるため、多少処理時間はかかるが位置が正確になる
- 余白なしで、質問の話し始め〜回答の話し終わりちょうどで切り出す
- `--mode qa` ではフィラー検出は行わない（プロンプト・出力トークンの無駄を避けるため）
- Q&Aペアは自動検証される（順序整列・時間超過のクランプ・重複除外）。除外されたペアは実行ログに警告が出る
- Whisper large-v3-turboモデルのダウンロードは初回のみ（約1.6GB）
- 処理時間の実測目安（このMacのCPU・large-v3-turbo・int8・vad_filter・全コア）：文字起こしは**動画の長さとほぼ同じ**（15分動画で約16分、10分動画で約10.5分）+ Claude解析1分以内 + 切り出し（クリップ数×数十秒）。旧設定（large-v3・vad_filterなし）では動画の長さの約2.3〜2.8倍かかっていた
- **基本はturboで実行し、精度に問題（検出漏れ・誤字による境界ズレ等）が疑われる場合のみ `--model large-v3` に切り替えて再実行する**運用（2026-07-12決定）。turboはlarge-v3よりデコーダー層が少なく、OpenAI公表でもわずかな精度低下がある
- 質問マーカーのクロスチェック（②事前チェック）と境界検査の冒頭/末尾マーカー判定（⑤事後検証B）は `qa`/`both` 専用。`group-consult`/`whole` では「◯つ目の質問」のような定型句が出ないため適用されない。この2モードでは**③事前レビューでの境界確認をより丁寧に行う**こと

## トラブルシューティング（詳細は [references/troubleshooting.md](references/troubleshooting.md)）

| 症状 | 原因 | 対処 |
|---|---|---|
| 語尾が切れる | Whisperの時刻は実際の発声より早く出る | `refine_endings_by_silence` が自動補正。手動確認は波形で（troubleshooting.md） |
| 無音検出が反応しない | 音源の音量が小さい | 閾値は `mean_volume - 6dB` を自動算出（実装済み） |
| 回答が相槌の手前で切れる | Claudeが相槌を回答終了と誤認 | `snap_answer_endings` がギャップ0.8秒未満なら延長 |
| クリップ頭がズレる／冒頭が乱れる | `-c copy` はキーフレーム単位でしか切れない | 再エンコード方式（実装済み）。`-c copy` に戻さない |
| 複数の質問が1クリップに結合される | AIが前振りを見逃す | `cross_check_qa_pairs` が警告。`analysis.json` を分割して再実行 |
| ドキュメントと挙動がズレる | 仕様変更時に片方だけ直す | `qa_report.md` の仕様準拠チェックが検出。両方同時に更新する |
| qa_report.mdの境界検査が誤検知する | tinyモデルの精度が粗い | 切り分け方はtroubleshooting.md参照 |
| 承認済みの警告で finalize.py がブロックされる | ⚠️が残っていると実行不可の仕様 | ユーザー承認を得た上で `finalize.py --force` |
| グルコン動画で質問マーカー系の誤警告が出る | qa用チェックがグルコン形式に非対応だった（2026-07-12修正済み） | `--mode group-consult` を使う。旧版なら更新する |

## オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--mode` | `both` | `filler` / `qa` / `both` / `group-consult` / `whole`（後2つは注意事項参照） |
| `--output` | `./output_{動画名}_{日付}` | 出力フォルダ |
| `--model` | `large-v3-turbo` | Whisperモデル名（速度優先。精度を上げたい場合は`large-v3`を指定） |
| `--ai-model` | `claude-haiku-4-5-20251001` | Claude AIモデル |
| `--skip-dl` | - | ダウンロードをスキップ |
| `--video` | - | ローカル動画パス |
| `--transcript` | - | 既存の文字起こしJSONを再利用 |
| `--analysis` | - | 既存の解析JSONを再利用 |
| `--review` | - | 切り出し前にqa_list.mdで一時停止して確認 |
| `--force` | - | 質問マーカーのクロスチェックで警告が出ても切り出しを続行する（非推奨） |
| `--cookies-from-browser` | - | 限定公開動画用（chrome/firefox/safari） |
