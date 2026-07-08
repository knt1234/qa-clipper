#!/usr/bin/env python3
"""
動画編集自動化 CLI

使い方:
  python main.py <YouTube_URL> [options]

オプション:
  --mode        filler / qa / both  (default: both)
  --output      出力ディレクトリ    (default: ./output_{動画名}_{日付})
  --model       Whisperモデル名     (default: large-v3)
  --skip-dl     ダウンロードをスキップ
  --video       --skip-dl時の動画パス
  --transcript  既存の文字起こしJSONを再利用
  --analysis    既存の解析JSONを再利用
  --review      切り出し前にQ&A一覧（qa_list.md）を出力して確認を挟む
  --cookies-from-browser  ブラウザ名（chrome/firefox/safari）限定公開動画用
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from downloader import download_video
from transcriber import load_transcript, save_transcript, transcribe
from analyzer import (
    analyze, load_analysis, save_analysis, validate_qa_pairs, snap_answer_endings,
    detect_question_markers, cross_check_qa_pairs,
)
from editor import extract_qa_clips, remove_fillers, refine_endings_by_silence, verify_clips, _get_duration


def _default_output_dir(video_path: str) -> Path:
    stem = Path(video_path).stem if video_path else "output"
    date = datetime.date.today().strftime("%Y%m%d")
    base = Path(f"./output_{stem}_{date}")
    candidate = base
    n = 2
    while candidate.exists():
        candidate = Path(f"{base}_{n}")
        n += 1
    return candidate


def _format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _write_qa_list(qa_pairs: list, words: list, output_dir: Path,
                    warnings: Optional[List[str]] = None) -> Path:
    lines = ["| # | タイトル | 開始 | 終了 | 長さ | 質問の冒頭 |", "|---|---------|------|------|------|-----------|"]
    for i, pair in enumerate(qa_pairs, start=1):
        q_start, a_end = pair["q_start"], pair["a_end"]
        preview_words = [w["word"] for w in words if w["start"] >= q_start][:15]
        preview = "".join(preview_words)[:30]
        lines.append(
            f"| {i} | {pair['title']} | {_format_time(q_start)} | {_format_time(a_end)} "
            f"| {_format_time(a_end - q_start)} | 「{preview}…」 |"
        )
    if warnings:
        lines.append("")
        lines.append("## ⚠️ 要確認")
        for w in warnings:
            lines.append(f"- {w}")
    path = output_dir / "qa_list.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="動画編集自動化ツール")
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("--mode", choices=["filler", "qa", "both"], default="both")
    parser.add_argument("--output", default=None)
    parser.add_argument("--model", default="large-v3", help="Whisperモデル名")
    parser.add_argument("--ai-model", default="claude-haiku-4-5-20251001",
                        help="Claude AIモデル名 (default: claude-haiku-4-5-20251001)")
    parser.add_argument("--skip-dl", action="store_true")
    parser.add_argument("--video", help="既存の動画ファイルパス（--skip-dl時に使用）")
    parser.add_argument("--transcript", help="既存の文字起こしJSONパス（再利用）")
    parser.add_argument("--analysis", help="既存の解析JSONパス（再利用）")
    parser.add_argument("--review", action="store_true",
                        help="切り出し前にqa_list.mdを出力して確認を挟む")
    parser.add_argument("--force", action="store_true",
                        help="質問マーカーのクロスチェックで警告が出ても切り出しを続行する")
    parser.add_argument("--cookies-from-browser", dest="cookies_from_browser",
                        help="Cookieを取得するブラウザ名（chrome/firefox/safari）")
    args = parser.parse_args()

    if not args.skip_dl and not args.url:
        parser.error("YouTube URLが必要です（--skip-dlを使う場合は--videoを指定）")

    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("エラー: 環境変数 ANTHROPIC_API_KEY が設定されていません")

    output_dir = Path(args.output) if args.output else _default_output_dir(args.video or args.url)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: ダウンロード ──
    if args.skip_dl:
        if not args.video:
            parser.error("--skip-dl を使う場合は --video でパスを指定してください")
        video_path = args.video
        print(f"[skip] 動画: {video_path}")
    else:
        print(f"[1/4] ダウンロード中: {args.url}")
        video_path, audio_path = download_video(args.url, str(output_dir), args.cookies_from_browser)
        print(f"      動画: {video_path}")
        print(f"      音声: {audio_path}")

    # ── Step 2: 文字起こし ──
    transcript_path = str(output_dir / "transcript.json")
    if args.transcript:
        print(f"[2/4] 文字起こし再利用: {args.transcript}")
        words = load_transcript(args.transcript)
    else:
        if args.skip_dl:
            audio_path = str(Path(video_path).with_suffix(".wav"))
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path,
                 "-ar", "16000", "-ac", "1", "-vn", audio_path],
                check=True, capture_output=True,
            )
        print(f"[2/4] 文字起こし中 (Whisper {args.model})…")
        words = transcribe(audio_path, model_name=args.model)
        save_transcript(words, transcript_path)
        print(f"      保存: {transcript_path}  ({len(words)} 単語)")

    # ── Step 3: Claude 解析 ──
    analysis_path = str(output_dir / "analysis.json")
    if args.analysis:
        print(f"[3/4] 解析結果再利用: {args.analysis}")
        analysis = load_analysis(args.analysis)
    else:
        print("[3/4] Claude API で解析中…")
        analysis = analyze(words, model=args.ai_model, mode=args.mode)
        save_analysis(analysis, analysis_path)
        fillers = analysis.get("fillers", [])
        qa_pairs = analysis.get("qa_pairs", [])
        print(f"      フィラー: {len(fillers)} 件  Q&Aペア: {len(qa_pairs)} 件")
        print(f"      保存: {analysis_path}")

    fillers = analysis.get("fillers", [])
    qa_pairs = analysis.get("qa_pairs", [])

    # ── Step 4: 編集 ──
    video_stem = Path(video_path).stem

    if args.mode in ("filler", "both"):
        out_filler = str(output_dir / f"{video_stem}_no_filler.mp4")
        print(f"[4/4] フィラー除去中 ({len(fillers)} 箇所)…")
        remove_fillers(video_path, fillers, out_filler)
        print(f"      完成: {out_filler}")

    if args.mode in ("qa", "both"):
        duration = _get_duration(video_path)
        qa_pairs = validate_qa_pairs(qa_pairs, duration)
        qa_pairs = snap_answer_endings(qa_pairs, words, duration)
        qa_pairs = refine_endings_by_silence(video_path, qa_pairs, duration)
        print(f"      検証後のQ&Aペア: {len(qa_pairs)} 件")

        # ── 事前チェック: 質問マーカーとのクロスチェック ──
        markers = detect_question_markers(words)
        cross_warnings = cross_check_qa_pairs(qa_pairs, markers)
        if cross_warnings:
            print(f"\n[事前チェック] ⚠️ {len(cross_warnings)} 件の警告:")
            for w in cross_warnings:
                print(f"      {w}")
            if not args.force:
                qa_list_path = _write_qa_list(qa_pairs, words, output_dir, warnings=cross_warnings)
                sys.exit(
                    f"\n検出漏れ・結合の疑いがあるため切り出しを中止しました。\n"
                    f"{qa_list_path} を確認し、analysis.json を修正してから再実行してください。\n"
                    f"（警告を無視して続行する場合は --force を指定）"
                )

        if args.review:
            qa_list_path = _write_qa_list(qa_pairs, words, output_dir, warnings=cross_warnings)
            print(f"\n[review] Q&A一覧を出力しました: {qa_list_path}")
            print("内容を確認してください。続行してよければ Enter を押してください。")
            input()

        qa_dir = str(output_dir / "qa")
        print(f"[4/4] Q&Aクリップ生成中 ({len(qa_pairs)} 件)…")
        clips = extract_qa_clips(video_path, qa_pairs, qa_dir, padding=0.0)
        for c in clips:
            print(f"      {c}")

        # ── 事後検証 ──
        print("\n[事後検証] クリップを検証中…")
        report_path = verify_clips(video_path, clips, qa_pairs, words, str(output_dir), analysis=analysis)
        print(f"      検証レポート: {report_path}")
        print(f'      承認後の最終配置は: python3 finalize.py --output "{output_dir}"')

    print("\n完了！")


if __name__ == "__main__":
    main()
