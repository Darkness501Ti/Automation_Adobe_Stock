"""Generate Adobe Stock stills with FLUX.2 Klein 4B Base through ComfyUI.

Run one image per ComfyUI queue to keep peak memory manageable on a 16 GB GPU.
The model uses the project's existing prompt.json and Adobe CSV format.
"""

import argparse
import csv
import io
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image


COMFY_URL = "http://127.0.0.1:8188"
MODEL_NAME = "flux-2-klein-base-4b-fp8.safetensors"
CLIP_NAME = "qwen_3_4b.safetensors"
VAE_NAME = "flux2-vae.safetensors"
UPSCALE_MODEL = "RealESRGAN_x4plus.pth"

# ComfyUI's official 4B Base template uses Flux2Scheduler, CFG 5 and Euler.
# 1280x720 is 16:9 and uses fewer latent pixels than its 1024x1024 example.
WIDTH = 1280
HEIGHT = 720
STEPS = 30
CFG = 5.0
POLL_SECONDS = 3
IMAGE_TIMEOUT_SECONDS = 30 * 60

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT_FILE = BASE_DIR / "prompt.json"
OUTPUT_BASE = BASE_DIR / "output"
CSV_FIELDS = ["Filename", "Title", "Keywords", "Category", "Releases"]
REQUIRED_FIELDS = ("name", "title", "keywords", "category", "positive", "negative")


def validate_prompts(prompts):
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("prompt file must contain a nonempty JSON array")
    for index, item in enumerate(prompts, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"prompt {index} must be an object")
        for field in REQUIRED_FIELDS:
            if field not in item or item[field] is None or not str(item[field]).strip():
                raise ValueError(f"prompt {index} is missing {field}")
        if type(item["category"]) is not int or not 1 <= item["category"] <= 21:
            raise ValueError(f"prompt {index} category must be an integer from 1 to 21")


def build_workflow(item, seed, image_index):
    """ComfyUI API graph based on the official FLUX.2 Klein 4B Base template."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": MODEL_NAME, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": CLIP_NAME, "type": "flux2"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
        "4": {"class_type": "UpscaleModelLoader", "inputs": {
            "model_name": UPSCALE_MODEL}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {
            "text": item["positive"], "clip": ["2", 0]}},
        "11": {"class_type": "CLIPTextEncode", "inputs": {
            "text": item["negative"], "clip": ["2", 0]}},
        "12": {"class_type": "EmptyFlux2LatentImage", "inputs": {
            "width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "13": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "14": {"class_type": "CFGGuider", "inputs": {
            "model": ["1", 0], "positive": ["10", 0],
            "negative": ["11", 0], "cfg": CFG}},
        "15": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "16": {"class_type": "Flux2Scheduler", "inputs": {
            "steps": STEPS, "width": WIDTH, "height": HEIGHT}},
        "17": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["13", 0], "guider": ["14", 0],
            "sampler": ["15", 0], "sigmas": ["16", 0],
            "latent_image": ["12", 0]}},
        "18": {"class_type": "VAEDecode", "inputs": {
            "samples": ["17", 0], "vae": ["3", 0]}},
        "19": {"class_type": "ImageUpscaleWithModel", "inputs": {
            "upscale_model": ["4", 0], "image": ["18", 0]}},
        "20": {"class_type": "SaveImage", "inputs": {
            "filename_prefix": f"Flux2Klein_{image_index}", "images": ["19", 0]}},
    }


def api_json(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{COMFY_URL}{path}", data=data,
        headers={"Content-Type": "application/json"} if data is not None else {})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def get_image(image_info):
    query = urllib.parse.urlencode({
        "filename": image_info["filename"],
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    })
    with urllib.request.urlopen(f"{COMFY_URL}/view?{query}", timeout=120) as response:
        return response.read()


def generate_image(item, seed, image_index):
    workflow = build_workflow(item, seed, image_index)
    response = api_json("/prompt", {"prompt": workflow})
    prompt_id = response["prompt_id"]
    deadline = time.monotonic() + IMAGE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        history = api_json(f"/history/{prompt_id}")
        if prompt_id in history:
            result = history[prompt_id]
            if result.get("status", {}).get("status_str") == "error":
                raise RuntimeError(f"ComfyUI execution error: {result['status'].get('messages', [])}")
            images = result.get("outputs", {}).get("20", {}).get("images", [])
            if not images:
                raise RuntimeError(f"ComfyUI finished without an image for prompt {image_index}")
            return get_image(images[0])
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"image {image_index} exceeded {IMAGE_TIMEOUT_SECONDS // 60} minutes")


def create_run_dir():
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%d%m%Y")
    number = 1
    while True:
        run_dir = OUTPUT_BASE / f"{today}_Run{number}_klein"
        try:
            run_dir.mkdir()
            return run_dir, today, number
        except FileExistsError:
            number += 1


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE)
    parser.add_argument("--limit", type=int, help="generate only the first N images")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    with args.prompt_file.open("r", encoding="utf-8") as stream:
        prompts = json.load(stream)
    validate_prompts(prompts)
    if args.limit:
        prompts = prompts[:args.limit]

    run_dir, today, run_number = create_run_dir()
    rows = []
    manifest = []
    print(f"FLUX.2 Klein 4B Base: {len(prompts)} images, {WIDTH}x{HEIGHT}, "
          f"{STEPS} steps, CFG {CFG}")
    print(f"Output: {run_dir}")

    try:
        for index, item in enumerate(prompts, start=1):
            seed = random.SystemRandom().randrange(1, 2**63)
            print(f"[{index}/{len(prompts)}] {item['name']} (seed {seed})", flush=True)
            data = generate_image(item, seed, index)
            filename = f"{today}_Run{run_number}_Klein_Image{index}.jpg"
            image_path = run_dir / filename
            with Image.open(io.BytesIO(data)) as image:
                image.convert("RGB").save(
                    image_path, "JPEG", quality=95, subsampling=0)
            rows.append({
                "Filename": filename,
                "Title": item["title"][:200],
                "Keywords": item["keywords"],
                "Category": item["category"],
                "Releases": "",
            })
            manifest.append({"index": index, "name": item["name"],
                             "seed": seed, "filename": filename})
            print(f" -> saved {filename}", flush=True)
    except (urllib.error.URLError, RuntimeError, TimeoutError, OSError, KeyError) as exc:
        print(f"Generation stopped: {exc}", file=sys.stderr)
        return_code = 1
    else:
        return_code = 0
    finally:
        write_csv(run_dir / "AdobeStock_Metadata.csv", rows)
        with (run_dir / "Generation_Manifest.json").open("w", encoding="utf-8") as stream:
            json.dump({"model": MODEL_NAME, "width": WIDTH, "height": HEIGHT,
                       "steps": STEPS, "cfg": CFG, "images": manifest},
                      stream, indent=2)

    print(f"Saved {len(rows)}/{len(prompts)} images to {run_dir}")
    return return_code


if __name__ == "__main__":
    sys.exit(main())
