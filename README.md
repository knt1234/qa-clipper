# QA Clipper 🎬

質問会・勉強会・インタビュー動画から、**1問1答形式の切り抜き動画を自動生成**するツールです。  
YouTubeのURLかローカルの動画ファイルを指定するだけで、Q&Aごとに分割されたMP4が出来上がります。

---

## 必要なもの

- Mac（M1/M2/M3/Intel どれでも可）
- インターネット接続
- [Anthropic](https://console.anthropic.com/) のAPIキー（Claude AI）

---

## セットアップ（初回のみ・30分程度）

### ステップ 1：このファイルをダウンロードする

1. このページ右上の緑色の「**Code**」ボタンをクリック
2. 「**Download ZIP**」をクリック
3. ダウンロードされたZIPファイルをダブルクリックして解凍
4. 解凍されたフォルダ（`qa-clipper-main`）を**デスクトップ**に移動

---

### ステップ 2：Homebrewをインストールする

Homebrew は Mac 用のソフトウェア管理ツールです。

1. Mac の **Spotlight**（画面右上の🔍マーク）を開く
2. 「**Terminal**」と入力してEnter
3. 以下のコマンドをターミナルに貼り付けてEnterを押す

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

4. パスワードを聞かれたら **Mac のログインパスワード** を入力（入力中は画面に何も表示されないが正常）
5. 途中で `Press RETURN/ENTER to continue` と表示されたら **Enterキー** を押す
6. 完了まで数分待つ

> ✅ `Installation successful!` と表示されれば完了

---

### ステップ 3：ffmpegをインストールする

ffmpeg は動画を編集するためのツールです。

1. ターミナルに以下を貼り付けてEnterを押す

```
brew install ffmpeg
```

2. 完了まで数分待つ

> ✅ エラーなく終わればOK

---

### ステップ 4：Python ライブラリをインストールする

1. ターミナルに以下を貼り付けてEnterを押す

```
pip3 install openai-whisper anthropic ffmpeg-python torch tqdm
```

2. 完了まで数分待つ（Whisperのダウンロードで時間がかかる場合あり）

> ✅ `Successfully installed` と表示されれば完了

---

### ステップ 5：APIキーを設定する

Claude AI を使うための鍵（APIキー）を設定します。

1. [Anthropic Console](https://console.anthropic.com/settings/keys) を開く
2. 「**Create Key**」をクリックしてAPIキーを作成
3. 表示された `sk-ant-...` から始まる文字列をコピー
4. ターミナルに以下を貼り付け、`ここにキーを貼る` の部分だけ置き換えてEnterを押す

```
echo 'export ANTHROPIC_API_KEY="ここにキーを貼る"' >> ~/.zshenv
```

5. ターミナルを一度閉じて、また開く

> ⚠️ APIキーは絶対に他人に見せないでください。チャットやSNSに貼り付けないよう注意してください。漏洩した場合はすぐに [Anthropic Console](https://console.anthropic.com/settings/keys) でキーを無効化して再発行してください。

---

## 使い方

### YouTube動画をQ&A形式に切り抜く

1. ターミナルを開く
2. 以下のコマンドの `YouTubeのURL` 部分を実際のURLに変えて実行

```
python3 ~/Desktop/qa-clipper-main/main.py "YouTubeのURL" --mode qa --output ~/Desktop/output
```

**例：**
```
python3 ~/Desktop/qa-clipper-main/main.py "https://youtu.be/abcd1234" --mode qa --output ~/Desktop/output
```

---

### ローカルの動画ファイルをQ&A形式に切り抜く

```
python3 ~/Desktop/qa-clipper-main/main.py --skip-dl --video "動画ファイルのパス" --mode qa --output ~/Desktop/output
```

**ヒント：** 動画ファイルをターミナルにドラッグ＆ドロップするとパスが自動入力されます

---

### 限定公開のYouTube動画を処理したい場合

Chrome でその動画にログインした状態で以下を実行してください：

```
python3 ~/Desktop/qa-clipper-main/main.py "YouTubeのURL" --mode qa --cookies-from-browser chrome
```

---

### 2回目以降は高速で実行できる

文字起こし（一番時間がかかる処理）は `transcript.json` として保存されます。  
同じ動画を再処理する場合はこのファイルを再利用できるので、数秒〜1分以内で完了します。

```
python3 ~/Desktop/qa-clipper-main/main.py \
  --skip-dl \
  --video "動画ファイルのパス" \
  --transcript ~/Desktop/output/transcript.json \
  --mode qa
```

---

### 処理の流れ

実行すると以下の順番で自動処理されます：

```
[1/4] 動画をダウンロード中...        （数十秒）
[2/4] 文字起こし中...                （10分動画で10〜20分）※初回のみ時間がかかる
[3/4] Claude AI でQ&A境界を検出中... （1分以内）
[4/4] Q&Aクリップを生成中...          （数十秒）

完了！
```

---

### 出力ファイル

処理が完了すると `~/Desktop/output/qa/` フォルダにクリップが保存されます：

```
output/
├── transcript.json        ← 文字起こし結果（再利用可）
├── analysis.json          ← Q&A検出結果（再利用可）
└── qa/
    ├── 001_質問タイトル.mp4
    ├── 002_質問タイトル.mp4
    └── ...
```

> 各クリップは**前後3秒の余白付き**で生成されます。  
> 短すぎるより長めの方が後から修正できるため、意図的に余白を長めに設定しています。  
> 長さの微調整は **YouTube Studio のトリミング機能** で行えます。

---

## 費用の目安

### 基本的な費用

| 項目 | 費用 | 備考 |
|---|---|---|
| 文字起こし（Whisper） | **無料** | 自分のPCで処理するため無料 |
| Q&A検出（Claude Haiku） | **約13〜30円 / 10分動画** | Anthropic APIの従量課金 |
| 動画編集（ffmpeg） | **無料** | |
| **合計** | **約13〜30円 / 10分動画** | |

> クリップが何本になっても費用は変わりません。Claude APIの呼び出しは1回だけです。

---

### AIモデルによる費用・精度の違い

このツールは2種類のAIモデルを選択できます：

| モデル | 10分動画の費用 | Q&A検出数の目安 | おすすめ用途 |
|---|---|---|---|
| **Haiku**（デフォルト） | 約13〜30円 | やや少なめ | まず試したいとき |
| **Sonnet** | 約50〜100円 | 多め・細かい | 精度を上げたいとき |

Sonnetに変更する場合はコマンドに `--ai-model claude-sonnet-4-5` を追加してください：

```
python3 ~/Desktop/qa-clipper-main/main.py "YouTubeのURL" --mode qa --ai-model claude-sonnet-4-5
```

---

### 動画の長さと費用の目安

| 動画の長さ | Haiku | Sonnet |
|---|---|---|
| 10分 | 約13〜30円 | 約50〜100円 |
| 30分 | 約40〜90円 | 約150〜300円 |
| 1時間 | 約80〜180円 | 約300〜600円 |

---

## 処理時間の目安

| 動画の長さ | 文字起こし（初回） | Q&A検出 | クリップ生成 |
|---|---|---|---|
| 10分 | 10〜20分 | 1分以内 | 数十秒 |
| 30分 | 30〜60分 | 1分以内 | 1〜2分 |
| 1時間 | 60〜120分 | 1〜2分 | 2〜3分 |

> 文字起こしはGPUがあると大幅に高速化されますが、MacのCPUでも動作します。  
> **2回目以降は `transcript.json` を再利用するため、数秒〜1分以内で完了します。**

---

## 容量の上限

容量の上限はありません。Macのストレージ空き容量の範囲内で処理できます。  
ただし実用的には **1〜2時間の動画まで** が快適に使える範囲です（文字起こしに時間がかかるため）。

---

## よくある質問

**Q. 初回の文字起こしがとても遅い**  
A. Whisperのモデルファイル（約3GB）を初回のみダウンロードします。2回目以降は保存済みのファイルを使うため速くなります。

**Q. クリップの前後が少し長い**  
A. YouTube Studio のトリミング機能で調整してください。短すぎると修正できないため、意図的に前後3秒の余白を設けています。

**Q. APIキーを間違えてチャットやSNSに貼ってしまった**  
A. すぐに [Anthropic Console](https://console.anthropic.com/settings/keys) でそのキーを「Revoke（無効化）」して、新しいキーを発行してください。

**Q. 「Q&Aではない動画」でも使える？**  
A. Q&A形式でない動画では検出精度が下がります。講演・インタビュー・勉強会など、質問と回答が明確に分かれている動画に向いています。

**Q. Windowsでは使えない？**  
A. 現在はMac専用です。Windowsには対応していません。

---

## 動作環境

- macOS 12以上
- Python 3.9以上
- インターネット接続
