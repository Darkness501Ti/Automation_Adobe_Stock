# Z-Image-Base — Implementation Guide for ComfyUI Adobe Stock Pipeline

Research date: 2026-06-19. Target: `z_image_bf16.safetensors` (Z-Image-**Base**, non-distilled) in ComfyUI with UNETLoader + CLIPLoader(`qwen_3_4b`, type `lumina2`) + VAELoader(`ae.safetensors`) + ModelSamplingAuraFlow + KSampler, then RealESRGAN x4.

---

## 1. How Z-Image works

- **Architecture:** Scalable Single-Stream DiT (**S3-DiT**), 30 transformer layers, **6.15B params**. Unlike dual-stream (Flux/SD3), it concatenates **text tokens + visual semantic tokens + image VAE tokens** into ONE unified sequence. Higher param efficiency, faster inference, hits quality comparable to 20B+ closed models.
- **Text encoder:** **Qwen3-4B** (file `qwen_3_4b.safetensors`, ComfyUI type `lumina2`). It is an LLM, not CLIP. Z-Image was trained on prompts formatted as **Qwen3 chat conversations** (system/user roles). It does sentence-level semantic understanding — this is WHY it follows natural language so well and why CLIP tag-optimization doesn't apply. Bilingual (EN/ZH), which is also why it spontaneously renders text.
- **Variants:**
  - **Turbo** = distilled (Decoupled-DMD + RL). ~8-9 steps, **CFG≈1 (0)**, **NO negative prompt** (CFG internalized). Brittle outside its lane.
  - **Base** (yours) = non-distilled foundation. **28-50 steps, real CFG 4-9, negatives WORK.** Apache 2.0, made for fine-tuning. More controllable and diverse; Turbo is roughly equal or slightly ahead on raw photoreal "pop" but less steerable.
  - **Edit** = instruction-based image editing (i2i). Not relevant here.
- **Why ModelSamplingAuraFlow / shift:** Z-Image is a **flow-matching / rectified-flow** model (AuraFlow / Lumina2 sigma parameterization). `ModelSamplingAuraFlow` reparameterizes the noise/sigma schedule so the model receives correctly-scaled noise. The `shift` value biases the schedule toward high-noise (structure/composition) vs low-noise (detail) steps. **Wrong shift = degraded output.** Comfy reference ZIT workflow uses **shift=3**; community pushes 5-7 for Base for cleaner large-area control.
- **Flux VAE + EmptySD3LatentImage:** VAE is **Flux-derived, 16-channel** (`ae.safetensors`). Latent space matches SD3's channel layout, so you MUST feed **`EmptySD3LatentImage`**, not `EmptyLatentImage`. Other 16-ch VAEs (e.g. Wan) have different scaling factors → color shifts; use the official `ae.safetensors`.

---

## 2. Pros / Cons for commercial/stock

**Pros:** Top-tier photorealism for an open model (esp. skin), strong prompt adherence, excellent micro-detail, huge style range, runs on **16GB VRAM at bf16 with no aggressive quant** (~6B). Apache 2.0 = sell outputs, train LoRAs, no per-image API cost. Predictable/consistent across seeds — good for batch stock work.

**Cons / where it breaks:**
- Spontaneous **unwanted text / titles / Chinese gibberish / watermarks** — the #1 problem (Section 5).
- **Brand-logo leakage** (Apple logo etc.) — it has memorized brands.
- Base is **slow** vs Turbo: ~3-5s on strong GPUs, but reportedly **~6 min for 30 steps on a 4060 Ti 16GB**. Budget time for batch runs.
- **Over-smoothing** ("plastic" skin) at some sampler/step combos.
- Hands/faces/small objects can drift (melting earrings, pulsing logo edges, extra fingers).
- White speckle noise at high res (fixable with dejpeg LoRA).
- Base may need **SageAttention** to render correctly in ComfyUI/Forge (some setups output **black images** at FP16 otherwise — known bug). Use bf16; if black, install Sage/check precision.

---

## 3. Recommended settings (Z-Image-Base)

| Setting | Recommended | Range / notes |
|---|---|---|
| **Steps** | **30** | 28-50. More steps = detail/stability. 28 fine for most. |
| **CFG** | **6-7** (try 7.5 for clean banners) | Sweet spot 6-7. 4-5 creative/soft (drifts). 8+ over-constrained, artifacts. Acts like a smooth "dimmer," not on/off. |
| **Sampler** | **euler_ancestral** (smoother skin) or **euler** (sharper) | euler_ancestral beautifies skin/fabric/fine detail; euler looks slightly rougher/more "real." res_2s and res_multistep also strong. |
| **Scheduler** | **simple** (your current) or **res_2s** | Community combos: `euler_ancestral + res_2s @ 28 steps, CFG 7` (quality standard); `bong_tangent` needs 30-35 steps + lower CFG 5-6. |
| **ModelSamplingAuraFlow shift** | **3 (reference) → 5** | 3 = Comfy reference for ZIT. 5-7 = more noise/large-area control. Treat as finesse dial paired with steps. **Don't leave at Flux defaults.** |
| **Resolution** | **1024-base; 1536x864 OK** | Native sweet spot ~1024 (1MP). 1024x1024, 1024x768, 768x1024 all solid. Your 1536x864 is fine (16:9) but the further from ~1MP, the more speckle/artifact risk — upscale (you do) rather than gen huge. |
| **Latent node** | **EmptySD3LatentImage** | Mandatory (16-ch SD3 layout). |
| **VAE** | official `ae.safetensors` | Flux-derived, 16-ch. |

**Does CFG change quality/artifacts?** Yes. Higher CFG = stricter prompt adherence but past ~8 you get harsh edges, over-contrast, and **higher artifact rate**. Lower CFG = softer/vaguer, may ignore parts of prompt. For stock photoreal: **6-7**. For poster/text-heavy: 7-8. **Higher CFG also makes negatives bite harder** (see Section 5).

**CFG by use case:** Portraits 6-7 · Landscapes 5-6 · Product shots 7 · Text rendering 7-8 · Abstract 4-5.

---

## 4. Prompting best practices

- **Natural language sentences, NOT tag lists.** Qwen3 TE wants 100-300 token descriptive prose. Official rec: subject → mood → style order. Tags work but NL is more stable at inference. Avoid SDXL/Danbooru comma-tag dumps.
- **Length:** 80-250 words is the sweet spot. Default max 512 tokens (raise to 1024 only if needed). **Long AND precise = good; long AND poetic/"novel-y" = worse.**
- **Structure scaffold (front-load what matters):**
  `[Shot & subject] + [age & appearance] + [clothing] + [environment] + [lighting] + [mood] + [style/medium] + [technical: lens/4K] + [cleanup constraints]`
- **Lighting & camera keywords are high-leverage** — Z-Image responds strongly to `soft diffused daylight`, `50mm lens`, `shallow depth of field`, `studio portrait lighting`, `rim lighting`.
- **Prompt weighting `(term:1.3)`:** **Do NOT rely on it.** The Qwen3/`lumina2` encoder is an LLM, not CLIP — ComfyUI's parentheses-attention weighting does not map to it the way it does for SD/SDXL/Flux-CLIP. Effect is unreliable/ignored. **Emphasize by position (front-load) and by explicit wording / repetition in natural language instead.** ("Dark moody photo of a cat" emphasizes style more than "cat in a dark moody setting.")
- **System prompt / enhancer:** Z-Image trained with a chat system prompt. The official Tongyi **Prompt Enhancer** (an LLM that rewrites a brief idea into a long structured prompt) exists; community node `Comfyui-Z-Image-Utilities` exposes it (templates: auto/chinese/english/custom). Useful for batch stock, but **always edit the output** to strip flourish and add your cleanup constraints (no text/logos/watermark).

### Do / Don't
**DO:** write full sentences · front-load subject+style · specify lighting+lens · keep 80-250 words · keep one language per text chunk · end with cleanup constraints · use the enhancer then trim.
**DON'T:** dump comma tags · rely on `(x:1.3)` weighting · write purple/poetic prose · name abstract "concepts" loosely (triggers slide-title text) · name brands · over-stuff (causes overfit/clutter) · gen far above ~1MP.

---

## 5. THE KEY PROBLEM — killing unwanted text / letters / watermarks / Chinese gibberish

**Root cause:** Qwen3 is a strong bilingual text-renderer. When prompts name abstract **"concepts," "ideas," "topics," "themes,"** or anything poster/slide/infographic/document-shaped, the model infers it should render **titles, captions, labels, slide text** — often as EN/ZH gibberish or watermark-like marks. Naming brands triggers logos.

**Good news for you:** You run **Base**, not Turbo — so **negative prompts DO work** (Turbo ignores them at CFG≈1; Base respects them and they bite harder as CFG rises). Use BOTH a negative prompt AND positive-phrasing tactics.

### Concrete tactics (apply several together)
1. **Negative prompt (Base honors it).** Put in the CLIP Text Encode (Negative):
   `text, words, letters, typography, caption, title, subtitle, slogan, signage, label, watermark, signature, logo, brand, UI, interface, poster text, slide, chinese characters, gibberish text, writing`
   Keep it **topical/short** — don't overload or it warps composition.
2. **Raise CFG so negatives bite.** At CFG 6-7 negatives are effective; at ≤2-3 they barely register. If text still appears, nudge CFG up 1.
3. **Positive cleanup clause at the END of the prompt:** `...clean image, no text, no watermark, no logos, no captions, no writing of any kind.` Qwen3's instruction-following respects "no X" phrasing — works even where pure CFG-negation is weak. Place AFTER the main scene.
4. **Avoid the trigger words.** Don't say "a concept of X," "an idea about X," "infographic," "presentation," "slide," "poster," "diagram," "magazine cover," "document" unless you actually want text. **Rephrase abstractions into concrete visual scenes** — describe the photograph, not the concept. E.g. instead of "concept of teamwork" → "three colleagues collaborating around a laptop in a bright office."
5. **No surface that implies text.** Blank screens, plain walls, empty signage invite the model to fill them. Specify `blank screen`, `plain unmarked surface`, `empty wall`.
6. **Kill brand leakage explicitly.** Negative: `apple logo, brand logo, trademark, branded device`. Positive: `generic unbranded laptop/phone, no visible brand`.
7. **If a stubborn watermark/title persists:** vary the seed (it's often seed-specific), or crop/inpaint it out post-gen, or lower resolution toward 1MP (high-res large empty areas attract text artifacts).

> Note on intensity: write negatives at the same "loudness" as the desired style. Overly aggressive `no text` can also suppress *wanted* distant signage/patterns — if you DO want some incidental texture, soften to `minimize text artifacts`.

---

## 6. Other weaknesses & mitigations

| Issue | Mitigation |
|---|---|
| **Hands/limbs** | Positive: `correct human anatomy, natural hands and fingers`. Negative: `extra fingers, extra limbs, deformed hands`. |
| **Over-smooth / plastic skin** | Use **euler** (not euler_ancestral) for rougher realism; add `natural skin texture, visible pores, film grain`; slightly lower CFG; or detail-pass / face inpaint with reduced blur + slightly expanded mask. |
| **Brand-logo leakage (Apple etc.)** | Negative `brand logo, apple logo, trademark`; positive `generic unbranded device`. |
| **White speckle at high res / proportions** | Apply **dejpeg LoRA** (`ench-ZI-dejpeg_lite` / DeJPEG-LoRA, strength 1.0, model-only) — suppresses speckle AND improves anatomy. |
| **Small-object artifacts** | Keep near ~1MP and upscale (you already RealESRGAN x4); add `sharp focus, clean detailed`; avoid cramming many tiny objects. |
| **Background clutter** | `simple uncluttered background, plain studio background, nothing distracting behind subject`. |
| **Black image / broken render (Base)** | Use bf16; install **SageAttention**; verify `lumina2` clip type + `EmptySD3LatentImage` + `ModelSamplingAuraFlow` present. |

---

## 7. LoRAs, detail/upscaling, seeds

- **LoRAs:** Apache 2.0; trainable on Base. Tag lists OR natural language both train fine (Qwen3 interprets context either way); NL inference more stable. Character LoRAs: a single trigger word often enough — over-captioning overfits. Save as standard safetensors. **dejpeg LoRA** is the must-have quality fix.
- **Detail/upscale:** Your RealESRGAN x4 is appropriate. dejpeg LoRA before/at gen cleans speckle. Generate near native (~1024-1.5MP) then upscale rather than generating huge.
- **Seeds:** Unwanted text/watermarks are frequently **seed-specific** — re-rolling the seed is a legit fix. Fix seed for reproducible stock batches; randomize to escape a bad artifact pattern.

---

## Sources
- [Tongyi-MAI/Z-Image GitHub](https://github.com/Tongyi-MAI/Z-Image)
- [Z-Image-Turbo HuggingFace card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
- [Official PROMPTING GUIDE discussion (HF)](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/discussions/8)
- [Z-Image-Turbo Prompting Guide gist (illuminatianon)](https://gist.github.com/illuminatianon/c42f8e57f1e3ebf037dd58043da9de32)
- [ComfyUI Wiki — Z-Image-Turbo release](https://comfyui-wiki.com/en/news/2025-11-27-alibaba-z-image-turbo-release)
- [StableLearn Z-Image tutorial (arch, variants, FAQ)](https://stable-learn.com/en/z-image-turbo-tutorial/)
- [Apatero — Z-Image-Base best scheduler & sampler](https://apatero.com/blog/z-image-base-best-scheduler-sampler-guide)
- [MyAIForce — Z-Image samplers & schedulers](https://myaiforce.com/z-image-samplers-schedulers/)
- [RunComfy — Z-Image Base workflow](https://www.runcomfy.com/comfyui-workflows/z-image-workflow-in-comfyui-high-fidelity-image-generation)
- [DeepWiki — Z-Image (ZIT/Lumina2) workflow (node table, shift=3, dejpeg)](https://deepwiki.com/wildminder/ComfyUI-DyPE/4.4-z-image-(zit-lumina-2)-workflow)
- [WaveSpeed — What is Z-Image-Base (CFG control)](https://wavespeed.ai/blog/posts/blog-what-is-z-image-base/)
- [WaveSpeed — Base vs Turbo quality/negatives](https://wavespeed.ai/blog/posts/blog-z-image-base-vs-turbo/)
- [Neurocanvas — Base vs Turbo (SageAttention, cons)](https://neurocanvas.net/blog/zimage-base-vs-turbo-comparison/)
- [fblissjr QwenImageWanBridge — z_image_intro](https://github.com/fblissjr/ComfyUI-QwenImageWanBridge/blob/main/nodes/docs/z_image_intro.md)
- [fblissjr QwenImageWanBridge — z_image_encoder (VAE, encoder)](https://github.com/fblissjr/ComfyUI-QwenImageWanBridge/blob/main/nodes/docs/z_image_encoder.md)
- [Koko-boya — Comfyui-Z-Image-Utilities (prompt enhancer)](https://github.com/Koko-boya/Comfyui-Z-Image-Utilities)
- [Lilting — De-distilling Z-Image-Turbo / LoRA & captions](https://lilting.ch/en/articles/z-image-turbo-lora-dedistill-adapter)
