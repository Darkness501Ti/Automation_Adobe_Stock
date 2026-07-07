"""One-off downloader: pull Z-Image-Base model files into ComfyUI's models folders.
Downloads via huggingface_hub directly into each target dir, flattening the
repo's split_files/ nesting. Skips files that already exist.
"""
import os
import shutil
from huggingface_hub import hf_hub_download

MODELS = r"C:\DD501_Sanbox\ComfyUI_windows_portable\ComfyUI\models"

# (repo_id, repo_filename, destination absolute path)
JOBS = [
    ("Comfy-Org/z_image",
     "split_files/diffusion_models/z_image_bf16.safetensors",
     os.path.join(MODELS, "diffusion_models", "z_image_bf16.safetensors")),
    ("Comfy-Org/z_image_turbo",
     "split_files/text_encoders/qwen_3_4b.safetensors",
     os.path.join(MODELS, "text_encoders", "qwen_3_4b.safetensors")),
    ("Comfy-Org/z_image_turbo",
     "split_files/vae/ae.safetensors",
     os.path.join(MODELS, "vae", "ae.safetensors")),
]


def fetch(repo_id, repo_filename, dest):
    if os.path.exists(dest):
        print(f"SKIP (exists): {dest}", flush=True)
        return
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)
    print(f"DOWNLOAD {repo_id}/{repo_filename}", flush=True)
    # Download straight into the destination dir, then flatten split_files/ nesting.
    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=repo_filename,
        local_dir=dest_dir,
    )
    if os.path.abspath(local_path) != os.path.abspath(dest):
        shutil.move(local_path, dest)
    # Clean up the empty split_files/ tree left behind by local_dir.
    stray = os.path.join(dest_dir, "split_files")
    if os.path.isdir(stray):
        shutil.rmtree(stray, ignore_errors=True)
    size_gb = os.path.getsize(dest) / (1024 ** 3)
    print(f"DONE  {dest}  ({size_gb:.2f} GB)", flush=True)


if __name__ == "__main__":
    for job in JOBS:
        fetch(*job)
    print("ALL DONE", flush=True)
