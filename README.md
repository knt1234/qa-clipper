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

> ⚠️ APIキーは他人に見せないでください

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

### 処理の流れ

実行すると以下の順番で自動処理されます：

```
[1/4] 動画をダウンロード中...      （数十秒）
[2/4] 文字起こし中...              （10分動画で10〜20分）
[3/4] Claude AI でQ&A境界を検出中... （1分以内）
[4/4] Q&Aクリップを生成中...        （数十秒）

完了！
```

---

### 出力ファイル

処理が完了すると `~/Desktop/output/qa/` フォルダにクリップが保存されます：

```
output/
└── qa/
    ├── 001_質問タイトル.mp4
    ├── 002_質問タイトル.mp4
    └── ...
```

> 各クリップは前後3秒の余白付きで生成されます。  
> 長さの微調整は **YouTube Studio のトリミング機能** で行えます。

---

## 費用の目安

| 項目 | 費用 |
|---|---|
| 文字起こし（Whisper） | **無料**（自分のPCで処理） |
| Q&A検出（Claude Haiku） | **約13〜30円 / 10分動画** |
| 動画編集（ffmpeg） | **無料** |

---

## よくある質問

**Q. 初回の文字起こしがとても遅い**  
A. Whisperのモデルファイル（約3GB）を初回のみダウンロードします。2回目以降は速くなります。

**Q. 限定公開のYouTube動画を処理したい**  
A. Chromeでその動画にログインした状態で以下を実行してください：
```
python3 ~/Desktop/qa-clipper-main/main.py "YouTubeのURL" --mode qa --cookies-from-browser chrome
```

**Q. クリップの前後が少し長い**  
A. YouTube Studio のトリミング機能で調整してください。短いよりも長い方が後から修正できるため、意図的に余白を長めに設定しています。

---

## 動作環境

- macOS 12以上
- Python 3.9以上
- インターネット接続
