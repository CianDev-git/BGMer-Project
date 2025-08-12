import os
from dataclasses import dataclass
from typing import List
from PIL import Image
from tqdm import tqdm
from transformers import BlipForConditionalGeneration, BlipProcessor
import imageio.v2 as imageio
import torch
import subprocess, tempfile, glob, os


def sample_frames(video_path: str, every_seconds: float = 0.5, max_frames: int = 16) -> List[Image.Image]:
    """FFmpeg backend via imageioでフレーム間引き取得（moviepy依存なし）"""
    reader = imageio.get_reader(video_path, format="ffmpeg")
    meta = reader.get_meta_data()
    fps = float(meta.get("fps", 30.0))
    step = max(1, int(round(every_seconds * fps)))
    frames: List[Image.Image] = []
    for i, frame in enumerate(reader):
        if i % step == 0:
            frames.append(Image.fromarray(frame))
            if len(frames) >= max_frames:
                break
    reader.close()
    return frames

@dataclass
class Captioner:
    model_id: str = os.getenv("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")

    def __post_init__(self):
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        self.processor = BlipProcessor.from_pretrained(self.model_id)
        self.model = BlipForConditionalGeneration.from_pretrained(self.model_id).to(self.device)

    def caption_images(self, images: List[Image.Image]) -> List[str]:
        caps = []
        for img in tqdm(images, desc="Captioning"):
            inputs = self.processor(images=img, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            out = self.model.generate(
                **inputs,
                max_new_tokens=30,
                do_sample=True,
                top_p=0.9,
                temperature=0.9,
                repetition_penalty=1.1
            )
            text = self.processor.decode(out[0], skip_special_tokens=True)
            caps.append(text)
        return caps
    
def get_video_duration(video_path: str) -> float:
    reader = imageio.get_reader(video_path, format="ffmpeg")
    meta = reader.get_meta_data()
    reader.close()
    return float(meta.get("duration", 0.0))

def build_prompt_from_captions(captions: List[str]) -> str:
    if not captions:
        return ("modern electronic with rich harmony and catchy lead melody, "
                "chord progression, pads and bassline, light percussion, 10-12 seconds")

    seen = set(); uniq = []
    for c in captions:
        c = c.strip().lower()
        if c and c not in seen:
            uniq.append(c); seen.add(c)

    # キーワードでざっくりムード推定
    scene = "; ".join(uniq[:8])
    fast_kw = ("run","jump","fast","speed","dance","car","sport","action","climb")
    dark_kw = ("night","dark","storm","rain","shadow","alley","underground")
    is_fast = (len(uniq) >= 6) or any(k in scene for k in fast_kw)
    is_dark = any(k in scene for k in dark_kw)

    tempo = "fast" if is_fast else "mid-tempo"
    mood  = "dark" if is_dark else "bright"

    # ドラム一色を避ける文言を明示
    instr = "catchy lead melody, evolving chord progression, warm pads, arpeggios, bassline, light percussion"
    return (f"{tempo}, {mood} modern track with {instr}, short hook and variation; "
            f"scene: {scene}; stereo, not drum-only")

def sample_scene_change_frames(video_path: str, scene_thresh: float = 0.35, max_frames: int = 12):
    """
    大きなシーン変化でフレーム抽出（似たフレームの連発を避ける）。
    ffmpegコマンドの引数は subprocess にリストで渡すので、クォートは入れない！
    """
    tmpdir = tempfile.mkdtemp(prefix="scenes_")
    out_pattern = os.path.join(tmpdir, "f_%04d.jpg")

    # フィルタ式は素の文字列でOK（シングルクォート不要）
    vf = f"select=gt(scene,{scene_thresh}),scale=640:-2"

    cmd = [
        "ffmpeg", "-y",
        "-analyzeduration", "5M", "-probesize", "10M",
        "-i", video_path,
        "-vf", vf,
        "-vsync", "vfr",
        out_pattern
    ]

    # 失敗時は通常サンプリングにフォールバック
    try:
        res = subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        # フォールバック（毎秒サンプリング）
        return sample_frames(video_path, every_seconds=0.6, max_frames=max_frames)

    files = sorted(glob.glob(out_pattern))[:max_frames]
    frames = [Image.open(f).convert("RGB") for f in files]
    if not frames:
        # シーン変化が少なすぎた場合もフォールバック
        return sample_frames(video_path, every_seconds=0.6, max_frames=max_frames)
    return frames[:max_frames]