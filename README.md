## Spec Requirements (Minimum)
* **GPU:** RTX 5070 TI 16GB
* **RAM:** 32GB

---

## Requirements
### Models & Tools
* `comfyui`
* `flux2-dev-nvfp4.safetensors`
* `mistral_3_small_flux2_fp8.safetensors`
* `flux2-vae.safetensors`
* `RealESRGAN_x4plus.pth`

### Dependencies
* **Python:** 13.x
* `pillow`
* `requests`

---

## How to use
1. Run **ComfyUI** with the required models loaded.
2. Configure your `promtp.json` file.
3. Run `Generate.bat`.

---

## prompt.json Structure
| Key | Description |
| :--- | :--- |
| `name` | File name |
| `title` | Photo name |
| `keywords` | Keywords for Adobe Stock |
| `category` | Category index for Adobe Stock |
| `positive` | Positive prompt sent to ComfyUI |
| `negative` | Negative prompt sent to ComfyUI |

### Example Config:
```json
[
  {
    "name": "name1",
    "title": "image1",
    "keywords": "animal, dog, cat, fish",
    "category": 0,
    "positive": "dog, cat, fish",
    "negative": "human, car"
  },
  {
    "name": "name2",
    "title": "image2",
    "keywords": "animal, dog, cat, fish",
    "category": 0,
    "positive": "dog, cat, fish",
    "negative": "human, car"
  }
]
