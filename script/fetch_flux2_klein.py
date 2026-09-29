"""Install the commercially licensed FLUX.2 Klein 4B Base weight for ComfyUI.

The Qwen 3 4B text encoder and Flux2 VAE are already used by this project's
ComfyUI installation. Only the FP8 diffusion model needs to be downloaded.
"""

import argparse
import hashlib
from pathlib import Path

from huggingface_hub import hf_hub_download


REPO_ID = "black-forest-labs/FLUX.2-klein-base-4b-fp8"
FILENAME = "flux-2-klein-base-4b-fp8.safetensors"
SHA256 = "44bab3a86fe98b85d21dd2a4729ebdc3ae51fb8a39f76e457e18c724219e6840"
DEFAULT_MODELS = Path(r"C:\DD501_Sanbox\ComfyUI_windows_portable\ComfyUI\models")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS)
    args = parser.parse_args()
    model_dir = args.models_dir / "diffusion_models"
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / FILENAME

    if target.exists() and sha256_file(target) == SHA256:
        print(f"Already installed and verified: {target}")
        return

    print(f"Downloading {REPO_ID}/{FILENAME} to {model_dir}", flush=True)
    path = Path(hf_hub_download(repo_id=REPO_ID, filename=FILENAME, local_dir=model_dir))
    actual = sha256_file(path)
    if actual != SHA256:
        raise RuntimeError(f"SHA256 mismatch for {path}: {actual}")
    print(f"Verified SHA256 and installed: {path}")


if __name__ == "__main__":
    main()
