# BGMer

短い動画を解析してテキスト要約（キャプション）を作り、その内容に合う **BGM を自動生成して合成**するローカルアプリです。

- 画像キャプション: **BLIP**
- 音楽生成: **MusicGen**
- UI: **Gradio**
- フレーム抽出: **ffmpeg**

> 動作確認: **Windows 11 / macOS (Apple Silicon)**

> 入力は **最大120秒**（マシン性能により処理時間が変動）ですが、 **60秒以内** を推奨します。

---

## 必要条件

- **Python 3.11+**
- **ffmpeg / ffprobe**
- 入れ方
  - Windows: `winget install -e --id Gyan.FFmpeg`
  - macOS:   `brew install ffmpeg`

---

## クイックスタート

### Windows（PowerShellにコピーして実行）

```powershell
$ErrorActionPreference = 'Stop'

$ids = @('Git.Git','GitHub.cli','Python.Python.3.11','Gyan.FFmpeg')
foreach ($id in $ids) {
  try {
    winget install -e --id $id --accept-source-agreements --accept-package-agreements --source winget | Out-Null
  } catch { Write-Host "[i] $id は既に入っているか、スキップしました。" }
}

try { gh auth status | Out-Null } catch { gh auth login --hostname github.com --web }

$Repo   = 'CianDev-git/BGMer-Project'
$Target = Join-Path $env:USERPROFILE 'BGMer-Project'
if (-not (Test-Path $Target)) { gh repo clone $Repo $Target }
Set-Location $Target

.\Run-BGMer-win.bat --console
```
> 実行するには数分時間を要する場合があります

> ブラウザが開かない場合は手動で http://127.0.0.1:7860/ を開いてください

### MacOS（ターミナルにコピーして実行）
```set -e
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew が見つかりません。https://brew.sh/ を参照してインストールしてください。"; exit 1
fi
brew install git gh python@3.11 ffmpeg
gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --web
cd ~
[ -d BGMer-Project ] || gh repo clone CianDev-git/BGMer-Project
cd BGMer-Project
chmod +x "Run BGMer(mac).sh"
./Run\ BGMer\(mac\).sh
```
> 実行するには数分時間を要する場合があります。

> ブラウザが開かない場合は手動で http://127.0.0.1:7860/ を開いてください。

### 使い方

1. **BGM をつけたい動画ファイルをアップロード**（最大 120 秒）
2. **スライダーで設定**
   - **Quality / Speed**：処理の重さと品質を調整（**1**=軽い/速い、**5**=重い/高品質）
   - **Temperature**：生成のランダムさ（**低い**=安定、**高い**=多彩・予想外）
   - **BGM Gain (dB)**：合成する BGM の音量
3. **「Run pipeline」** をクリック（実行には3分以上かかる場合があります）

## 終了方法

> **注意**：ブラウザのタブを閉じてもサーバーは終了しません。
> 無操作が **10分** 続くと自動停止します。

### MacOS
- 実行中の **ターミナル** で **Control + C（⌃C）**
- またはターミナルウィンドウを閉じる（プロセスも終了します）
- （強制終了が必要なとき）
  ```bash
  # ポート 7860 のプロセスを終了
  lsof -ti :7860 | xargs kill
  # 落ちない場合
  lsof -ti :7860 | xargs kill -9
  ```

### Windows
- 実行中の **PowerShell/コマンドプロンプト** で **CTRL+BREAK+C**
- またはPowerShell/コマンドプロンプトのウィンドウを閉じる（プロセスも終了します）
- （強制終了が必要なとき）
  ```Get-NetTCPConnection -LocalPort 7860 -State Listen |
  Select-Object -Expand OwningProcess |
  ForEach-Object { Stop-Process -Id $_ -Force }
  ```
