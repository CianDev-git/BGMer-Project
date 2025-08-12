import os, sys, time, threading, secrets, webbrowser, socket, inspect
from pathlib import Path
import gradio as gr

APP_NAME = "BGMer"

# ===== 共通の環境変数 =====
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
if sys.platform == "darwin":
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# ローカルUIにプロキシを噛ませない（全OS共通）
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
os.environ["GRADIO_LAUNCH_BROWSER"] = "0"

# app.py の import 群の下で追加
from pathlib import Path
import shutil

def _prepend_to_path(p: Path):
    os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")

def _ensure_ffmpeg():
    """
    ffmpeg/ffprobe が PATH に無ければ、プロジェクト内の候補パスを探して PATH へ追加。
    それでも無ければ Gradio の UI エラーで案内する。
    - Windows: ./bin/ffmpeg/bin に ffmpeg.exe / ffprobe.exe を置けば動く
    - mac/Linux: ./bin に ffmpeg / ffprobe を置けば動く
    """
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return

    # プロジェクト内の候補を探す
    here = Path(__file__).resolve().parent
    candidates = []
    if os.name == "nt":
        candidates += [
            here / "bin" / "ffmpeg" / "bin",   # 推奨配置
            here / "bin",                      # 予備
        ]
    else:
        candidates += [
            here / "bin",                      # mac/Linux はここに実行ファイルを置けばOK
        ]

    for c in candidates:
        if c.is_dir():
            _prepend_to_path(c)

    # もう一度探す
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not (ffmpeg and ffprobe):
        raise gr.Error(
            "ffmpeg/ffprobe が見つかりません。\n"
            "Windows: ffmpeg フルビルドを導入して PATH を通すか、プロジェクトの bin\\ffmpeg\\bin に ffmpeg.exe / ffprobe.exe を置いてください。\n"
            "mac: `brew install ffmpeg` で導入するか、プロジェクトの bin に配置してください。"
        )


# ======== 互換パッチ（古い gradio_client / schema=bool 対策）========
def _patch_gradio_schema_parsing():
    # 1) client 側の変換を安全化
    try:
        import gradio_client.utils as _gc  # type: ignore
        _orig_json = getattr(_gc, "json_schema_to_python_type", None)
        if callable(_orig_json):
            def _safe_json(schema, defs=None):
                try:
                    if isinstance(schema, bool):
                        return "Any"
                    return _orig_json(schema, defs) if defs is not None else _orig_json(schema)
                except Exception:
                    return "Any"
            _gc.json_schema_to_python_type = _safe_json  # type: ignore
    except Exception:
        pass

    # 2) Blocks.get_api_info 自体を安全化（最終バリア）
    try:
        from gradio.blocks import Blocks  # type: ignore
        _orig_get_api_info = Blocks.get_api_info
        def _safe_get_api_info(self, *a, **kw):
            try:
                return _orig_get_api_info(self, *a, **kw)
            except Exception as e:
                print("[gradio] get_api_info() suppressed:", e)
                return {}  # ここで空を返せばフロントは動く
        Blocks.get_api_info = _safe_get_api_info  # type: ignore
    except Exception:
        pass

_patch_gradio_schema_parsing()
# ================================================================

# ===== ユーザーデータ/出力先 =====
def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base

DATA_DIR = _user_data_dir()
OUTPUT_DIR = DATA_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 遅延 import（起動を軽くする） =====
def _lazy_imports():
    global sample_scene_change_frames, Captioner, build_prompt_from_captions, get_video_duration
    global MusicGenerator, GenerateConfig, fit_audio_exact_seconds, save_wav, mux_mix_audio_to_video
    from src.video2text import (
        sample_scene_change_frames, Captioner, build_prompt_from_captions, get_video_duration
    )
    from src.text2music import (
        MusicGenerator, GenerateConfig, fit_audio_exact_seconds, save_wav, mux_mix_audio_to_video
    )

# ===== グローバルモデル（初回アクセスで初期化） =====
CAP = None
GEN = None

def _warmup_models():
    """UI表示後にバックグラウンドでモデルを温める（失敗しても本処理で再トライ）"""
    global CAP, GEN
    try:
        _lazy_imports()
        if CAP is None:
            CAP = Captioner()
        if GEN is None:
            GEN = MusicGenerator()
    except Exception as e:
        print("[warmup] failed:", e)

# ===== UI =====
with gr.Blocks(css=".big-title{font-size:48px!important;font-weight:800;margin:6px 0;}") as demo:
    gr.Markdown("<div class='big-title'>BGMer</div>")
    with gr.Row():
        with gr.Column():
            video = gr.Video(label="Upload a video")
            level = gr.Slider(1, 5, value=2, step=1, label="Quality / Speed (1=Light, 5=Heavy)")
            temperature = gr.Slider(0.6, 1.6, value=1.0, step=0.05, label="Temperature")
            bgm_gain = gr.Slider(-24, 6, value=-4, step=1, label="BGM gain (dB)")
            edit_prompt = gr.Textbox(label="(Optional) Override prompt", lines=2)
            btn = gr.Button("Run pipeline")
        with gr.Column():
            audio_out = gr.Audio(label="Generated music", type="numpy")
            video_out = gr.Video(label="Video with original+bgm")

    def pipeline(video, level, temperature, edit_prompt, bgm_gain_db):
        _ensure_ffmpeg()
        global CAP, GEN

        # 1) 初回実行で確実に初期化
        if CAP is None or GEN is None:
            _lazy_imports()
            if CAP is None:
                CAP = Captioner()
            if GEN is None:
                GEN = MusicGenerator()

        # 2) 動画パス正規化（gr.Video は dict になることがある）
        if isinstance(video, dict):
            video = video.get("name") or video.get("path") or video.get("video") or video
        if not (isinstance(video, str) and os.path.exists(video)):
            raise gr.Error("動画ファイルを読み込めませんでした。もう一度アップロードしてください。")

        # 3) 推論
        seconds = max(4, min(120, int(round(get_video_duration(video)))))
        presets = {
            1: {"max_frames": 6,  "tokens_per_sec": 32, "guidance": 1.8, "top_k": 120},
            2: {"max_frames": 8,  "tokens_per_sec": 36, "guidance": 2.0, "top_k": 160},
            3: {"max_frames": 10, "tokens_per_sec": 40, "guidance": 2.2, "top_k": 200},
            4: {"max_frames": 12, "tokens_per_sec": 46, "guidance": 2.6, "top_k": 240},
            5: {"max_frames": 16, "tokens_per_sec": 50, "guidance": 3.0, "top_k": 280},
        }
        p = presets[int(level)]

        frames = sample_scene_change_frames(video, scene_thresh=0.35, max_frames=p["max_frames"])
        captions = CAP.caption_images(frames)
        auto_prompt = build_prompt_from_captions(captions)
        final_prompt = (edit_prompt or "").strip() or auto_prompt

        cfg = GenerateConfig(
            seconds=seconds,
            temperature=float(temperature),
            guidance_scale=float(p["guidance"]),
            top_k=int(p["top_k"]),
            tokens_per_sec=int(p["tokens_per_sec"]),
            seed=secrets.randbits(31),
        )
        sr, audio = GEN.generate(final_prompt, cfg)

        # ★ 順序: (audio, target_seconds, sr)
        audio = fit_audio_exact_seconds(audio, seconds, sr)

        wav_path = str(OUTPUT_DIR / "bgm.wav")
        save_wav(wav_path, sr, audio)
        try:
            out_mp4 = mux_mix_audio_to_video(
                video, wav_path, str(OUTPUT_DIR / "video_with_bgm.mp4"),
                bgm_gain_db=float(bgm_gain_db)
            )
        except FileNotFoundError as e:
            # ffmpeg 不在など
            raise gr.Error("ffmpeg が見つかりません。インストールし、PATH を通してください。") from e
        return (sr, audio), out_mp4

    # Gradio バージョン差分への耐性（古い環境だと concurrency_limit が無い）
    try:
        btn.click(
            pipeline,
            [video, level, temperature, edit_prompt, bgm_gain],
            [audio_out, video_out],
            concurrency_limit=1,
        )
    except TypeError:
        btn.click(
            pipeline,
            [video, level, temperature, edit_prompt, bgm_gain],
            [audio_out, video_out],
        )

# ===== 起動ユーティリティ =====
def find_free_port(start=7860, tries=30) -> int:
    for p in range(start, start + tries):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start

def _open_browser_when_ready(host: str, port: int, timeout: float = 25.0):
    """サーバが立ったら既定ブラウザを開く（Gradioの inbrowser が失敗する環境の保険）"""
    deadline = time.time() + timeout
    url = f"http://{host}:{port}/"
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                if os.name == "nt":
                    # Windows専用：既定ブラウザで開く（mac/Linuxでは使わない）
                    try:
                        os.startfile(url)  # type: ignore[attr-defined]
                        return True
                    except Exception:
                        pass
                webbrowser.open(url)
                return True
        except OSError:
            time.sleep(0.4)
    return False

def _safe_launch(demo: gr.Blocks, host: str, port: int):
    """
    - allowed_paths / show_api が使えるGradioなら付与、ダメなら自動で外す
    - localhost にアクセスできない環境では share=True に自動切替
    - Windows専用のAPIは Windows のときだけ使用
    """
    params = dict(server_name=host, server_port=port, inbrowser=False, show_error=True, share=False)

    # バージョン差に応じて動的に引数を付ける
    sig = inspect.signature(demo.launch)
    if "allowed_paths" in sig.parameters:
        params["allowed_paths"] = [str(OUTPUT_DIR)]
    if "show_api" in sig.parameters:
        params["show_api"] = False  # API情報生成を抑止（古い組合せの ISE 対策）

    # ブラウザのフォールバック起動
    threading.Thread(target=_open_browser_when_ready, args=(host, port), daemon=True).start()

    # 1st try
    try:
        demo.launch(**params)
        return
    except TypeError:
        # 未対応引数を削除して再トライ
        params.pop("allowed_paths", None)
        params.pop("show_api", None)
        demo.launch(**params)
        return
    except ValueError as e:
        msg = str(e)
        # localhost 不可 → 代替ホストで再トライ
        if "localhost is not accessible" in msg or "check your proxy" in msg:
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                os.environ.pop(k, None)
            try:
                alt_host = "localhost"
                threading.Thread(target=_open_browser_when_ready, args=(alt_host, port), daemon=True).start()
                params.update(server_name=alt_host, share=False)
                demo.launch(**params)
                return
            except Exception:
                pass
            # それでもダメなら共有URL
            params.update(server_name="0.0.0.0", share=True)
            params.pop("allowed_paths", None)
            params.pop("show_api", None)
            try:
                demo.launch(**params)
                return
            except Exception as e2:
                print("[gradio] share=True also failed:", e2)
                # 最後はローカルに戻してそのまま例外
        raise

def main():
    # UIを出してからモデルを温める（体感を軽く）
    threading.Thread(target=_warmup_models, daemon=True).start()

    # ポート固定の希望があれば環境変数で上書き
    base_port = int(os.environ.get("GRADIO_SERVER_PORT", "7860"))
    port = find_free_port(start=base_port, tries=30)

    host = "127.0.0.1"
    url = f"http://{host}:{port}/"
    print(f"[BGMer] Launching UI at {url}", flush=True)

    # ブロッキング起動（=プロセスは待機し続ける）
    demo.queue(default_concurrency_limit=1, max_size=8, status_update_rate=2.5)
    _safe_launch(demo, host, port)

if __name__ == "__main__":
    main()
