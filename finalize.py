#!/usr/bin/env python3
"""
qa-clipper 最終配置・バックアップ自動化

クリップのレビュー承認後に実行する:
  1. 事前チェック（qa_report.md が合格していること・GDriveマウント確認）
  2. ローカル完成品フォルダへクリップをコピー
  3. Google Drive へ output フォルダ一式をコピー
  4. 両方の検証（ファイル数・バイトサイズ照合）
  5. 検証を全通過した場合のみローカル作業フォルダを削除

使い方:
  python3 finalize.py --output "output_xxx_20260707" [--keep-local] [--yes]
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

LOCAL_FINISHED_ROOT = Path("/Users/Kenta/Documents/動画編集_完成品")
GDRIVE_ROOT = Path(
    "/Users/Kenta/Library/CloudStorage/GoogleDrive-kenta0720fila@gmail.com"
    "/マイドライブ/動画編集_中間ファイル"
)


def _extract_video_name(output_dir: Path) -> str:
    name = output_dir.name
    name = re.sub(r"^output_", "", name)
    name = re.sub(r"_\d{8}(_\d+)?$", "", name)
    return name


def _dir_files(root: Path):
    """root配下の全ファイルを (root相対パス, サイズ) のリストで返す。"""
    return sorted(
        (p.relative_to(root), p.stat().st_size)
        for p in root.rglob("*") if p.is_file()
    )


def _verify_copy(src_files, dst_root: Path) -> list:
    """コピー元のファイル一覧とコピー先を突き合わせ、不一致のリストを返す（空なら一致）。"""
    mismatches = []
    for rel_path, src_size in src_files:
        dst_path = dst_root / rel_path
        if not dst_path.exists():
            mismatches.append(f"欠落: {rel_path}")
        elif dst_path.stat().st_size != src_size:
            mismatches.append(f"サイズ不一致: {rel_path}")
    return mismatches


def _report_verdict(report_path: Path) -> str:
    """レポートの総合判定行を返す（存在しなければ空文字）。"""
    if not report_path.exists():
        return ""
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("総合判定:"):
            return line
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="qa-clipper 最終配置・バックアップ")
    parser.add_argument("--output", required=True, help="対象の出力フォルダ")
    parser.add_argument("--keep-local", action="store_true",
                        help="ローカル作業フォルダを削除しない（コピーと検証のみ）")
    parser.add_argument("--yes", action="store_true",
                        help="確認プロンプトをスキップして実行")
    parser.add_argument("--force", action="store_true",
                        help="qa_report.mdに⚠️が残っていても、内容を確認・承認した上で続行する")
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    video_name = _extract_video_name(output_dir)

    # ── 事前チェック ──
    if not output_dir.is_dir():
        sys.exit(f"エラー: 出力フォルダが存在しません: {output_dir}")

    qa_dir = output_dir / "qa"
    clips = sorted(qa_dir.glob("*.mp4")) if qa_dir.is_dir() else []
    if not clips:
        sys.exit(f"エラー: {qa_dir} にクリップ(.mp4)が見つかりません")

    report_path = output_dir / "qa_report.md"
    verdict = _report_verdict(report_path)
    if "✅ 合格" not in verdict:
        if not verdict:
            sys.exit(f"エラー: {report_path} が見つかりません。先に main.py の事後検証を実行してください。")
        if not args.force:
            sys.exit(
                f"エラー: {verdict}\n"
                f"⚠️が残っている状態では最終配置できません。{report_path} を確認し、\n"
                f"内容に問題なければ --force を付けて再実行してください。"
            )
        print(f"[警告を確認済みとして続行] {verdict}\n")

    if not GDRIVE_ROOT.parent.is_dir():
        sys.exit(
            f"エラー: Google Drive がマウントされていません: {GDRIVE_ROOT.parent}\n"
            f"未マウントのまま実行すると同期されないフォルダを作ってしまうため中止します。"
        )

    local_dest = LOCAL_FINISHED_ROOT / f"QA_{video_name}"
    gdrive_dest = GDRIVE_ROOT / f"qa_{video_name}"

    src_files = _dir_files(output_dir)
    total_size = sum(size for _, size in src_files)

    print("── 実行予定の操作 ──")
    print(f"  ローカル完成品へ: クリップ{len(clips)}本 → {local_dest}")
    print(f"  Google Driveへ:  出力一式({total_size / 1e6:.0f}MB) → {gdrive_dest}")
    if args.keep_local:
        print(f"  ローカル作業フォルダ: 削除しない（--keep-local）")
    else:
        print(f"  ローカル作業フォルダ: 検証後に削除 → {output_dir}")

    if local_dest.exists():
        print(f"  [注意] {local_dest} は既に存在します。中身を上書き・追加します。")
    if gdrive_dest.exists():
        print(f"  [注意] {gdrive_dest} は既に存在します。中身を上書き・追加します。")

    if not args.yes:
        answer = input("\nこの内容で実行してよろしいですか？ [y/N]: ").strip().lower()
        if answer != "y":
            sys.exit("中止しました。")

    # ── ローカル完成品へコピー ──
    local_dest.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        shutil.copy2(clip, local_dest / clip.name)
    print(f"\n[1/4] ローカル完成品へコピー完了: {local_dest}")

    # ── Google Driveへコピー ──
    if gdrive_dest.exists():
        shutil.copytree(output_dir, gdrive_dest, dirs_exist_ok=True)
    else:
        shutil.copytree(output_dir, gdrive_dest)
    print(f"[2/4] Google Driveへコピー完了: {gdrive_dest}")

    # ── 検証 ──
    local_mismatches = _verify_copy(
        [(clip.name, clip.stat().st_size) for clip in clips], local_dest
    )
    gdrive_mismatches = _verify_copy(src_files, gdrive_dest)

    if local_mismatches or gdrive_mismatches:
        print("\n[3/4] 検証: 不一致が見つかりました。ローカル作業フォルダは削除しません。")
        for m in local_mismatches:
            print(f"      [ローカル] {m}")
        for m in gdrive_mismatches:
            print(f"      [GDrive] {m}")
        sys.exit("検証に失敗したため中止しました。")

    print("[3/4] 検証: すべて一致しました。")

    # ── ローカル作業フォルダ削除 ──
    if args.keep_local:
        print("[4/4] --keep-local のため削除をスキップしました。")
    else:
        freed = sum(size for _, size in src_files)
        shutil.rmtree(output_dir)
        for log in output_dir.parent.glob(f"{output_dir.name}*.log"):
            log.unlink()
        print(f"[4/4] ローカル作業フォルダを削除しました（{freed / 1e6:.0f}MB解放）: {output_dir}")

    print("\n完了！")
    print(f"  ローカル完成品: {local_dest}（クリップ{len(clips)}本）")
    print(f"  Google Driveバックアップ: {gdrive_dest}（{total_size / 1e6:.0f}MB）")


if __name__ == "__main__":
    main()
