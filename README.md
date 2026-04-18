#Spec requirements Minimum
RTX 5070 TI 16GB
RAM 32GB

#Requirement 
comfyui
flux2-dev-nvfp4.safetensors
mistral_3_small_flux2_fp8.safetensors
flux2-vae.safetensors
RealESRGAN_x4plus.pth

Python 13.x
pillow
requests

#How to use
1) run comfyui with Requirement model
2) config promtp.json
3) run Generate.bat

#promtp.json
name = name
title = photo name
keywords =  keywords in Adobe Stock
category = category in Adobe Stock
positive, negative = promtp sent to comfyui
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
"title": "inamge2",
"keywords": "animal, dog, cat, fish",
"category": 0,
"positive": "dog, cat, fish",
"negative": "human, car"
}
]