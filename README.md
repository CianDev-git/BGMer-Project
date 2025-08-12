# BGMer

短い動画を解析してテキスト要約（キャプション）を作り、その内容に合う **BGM を自動生成して合成**するローカルアプリです。

- 画像キャプション: **BLIP**
- 音楽生成: **MusicGen**
- UI: **Gradio**
- フレーム抽出: **ffmpeg**

> 動作確認: **Windows 11 / macOS (Apple Silicon)**  
> 入力**最大120秒**（マシン性能により処理時間が変動します）ですが、**60秒以内**推奨です。

---

## 必要条件

- **Python 3.11+**
- **ffmpeg / ffprobe**（PATHに通っていること）
  - Windows: `winget install -e --id Gyan.FFmpeg`
  - macOS:   `brew install ffmpeg`
---

##

### Windows

１）Git を用意（初回のみ）
  コマンドプロンプトで以下を入力
   ```powershell
   winget install -e --id Git.Git'''
２）リポジトリ取得
  コマンドプロンプトで以下を入力
  ```git clone https://github.com/CianDev-git/BGMer-Project.git
  cd BGMer-Project```

