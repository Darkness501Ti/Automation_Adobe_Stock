import urllib.request
import urllib.parse
import json
import time
import os
import csv
import random
import io
from PIL import Image
from datetime import datetime

# 1. Setup Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_FILE = os.path.join(BASE_DIR, "prompt.json")
OUTPUT_BASE = os.path.join(BASE_DIR, "output")

if not os.path.exists(OUTPUT_BASE):
    os.makedirs(OUTPUT_BASE)

# 2. Generate Output Folder (ddmmyyyy_X)
today_str = datetime.now().strftime("%d%m%Y")
run_num = 1
while True:
    OUTPUT_DIR = os.path.join(OUTPUT_BASE, f"{today_str}_Run{run_num}")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        break
    run_num += 1

COMFY_URL = "http://127.0.0.1:8188"

# 3. ComfyUI API Functions
def queue_prompt(prompt_workflow):
    data = json.dumps({"prompt": prompt_workflow}).encode('utf-8')
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())

def get_history(prompt_id):
    with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{COMFY_URL}/view?{url_values}") as response:
        return response.read()

# 4. Build the Mega-Graph Payload
def build_mega_workflow(prompts):
    # These loader nodes are shared and only loaded ONCE by ComfyUI
    workflow = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux2-dev-nvfp4.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "RealESRGAN_x4plus.pth"}}
    }

    # Dynamically generate nodes for EVERY prompt in the JSON file
    for i, item in enumerate(prompts):
        idx = i + 1
        lat_id  = f"10{idx}"
        pos_id  = f"20{idx}"
        neg_id  = f"30{idx}"
        sam_id  = f"40{idx}"
        vae_id  = f"50{idx}"
        up_id   = f"60{idx}"
        save_id = f"70{idx}"

        workflow[lat_id] = {"class_type": "EmptyLatentImage", "inputs": {"width": 1536, "height": 864, "batch_size": 1}}
        workflow[pos_id] = {"class_type": "CLIPTextEncode", "inputs": {"text": item["positive"], "clip": ["2", 0]}}
        workflow[neg_id] = {"class_type": "CLIPTextEncode", "inputs": {"text": item["negative"], "clip": ["2", 0]}}
        workflow[sam_id] = {"class_type": "KSampler", "inputs": {"seed": random.randint(1, 1000000000000), "steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0, "model": ["1", 0], "positive": [pos_id, 0], "negative": [neg_id, 0], "latent_image": [lat_id, 0]}}
        workflow[vae_id] = {"class_type": "VAEDecode", "inputs": {"samples": [sam_id, 0], "vae": ["3", 0]}}
        workflow[up_id]  = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["4", 0], "image": [vae_id, 0]}}
        workflow[save_id] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"StockGen_{idx}", "images": [up_id, 0]}}

    return workflow

def main():
    print(f"Starting batch generation...")
    print(f"Output folder created: {OUTPUT_DIR}\n")
    
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    print(f"Building Mega-Graph for {len(prompts)} prompts...")
    workflow = build_mega_workflow(prompts)
    csv_data = []

    try:
        res = queue_prompt(workflow)
        prompt_id = res['prompt_id']
        print("Mega-Graph sent to ComfyUI! Waiting for all generations to complete...")
        
        # Poll ComfyUI History until the entire batch finishes
        while True:
            history = get_history(prompt_id)
            if prompt_id in history:
                print("\nBatch processing complete! Downloading and optimizing images...")
                outputs = history[prompt_id]['outputs']
                
                for i, item in enumerate(prompts):
                    idx = i + 1
                    save_id = f"70{idx}"
                    
                    if save_id in outputs and 'images' in outputs[save_id]:
                        img_info = outputs[save_id]['images'][0]
                        
                        # 1. Download raw PNG bytes from ComfyUI
                        img_data = get_image(img_info['filename'], img_info['subfolder'], img_info['type'])
                        
                        # 2. Enforce Globally Unique Naming (Date_RunNum_ImageIdx.jpg)
                        final_filename = f"{today_str}_Run{run_num}_Image{idx}.jpg"
                        save_path = os.path.join(OUTPUT_DIR, final_filename)
                        
                        # 3. In-Memory JPEG Conversion (Bypasses SSD PNG write)
                        try:
                            # Load bytes into System RAM
                            img_byte_arr = io.BytesIO(img_data)
                            with Image.open(img_byte_arr) as img:
                                # Convert RGBA to RGB and save as commercial-grade JPEG
                                rgb_img = img.convert('RGB')
                                rgb_img.save(save_path, "JPEG", quality=95, subsampling=0)
                            
                            print(f" -> Saved (Optimized JPEG): {final_filename}")
                            
                            # Log Metadata for Adobe Stock CSV
                            csv_data.append({
                                "Filename": final_filename,
                                "Title": item["title"][:70],
                                "Keywords": item["keywords"],
                                "Category": item["category"],
                                "Releases": ""
                            })
                            
                        except Exception as cvt_error:
                            print(f" -> Error converting image {idx}: {cvt_error}")

                break
            time.sleep(3)
            
    except Exception as e:
        print(f" Error processing Mega-Graph: {e}")

    # 5. Write the Adobe Stock CSV Format
    csv_path = os.path.join(OUTPUT_DIR, "AdobeStock_Metadata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Filename", "Title", "Keywords", "Category", "Releases"])
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"\nBatch complete! CSV and Images saved to {OUTPUT_DIR}")

if __name__ == '__main__':
    main()