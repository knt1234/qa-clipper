# qa-clipper リポジトリ・ドキュメント整理 設計書

作成: 2026-07-08 Fable 5 / 実装想定: Sonnet 5
対象: `/Users/Kenta/Claude Code/video_editor/`（= スキル qa-clipper の実体。シンボリックリンク経由）

**方針: この設計書に従って実装すること。判断は確定済み。ただし P1（旧データ削除）と P5（git push）はユーザー確認を挟むこと。**

---

## 現状診断（2026-07-08時点）

| # | 問題 | 深刻度 |
|---|---|---|
| 1 | **今週の大改修（8ファイル変更+5新規）が一切コミットされていない。** 最終コミットは4月。マシン障害でスキル改善の全履歴が消えるリスク | 高 |
| 2 | **4月の旧outputフォルダ6個・計約220MB** が放置（output, output2, output2_sonnet, output3, output3_v2, output3_v3）。現運用では finalize.py が作業フォルダを削除するため、この形の残骸は今後発生しないが過去分が残っている | 中 |
| 3 | **実装済みのDESIGN_*.md 4本** がリポジトリ直下に堆積。使い捨ての実装指示書であり、恒久ドキュメント（SKILL.md/lessons.md）と混在して見通しが悪い | 中 |
| 4 | **README.md が配布用の体裁のまま乖離**。リポジトリの位置づけは「自分用バックアップ」に変更されたため（2026-07-08決定）、第三者向けガイドの大部分が不要。SKILL.mdとの二重管理が乖離の温床 | 中 |
| 5 | **SKILL.md が214行・約16KB** に肥大。スキル起動のたびに全文がロードされる。詳細手順は references/ に分離するのがスキルの設計原則 | 低〜中 |
| 6 | .gitignore に `*.log` がない（現在ログはfinalize時に消える運用だが、途中中断時に残り得る） | 低 |

---

## P1: 旧outputフォルダの処分（要ユーザー確認）

対象: `output/ output2/ output2_sonnet/ output3/ output3_v2/ output3_v3/`（計約220MB、2026年4月のテストデータ）

実装時にユーザーへ次の2択を確認してから実行する:
- **(a) 完全削除**（4月のテスト素材で、成果物は既に別所にあるはず）
- **(b) GDrive退避後に削除**（`動画編集_中間ファイル/qa_旧テストデータ_202604/` へまとめて移動）

削除前に各フォルダの中身一覧（ファイル名のみ）を提示すること。

## P2: DESIGN文書のアーカイブ化

1. `references/design-archive/` を作成し、実装済みの4本を移動:
   - DESIGN_IMPROVEMENTS.md / DESIGN_SKILL_UPDATE.md / DESIGN_QUALITY_ASSURANCE.md / DESIGN_FINALIZE.md
   - 本書（DESIGN_CLEANUP.md）も実装完了後に同フォルダへ移動する
2. **ふりかえり記録テンプレートの引っ越し**: メモリ（feedback_video_pipeline_review.md）が「テンプレートは DESIGN_QUALITY_ASSURANCE.md の実装3を参照」としているが、アーカイブに参照を向けるのは筋が悪い。テンプレート定義を `references/lessons.md` の冒頭（「このファイルの書き方」セクションとして）へ転記し、メモリの該当参照を「lessons.md 冒頭のテンプレート」へ書き換える
3. lessons.md 内に DESIGN_*.md への相対リンクがあれば `design-archive/` パスへ更新する

## P3: README.md の縮小（配布用をやめ、自分用バックアップリポジトリの説明書きへ）

**前提変更（2026-07-08 ユーザー決定）**: このリポジトリは第三者への配布用ではなく、自分用のバックアップ。READMEから配布ガイドの体裁（第三者向けの丁寧なセットアップ手順・FAQ・費用説明）を撤去し、将来の自分が見て思い出せる最小限の内容に縮小する。

新READMEの構成（30〜50行程度）:
1. **一言説明**: Q&A動画を1問1答クリップに自動分割するツール。Claude Codeのスキル `qa-clipper` として使う
2. **実体の場所**: `~/.claude/skills/qa-clipper` → このリポジトリへのシンボリックリンク。**運用手順・フロー・トラブルシューティングはすべて [SKILL.md](SKILL.md) が正**で、READMEには書かない（二重管理をやめる。乖離の原因だった）
3. **ファイル構成の早見表**: 各 .py の役割1行ずつ（main / analyzer / transcriber / editor / finalize / downloader）、references/（lessons・troubleshooting・design-archive）の説明
4. **最小セットアップ**: 依存インストール1ブロック（`pip3 install ...` / `brew install ffmpeg`）とAPIキー設定のみ。Homebrew自体の導入手順・スクショ的な説明・FAQ・費用表・処理時間表は削除
5. 削除する既存セクション: 「このファイルをダウンロードする」「Homebrewをインストールする」「よくある質問」「費用の目安」「AIモデルによる費用・精度の違い」「動画の長さと費用の目安」「処理時間の目安」「容量の上限」「動作環境」（これらの情報のうち今後も価値があるもの＝モデル別費用の目安はSKILL.mdの概要にすでに一言あるため転記不要）

GitHubリポジトリの説明文（About）が「配布用」を示唆している場合もあるが、リモート側の設定変更はスコープ外（必要ならユーザーに一言案内するだけでよい）。

## P4: SKILL.md のスリム化

原則: **実行フロー・チェックリスト・オプション表は本体に残す**（毎回必要）。詳細解説・コマンド例・切り分け手順は references/ へ。

1. `references/troubleshooting.md` を新設し、以下を移動:
   - トラブルシューティング表の詳細（表自体は本体に残し、各行の「対処」を1行要約に圧縮。詳細手順はリンク先へ）
   - 「語尾を手動で確認するコマンド」
   - 「冒頭マーカー警告の切り分け方」
2. 「事後検証（qa_report.md）」セクションのA〜D詳細説明を `references/troubleshooting.md`（または `references/qa_report_spec.md`。項目数が少ないのでtroubleshooting.mdに同居でよい）へ移し、本体には4系統の1行サマリと「⚠️は自動失格ではない」の注意だけ残す
3. 目標: SKILL.md を約100〜120行に（現214行）
4. **注意**: verify_clips の仕様準拠チェック（editor.py compliance_rows）が照合する「SKILL.mdの約束事項」の文言は本体に残すこと（余白なし・再エンコード等の注意事項セクションは移動しない）

## P5: git整理とコミット（pushは要ユーザー確認）

1. `.gitignore` に追記: `*.log`
2. コミットは意味単位で分割（履歴が追える粒度）:
   - ① コード改修一式（analyzer/editor/transcriber/downloader/main/finalize/requirements）
   - ② ドキュメント（SKILL.md/README.md/references/）
   - ③ design-archive の追加
3. コミットメッセージは英語1行サマリ+日本語本文可（既存履歴は英語なので英語推奨）
4. **push はユーザーに確認してから**（公開リポジトリ knt1234/qa-clipper のため。コード内にAPIキー等の秘匿情報がないことを push 前に `git diff --cached` で確認する）

---

## 実施順序

P2 → P4 → P3 → P5の準備（.gitignore追記まで） → P1（ユーザー確認） → P5（コミット、pushは確認）

理由: ドキュメント移動・分割を先に済ませてからコミットしないと、コミット直後にまたファイル移動で履歴が汚れる。P1はいつでもよいがgitignore済みなのでコミットとは独立。

## 受け入れチェック（実装後に確認）

1. `python3 -c "import editor, analyzer, transcriber, downloader, main, finalize"` が通る
2. SKILL.md 内のすべての相対リンク（references/...）が実在するファイルを指す
3. メモリ（feedback_video_pipeline_review.md）の参照先が実在する（DESIGN_QUALITY_ASSURANCE.md への参照が残っていない）
4. リポジトリ直下に DESIGN_*.md が残っていない（本書は実装完了後に移動）
5. `git status` がクリーン（旧outputの処分後）
6. SKILL.md が130行以下になっている
6b. README.md が50行程度以下で、使い方の詳細（フロー・オプション・トラブルシューティング）を含んでいない（SKILL.md参照になっている）
7. verify_clips の仕様準拠チェックが引き続き全項目照合できる（注意事項セクションの文言を壊していないこと）

## 実装モデルの判断

**Sonnet で実施**。全項目が機械的なファイル移動・文書編集・git操作であり、判断はこの設計書で確定済み。P1の削除とP5のpushのみユーザー確認を挟む。
