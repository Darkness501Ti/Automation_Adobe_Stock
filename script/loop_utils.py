"""Pure helpers for the seamless-loop video mode (no I/O, no ComfyUI).

Spec: docs/superpowers/specs/2026-07-07-ltx-seamless-loop-design.md
"""
import copy
import re

# Keywords that may only ship in the CSV if the seam SSIM gate passes.
LOOP_KEYWORDS = {"seamless loop", "looping", "loop", "seamless", "loopable"}


def strip_loop_keywords(keywords):
    """Remove loop-claim keywords from a comma-separated keyword string."""
    kept = [k.strip() for k in keywords.split(",")]
    kept = [k for k in kept if k and k.lower() not in LOOP_KEYWORDS]
    return ", ".join(kept)


def parse_ssim(ffmpeg_stderr):
    """Extract the overall SSIM ('All:<v>') from ffmpeg ssim-filter stderr."""
    m = re.search(r"All:([0-9.]+)", ffmpeg_stderr)
    if not m:
        raise ValueError("no SSIM 'All:' value in ffmpeg output")
    return float(m.group(1))


def add_loop_guides(wf, anchor_name, frames, strength=1.0):
    """Insert first=last frame anchor conditioning into a T2V workflow (loop pass 2).

    Pins the uploaded anchor image at frame 0 and at frame `frames-1` so the
    generated motion returns to its start. LTXVAddGuide appends guide latents
    to the video latent; the existing LTXVCropGuides node ("32") removes them
    after stage-1 sampling, so the stage-2 upsampler is rewired to consume the
    cropped latent output. frames-1 must be a multiple of 8 (LTX latent grid).
    """
    wf = copy.deepcopy(wf)
    wf["6"] = {"class_type": "LoadImage", "inputs": {"image": anchor_name}}
    wf["13"] = {"class_type": "LTXVAddGuide", "inputs": {
        "positive": ["12", 0], "negative": ["12", 1], "vae": ["1", 2],
        "latent": ["20", 0], "image": ["6", 0],
        "frame_idx": 0, "strength": strength}}
    wf["14"] = {"class_type": "LTXVAddGuide", "inputs": {
        "positive": ["13", 0], "negative": ["13", 1], "vae": ["1", 2],
        "latent": ["13", 2], "image": ["6", 0],
        "frame_idx": frames - 1, "strength": strength}}
    wf["22"]["inputs"]["video_latent"] = ["14", 2]
    wf["23"]["inputs"]["positive"] = ["14", 0]
    wf["23"]["inputs"]["negative"] = ["14", 1]
    wf["32"]["inputs"]["positive"] = ["14", 0]
    wf["32"]["inputs"]["negative"] = ["14", 1]
    wf["30"]["inputs"]["samples"] = ["32", 2]
    return wf
