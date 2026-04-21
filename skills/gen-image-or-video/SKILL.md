---
name: gen-image-or-video
description: Use when generating AI images or videos — marketing visuals, hero banners, social media assets, product mockups, ad creative, animated backgrounds, exploding views, 3D renders, scroll-synced video assets. Triggers on 'generate an image', 'create an image', 'gen-image', 'make me an image', 'image gen', 'marketing image', 'product mockup', 'hero image', 'generate a video', 'create a video', 'gen-video', 'make me a video', 'video gen', 'animated background', 'exploding view', 'veo', 'video asset', 'scroll animation video'.
---

# AI Image & Video Generation

## Image Generation

Three tiers: **1) Gemini API** (default, Python script) → **2) LiteImage** (local SD) → **3) Kuroryuu Gateway** (SSE).

## Video Generation

Google Veo via Gemini API: **1) Text-to-video** → **2) Image-to-video** → **3) Video extension**.

---

## Step 1: Detect Media Type

Read the user's request. Determine if they need an **image** or a **video**:

- **Video signals:** "animated", "video", "scroll animation", "exploding view", "rotating", "3D animation", "hero background video", "motion", "cinematic", "panning shot", "Veo", "mp4"
- **Image signals:** "image", "banner", "mockup", "screenshot", "poster", "thumbnail", "png", "jpg"
- **Ambiguous:** Ask which they want via request_user_input.

---

## Step 2: Gather Parameters (MANDATORY)

**CRITICAL: You MUST call the request_user_input tool IMMEDIATELY as your FIRST action.** Do NOT respond with plain text. Do NOT ask questions via normal chat. Do NOT skip this step. Do NOT generate anything until request_user_input has been answered.

**The ONLY exception:** If the user's message explicitly provides ALL required parameters, skip straight to Step 3.

### For Images — collect these 5:

1. **Aspect ratio** — `1:1`, `3:4`, `4:3`, `9:16`, `16:9` (default), `21:9`
2. **Resolution** — `1K` (default), `2K`, `4K` (pro model only)
3. **Reference images** — paths or "none"
4. **Purpose** — hero banner, social post, ad, mockup, etc.
5. **Save location** — default: `~/Pictures/gen-image/`

### For Videos — collect these 6:

1. **Aspect ratio** — `16:9` (default) or `9:16`
2. **Resolution** — `720p` (default), `1080p`, `4k` (1080p/4k require duration=8)
3. **Duration** — `4`, `6`, or `8` seconds (default: 8)
4. **Model** — `fast` (default, $0.15/sec) or `standard` ($0.40/sec)
5. **Purpose** — hero background, scroll animation, product demo, social, etc.
6. **Save location** — default: `~/Videos/gen-video/`

**Also ask:** Do they have a starting image? (enables image-to-video mode)

### request_user_input templates:

**Image:**
```
Before I generate the image:

1. **Aspect ratio?** 16:9 (banner), 1:1 (social), 9:16 (story)? [default: 16:9]
2. **Resolution?** 1K, 2K, or 4K? [default: 1K]
3. **Reference images?** Any existing images to match the style? (paste paths or "none")
4. **Purpose?** Hero banner, social post, ad, mockup, etc.?
5. **Save to?** [default: ~/Pictures/gen-image/]
```

**Video:**
```
Before I generate the video:

1. **Aspect ratio?** 16:9 (landscape) or 9:16 (portrait)? [default: 16:9]
2. **Resolution?** 720p, 1080p, or 4k? [default: 720p]
3. **Duration?** 4, 6, or 8 seconds? [default: 8]
4. **Model?** fast (~$1.20/8s) or standard (~$3.20/8s)? [default: fast]
5. **Starting image?** Any image to animate from? (paste path or "none")
6. **Save to?** [default: ~/Videos/gen-video/]
```

**Omit any parameter the user already provided.**

### Red flags — if you're thinking any of these, STOP:
- "I'll just ask in chat" — NO. Use the request_user_input tool.
- "I have enough info" — Do you have ALL required params? If not, ask.
- "I'll use defaults" — The USER picks defaults, not you. Ask them.
- "Let me generate first and ask later" — WRONG ORDER. Ask first.

## Ongoing: Keep Asking Via request_user_input

After generating, you remain in generation mode. Any follow-up questions — regeneration, tweaks, batch requests — MUST go through request_user_input, NOT plain text.

**Stop condition:** Only stop if the user explicitly moves on to a different topic.

---

## Step 3: Generate

### Image — Gemini API (Default)

```bash
# Requires: pip install google-genai Pillow python-dotenv
# Env var: GOOGLE_AI_API_KEY (get from https://aistudio.google.com/apikey)
GEN="python ~/.codex/skills/gen-image-or-video/gen_image.py"

# Generate
$GEN output.png "SaaS dashboard, dark theme, modern UI" --aspect 16:9
$GEN output.png "Epic dragon" --aspect 16:9 --size 4K --model pro

# Reference images for style consistency (up to 14)
$GEN out.png "Same style, new subject" --ref style_ref.png

# Batch variations
$GEN out.png "cube" "sphere" "pyramid" --aspect 1:1

# Style template (.md with {subject} placeholder)
$GEN out.png "gear icon" --style styles/blue_glass_3d.md

# Edit existing image(s) — style transfer, multi-image mixing
$GEN edit out.png "Change background to blue" -i input.png
$GEN edit out.png "Merge these art styles" -i style1.png -i style2.png

# Describe / analyze images
$GEN describe image.png
$GEN describe a.png b.png --prompt "Compare these two images"
```

#### Image Models

| Alias | Model ID | Quality | Max Resolution |
|-------|----------|---------|----------------|
| `flash` | `gemini-2.5-flash-image` | Fast (default) | 1K |
| `pro` | `gemini-3-pro-image-preview` | Best | 4K |
| `legacy` | `gemini-2.0-flash-exp` | Fallback | 1K |

**Resolution:** `--size 1K` (default), `2K`, `4K` (pro only)
**Aspect ratios:** `1:1`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9` (default), `21:9`
**References:** Up to 14 images for style/composition guidance.

#### Model Selection Rules

Auto-select model based on quality signals in the user's message — no need to ask:

| Signal | Model | Examples |
|--------|-------|---------|
| **Cheap / fast** | `flash` (default) | "go cheap", "don't spend a lot", "quick image", "test this", "rough draft" |
| **High quality** | `pro` | "go big", "best quality", "really good", "4K", "hero image", "final version", "production ready", "make it perfect" |
| **No signal** | `flash` | default — save money unless quality is explicitly needed |

---

### Video — Google Veo (Gemini API)

```bash
# Requires: pip install google-genai python-dotenv
# Env var: GOOGLE_AI_API_KEY (same key as image gen)
VEO="python ~/.codex/skills/gen-image-or-video/gen_video.py"

# Text to video
$VEO out.mp4 "Cinematic aerial shot of a coastal city at golden hour"
$VEO out.mp4 "Rotating 3D globe, dark bg" --res 1080p --duration 8
$VEO out.mp4 "Exploding view of a house, white bg" --model standard --res 4k

# Generate multiple variants to pick the best
$VEO out.mp4 "Floating app icons orbiting a golden hub" --count 3

# Image to video (animate a still image)
$VEO i2v out.mp4 --image hero.png "Camera slowly pans across the scene"
$VEO i2v out.mp4 --image start.png --last-frame end.png "Smooth interpolation"

# Extend an existing video by ~7 seconds
$VEO extend longer.mp4 --input clip.mp4 "Continue the camera movement"
```

#### Video Models

| Alias | Model ID | Cost (720p/1080p) | Cost (4K) |
|-------|----------|-------------------|-----------|
| `fast` | `veo-3.1-fast-generate-preview` | $0.15/sec | $0.35/sec |
| `standard` | `veo-3.1-generate-preview` | $0.40/sec | $0.60/sec |
| `veo2` | `veo-2.0-generate-001` | $0.35/sec | — |

#### Cost Examples (8-second clip)

| Model | 720p | 1080p | 4K |
|-------|------|-------|-----|
| fast | $1.20 | $1.20 | $2.80 |
| standard | $3.20 | $3.20 | $4.80 |

#### Video Specs

| Property | Value |
|----------|-------|
| Format | MP4, 24fps |
| Resolutions | 720p (default), 1080p, 4K |
| Aspect ratios | 16:9 (landscape), 9:16 (portrait) |
| Duration | 4, 6, or 8 seconds per generation |
| Audio | Natively generated (Veo 3.1+) |
| Extension | +7 seconds per call, up to 20 extensions (~141s total) |
| Latency | 11s to 6 min depending on load |

#### Constraints

- 1080p and 4K require `duration=8`
- Video extension is 720p only
- Image-to-video uses `person_generation="allow_adult"` (not `"allow_all"`)
- Generated video URIs expire after 2 days — download immediately
- SynthID watermark embedded in all outputs

---

### Image Fallback 2: LiteImage API (Local SD)

If LiteImage is running — local Stable Diffusion on port **7426**.

```bash
curl -s -X POST http://127.0.0.1:7426/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Professional SaaS dashboard screenshot, dark theme",
    "width": 1024, "height": 576, "steps": 25,
    "guidance_scale": 7.5,
    "negative_prompt": "blurry, low quality, distorted"
  }' --max-time 300
```

Response includes `imagePath` (saved file) and `imageBase64` (inline). Check status first:

```bash
curl -s http://127.0.0.1:7426/status  # { ok, status, model, queueLength }
curl -s http://127.0.0.1:7426/models  # Available models
```

#### LiteImage Parameters

| Param | Default | Notes |
|-------|---------|-------|
| `prompt` | *required* | Image description |
| `width` | 512 | Pixel width |
| `height` | 512 | Pixel height |
| `steps` | 20 | Inference steps (20-30 for quality) |
| `guidance_scale` | 7.5 | Prompt adherence (5-12 range) |
| `negative_prompt` | "" | What to avoid |
| `seed` | -1 | -1 = random, set for reproducibility |
| `batch_count` | 1 | Number of images |

#### Common Sizes

| Use Case | Width | Height | Ratio |
|----------|-------|--------|-------|
| YouTube thumbnail / hero banner | 1280 | 720 | 16:9 |
| Instagram / Twitter post | 1024 | 1024 | 1:1 |
| Instagram/TikTok Story | 576 | 1024 | 9:16 |
| Blog / presentation | 1024 | 768 | 4:3 |
| Pinterest / Facebook ad | 768 | 1024 | 3:4 |

### Image Fallback 3: Kuroryuu Gateway (SSE)

If the Gateway is running on port **8200**, SSE streaming endpoint:

```bash
curl -X POST http://127.0.0.1:8200/v1/marketing/generate/image \
  -H "Content-Type: application/json" \
  -d '{"prompt": "...", "style": "photorealistic", "aspect_ratio": "16:9"}' \
  --no-buffer 2>/dev/null | while IFS= read -r line; do
    [[ "$line" == data:* ]] && echo "${line#data: }"
  done || true
```

**Gateway styles:** `photorealistic`, `illustration`, `3d-render`, `flat-design`, `cinematic`

---

## Prompt Engineering

### Image Prompts

**Structure:** `[Subject] + [Context/Setting] + [Style] + [Mood] + [Technical quality]`

```
"Young professional using laptop at modern coworking space,
 natural light, confident expression, photorealistic, 8k"
```

### Video Prompts

**Structure:** `[Camera movement] + [Subject/Action] + [Style] + [Background] + [Mood]`

```
# Hero background
"Slow cinematic orbit around floating holographic app icons,
 dark background with subtle gold particle effects, premium tech aesthetic"

# Exploding view (Nick Saraev style)
"High quality exploding view animation of a house showing interior design,
 white background, explodes in all directions vertically and horizontally,
 nothing goes outside the frame"

# 3D product rotation
"Rotating 3D globe with glowing data connections, dark background,
 center of mass stays fixed, smooth rotation on axis"

# Scroll-synced (generate then extract frames)
"Smooth zoom into a futuristic dashboard interface,
 camera pushes forward through layers of UI panels, dark theme with gold accents"
```

**Tips for video:**
- Specify camera movement (orbit, pan, zoom, dolly, static)
- Say "white background" or "dark background" for easy website integration
- Say "nothing goes outside the frame" to keep assets contained
- Generate 2-3 variants and pick the best one
- For scroll-synced: extract frames as JPEGs with ffmpeg after generation

### Post-Processing: Background Removal (MANDATORY for Images)

**After EVERY image generation, remove the background unless the user explicitly says to keep it.**

Gemini-generated images always have a solid background (usually white or light gray corners on icons/logos). Strip it immediately:

```python
python -c "
from PIL import Image
import numpy as np

img = Image.open('OUTPUT.png').convert('RGBA')
data = np.array(img)
r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

# Remove white/light corners (threshold 200+ on all channels)
white_mask = (r > 200) & (g > 200) & (b > 200)
data[white_mask, 3] = 0

Image.fromarray(data).save('OUTPUT.png')
"
```

Adjust the threshold based on the background color:
- **White backgrounds:** `> 200` on R, G, B
- **Light gray:** `> 180` on R, G, B
- **Specific color:** target that color's range

**When NOT to remove:** User says "keep background", "solid background", or the image is a photograph/scene (not an icon/logo/asset).

### Post-Processing: Frame Extraction for Scroll Animations

After generating a video for scroll-synced use:

```bash
# Extract frames as optimized JPEGs (for scroll-tied playback)
mkdir -p frames
ffmpeg -i video.mp4 -vf "fps=24" -q:v 2 frames/frame_%04d.jpg

# Or as WebP for better compression
ffmpeg -i video.mp4 -vf "fps=24" -quality 80 frames/frame_%04d.webp

# Compress hero video for web (background playback)
ffmpeg -i hero.mp4 -vcodec libx264 -crf 28 -preset slow -an hero_compressed.mp4
```

---

## Workflow

1. Detect media type (image vs video)
2. Gather parameters via request_user_input
3. **Image:** run `gen_image.py` (Gemini default) or LiteImage/Gateway fallback
4. **Image:** remove background (MANDATORY — see Post-Processing section)
5. **Video:** run `gen_video.py` (Veo default)
6. Review output (use Read tool on saved path)
7. Post-process if needed (frame extraction, compression)
8. Generate 2-3 variants for A/B testing when doing marketing work
