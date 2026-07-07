# LTX Seamless-Loop Video Mode — Design Spec (V1)

Date: 2026-07-07
Status: Approved by user (V1)
Parent spec: docs/superpowers/specs/2026-07-06-ltx-video-pipeline-design.md

## Goal

Add a **mathematically seamless loop mode** to the existing LTX-2.3 video pipeline
(`script/main_ltxvideo.py`). A loop clip's last frame flows back into its first frame with
no visible seam, honestly earning the high-traffic `seamless loop` / `looping` keywords on
Adobe Stock motion backgrounds (category 8, our proven niche).

## Decisions made during brainstorming

1. **Loop bar:** mathematically seamless (not crossfade/near-seamless).
2. **Technique:** first = last frame conditioning (approach A), palindrome encode as fallback.
3. **Anchor source:** LTX **self-anchor** (two-pass, text-only) — no Z-Image / image-pipeline
   coupling. One prompt file, no asset management; cost ≈ 1.5× a normal clip.

## Loop mechanism (core)

Two-pass self-anchor per loop clip:

1. **Pass 1 — anchor harvest.** Short, cheap T2V run of the same prompt (~33 frames instead
   of 241), solely to produce a high-quality opening frame. Decode frame 0, save as the
   anchor image.
2. **Pass 2 — loop generation.** Full 241-frame run with the anchor image conditioned at
   **frame index 0 and frame index 240** (LTX guide-conditioning nodes — the same machinery
   the official template's I2V branch uses; `LTXVCropGuides` already sits in our stage-2
   path, so guide latents are handled). The model generates continuous motion that returns
   to its start.
3. **Encode.** ffmpeg trims the duplicated final frame → exactly 240 frames = 10.000 s
   @ 24 fps; playback wraps seamlessly. All existing encode settings unchanged
   (H.264, yuv420p, CRF 17, `-an`, faststart, crop 1920×1080).

**Implementation-time verification (ComfyUI must be running):** query
`http://127.0.0.1:8188/object_info` and confirm the exact conditioning node available for
LTX-2.3 that accepts an arbitrary/last frame index (`LTXVAddGuide` or the template's
`LTXVImgToVideoInplace` family). The chosen node and its parameters get recorded in the
implementation plan.

Estimated cost: ~1.5× a normal clip (short pass 1 + full pass 2) ≈ **~7 min/clip** on the
RTX 5070 Ti. VRAM expected ≈ same peak as current (~15.7 GB) since passes run sequentially.

## Seam QA gate (protects the honest keyword)

After encode:

1. Extract first and last frames (ffmpeg).
2. Compute SSIM between them (ffmpeg ssim filter). Threshold: tuned at feasibility
   (start ≈ 0.95).
3. **Pass** → clip keeps `seamless loop, looping` keywords in the CSV.
4. **Fail** → clip is **still uploadable as a normal clip**: base keywords kept, loop terms
   stripped automatically, console flags it for eyeballing. No quarantine unless the
   existing ffprobe spec gate also fails.

A misbehaving loop costs us the keyword, never the clip.

## Batch schema

`prompt_video.json` gains one optional per-entry field:

```json
{ "name": "...", "title": "...", "keywords": "...", "category": 8,
  "positive": "...", "negative": "...", "loop": true }
```

- `"loop": true` → two-pass loop path.
- Field absent / false → existing single-pass path, byte-for-byte untouched behavior.
- Loop entries' keyword lists include `seamless loop, looping` (stripped by the script if
  the seam gate fails).

## Prompt-craft rule (new; promote to CLAUDE.md after validation)

Loop prompts must describe **ambient / cyclic motion** — pulsing, undulating, orbiting,
shimmering, slow drift with no net direction. **Never one-way sweeps**: a left-to-right
particle stream forced back to its start frame can produce a visible "rubber-band"
deceleration near the endpoints. Same positive-only anti-text defense as the base video
rules (CFG 1 → negative inert).

## Risks & fallback

- **Motion easing/stalling near pinned endpoints** → could trip Adobe's "limited motion"
  rejection. Mitigations: cyclic-motion prompting, seed re-roll.
- **Endpoint conditioning unreliable across the feasibility test** → fallback is the
  **palindrome (ping-pong) encode**: pure ffmpeg (`forward + reverse` concat), seam-free at
  both ends, used only for pulse/glow content where motion reversal is invisible.
  Directional-flow content is never palindromed.
- **Anchor frame quality from short pass 1** — if the ~33-frame harvest yields a soft/noisy
  frame 0, increase pass-1 length before considering other changes.

## Feasibility gate

Same discipline as the parent pipeline: **one** loop clip end-to-end first. Record
min/clip, peak VRAM, seam SSIM, motion quality (no easing/stall). Pass → 2-clip loop
batch. Fail → document numbers, evaluate palindrome fallback.

## Scope

- Modified: `script/main_ltxvideo.py` (loop branch in workflow builder, pass-1 anchor
  harvest, seam gate, CSV keyword handling), `prompt_video.json` (new entries with
  `"loop": true`).
- No new scripts, no new .bat file, no changes to the image pipeline.

## Out of scope (V1)

Z-Image stills as anchors (revisit if self-anchor quality disappoints); latent-space wrap
blending; loop durations other than 10 s; vertical 9:16 loops; 4K loops.

## Success criteria

1. Feasibility numbers recorded (min/clip, VRAM, seam SSIM).
2. One loop clip passing both gates (ffprobe spec + seam SSIM) with continuous,
   non-stalling motion.
3. Loop keywords present only on clips that passed the seam gate.
4. Non-loop entries still generate identically to before the change.
