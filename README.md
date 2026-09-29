# Adobe Stock image and video generator

## Image model

The default image launcher, `Generate.bat`, runs **FLUX.2 Klein 4B Base FP8**
through `script/main_flux2_klein.py`. The model is Apache 2.0 licensed for
commercial use. The project also retains `Generate_ZImage.bat` for the earlier
Z-Image pipeline and `Generate_LTXVideo.bat` for video.

Hardware used here: RTX 5070 Ti with 16 GB VRAM and 32 GB system RAM.

### Install the image model

1. Install or update ComfyUI so it includes `Flux2Scheduler` and
   `EmptyFlux2LatentImage`.
2. Install Pillow and `huggingface_hub` in the Python used by `py`.
3. Run `py script/fetch_flux2_klein.py`. It downloads and SHA256-verifies only
   `flux-2-klein-base-4b-fp8.safetensors` from Black Forest Labs into the
   configured ComfyUI `models/diffusion_models` folder. The existing
   `qwen_3_4b.safetensors`, `flux2-vae.safetensors`, and
   `RealESRGAN_x4plus.pth` files are reused.

The downloader's default ComfyUI path is set for this PC. On another PC, pass
`--models-dir PATH` to point it at that ComfyUI installation's `models` folder.

### Generate images

1. Start ComfyUI on `127.0.0.1:8188`.
2. Review `prompt.json`, which contains 50 Graphic Resources prompts. Edit it
   before generating a new batch.
3. Run `Generate.bat`, or run `py script/main_flux2_klein.py --limit 1` for a
   single-image test.

The script generates one prompt at a time at 1280×720, uses 30 steps and CFG 5,
upscales 4× with RealESRGAN, and writes JPGs, an Adobe Stock metadata CSV, and
a seed manifest to `output/DDMMYYYY_RunN_klein/`. A failed run exits with an
error and retains successfully completed images and their matching CSV rows.
Check every render for visual defects, unwanted text, logos, and similarity
before uploading. Mark uploaded images as generated with AI on Adobe Stock.

`prompt.json` is an array of objects with `name`, `title`, `keywords`,
`category` (integer 1–21), `positive`, and `negative`. Titles and keywords go
to the CSV; positive and negative descriptions go to ComfyUI. Keep keyword
order by buyer relevance and verify metadata describes the final image.
Video generation requires a new `prompt_video.json`.

Model sources: [Black Forest Labs 4B Base FP8](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4b-fp8),
[ComfyUI FLUX.2 Klein guide](https://docs.comfy.org/tutorials/flux/flux-2-klein).
