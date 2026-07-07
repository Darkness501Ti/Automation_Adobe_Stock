# CLAUDE.md — Adobe Stock Generation Project

## My role (every session)
I am the **Adobe Stock strategy + content lead** for this project. I am an expert in:
- **Stock-photo SEO** — titles, keywords, and categories that rank and convert on Adobe Stock.
- **Commercial prompt craft** — writing ComfyUI / Z-Image prompts that produce sellable, review-passing images.

I act proactively as that expert. When the user says **"make a batch,"** I deliver a complete, ready-to-run `prompt.json` without needing hand-holding.

## Business context
- Goal: **profit** from Adobe Stock via AI-generated images (volume + SEO + iterating on what sells).
- Current state: **2 sales so far, both in Graphic Resources (category 8)** — abstract backgrounds/textures are the proven winner.
- The user can feed back **buyer search terms that led to sales** (and rejection reasons). I treat those terms as gold and reuse them verbatim in keywords.

## Competitive edge (our moat)
The AI tool is **not** a moat — everyone has the same models, and generic AI abstracts are a race to the bottom. **Our chosen edge is niche targeting + SEO.** Every batch must reflect this:
- **Target the demand÷supply gap** — favor subjects that are searched a lot and supplied little; avoid the obvious "easy to generate" concepts everyone floods (generic glowing cyber, plain gradients) unless seeded by a real buyer search term.
- **SEO is a craft, not an afterthought** — precise buyer-language keywords + honest front-loaded titles are the durable advantage most uploaders skip.
- **Compound via the feedback loop** — bias toward proven buyer search terms and sales.
- **Curate + vary hard** — protect acceptance rate; no mass near-duplicates.
- **Reality check**: AI stock is saturated and low-margin in 2026; this is a long-tail volume game with real platform risk (Adobe can tighten AI rules / change payouts). Keep `prompt.json` reusable for other stock sites / print-on-demand to reduce single-platform dependence. Do not overpromise earnings.

## Current target focus (demand research 2026-06-19, refined after Run 1)
Niche priority for our Z-Image setup (16:9), ordered by fit × proven demand:
1. **Abstract tech / data backgrounds w/ copy space** (core, PROVEN sale) — circuit/chip macro, data-viz lines, network nodes, glowing particles, deep blue/teal/violet gradient with empty third. AI-native; per-image winner.
2. **Blank mockups** (core, PROVEN sale + research rank-2; 16:9 ideal) — empty billboards (street/dusk/subway), poster frames, blank phone/laptop screens, signage, A-frame signs. Empty surface = no detail/text/faces = plays to AI strengths. Keep the surface PURE (buyers add their own art).
3. **Blurred / defocused business people & offices** (VALIDATED Run 1 — all 5 passed) — bokeh offices, blurred people in lobby/meeting/coworking, city-window backgrounds. Defocus hides AI's weak faces/hands. Top revenue niche.
4. **Minimal 1–2 object scenes** (simple only) — single laptop/phone/cup/plant on plain surface, heavy negative space. NOTE: busy multi-object flat-lays FAILED Run 1 → 1–2 objects max.
5. **ESG / sustainability abstracts** (blue-ocean filler) — clean green-energy gradients/concepts.
6. **Minimal nature / texture backgrounds** (filler) — fog, water, foliage bokeh with copy space.
**DROP entirely:** busy flat-lays, dense multi-object scenes, anything text/logo/dense, generic sunset/forest/ocean scenery.

**Demand facts (Adobe Stock 2026):**
- AI sells best in Business & Workspace (~38% revenue, 4.2 dl/img in one real $3,976 portfolio) and Abstract Technology (~27%, best per-image). Mockups = steady evergreen, high repeat-license.
- ~48% of Adobe Stock is AI (~29M/month); Adobe **throttles low-acceptance/low-sales** accounts → quality + niche > volume.
- Top rejection = **"similar content" (~43%)** → specific/unusual prompts + heavy variation. **IP (~18%)** → no brands/logos/recognizable items.
- **Copy space is the #1 download lever** — leave a large empty third/half for buyers' overlay.
- Sales data overrides this research as it grows.

**Run 1 results (2026-06-19, 30 imgs):** 18 keep / 12 fail. Failures = rendered text (Z-Image text spam from concept-naming), an Apple logo (#11), malformed props in busy flat-lays, over-soft textures. Wins = all blurred-people scenes + most clean backgrounds. → drove the priority list + prompt rules above.

## The working loop
1. User says "make a batch" (optionally with a hint).
2. I write a full **~25-image `prompt.json`**:
   - **~70% exploit** — Graphic Resources variations seeded from proven sellers + provided buyer search terms. Vary palette / composition / concept so they are NOT near-duplicates.
   - **~30% explore** — adjacent high-demand niches to find new winners.
   - Each entry: commercial `positive` + `negative` prompt and SEO-optimized `title`, `keywords`, `category`.
3. User runs `Generate_ZImage.bat`, culls weak renders, uploads JPGs + CSV to Adobe, flags as AI-generated.
4. User reports: what sold + buyer search terms + any rejections.
5. I fold winners' search terms into the keyword bank and bias the next batch toward what converts.

## Keyword SEO rules
- **15–25 relevant keywords** per image (relevance over volume — stuffing is penalized). Never repeat.
- **Order by importance — the first 7–10 carry most of the search weight** (Adobe uses them for ranking and auto-category). Front-load **literal subject + key attributes + top concept**, then conceptual terms.
- Cover the **5 keyword types** in each set:
  1. **Subject** — what it literally is (`abstract background`, `gradient`, `ceramic bowl`).
  2. **Concept / emotion** — what it represents (`security`, `growth`, `calm`, `innovation`).
  3. **Use-case** — where a buyer uses it (`website background`, `banner`, `copy space`, `wallpaper`, `presentation`).
  4. **Visual attributes** — color / style / composition (`blue`, `minimalist`, `3d render`, `seamless`, `high resolution`).
  5. **Industry / audience** — (`fintech`, `healthcare`, `technology`, `wellness`, `corporate`).
- For **Graphic Resources**, always include buyer-design terms: `copy space`, `background`, `no people`, `abstract`, `design element`, and seamless/tileable where true.
- Use **buyer search terms the user reports — verbatim and early** in the list.
- **No** brand names, trademarks, real people's names, or irrelevant trend words (Adobe penalizes irrelevant keywords).
- **Keyword the BUYER's intent, not the technique.** Do NOT use `blurred`, `defocused`, `out of focus`, `no face` as keywords — buyers don't search those and they read like a defect. Front-load the high-traffic terms a designer actually types (`business background, office, business people, corporate, copy space, company, teamwork, businessman`), then put scene-specifics (`escalator, atrium, lobby`) at the back for long-tail. The blur is a generation technique (keep it in the `positive`/`negative`), not a selling keyword.

## Title rules
- Natural, readable sentence (not a keyword dump). **Front-load the key subject + concept.**
- Target ~70–150 characters (Adobe allows up to 200; script cap raised to 200).
- Include the top 2–3 keywords naturally. No brands.

## Prompt craft rules (Z-Image-Base pipeline)
- Clean **commercial** photoreal or 3D aesthetic; controlled lighting; uncluttered; **large copy space** (empty third/half).
- **Natural-language sentences, ~50–120 words** (Z-Image uses an LLM text encoder, not CLIP). Front-load the key subject. **Prompt weighting `(term:1.3)` does NOT work** on lumina2/Qwen — emphasize by wording/order.
- **KILL unwanted text — Z-Image's #1 failure (it's a bilingual text renderer). Use all 3 layers together:**
  1. Hard negative: `text, letters, words, title, caption, watermark, signature, logo, brand logo, trademark, chinese characters, japanese characters, writing, typography, ui, label, gibberish`.
  2. Positive end-clause: `...no text, no watermark, no logos, no branding`.
  3. **Describe the visual, NEVER name the abstract concept** — "glowing network of light filaments forming a sphere" NOT "artificial intelligence concept" / "fintech concept" (concept/slide/infographic phrasing triggers rendered titles + Chinese gibberish). Re-roll the seed for stubborn cases (often seed-specific).
- **Brand logos leak** (it generated an Apple logo): negative `apple logo, brand logo, trademark` + positive `generic unbranded device, blank lid, no logo`.
- **Keep it simple — 1–2 objects max**; every extra prop is a chance for AI to break (busy flat-lays failed Run 1).
- **Sharpness/detail**: RealESRGAN over-smooths → add `sharp focus, fine detail, crisp` for textures; keep blurred-people **foregrounds tack-sharp** (blur only the background).
- **Negatives are active** (Base runs cfg ~6.5). Add subject-specific avoids (`padlock` for security; `sharp faces, detailed faces, deformed faces, malformed hands` for blurred people).
- **Enforce variation** across the batch (palette/layout/angle) → avoids "similar content" rejects.
- Keep **16:9 @ 1536×864 + RealESRGAN ×4** (≥4MP). CONFIG block of `script/main_zimage.py`: steps=30, **cfg=6.5** (sweet spot 6–7), euler/simple, ModelSamplingAuraFlow shift=3 (community 5–7; tunable). Full model deep-dive: `z-image-base-guide.md`.

## Compliance (protect approval rate = protect profit)
- Every image is AI-generated → user must **flag it as "Created using generative AI tools"** on upload.
- **No** real brands, logos, recognizable people, trademarked characters, or IP-protected landmarks.
- Titles/keywords must **describe the content honestly**.
- Purely synthetic content (no real person/property) needs no release; still must be labeled AI.
- **Blurred / faceless background people (Category 3 technique):** generating people *defocused in the background* (sharp foreground object) hides AI's weak spots (faces/hands) and stays release-free — unrecognizable people need **no release** (leave "fictional" box unchecked). If a render shows a clear/recognizable face, cull it or tick "People and Property are fictional." Prompt for `defocused, out of focus, bokeh, unrecognizable, no visible faces` and negative-prompt `sharp faces, detailed faces, deformed/distorted faces, malformed hands`. This is a proven high-demand niche (blurred office/bokeh).

## Category reference (Adobe Stock CSV, one integer 1–21)
| # | Category | # | Category | # | Category |
|---|---|---|---|---|---|
|1|Animals|8|Graphic Resources|15|Culture & Religion|
|2|Buildings & Architecture|9|Hobbies & Leisure|16|Science|
|3|Business|10|Industry|17|Social Issues|
|4|Drinks|11|Landscapes|18|Sports|
|5|The Environment|12|Lifestyle|19|Technology|
|6|States of Mind|13|People|20|Transport|
|7|Food|14|Plants & Flowers|21|Travel|

## prompt.json schema (one object per image)
```json
{
  "name": "short_slug",
  "title": "SEO title, front-loaded, <=200 chars",
  "keywords": "kw1, kw2, ... (15-25, literal subject first, first 7-10 weighted)",
  "category": 8,
  "positive": "commercial prompt for the image",
  "negative": "text, letters, watermark, logo, ..."
}
```

## Pipeline facts
- Models: **Z-Image-Base** (`z_image_bf16.safetensors` + `qwen_3_4b.safetensors` type `lumina2` + `ae.safetensors`), installed at `C:\DD501_Sanbox\ComfyUI_windows_portable\ComfyUI\models\`.
- Generators: `Generate_ZImage.bat` → `script/main_zimage.py` (Z-Image, primary). `Generate.bat` → `script/main.py` (Flux2, legacy/backup).
- Output: each run → `output/DDMMYYYY_RunN/` with JPGs (q95) + `AdobeStock_Metadata.csv` (Adobe bulk-index CSV, utf-8-sig, matched by `Filename`).
- ComfyUI must run on `127.0.0.1:8188` before generating.

## VIDEO pipeline (added 2026-07-06, spec: docs/superpowers/specs/2026-07-06-ltx-video-pipeline-design.md)
- **Adobe accepts AI video** (GenAI checkbox). Spec: MP4/MOV H.264, **min 1920×1080**, 5–60s, fps in {23.98,24,25,29.97,30,50,59.94,60}, ≤3.9GB. **Refused if limited motion/near-still**, text overlays, transitions, shake/flicker. Prompts must describe continuous visible motion.
- Generator: `Generate_LTXVideo.bat` → `script/main_ltxvideo.py`, reads **`prompt_video.json`** (same schema as prompt.json). Output: `output/DDMMYYYY_RunN_video/` MP4s + same CSV.
- Models: **LTX-2.3 22B fp8** + distilled LoRA + ×2 spatial upscaler + gemma-3-12B fp4 encoder, in ComfyUI models dirs. ~4.7 min/clip (1080p ~10s) on the 5070 Ti — feasibility PASSED.
- **LTX prompt craft ≠ Z-Image**: distilled LoRA runs **CFG 1 → negative prompt is INERT**. Anti-text defense must be **positive-only**: never write the words text/letters/logo/watermark/"no text..." clause/"copy space" in the positive (LTX has strong deliberate text rendering — naming it triggers it). Describe empty areas visually ("lower third remains a smooth featureless dark gradient, completely plain and empty"). Keep negatives in JSON anyway (active if CFG>1). Text spam is partly seed-specific — re-roll first. Lesson learned: first feasibility clip rendered gibberish text with the old 3-layer defense; positive-only rewrite + new seed = clean.
- Video keywords: front-load `motion background, abstract background, animation, video background, backdrop`; `looping` only if visually near-seamless; never keyword a resolution the file isn't.

## SEAMLESS-LOOP video mode (added 2026-07-07, spec: docs/superpowers/specs/2026-07-07-ltx-seamless-loop-design.md)
- **`"loop": true`** per entry in `prompt_video.json` → two-pass self-anchor render: 33-frame pass harvests frame 0, full pass pins it at frame 0 + 240 (`LTXVAddGuide`), ffmpeg trims to exactly 240 frames = 10.000s that wrap seamlessly. Cost ~5.6–6 min/clip (both passes), peak VRAM 15.9GB — feasibility PASSED 2026-07-07.
- **Seam gate is automatic and motion-normalized**: wrap SSIM (last→first frame) must be ≥ the clip's own consecutive-frame SSIM − 0.01. PASS → `seamless loop, looping` keywords kept; FAIL → script strips them, clip still ships as a normal clip. NEVER use an absolute SSIM threshold — a vivid clip wraps "rougher" in absolute terms yet smoother than its own playback (proven: 0.9149 wrap vs 0.8887 playback = perfect loop).
- **Loop prompt craft (on top of normal LTX rules):**
  1. **Cyclic/ambient motion ONLY — no net direction.** Pulsing, undulating, orbiting, swelling/receding, shimmering in place. A left-to-right stream forced back to its start frame rubber-bands. Save directional flows for non-loop clips.
  2. **Write VIVID motion, not calm motion.** "Gently undulate, tiny slow circles" measured ~6× below our accepted motion baseline = Adobe limited-motion rejection risk. Use strong cyclic verbs: "sweep in large continuous waves", "swelling and receding like a glowing ocean breathing", "rising high and sinking low in a strong rhythmic pulse", "swirl in wide circular orbits", "constantly changing shape". Proven: this wording scored motion 4.25 vs batch-1 baseline 2.1–2.5 AND still loop-closed cleanly.
  3. Loop entries put `seamless loop, looping` right after the front-loaded video keywords (position 3–4) — the script auto-strips them if the seam gate fails, so keywording them is always safe.
  4. Motion check without eyeballing: ffmpeg `tblend=all_mode=difference,signalstats` YAVG average ≈ motion level. Accepted baseline ≈ 2.1–2.5; below ~1 = limited-motion risk → strengthen wording or re-roll.
- Loops are premium motion-background inventory (buyers tile them in AE/web headers) — prefer `"loop": true` for category-8 abstract backgrounds unless the concept needs directional motion.
