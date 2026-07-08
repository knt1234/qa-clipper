# qa-clipper スキル更新 設計書（2026-07-07 実運用の知見反映）

作成: Fable 5 / 実装想定: Sonnet 5
対象: `/Users/Kenta/.claude/skills/qa-clipper/`（SKILL.md はvideo_editor側とハードリンク）と `/Users/Kenta/Claude Code/video_editor/`

**方針: コードは実装済み。今回はドキュメント整備のみ。この設計書を正とし、実装者は内容の再判断をしないこと。**

---

## 今回のセッションで確定した知見（反映すべき事実）

### 実運用で出たユーザー指摘と対応の経緯
1. **「前後の余白3秒はいらない。話始め・話終わりピッタリで切る」**
   → padding デフォルトを 3.0 → 0.0 に変更（実装済み）
2. **「終わりの判断が早い。数秒切れている」（1回目）**
   → 原因1: Claude の a_end が言い直し・相槌の手前で止まることがある
   → `snap_answer_endings()`: 単語間ギャップ0.8秒未満は同一発話とみなして a_end を延長（実装済み）
3. **「全体的にまだ終わりが切れている」（2回目）**
   → 原因2: **Whisper の単語終了タイムスタンプは実際の発声より0.2〜0.5秒早い**（全クリップで確認）
   → 原因3: この動画は平均音量 -40dB と小さく、既定の -30dB 閾値では無音検出が機能しなかった
   → `refine_endings_by_silence()`: 平均音量から閾値を自動算出（mean-6dB）し、波形上の無音開始+0.12秒に a_end を補正（実装済み）

### 確立した終端決定の3段パイプライン（コードは main.py に実装済み）
```
Claude解析(a_end) → validate_qa_pairs（整合性検証）
  → snap_answer_endings（文字起こしベースで文末まで延長）
  → refine_endings_by_silence（波形ベースで真の発話終端+余韻0.12秒へ補正）
```

### 検証で有効だったコマンド（トラブルシューティングに載せる）
- 真の発話終端の測定: `ffmpeg -ss <start> -to <end> -i audio.wav -af silencedetect=noise=<mean-6>dB:d=0.3 -f null -`
- 平均音量の取得: `ffmpeg -i audio.wav -af volumedetect -f null -` → `mean_volume`
- 境界前後の単語確認: transcript.json から a_end±5秒の単語を抜き出して目視

---

## 変更ファイルと内容

### 1. SKILL.md（`.claude/skills/qa-clipper/SKILL.md`＝`video_editor/SKILL.md`、ハードリンクなので片方の編集でOK）

**a. 「概要」セクション**: 変更不要（余白なしは反映済み）

**b. 「実行フロー」に終端補正の説明を1行追加**:
ステップ1の解析の後に「a_end は3段補正（検証→文字起こしベース延長→波形ベース補正）が自動で入る」旨を記載。ユーザーが「なぜqa_list.mdの終了時刻がClaudeの生の値と違うのか」を後で見て分かるように。

**c. 「完了時チェックリスト」に語尾チェックを追加**:
```
- [ ] 最後のクリップと、任意の1本について、末尾2秒に発話が残っていないか
      silencedetect（閾値は mean_volume - 6dB）で確認する
      （Whisperのタイムスタンプは信用しない。波形で確認する）
```

**d. 「トラブルシューティング」セクションを新設**（SKILL.md末尾）:
| 症状 | 原因 | 対処 |
|---|---|---|
| 語尾が切れる | Whisperの単語終了時刻は実際より0.2〜0.5秒早い | refine_endings_by_silence が自動補正。手動確認は silencedetect |
| 無音検出が反応しない | 音源の音量が小さい（Zoom録画は平均-40dB程度のことがある） | 閾値は固定値でなく mean_volume - 6dB を使う（実装済みの既定動作） |
| 回答が相槌の手前で切れる | Claudeが「はい」等の相槌を回答終了と誤認 | snap_answer_endings が0.8秒未満のギャップを繋いで延長 |
| クリップ頭がズレる/乱れる | `-c copy` はキーフレーム単位でしか切れない | 再エンコード方式（実装済み）。-c copy に戻さないこと |

**e. 「注意事項」の処理時間目安を実測値に更新**:
15分動画の実測: 文字起こし(faster-whisper large-v3)約5分 + Claude解析1分以内 + 切り出し(再エンコード5本)約3分。

### 2. README.md（video_editor/）の同期
- openai-whisper の記述を faster-whisper に更新
- 終端3段補正パイプラインの説明を追加
- 余白3秒の記述を「余白なし」に更新
- セットアップコマンドを SKILL.md と一致させる
（READMEとSKILL.mdで矛盾があると次回作業時に混乱するため。内容はSKILL.mdに準拠）

### 3. DESIGN_IMPROVEMENTS.md の状態更新
- 冒頭に「※ P0/P1 は 2026-07-07 実装済み。P2（K/L/M）は未実装のまま保留」と追記
- 削除はしない（K/L/M の設計が残っているため）

### 4. 運用メモの新設: `.claude/skills/qa-clipper/references/lessons.md`
SKILL.md を肥大化させないため、経緯・根拠は参照ファイルに分離する。内容:
- 上記「今回のセッションで確定した知見」をそのまま整理して記録
- 「やり直しになった失敗事例」として: ①余白3秒で納品→やり直し ②文字起こしベースの補正だけで納品→やり直し（波形確認を省略したため）
- 教訓の一般化: **「切り出し境界の最終確認は文字起こしではなく音声波形で行う」**
- SKILL.md からは「詳細な経緯は references/lessons.md 参照」と1行リンク

---

## 実装しないこと（スコープ外）
- コード変更（全て実装済み・動作確認済み）
- P2項目（長尺チャンク分割・transcript圧縮・cache_control削除）
- video-pipeline 等の他スキルへの波及修正

## 受け入れチェック（実装後にSonnetが確認）
1. SKILL.md に「余白3秒」の記述が残っていないこと（grep で確認）
2. SKILL.md / README.md / lessons.md の間で数値（余韻0.12秒、ギャップ0.8秒、閾値 mean-6dB）が一致していること
3. ハードリンクが維持されていること（`stat -f %i` で両パスの inode 一致）
4. references/ ディレクトリがスキル側に作成され、lessons.md が存在すること

## 実装モデルの判断
**Sonnet で実施**。理由: 全てドキュメント編集で、記載内容・数値・構成はこの設計書で確定済み。判断の余地がなく、Opus を使う意味がない。
