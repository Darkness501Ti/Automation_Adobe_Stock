# LTX-2.3 Video Pipeline for Adobe Stock — Design Spec

Date: 2026-07-06
Status: Approved by user (amendments: prompt file = `prompt_video.json`; first real batch = 2 clips)

## Goal

Extend the existing Adobe Stock image pipeline (Z-Image → JPG + CSV) to **AI-generated stock video**: T2V abstract-tech **motion backgrounds** (our proven category 8 niche, in video form), generated locally with **LTX-2.3 22B fp8** in ComfyUI, encoded to Adobe-compliant MP4, with the same metadata-CSV upload flow.

## Verified constraints (Adobe Stock, June 2026 docs)

- AI video is accepted; tick **"Created using generative AI tools"** on upload.
- **Resolution ≥ 1920×1080** (also 2K/UHD/4K; vertical 1080×1920 allowed).
- **Duration 5–60 s**, file ≤ 3.9 GB, MP4/MOV, **H.264** (or ProRes), fps ∈ {23.98, 24, 25, 29.97, 30, 50, 59.94, 60}.
- Refused if: **limited motion / near-still**, text overlays, transitions, shake/flicker, IP/brands.
- Same prohibited-prompt rules as images (no artists, real people, IP, agencies, newsworthy events).

## Hardware

RTX 5070 Ti 16 GB VRAM (Blackwell, good FP8), 32 GB RAM, Windows 11. ComfyUI portable at `C:\DD501_Sanbox\ComfyUI_windows_portable\`, server on `127.0.0.1:8188`.

## Architecture

Mirror of the image pipeline:

```
prompt_video.json ──> Generate_LTXVideo.bat ──> script/main_ltxvideo.py
                                                   │ ComfyUI API (127.0.0.1:8188)
                                                   │ LTX-2.3 22B fp8 + distilled LoRA
                                                   │ + ×2 latent spatial upscaler
                                                   ▼
                              raw frames/video ──> ffmpeg: H.264 MP4, yuv420p,
                                                   high bitrate, AUDIO STRIPPED (-an)
                                                   ▼
                                                   ffprobe spec-check gate
                                                   ▼
                              output/DDMMYYYY_RunN_video/  (MP4s + AdobeStock_Metadata.csv)
```

### Components

1. **`script/main_ltxvideo.py`** — sibling of `main_zimage.py`. Reads `prompt_video.json` (same schema: name/title/keywords/category/positive/negative), posts the LTX-2.3 T2V workflow in API format per entry, polls, retrieves output, runs ffmpeg encode + ffprobe verify, writes CSV. CONFIG block at top: WIDTH=1920, HEIGHT=1080, FPS=24, DURATION_S≈10 (frame count per LTX frame rules, ~241), steps/cfg per LTX-2.3 defaults with distilled LoRA, plus a commented 4K switch (3840×2160) to enable only after speed is proven.
2. **`Generate_LTXVideo.bat`** — mirror of `Generate_ZImage.bat`, runs the script.
3. **`prompt_video.json`** — video batch file, same schema as `prompt.json`. Video prompt-craft rules apply (below).
4. **Models** (into `C:\DD501_Sanbox\ComfyUI_windows_portable\ComfyUI\models\`):
   - `checkpoints/ltx-2.3-22b-dev-fp8.safetensors` — https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-dev-fp8.safetensors
   - `loras/ltx-2.3-22b-distilled-lora-384.safetensors` — https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors
   - `latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.0.safetensors` — https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.0.safetensors
   - `text_encoders/gemma_3_12B_it_fp4_mixed.safetensors` — https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors
   - Base workflow: official ComfyUI LTX-2.3 template (docs: https://docs.comfy.org/tutorials/video/ltx/ltx-2-3). Check disk space before download (~35 GB).

## Feasibility gate (must pass before batch runner is trusted)

Render **one** test clip end-to-end. Record: minutes/clip, peak VRAM, RAM pressure, output quality.
- **Pass** → proceed to the 2-clip first batch.
- **Fail** (OOM, >20 min/clip, unusable quality) → fallback path is **Wan 2.2 14B fp8 + Lightning 4-step LoRA** at 720p + video upscale stage; same script architecture, swap the workflow JSON. Document the failure numbers first.

## Encoding & verification

- ffmpeg: H.264, `yuv420p`, CRF ~16–18 or ≥30 Mbps, `-an` (strip LTX audio — AI audio is a review liability; stock b-roll is expected silent), faststart.
- ffprobe gate on every output: width ≥1920, height ≥1080, fps in Adobe's allowed set, 5 s ≤ duration ≤ 60 s, codec h264, size ≤ 3.9 GB. A clip failing spec is quarantined and never enters the CSV.
- CSV identical format to image pipeline (utf-8-sig, matched by Filename).

## Video prompt-craft rules (delta from image rules)

- LTX wants **long, descriptive natural-language prompts** — describe the scene AND the motion explicitly (drift, flow, ripple, pulse, slow camera push-in). Adobe refuses limited-motion clips, so every prompt must specify continuous visible motion.
- Same 3-layer anti-text defense (hard negative list; positive end-clause "no text, no watermark, no logos"; describe visuals, never name concepts).
- No transitions, no overlays, no flicker/strobe; smooth stable motion only.
- Variation across batch: palette / motion type / direction / speed.
- Keywords: buyer-intent video terms front-loaded — `motion background`, `abstract background`, `animation`, `video background`, `backdrop`, `technology`, `copy space`, `looping` only if visually near-seamless. No technique words.

## First batch (2 clips, category 8)

1. **`particle_wave_blue`** — slow-flowing waves of glowing blue-teal particles streaming left to right across a deep navy void, lower third empty for copy space, gentle continuous undulating motion, soft depth-of-field glow, static camera. Title/keywords per SEO rules (motion background, abstract technology…).
2. **`network_violet_drift`** — dark violet-magenta gradient backdrop with a delicate luminous network of thin light filaments slowly drifting and gently pulsing on the right half, left half clean for copy space, continuous slow motion, static camera. Distinct palette + motion from clip 1.

Exact positive/negative/title/keyword sets to be authored in `prompt_video.json` following CLAUDE.md SEO rules (15–25 keywords, first 7–10 weighted, 5 keyword types).

## Compliance

- Flag "Created using generative AI tools" on every upload. No people in batch 1 → no release, fictional box unchecked.
- Honest titles/keywords; no `4K` keyword on 1080p clips.

## Success criteria

1. Feasibility numbers recorded (min/clip, VRAM).
2. Two MP4s in `output/…_video/` passing the ffprobe gate + valid CSV.
3. Clips show continuous obvious motion (limited-motion reject risk addressed).
4. User uploads, reports acceptance/sales → feeds the normal working loop.

## Out of scope (this iteration)

I2V from existing stills; 4K default; vertical 9:16; audio tracks; Wan fallback build-out (only if gate fails); multi-site distribution.
