# qa-clipper モード統合・VAD修正 設計書

作成: 2026-07-12 Fable 5 / 実装想定: Sonnet 5
対象: `/Users/Kenta/Claude Code/video_editor/`（transcriber.py / analyzer.py / editor.py / main.py / SKILL.md / references/lessons.md）

**方針: この設計書に従って実装すること。判断は確定済み。実装完了後、本書は references/design-archive/ へ移動する。**

---

## 背景（Fableレビューで発見した問題）

現在の作業ツリーには2系統の未コミット変更が混在している:
- **(a) 文字起こし高速化**（今セッション）: turbo化・vad_filter・cpu_threads
- **(b) group-consult / whole モード追加**（別セッション）: グループコンサル形式・全体1本扱いの新モード

(b)は解析プロンプトとmain.pyの分岐は実装済みだが、**qaモード前提で作った検証システム（事前チェック・事後検証）がそのまま適用される**構造になっており、グルコン動画を処理すると誤警告でブロックされる。また(a)のvad_filterが検証用の文字起こしにも効いてしまう副作用がある。

## 発見した問題

| # | 問題 | 影響 |
|---|---|---|
| A | `transcribe()` に `vad_filter=True` を固定で入れたため、`verify_clips` の冒頭/末尾検査（tinyモデル）にもVADが効く。低音量音源（Zoom録画は平均-40dB）ではVADが実際の発話を無音と誤判定し、検査テキストが欠けて偽陽性⚠️や検査能力低下を招く恐れ | 中 |
| B | group-consult モードに qa 用の検証がそのまま適用される: ①長さ外れ値チェック（中央値1.8倍）はセッション長がばらつくグルコンでほぼ確実に誤警告→切り出しブロック ②質問マーカークロスチェックは「質問」系定型句前提でグルコンの指名（人名+さん）とは無関係 ③verify_clips のB検査（冒頭に質問マーカー必須）はグルコンの全クリップが⚠️になる | 高（グルコン動画を処理すると必ず詰まる） |
| C | SKILL.md が新モードを知らない: `--mode` の説明が `filler / qa / both` のまま。group-consult / whole の使い方・検証の適用範囲が未記載（「ドキュメントとコードのセット更新」原則からの逸脱） | 中 |
| D | whole モードは「タイトル1つ生成するだけ」なのに transcript 全文（15分動画で約9.5万トークン）を Claude に送る。タイトル生成に全文は不要 | 低（数十円の無駄） |

---

## 実装1: vad_filter の引数化（問題A）

`transcriber.py`:
```python
def transcribe(audio_path, model_name="large-v3-turbo", vad_filter=True):
    ...
    segments, _info = model.transcribe(..., vad_filter=vad_filter)
```
- 既定 True（本編の文字起こしは高速化の恩恵を受ける）
- `editor.py` の `_transcribe_window` は `transcribe(tmp_path, model_name="tiny", vad_filter=False)` に変更（検査用途は正確さ優先。6秒の窓なので速度影響は無視できる）

## 実装2: 検証システムのモード対応（問題B）

### main.py
- `cross_check_qa_pairs` の実行を `args.mode in ("qa", "both")` のときのみに限定する。group-consult では実行しない（指名パターンは人名依存でルールベース検出が困難。境界の妥当性は③事前レビューの人間確認に委ねる）
- group-consult でも `validate_qa_pairs → snap_answer_endings → refine_endings_by_silence` の3段補正は現行どおり適用（形式に依存しない補正のため）
- `verify_clips` に `mode=args.mode` を渡す

### editor.py（verify_clips）
- シグネチャに `mode: str = "qa"` を追加
- B検査の「冒頭に質問マーカーが見当たらない」⚠️判定は `mode in ("qa", "both")` のときだけ。group-consult / whole では冒頭・末尾テキストをレポートに**表示するだけ**（人間の判断材料。⚠️にしない）
- B検査の「末尾に次の質問マーカー混入」⚠️も同様に qa/both 限定（グルコンで「最後の質問」等が受講生の発言に出ても誤検知しないように）
- A（健全性）・C（カバレッジ）・D（仕様準拠）は全モード共通のまま

## 実装3: whole モードの送信データ削減（問題D）

`analyzer.py` の `analyze()`: `mode == "whole"` のとき、Claude に送る words を**先頭300語**に間引く（タイトル生成には冒頭で十分）。transcript.json 自体は全文保存のまま変えない。

## 実装4: SKILL.md へのモード文書化（問題C）

1. オプション一覧の `--mode` 行を更新: `filler / qa / both / group-consult / whole`
2. 「使い方」に2例追加:
   ```bash
   # グループコンサル形式（講師が受講生を指名して対話する動画。指名〜次の指名で1クリップ）
   python3 main.py --skip-dl --video "..." --mode group-consult --review
   # 動画全体を1本として扱う（区切り検出なし、タイトルだけAI生成）
   python3 main.py --skip-dl --video "..." --mode whole
   ```
3. 「注意事項」に1行追加: 質問マーカーのクロスチェックと境界検査（冒頭マーカー）は qa/both モード専用。group-consult / whole では適用されないため、**③事前レビューでの境界確認をより丁寧に行う**
4. トラブルシューティングに1行追加: `| グルコン動画で誤警告が出て進まない | qa用チェックがグルコン形式に非対応だった（2026-07-12修正済み） | --mode group-consult を使う。旧版なら更新する |`

## 実装5: lessons.md ふりかえり追記

2026-07-12 エントリ（既存の速度実測エントリ）に指摘行を追加、または新ブロック:
- 発見: 別セッションでのモード追加が、qa前提の検証システムと未統合のまま入っていた
- 教訓: **新モードを追加するときは「解析プロンプト＋main分岐」だけでなく、事前チェック・事後検証・SKILL.mdの3点への影響を必ず確認する**（チェック網が広がったぶん、新機能はチェック網との整合コストを払う）

## 実装6: コミット整理（pushは要ユーザー確認）

意味単位で2コミット:
1. **文字起こし高速化**: transcriber.py（vad引数化含む）+ main.py の `--model` デフォルト + SKILL.md の速度記述 + lessons.md の速度エントリ
2. **group-consult/wholeモード + 検証のモード対応**: analyzer.py + main.py のモード分岐 + editor.py の verify_clips モード対応 + SKILL.md のモード文書化 + lessons.md の統合エントリ

ファイル単位で綺麗に分けられない場合（main.py が両方に跨る）は `git add -p` で分割。煩雑になりすぎるなら1コミットにまとめてよい（履歴の綺麗さより正確さ優先。その場合はコミットメッセージに両方を明記）。
コミット前に秘匿情報スキャン（`git diff --cached | grep -iE "sk-ant-[a-zA-Z0-9]{10,}"` 等）。**push はユーザー確認後**。

---

## テスト計画（Sonnet が実装後に実行）

1. 構文: `python3 -c "import editor, analyzer, transcriber, downloader, main, finalize"`
2. vad引数化: `transcribe` のシグネチャ確認 + `_transcribe_window` が `vad_filter=False` を渡すことを grep で確認
3. プロンプト生成: `_build_system_prompt("group-consult")` / `("whole")` が正しいセクション・JSONフィールドを含むこと（print で目視）
4. モード分岐ユニット: ダミー qa_pairs で
   - `verify_clips(..., mode="group-consult")` が冒頭マーカー無しでも⚠️を出さないこと（実クリップが無いため、GDriveバックアップの既存クリップ2〜3本を /tmp にコピーして使う）
   - `verify_clips(..., mode="qa")` は従来どおり⚠️を出すこと（回帰確認）
5. whole の間引き: `analyze` に渡る words が300語に切られることをユニットで確認（API は呼ばない。プロンプト構築前のデータを検査）
6. SKILL.md のリンク・行数確認（135行以内目安）

## 実装モデルの判断

**Sonnet で実施**。全変更が本書で確定済みの局所修正。グルコン実データでの本番検証は、次回グルコン動画を処理するときに行う（それまでは上記ユニットテストで担保）。
