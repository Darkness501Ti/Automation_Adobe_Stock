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
