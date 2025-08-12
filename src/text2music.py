import os
import shutil
import subprocess
import numpy as np
import torch
import wave
from typing import Optional, Tuple
from dataclasses import dataclass
from transformers import AutoProcessor, MusicgenForConditionalGeneration

SAMPLE_RATE = 32000

@dataclass
class GenerateConfig:
    seconds: int = 10
    guidance_scale: float = 3.0
    temperature: float = 1.0
    top_k: int = 250
    seed: Optional[int] = 42
    tokens_per_sec: int = 50

try:
    import imageio_ffmpeg
    IIO_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    IIO_FFMPEG = None

class MusicGenerator:
    def __init__(self, model_id: str = os.getenv("MODEL_ID", "facebook/musicgen-small")):
        if os.getenv("USE_CPU") == "1":
            self.device, self.dtype = "cpu", torch.float32
        elif torch.cuda.is_available():
            self.device, self.dtype = "cuda", torch.float16
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            self.device, self.dtype = "mps", torch.float32
        else:
            self.device, self.dtype = "cpu", torch.float32
        print(f"[MusicGen] device={self.device}, dtype={self.dtype}")

        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            model_id, torch_dtype=self.dtype, low_cpu_mem_usage=True
        ).to(self.device)

    def _seconds_to_tokens(self, seconds: int, tokens_per_sec: int) -> int:
        return max(1, int(seconds * tokens_per_sec))  # ← 固定50を廃止

    def generate(self, prompt: str, cfg: Optional[GenerateConfig] = None) -> Tuple[int, np.ndarray]:
        if cfg is None:
            cfg = GenerateConfig()
        if cfg.seed is not None:
            torch.manual_seed(int(cfg.seed)); np.random.seed(int(cfg.seed))
        inputs = self.processor(text=[prompt], padding=True, return_tensors="pt").to(self.device)
        computed = self._seconds_to_tokens(cfg.seconds, cfg.tokens_per_sec)
        max_new_tokens = max(64, min(2048, computed))
        with torch.no_grad():
            audio_values = self.model.generate(
                **inputs,
                do_sample=True,
                guidance_scale=float(cfg.guidance_scale),
                temperature=float(cfg.temperature),
                top_k=int(cfg.top_k),
                max_new_tokens=int(max_new_tokens),
            )
        audio = audio_values[0].detach().cpu().numpy()
        if audio.ndim == 2:
            audio = audio.mean(axis=0)
        audio = audio / (np.max(np.abs(audio)) + 1e-8)
        return SAMPLE_RATE, audio

def fit_audio_exact_seconds(audio: np.ndarray, sr: int, target_seconds: float) -> np.ndarray:
    target_len = int(round(target_seconds * sr))
    if len(audio) < target_len:
        reps = int(np.ceil(target_len / len(audio)))
        audio = np.tile(audio, reps)
    audio = audio[:target_len]
    fade = int(0.03 * sr)
    if fade > 0 and len(audio) > 2 * fade:
        audio[:fade] *= np.linspace(0, 1, fade)
        audio[-fade:] *= np.linspace(1, 0, fade)
    return audio

def save_wav(path: str, rate: int, audio: np.ndarray) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # [-1,1] にクリップして 16-bit PCM へ
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)      # モノラル（stereoなら2に）
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(rate)   # 例: 32000
        wf.writeframes(pcm16.tobytes())
    return path

def _has_audio_stream(video_path: str, ffbin: str) -> bool:
    # ffprobeで音声ストリームの有無を確認
    ffprobe = ffbin.replace("ffmpeg", "ffprobe")  # imageio-ffmpeg なら同じフォルダにある
    if not shutil.which(ffprobe):
        # ffprobe が無い場合は保守的に True 扱い（後段で失敗しないように）
        return True
    p = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", video_path],
        capture_output=True, text=True
    )
    return bool(p.stdout.strip())

def mux_mix_audio_to_video(video_path: str, wav_path: str, out_path: str,
                           bgm_gain_db: float = -3.0) -> str:
    ffbin = shutil.which("ffmpeg") or IIO_FFMPEG
    if not ffbin:
        raise RuntimeError("ffmpeg が見つかりません。")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    if _has_audio_stream(video_path, ffbin):
        # ① 元音声あり → amix で合成
        fc = (
            f"[0:a:0]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a0];"
            f"[1:a:0]volume={bgm_gain_db}dB,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a1];"
            f"[a0][a1]amix=inputs=2:dropout_transition=0:normalize=0,aresample=48000[am]"
        )
        cmd = [
            ffbin, "-y",
            "-i", video_path,
            "-i", wav_path,
            "-map", "0:v:0",
            "-map", "[am]",
            "-filter_complex", fc,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            "-shortest",
            out_path,
        ]
    else:
        # ② 元音声なし → BGMのみを付与（最初からこっちにする）
        cmd = [
            ffbin, "-y",
            "-i", video_path,
            "-i", wav_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-filter:a:0", f"volume={bgm_gain_db}dB",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            "-shortest",
            out_path,
        ]

    subprocess.run(cmd, check=True)
    return out_path
