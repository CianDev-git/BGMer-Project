import argparse
from src.video2text import sample_frames, Captioner, build_prompt_from_captions

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--every", type=float, default=0.5, help="seconds between frames")
    ap.add_argument("--max_frames", type=int, default=12)
    ap.add_argument("--out", default="prompt.txt")
    args = ap.parse_args()

    frames = sample_frames(args.video, every_seconds=args.every, max_frames=args.max_frames)
    cap = Captioner()
    captions = cap.caption_images(frames)
    prompt = build_prompt_from_captions(captions)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(prompt + "\n")
    print("Captions:")
    for c in captions:
        print("-", c)
    print("\nPrompt:", prompt)

if __name__ == "__main__":
    main()
