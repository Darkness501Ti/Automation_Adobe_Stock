# LTX Seamless-Loop Video Mode (V1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `"loop": true` mode to `script/main_ltxvideo.py` that produces mathematically seamless looping MP4s via two-pass self-anchor (same image conditioned at first and last frame), with an SSIM seam gate that strips loop keywords from the CSV when the seam isn't clean.

**Architecture:** Pass 1 renders a short (33-frame) clip of the same prompt only to harvest a high-quality frame 0 (the anchor). Pass 2 re-renders the full 241 frames with the anchor pinned at frame 0 and frame 240 via `LTXVAddGuide`; ffmpeg trims the duplicated final frame → exactly 240 frames = 10.000 s @ 24 fps that wrap seamlessly. Pure helpers live in a new `script/loop_utils.py` (import-side-effect-free, unit-tested with stdlib `unittest`); ComfyUI/ffmpeg orchestration stays in `main_ltxvideo.py`.

**Tech Stack:** Python 3 stdlib only (urllib, subprocess, unittest — no new deps), ComfyUI API on `127.0.0.1:8188`, ffmpeg/ffprobe (WinGet Gyan.FFmpeg), LTX-2.3 22B fp8 + distilled LoRA.

**Spec:** `docs/superpowers/specs/2026-07-07-ltx-seamless-loop-design.md`

## Global Constraints

- Adobe video spec unchanged: H.264, yuv420p, ≥1920×1080, fps ∈ {23.98, 24, 25, 29.97, 30, 50, 59.94, 60}, 5–60 s, ≤3.9 GB, no audio (`-an`).
- LTX frame rule: frame counts must be `8n+1` (241 full, 33 anchor pass). Guide `frame_idx` must land on a multiple of 8 (240 ✓).
- CFG = 1 (distilled LoRA) → **negative prompt inert**; anti-text defense is positive-only. Never write the words text/letters/logo/watermark/typography or "copy space" in a positive prompt.
- Non-loop entries must behave **identically** to the current pipeline (single pass, 241 frames, no trim, keywords untouched).
- Loop keyword policy: `seamless loop, looping` may appear in the CSV **only** if the seam SSIM gate passes (threshold 0.95, config-tunable).
- No new scripts beyond `script/loop_utils.py` + tests; no new .bat file; image pipeline untouched.
- Windows: subprocess calls use list args (no shell); ffmpeg `select` filter commas escaped as `\,`.
- All configuration goes in the existing CONFIG block style (UPPER_CASE at top of file, commented).

---

### Task 1: Import-safe refactor of `main_ltxvideo.py` (no behavior change)

The module currently creates a fresh `output/DDMMYYYY_RunN_video/` directory **at import time** (lines 59–76). Tests can't import it without polluting `output/`. Move run-dir creation into a function called from `main()`, and extend `build_workflow` with a `frames` parameter (default keeps current behavior). Also extract the queue-and-poll loop into `generate_and_wait()` so the loop path (Task 4) can call it twice per clip.

**Files:**
- Modify: `script/main_ltxvideo.py:59-76` (dir creation), `:117-119` (build_workflow signature), `:134-137` (frame counts), `:218-257` (main loop)
- Test: `tests/test_main_import.py`

**Interfaces:**
- Produces: `create_run_dir() -> (output_dir: str, today_str: str, run_num: int)`;
  `build_workflow(positive: str, negative: str, frames: int = FRAMES) -> dict`;
  `generate_and_wait(workflow: dict, label: str) -> dict | None` (ComfyUI outputs dict, or None on timeout/error — already prints the reason);
  `download_video(outputs: dict, dest_path: str) -> bool`.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_main_import.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))


class TestImportSideEffects(unittest.TestCase):
    def test_import_creates_no_run_dir(self):
        base = os.path.join(os.path.dirname(__file__), "..", "output")
        before = set(os.listdir(base)) if os.path.exists(base) else set()
        import main_ltxvideo  # noqa: F401
        after = set(os.listdir(base)) if os.path.exists(base) else set()
        self.assertEqual(before, after, "importing main_ltxvideo must not create run dirs")

    def test_build_workflow_frames_param(self):
        import main_ltxvideo as m
        wf = m.build_workflow("pos", "neg", frames=33)
        self.assertEqual(wf["20"]["inputs"]["length"], 33)
        self.assertEqual(wf["21"]["inputs"]["frames_number"], 33)
        wf_default = m.build_workflow("pos", "neg")
        self.assertEqual(wf_default["20"]["inputs"]["length"], m.FRAMES)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run (from repo root): `python -m unittest discover -s tests -v`
Expected: `test_import_creates_no_run_dir` FAILS (a new `_video` run dir appears on import) and/or `test_build_workflow_frames_param` FAILS with `TypeError: build_workflow() got an unexpected keyword argument 'frames'`.

- [ ] **Step 3: Refactor `main_ltxvideo.py`**

3a. Replace the module-level sections 1–2 (lines 59–76: `PROMPT_FILE`/`OUTPUT_BASE` setup, `os.makedirs`, the `today_str`/`run_num`/`OUTPUT_DIR`/`QUARANTINE_DIR` while-loop) with:

```python
# 1. Paths (directories are created in main(), not at import time)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_FILE = os.path.join(BASE_DIR, "prompt_video.json")
OUTPUT_BASE = os.path.join(BASE_DIR, "output")


# 2. Output folder (ddmmyyyy_RunX_video)
def create_run_dir():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    today_str = datetime.now().strftime("%d%m%Y")
    run_num = 1
    while True:
        out_dir = os.path.join(OUTPUT_BASE, f"{today_str}_Run{run_num}_video")
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            return out_dir, today_str, run_num
        run_num += 1
```

3b. Change the `build_workflow` signature and the two frame-count inputs (keep everything else in the function byte-identical):

```python
def build_workflow(positive, negative, frames=FRAMES):
```

Node `"20"`: `"length": frames` (was `FRAMES`). Node `"21"`: `"frames_number": frames` (was `FRAMES`).

3c. Add after `find_video_output` (section 6) two helpers extracted from the current `main()` body — queueing+polling (from lines 230–257) and download (from lines 260–268):

```python
# 6b. Queue a workflow and poll until finished. Returns outputs dict or None.
def generate_and_wait(workflow, label):
    t0 = time.time()
    try:
        res = queue_prompt(workflow)
        prompt_id = res["prompt_id"]
    except urllib.error.HTTPError as e:
        print(f" -> ComfyUI rejected workflow ({label}): {e.read().decode()[:500]}")
        return None
    while True:
        if time.time() - t0 > CLIP_TIMEOUT_S:
            print(f" -> TIMEOUT after {CLIP_TIMEOUT_S/60:.0f} min ({label})")
            return None
        history = get_history(prompt_id)
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                print(f" -> ComfyUI execution error ({label}): {json.dumps(msgs)[:500]}")
                return None
            if entry.get("outputs"):
                return entry["outputs"]
        time.sleep(5)


# 6c. Pull the rendered video out of ComfyUI into dest_path.
def download_video(outputs, dest_path):
    vid = find_video_output(outputs)
    if not vid:
        print(f" -> No video file in ComfyUI outputs: {list(outputs.keys())}")
        return False
    raw_bytes = get_file(vid["filename"], vid.get("subfolder", ""), vid.get("type", "output"))
    with open(dest_path, "wb") as f:
        f.write(raw_bytes)
    return True
```

3d. Rewrite `main()` to use them (same behavior, same prints; `OUTPUT_DIR`/`QUARANTINE_DIR`/`today_str`/`run_num` become locals):

```python
def main():
    print("Starting LTX-2.3 video batch generation...")
    output_dir, today_str, run_num = create_run_dir()
    quarantine_dir = os.path.join(output_dir, "quarantine")
    print(f"Output folder created: {output_dir}")
    print(f"Config: {GEN_WIDTH}x{GEN_HEIGHT} -> crop {OUT_WIDTH}x{OUT_HEIGHT}, {FPS}fps, {DURATION_S}s ({FRAMES} frames)\n")

    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    csv_data = []
    for i, item in enumerate(prompts):
        idx = i + 1
        print(f"[{idx}/{len(prompts)}] {item['name']}: queueing...")
        t0 = time.time()

        outputs = generate_and_wait(build_workflow(item["positive"], item["negative"]), "t2v")
        if not outputs:
            continue

        gen_min = (time.time() - t0) / 60
        raw_path = os.path.join(output_dir, f"raw_{idx}.mp4")
        if not download_video(outputs, raw_path):
            continue

        final_filename = f"{today_str}_Run{run_num}_Video{idx}.mp4"
        final_path = os.path.join(output_dir, final_filename)
        try:
            encode_clip(raw_path, final_path)
        except RuntimeError as e:
            print(f" -> {e}")
            continue
        os.remove(raw_path)

        ok, detail = probe_gate(final_path)
        if not ok:
            os.makedirs(quarantine_dir, exist_ok=True)
            shutil.move(final_path, os.path.join(quarantine_dir, final_filename))
            print(f" -> QUARANTINED ({detail})")
            continue

        print(f" -> Saved: {final_filename} ({detail}, gen {gen_min:.1f} min)")
        csv_data.append({
            "Filename": final_filename,
            "Title": item["title"][:200],
            "Keywords": item["keywords"],
            "Category": item["category"],
            "Releases": ""
        })

    # 9. Write the Adobe Stock CSV Format
    csv_path = os.path.join(output_dir, "AdobeStock_Metadata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Filename", "Title", "Keywords", "Category", "Releases"])
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nBatch complete! {len(csv_data)}/{len(prompts)} clips passed the spec gate.")
    print(f"CSV and videos saved to {output_dir}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -v`
Expected: 2 tests PASS. Also confirm no stray `output/*_video` dir was created by the test run (the import test asserts this).

- [ ] **Step 5: Commit**

```bash
git add script/main_ltxvideo.py tests/test_main_import.py
git commit -m "refactor: make main_ltxvideo import-safe, add frames param + generate helpers"
```

---

### Task 2: `loop_utils.py` — keyword stripping + SSIM parsing

Pure helpers, no I/O, stdlib only. `strip_loop_keywords` enforces the honest-keyword policy when the seam gate fails; `parse_ssim` reads ffmpeg's ssim filter output.

**Files:**
- Create: `script/loop_utils.py`
- Test: `tests/test_loop_utils.py`

**Interfaces:**
- Produces: `strip_loop_keywords(keywords: str) -> str` (comma-separated in, comma-separated out, order preserved);
  `parse_ssim(ffmpeg_stderr: str) -> float` (raises `ValueError` if no `All:` value);
  module constant `LOOP_KEYWORDS: set[str]`.
- Consumes: nothing.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_loop_utils.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))

from loop_utils import parse_ssim, strip_loop_keywords


class TestStripLoopKeywords(unittest.TestCase):
    def test_strips_loop_terms_preserves_order(self):
        kw = "motion background, seamless loop, technology, looping, teal, loop"
        self.assertEqual(strip_loop_keywords(kw), "motion background, technology, teal")

    def test_case_insensitive(self):
        self.assertEqual(strip_loop_keywords("Seamless Loop, glow, LOOPING"), "glow")

    def test_untouched_when_no_loop_terms(self):
        kw = "motion background, abstract background, animation"
        self.assertEqual(strip_loop_keywords(kw), kw)

    def test_normalizes_whitespace(self):
        self.assertEqual(strip_loop_keywords("a ,  seamless loop ,b"), "a, b")


class TestParseSsim(unittest.TestCase):
    def test_parses_all_value(self):
        stderr = ("[Parsed_ssim_0 @ 000001] SSIM Y:0.981234 (17.2) U:0.995 V:0.994 "
                  "All:0.987654 (19.1)")
        self.assertAlmostEqual(parse_ssim(stderr), 0.987654)

    def test_raises_without_value(self):
        with self.assertRaises(ValueError):
            parse_ssim("frame=  240 fps=0.0 q=-1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_loop_utils -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'loop_utils'`.

- [ ] **Step 3: Write the implementation**

Create `script/loop_utils.py`:

```python
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
```

(`copy` is imported now because `add_loop_guides` in Task 3 lives in this same module and needs it; if the linter flags it as unused at this commit, keep it — Task 3 lands next.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_loop_utils -v`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add script/loop_utils.py tests/test_loop_utils.py
git commit -m "feat: loop keyword stripping + ffmpeg SSIM parsing helpers"
```

---

### Task 3: `add_loop_guides` — pin the anchor at first and last frame

Pure workflow-dict transform: takes the T2V workflow from `build_workflow`, inserts a `LoadImage` + two `LTXVAddGuide` nodes (frame 0 and frame `frames-1`), and rewires stage-1 sampling and the stage-2 guide-crop path. `LTXVAddGuide` appends guide latents to the video latent; the existing `LTXVCropGuides` node ("32") removes them after stage-1 sampling — but its cropped-latent output (index 2) is currently unused, so in loop mode the upsampler ("30") must consume `["32", 2]` instead of the raw `["28", 0]`.

**Files:**
- Modify: `script/loop_utils.py` (add function)
- Test: `tests/test_loop_utils.py` (add test class)

**Interfaces:**
- Consumes: workflow dict shape from `build_workflow` (Task 1): nodes `"12"` (LTXVConditioning), `"20"` (EmptyLTXVLatentVideo), `"22"` (LTXVConcatAVLatent), `"23"` (stage-1 CFGGuider), `"28"` (LTXVSeparateAVLatent), `"30"` (LTXVLatentUpsampler), `"32"` (LTXVCropGuides); VAE at `["1", 2]`.
- Produces: `add_loop_guides(wf: dict, anchor_name: str, frames: int, strength: float = 1.0) -> dict` (deep copy; input not mutated). `anchor_name` is the server-side filename returned by ComfyUI's `/upload/image`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loop_utils.py` (add `from loop_utils import add_loop_guides` to the imports):

```python
class TestAddLoopGuides(unittest.TestCase):
    def _t2v(self):
        import main_ltxvideo as m
        return m.build_workflow("pos", "neg")

    def test_guide_nodes_and_rewiring(self):
        wf = add_loop_guides(self._t2v(), "anchor.png", 241)
        self.assertEqual(wf["6"]["class_type"], "LoadImage")
        self.assertEqual(wf["6"]["inputs"]["image"], "anchor.png")
        self.assertEqual(wf["13"]["class_type"], "LTXVAddGuide")
        self.assertEqual(wf["13"]["inputs"]["frame_idx"], 0)
        self.assertEqual(wf["13"]["inputs"]["latent"], ["20", 0])
        self.assertEqual(wf["14"]["inputs"]["frame_idx"], 240)  # 8-aligned last frame
        self.assertEqual(wf["14"]["inputs"]["latent"], ["13", 2])
        # stage 1 consumes guided latent + conditioning
        self.assertEqual(wf["22"]["inputs"]["video_latent"], ["14", 2])
        self.assertEqual(wf["23"]["inputs"]["positive"], ["14", 0])
        self.assertEqual(wf["23"]["inputs"]["negative"], ["14", 1])
        # stage 2 crops guides, upsampler consumes the CROPPED latent
        self.assertEqual(wf["32"]["inputs"]["positive"], ["14", 0])
        self.assertEqual(wf["32"]["inputs"]["negative"], ["14", 1])
        self.assertEqual(wf["30"]["inputs"]["samples"], ["32", 2])

    def test_strength_and_no_mutation(self):
        original = self._t2v()
        snapshot = repr(original)
        wf = add_loop_guides(original, "a.png", 241, strength=0.9)
        self.assertEqual(wf["13"]["inputs"]["strength"], 0.9)
        self.assertEqual(wf["14"]["inputs"]["strength"], 0.9)
        self.assertEqual(repr(original), snapshot, "input workflow must not be mutated")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_loop_utils -v`
Expected: new tests FAIL with `ImportError: cannot import name 'add_loop_guides'`.

- [ ] **Step 3: Write the implementation**

Append to `script/loop_utils.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -v`
Expected: all tests PASS (Task 1's + Task 2's + these).

- [ ] **Step 5: Commit**

```bash
git add script/loop_utils.py tests/test_loop_utils.py
git commit -m "feat: add_loop_guides pins anchor at first+last frame in LTX workflow"
```

---

### Task 4: Loop branch in `main_ltxvideo.py` — anchor harvest, seam gate, CSV policy

Wire it together: new CONFIG constants, image upload + frame extraction + seam-SSIM helpers, `-frames:v` trim in `encode_clip`, and the `"loop": true` branch in `main()`. These helpers hit ComfyUI/ffmpeg, so they're covered by the feasibility run (Task 5), not unit tests — but the file must still import cleanly and all existing tests must stay green.

**Files:**
- Modify: `script/main_ltxvideo.py` (CONFIG block, imports, new section 7b/7c helpers, `encode_clip`, `main()` loop body)

**Interfaces:**
- Consumes: `generate_and_wait`, `download_video`, `build_workflow(..., frames=)` (Task 1); `add_loop_guides`, `strip_loop_keywords`, `parse_ssim` (Tasks 2–3).
- Produces: `upload_image(path: str) -> str` (server-side name); `extract_frame(video_path: str, png_path: str, frame_idx: int) -> None` (raises RuntimeError); `seam_ssim(video_path: str, last_idx: int) -> float`; `encode_clip(raw_path, final_path, frames_limit: int | None = None)`.

- [ ] **Step 1: Add CONFIG constants and import**

In the CONFIG block of `script/main_ltxvideo.py`, after the `STAGE2_SEED = 42` line, insert:

```python
# Seamless-loop mode ("loop": true in prompt_video.json)
# Spec: docs/superpowers/specs/2026-07-07-ltx-seamless-loop-design.md
# Pass 1 harvests an anchor frame (short cheap render), pass 2 pins it at
# frame 0 and frame FRAMES-1 (LTXVAddGuide), ffmpeg trims the duplicated
# last frame -> exactly LOOP_FRAMES frames that wrap seamlessly.
ANCHOR_FRAMES   = 33     # pass-1 length, LTX rule 8n+1 (~1/7 of full render)
GUIDE_STRENGTH  = 1.0    # anchor conditioning strength at both endpoints
LOOP_FRAMES     = FPS * DURATION_S   # 240 -> exact 10.000s after trim
SSIM_THRESHOLD  = 0.95   # seam gate: below this, loop keywords are stripped
```

Below the existing imports (after `from datetime import datetime`) add:

```python
from loop_utils import add_loop_guides, parse_ssim, strip_loop_keywords
```

(`main_ltxvideo.py` and `loop_utils.py` are siblings in `script/`, and the script is run as `python script/main_ltxvideo.py`, so the plain import resolves.)

- [ ] **Step 2: Add upload / frame-extract / seam helpers**

After `download_video` (added in Task 1), insert:

```python
# 6d. Upload an image to ComfyUI's input folder (multipart, stdlib only).
def upload_image(path):
    boundary = "----ltxloop" + str(random.randint(0, 10**12))
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        filedata = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + filedata + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())["name"]


# 6e. Extract a single frame as PNG (comma in select= escaped for the filtergraph).
def extract_frame(video_path, png_path, frame_idx):
    cmd = [FFMPEG, "-y", "-i", video_path,
           "-vf", f"select=eq(n\\,{frame_idx})", "-frames:v", "1", png_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(png_path):
        raise RuntimeError(f"frame extract failed: {res.stderr[-300:]}")


# 6f. Seam gate: SSIM between first frame and last frame of the final clip.
def seam_ssim(video_path, last_idx):
    first_png = video_path + ".first.png"
    last_png = video_path + ".last.png"
    try:
        extract_frame(video_path, first_png, 0)
        extract_frame(video_path, last_png, last_idx)
        cmd = [FFMPEG, "-i", first_png, "-i", last_png,
               "-filter_complex", "ssim", "-f", "null", "-"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return parse_ssim(res.stderr)
    finally:
        for p in (first_png, last_png):
            if os.path.exists(p):
                os.remove(p)
```

- [ ] **Step 3: Add `frames_limit` to `encode_clip`**

Replace the current `encode_clip` with:

```python
# 7. ffmpeg re-encode: crop to spec, H.264 yuv420p, strip audio, faststart.
#    frames_limit trims loop clips to exactly LOOP_FRAMES (drops the duplicated
#    final frame so playback wraps seamlessly).
def encode_clip(raw_path, final_path, frames_limit=None):
    cmd = [FFMPEG, "-y", "-i", raw_path]
    if frames_limit:
        cmd += ["-frames:v", str(frames_limit)]
    cmd += ["-vf", f"crop={OUT_WIDTH}:{OUT_HEIGHT}",
            "-c:v", "libx264", "-crf", str(FF_CRF), "-preset", FF_PRESET,
            "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
            final_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {res.stderr[-500:]}")
```

- [ ] **Step 4: Add the loop branch to `main()`**

In `main()` (as rewritten in Task 1), replace the block from `outputs = generate_and_wait(...)` down to (and including) the `csv_data.append({...})` call with:

```python
        is_loop = bool(item.get("loop"))
        if is_loop:
            # Pass 1: short render, harvest frame 0 as the anchor image.
            print(" -> loop mode: anchor harvest pass...")
            outputs = generate_and_wait(
                build_workflow(item["positive"], item["negative"], frames=ANCHOR_FRAMES),
                "anchor pass")
            if not outputs:
                continue
            anchor_mp4 = os.path.join(output_dir, f"anchor_{idx}.mp4")
            anchor_png = os.path.join(output_dir, f"anchor_{idx}.png")
            if not download_video(outputs, anchor_mp4):
                continue
            try:
                extract_frame(anchor_mp4, anchor_png, 0)
                anchor_name = upload_image(anchor_png)
            except (RuntimeError, urllib.error.URLError) as e:
                print(f" -> anchor prep failed: {e}")
                continue
            finally:
                for p in (anchor_mp4, anchor_png):
                    if os.path.exists(p):
                        os.remove(p)
            # Pass 2: full render with the anchor pinned at both endpoints.
            print(" -> loop mode: guided loop pass...")
            wf = add_loop_guides(
                build_workflow(item["positive"], item["negative"]),
                anchor_name, FRAMES, GUIDE_STRENGTH)
            outputs = generate_and_wait(wf, "loop pass")
        else:
            outputs = generate_and_wait(
                build_workflow(item["positive"], item["negative"]), "t2v")
        if not outputs:
            continue

        gen_min = (time.time() - t0) / 60
        raw_path = os.path.join(output_dir, f"raw_{idx}.mp4")
        if not download_video(outputs, raw_path):
            continue

        final_filename = f"{today_str}_Run{run_num}_Video{idx}.mp4"
        final_path = os.path.join(output_dir, final_filename)
        try:
            encode_clip(raw_path, final_path, frames_limit=LOOP_FRAMES if is_loop else None)
        except RuntimeError as e:
            print(f" -> {e}")
            continue
        os.remove(raw_path)

        ok, detail = probe_gate(final_path)
        if not ok:
            os.makedirs(quarantine_dir, exist_ok=True)
            shutil.move(final_path, os.path.join(quarantine_dir, final_filename))
            print(f" -> QUARANTINED ({detail})")
            continue

        keywords = item["keywords"]
        if is_loop:
            # Seam gate: keep loop keywords only if the wrap is actually clean.
            try:
                ssim = seam_ssim(final_path, LOOP_FRAMES - 1)
            except (RuntimeError, ValueError) as e:
                ssim = 0.0
                print(f" -> seam gate could not run ({e}), treating as FAIL")
            if ssim >= SSIM_THRESHOLD:
                print(f" -> seam gate PASS (SSIM {ssim:.4f}) - loop keywords kept")
            else:
                keywords = strip_loop_keywords(keywords)
                print(f" -> seam gate FAIL (SSIM {ssim:.4f} < {SSIM_THRESHOLD}) "
                      f"- loop keywords stripped, review clip manually")

        print(f" -> Saved: {final_filename} ({detail}, gen {gen_min:.1f} min)")
        csv_data.append({
            "Filename": final_filename,
            "Title": item["title"][:200],
            "Keywords": keywords,
            "Category": item["category"],
            "Releases": ""
        })
```

- [ ] **Step 5: Verify imports and full test suite**

Run: `python -c "import sys; sys.path.insert(0, 'script'); import main_ltxvideo; print('import OK')"`
Expected: `import OK` (and no new dir in `output/`).

Run: `python -m unittest discover -s tests -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add script/main_ltxvideo.py
git commit -m "feat: seamless-loop mode - two-pass self-anchor + SSIM seam gate"
```

---

### Task 5: Feasibility batch — loop prompt + node verification + run instructions

Author the 1-entry feasibility `prompt_video.json` (cyclic-motion prompt per the spec's prompt-craft rule) and verify the `LTXVAddGuide` node exists in the installed ComfyUI before burning GPU time. The actual render needs ComfyUI running on the 5070 Ti — if it isn't up, everything except the render still completes and the render becomes the user's next action.

**Files:**
- Modify: `prompt_video.json` (replace contents — the 2-clip batch-1 content is preserved in git history at commit `0fa6510`)

**Interfaces:**
- Consumes: `"loop": true` field handling (Task 4).
- Produces: feasibility numbers for the spec's success criteria (min/clip, VRAM, seam SSIM).

- [ ] **Step 1: Verify LTXVAddGuide exists in ComfyUI (requires ComfyUI running)**

Run in PowerShell:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8188/object_info/LTXVAddGuide" -TimeoutSec 10 | ConvertTo-Json -Depth 6
```

Expected: JSON describing the node with inputs `positive, negative, vae, latent, image, frame_idx, strength`.
If ComfyUI is not running: defer this check to just before the render (Step 3) — do not skip it.
If the node is missing or lacks `frame_idx`: STOP — record what nodes matching `LTX.*Guide|ImgToVideo` exist (`Invoke-RestMethod http://127.0.0.1:8188/object_info | ...`), and revisit the spec's fallback (palindrome encode) before proceeding.

- [ ] **Step 2: Write the feasibility prompt file**

Replace the contents of `prompt_video.json` with:

```json
[
  {
    "name": "teal_wave_ribbons_loop",
    "title": "Abstract teal light waves seamless loop motion background, glowing ribbons and particles gently undulating over dark navy backdrop with empty space",
    "keywords": "motion background, abstract background, seamless loop, looping, animation, video background, backdrop, technology, teal, glowing, wave, particles, futuristic, digital, energy, flowing, dark background, cyan, presentation, website header, screensaver",
    "category": 8,
    "positive": "Abstract motion background. Soft luminous ribbons of teal and cyan light gently undulate in place against a deep dark navy void, rising and falling in a slow continuous wave-like pulse that never stops and never travels in one direction. Fine glowing particles hover around the ribbons, each drifting in tiny slow circles and softly twinkling. The lower third of the frame remains a smooth featureless dark navy gradient, completely plain and empty. Static camera, constant gentle ambient motion, soft cinematic glow, shallow depth of field, high quality, photorealistic render.",
    "negative": "text, letters, words, title, caption, watermark, signature, logo, brand logo, trademark, chinese characters, japanese characters, writing, typography, ui, label, gibberish, transitions, flicker, strobe, camera shake, still frame, frozen motion",
    "loop": true
  }
]
```

Prompt-craft notes baked in: cyclic motion only (undulate/pulse/orbit — no net direction, per the rubber-band risk), positive-only anti-text defense (no text/letters/logo/"copy space" words in the positive; empty area described visually), negative kept for CFG>1 futures.

- [ ] **Step 3: Feasibility render (requires ComfyUI + GPU; ~12 min total)**

1. Start ComfyUI (`run_nvidia_gpu.bat`), wait for `127.0.0.1:8188`.
2. Run Step 1's node check if it was deferred.
3. Run `Generate_LTXVideo.bat`.
4. Record: anchor-pass minutes, loop-pass minutes, peak VRAM (Task Manager / `nvidia-smi`), seam gate SSIM printed by the script, ffprobe gate detail line.

Expected console flow: `loop mode: anchor harvest pass...` → `loop mode: guided loop pass...` → `seam gate PASS (SSIM 0.9xxx)` → `Saved: ..._Video1.mp4 (1920x1080 24.0fps 10.00s h264 ...)`.

- [ ] **Step 4: Visual QA**

Open the MP4 in a player with loop-repeat enabled (e.g., Windows Media Player repeat, or `ffplay -loop 0 <file>`). Check: (a) no visible jump at the wrap point, (b) motion does NOT stall or decelerate near the ends (Adobe limited-motion risk), (c) no rendered text/gibberish, (d) lower third clean.

Failure handling per spec: text/gibberish → re-roll (delete output, run again, new seed is automatic); motion stalls at endpoints → re-roll once, then consider `GUIDE_STRENGTH = 0.85`; ComfyUI validation error on the guide nodes → record the error, evaluate palindrome fallback per spec.

- [ ] **Step 5: Commit + record results**

```bash
git add prompt_video.json
git commit -m "feat: feasibility loop prompt (teal wave ribbons, loop:true)"
```

Record the feasibility numbers (min/clip, VRAM, SSIM, visual QA verdict) in the session summary for the user — they gate the go/no-go on a 2-clip loop batch and the CLAUDE.md prompt-rule promotion (which happens only after validation, per spec).

---

## Self-Review (completed)

- **Spec coverage:** loop mechanism (Tasks 1, 3, 4), seam QA gate + keyword policy (Tasks 2, 4), batch schema `"loop": true` (Tasks 4, 5), prompt-craft rule applied (Task 5), node verification (Task 5 Step 1), feasibility gate (Task 5 Steps 3–4), fallback decision point (Task 5 Step 4), non-loop path unchanged (Task 1 refactor + Task 4 else-branch). CLAUDE.md update intentionally deferred until validation, per spec.
- **Placeholder scan:** none — every step has full code/commands.
- **Type consistency:** `build_workflow(positive, negative, frames=FRAMES)` consistent across Tasks 1/3/4; `add_loop_guides(wf, anchor_name, frames, strength)` consistent across Tasks 3/4; `LOOP_FRAMES = 240`, `seam_ssim(path, LOOP_FRAMES - 1)` → frame index 239 vs frame 0, correct after trimming frame 240.
