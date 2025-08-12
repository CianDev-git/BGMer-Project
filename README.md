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
ブラウザが開かない場合は手動で http://127.0.0.1:7860/ を開いてください

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
ブラウザが開かない場合は手動で http://127.0.0.1:7860/ を開いてください


