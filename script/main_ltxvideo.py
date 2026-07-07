import urllib.request
import urllib.parse
import json
import time
import os
import csv
import random
import shutil
import subprocess
from datetime import datetime

from loop_utils import add_loop_guides, parse_ssim, strip_loop_keywords

# =============================================================
# LTX-2.3 VIDEO CONFIG  (tune here, no need to touch the code below)
# Spec: docs/superpowers/specs/2026-07-06-ltx-video-pipeline-design.md
# =============================================================
COMFY_URL = "http://127.0.0.1:8188"

# Model files (see ComfyUI/models/...)
CKPT_NAME     = "ltx-2.3-22b-dev-fp8.safetensors"                                        # models/checkpoints/
LORA_NAME     = "ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors"  # models/loras/
LORA_STRENGTH = 0.5
TEXT_ENCODER  = "gemma_3_12B_it_fp4_mixed.safetensors"                                    # models/text_encoders/
UPSCALER_NAME = "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"                             # models/latent_upscale_models/

# Output geometry / timing
# Generate at 1920x1088 (LTX needs W/2 and H/2 divisible by 32), then crop to 1920x1080.
GEN_WIDTH   = 1920
GEN_HEIGHT  = 1088
OUT_WIDTH   = 1920
OUT_HEIGHT  = 1080
FPS         = 24
DURATION_S  = 10
FRAMES      = FPS * DURATION_S + 1          # LTX frame rule: fps * seconds + 1  -> 241
# 4K switch (only after feasibility is proven; latent halves must stay /32):
# GEN_WIDTH, GEN_HEIGHT, OUT_WIDTH, OUT_HEIGHT = 3840, 2176, 3840, 2160

# Distilled two-stage sampling (values from official ComfyUI video_ltx2_3_t2v template)
# PROVEN DEFAULT (feasibility 2026-07-06): distilled LoRA @ 0.5 + CFG 1 = ~4.7 min/clip,
# ~15.7GB peak VRAM on RTX 5070 Ti 16GB, clean output.
# WARNING: at CFG=1 the NEGATIVE PROMPT IS IGNORED (CFGGuider skips the uncond branch).
# All anti-text defense must live in the POSITIVE prompt: never write the words
# text/letters/logo/watermark/typography or "copy space" there (LTX-2.3 is a strong text
# renderer and draws them); describe empty areas visually instead
# ("remains a smooth featureless dark gradient, completely plain and empty").
# Keep the full negative list in prompt_video.json anyway - it becomes active if CFG > 1.
STAGE1_SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
STAGE2_SIGMAS = "0.85, 0.7250, 0.4219, 0.0"
CFG           = 1.0                          # distilled LoRA -> cfg 1 (see warning above)
SAMPLER_NAME  = "euler"
STAGE2_SEED   = 42                           # fixed refine noise (template default)

# Seamless-loop mode ("loop": true in prompt_video.json)
# Spec: docs/superpowers/specs/2026-07-07-ltx-seamless-loop-design.md
# Pass 1 harvests an anchor frame (short cheap render), pass 2 pins it at
# frame 0 and frame FRAMES-1 (LTXVAddGuide), ffmpeg trims the duplicated
# last frame -> exactly LOOP_FRAMES frames that wrap seamlessly.
ANCHOR_FRAMES   = 33     # pass-1 length, LTX rule 8n+1 (~1/7 of full render)
GUIDE_STRENGTH  = 1.0    # anchor conditioning strength at both endpoints
LOOP_FRAMES     = FPS * DURATION_S   # 240 -> exact 10.000s after trim
SSIM_THRESHOLD  = 0.95   # seam gate: below this, loop keywords are stripped

# ffmpeg encode (Adobe: H.264, 5-60s, >=1920x1080, <=3.9GB)
FF_CRF        = 17
FF_PRESET     = "slow"
CLIP_TIMEOUT_S = 30 * 60                     # abort a clip stuck longer than this
ADOBE_FPS_SET = {23.98, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0}
# =============================================================

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

# 3. Locate ffmpeg / ffprobe (PATH first, then WinGet links)
def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    links = os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Links\{name}.exe")
    if os.path.exists(links):
        return links
    import glob
    hits = glob.glob(os.path.expandvars(
        rf"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\{name}.exe"))
    if hits:
        return hits[0]
    raise FileNotFoundError(f"{name} not found on PATH or in WinGet locations. Install: winget install Gyan.FFmpeg")

FFMPEG  = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")

# 4. ComfyUI API Functions
def queue_prompt(prompt_workflow):
    data = json.dumps({"prompt": prompt_workflow}).encode('utf-8')
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())

def get_history(prompt_id):
    with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_file(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{COMFY_URL}/view?{url_values}") as response:
        return response.read()

# 5. Build the LTX-2.3 T2V Workflow (API format, one clip per queue -- video is VRAM heavy)
# Mirrors official template video_ltx2_3_t2v.json with the inert I2V branch removed
# (its LTXVImgToVideoInplace nodes run bypass=true in T2V) and the prompt enhancer skipped.
# Audio latents are integral to the AV model, but we never decode audio (clips ship silent).
def build_workflow(positive, negative, frames=FRAMES):
    seed = random.randint(1, 1000000000000)
    return {
        # Shared loaders (cached by ComfyUI across queues)
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT_NAME}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0], "lora_name": LORA_NAME, "strength_model": LORA_STRENGTH}},
        "3": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
            "text_encoder": TEXT_ENCODER, "ckpt_name": CKPT_NAME, "device": "default"}},
        "4": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": CKPT_NAME}},
        "5": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": UPSCALER_NAME}},
        # Conditioning
        "10": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["3", 0]}},
        "11": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["3", 0]}},
        "12": {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["10", 0], "negative": ["11", 0], "frame_rate": float(FPS)}},
        # Stage 1: half-res AV generation
        "20": {"class_type": "EmptyLTXVLatentVideo", "inputs": {
            "width": GEN_WIDTH // 2, "height": GEN_HEIGHT // 2, "length": frames, "batch_size": 1}},
        "21": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
            "frames_number": frames, "frame_rate": FPS, "batch_size": 1, "audio_vae": ["4", 0]}},
        "22": {"class_type": "LTXVConcatAVLatent", "inputs": {
            "video_latent": ["20", 0], "audio_latent": ["21", 0]}},
        "23": {"class_type": "CFGGuider", "inputs": {
            "model": ["2", 0], "positive": ["12", 0], "negative": ["12", 1], "cfg": CFG}},
        "24": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": SAMPLER_NAME}},
        "25": {"class_type": "ManualSigmas", "inputs": {"sigmas": STAGE1_SIGMAS}},
        "26": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "27": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["26", 0], "guider": ["23", 0], "sampler": ["24", 0],
            "sigmas": ["25", 0], "latent_image": ["22", 0]}},
        "28": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["27", 0]}},
        # Stage 2: x2 latent upscale + short refine
        "30": {"class_type": "LTXVLatentUpsampler", "inputs": {
            "samples": ["28", 0], "upscale_model": ["5", 0], "vae": ["1", 2]}},
        "31": {"class_type": "LTXVConcatAVLatent", "inputs": {
            "video_latent": ["30", 0], "audio_latent": ["28", 1]}},
        "32": {"class_type": "LTXVCropGuides", "inputs": {
            "positive": ["12", 0], "negative": ["12", 1], "latent": ["28", 0]}},
        "33": {"class_type": "CFGGuider", "inputs": {
            "model": ["2", 0], "positive": ["32", 0], "negative": ["32", 1], "cfg": CFG}},
        "34": {"class_type": "ManualSigmas", "inputs": {"sigmas": STAGE2_SIGMAS}},
        "35": {"class_type": "RandomNoise", "inputs": {"noise_seed": STAGE2_SEED}},
        "36": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["35", 0], "guider": ["33", 0], "sampler": ["24", 0],
            "sigmas": ["34", 0], "latent_image": ["31", 0]}},
        "37": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["36", 0]}},
        # Decode video only (audio stripped by design) and save
        "40": {"class_type": "VAEDecodeTiled", "inputs": {
            "samples": ["37", 0], "vae": ["1", 2],
            "tile_size": 768, "overlap": 64, "temporal_size": 4096, "temporal_overlap": 4}},
        "41": {"class_type": "CreateVideo", "inputs": {"images": ["40", 0], "fps": float(FPS)}},
        "42": {"class_type": "SaveVideo", "inputs": {
            "video": ["41", 0], "filename_prefix": "LTXVideo", "format": "auto", "codec": "auto"}},
    }

# 6. Find the saved video file in a history entry (SaveVideo output key varies by version)
def find_video_output(outputs):
    for node_out in outputs.values():
        for key in ("images", "video", "videos", "gifs"):
            for f in node_out.get(key, []):
                if isinstance(f, dict) and f.get("filename", "").lower().endswith((".mp4", ".mov", ".webm")):
                    return f
    return None


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

# 8. ffprobe gate: every Adobe spec check must pass or the clip is quarantined
def probe_gate(path):
    cmd = [FFPROBE, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,codec_name,avg_frame_rate:format=duration,size",
           "-of", "json", path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return False, f"ffprobe failed: {res.stderr[-200:]}"
    info = json.loads(res.stdout)
    st = info["streams"][0]
    fmt = info["format"]
    num, den = st["avg_frame_rate"].split("/")
    fps = round(int(num) / int(den), 2)
    checks = {
        "width>=1920":  st["width"] >= 1920,
        "height>=1080": st["height"] >= 1080,
        "codec=h264":   st["codec_name"] == "h264",
        "fps in Adobe set": any(abs(fps - a) < 0.02 for a in ADOBE_FPS_SET),
        "5s<=dur<=60s": 5.0 <= float(fmt["duration"]) <= 60.0,
        "size<=3.9GB":  int(fmt["size"]) <= 3900 * 1024 * 1024,
    }
    failed = [k for k, ok in checks.items() if not ok]
    detail = f"{st['width']}x{st['height']} {fps}fps {float(fmt['duration']):.2f}s {st['codec_name']} {int(fmt['size'])/1e6:.1f}MB"
    return (len(failed) == 0), (detail if not failed else f"{detail} FAILED: {', '.join(failed)}")

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

    # 9. Write the Adobe Stock CSV Format
    csv_path = os.path.join(output_dir, "AdobeStock_Metadata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Filename", "Title", "Keywords", "Category", "Releases"])
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nBatch complete! {len(csv_data)}/{len(prompts)} clips passed the spec gate.")
    print(f"CSV and videos saved to {output_dir}")

if __name__ == '__main__':
    main()
