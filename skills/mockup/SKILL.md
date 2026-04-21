---
name: mockup
description: Use when creating visual mockups, screenshot layouts, page previews, prototype arrangements, or data visualizations as self-contained HTML files. Triggers on 'mockup', 'create a mockup', 'layout mockup', 'screenshot preview', 'page preview', 'arrange screenshots', 'visual prototype', 'visualize this', 'make this pretty', 'visualize this markdown', 'visualize this document'.
---

# Mockup

Generate self-contained HTML mockup files — single file, inline CSS, zero dependencies, opens in any browser.

Supports two modes:
- **Asset mockups** — arrange screenshots, images, and designs into a visual layout
- **Data mockups** — transform markdown documents, research, tables, and structured data into beautiful visual dashboards

## Step 1: Load Design Principles

**MANDATORY first action** — invoke the frontend-design skill before any design decisions:

```
Skill tool → skill: "frontend-design:frontend-design"
```

This loads anti-slop design thinking (distinctive typography, bold color, spatial composition). The mockup skill provides *structure*, frontend-design provides *taste*.

## Step 2: Understand the Mockup

Ask (or infer from context):
- **What** is being mocked up? (app screenshots, page layout, component arrangement, wireframe)
- **Who** sees it? (internal review, client presentation, marketing team)
- **What assets exist?** Use Glob to find screenshots/images in the project

## Step 3: Gather Assets

```
Glob: **/screenshots/**/*.png
Glob: **/marketing/**/*.{png,jpg}
Glob: **/public/**/*.{png,jpg}
```

Confirm paths exist before referencing. Use `file:///` absolute paths for local assets.

## Step 4: Write the HTML

### Output Rules

- **One file** — everything inline (CSS in `<style>`, no external sheets/scripts)
- **Local assets** — reference via `file:///C:/absolute/path/to/image.png`
- **Responsive** — media queries for mobile breakpoints
- **Dark by default** — override if user specifies otherwise

### Default Design Tokens (Litesuite.dev)

```css
:root {
  --bg: #0a0a0b;
  --text: #e8e0d4;
  --accent: #c9a24d;
  --accent-hover: #e0b85a;
  --muted: #8a8078;
  --dim: #6a6560;
  --subtle: #3a3530;
  --surface: rgba(20,18,16,0.8);
  --border: rgba(255,255,255,0.06);
  --accent-border: rgba(201,162,77,0.15);
  --accent-bg: rgba(201,162,77,0.12);
}
```

Adapt tokens freely for non-litesuite brands. Frontend-design's aesthetic direction guides the palette.

### Layout Components

Use these as building blocks — mix and match based on content:

**Nav** — Sticky top bar with anchor links to sections
```html
<nav class="nav">
  <span class="logo">Title</span>
  <a href="#section">Section</a>
</nav>
```

**Section** — One per app/feature/topic. Header with optional badges, tagline, description.
```html
<section class="app-section" id="name">
  <div class="app-header">
    <span class="app-badge">Badge</span>
  </div>
  <h1 class="app-name">Name</h1>
  <p class="app-tagline">One-line hook</p>
  <p class="app-desc">2-3 sentence description</p>
</section>
```

**Screenshot** — Full-width image with floating label and caption
```html
<div class="screenshot">
  <span class="label">Label</span>
  <img src="file:///path/to/image.png" alt="Description">
</div>
<p class="screenshot-caption">What this shows and why it matters</p>
```

**Feature Grid** — 2-column cards with image + text
```html
<div class="feature-grid"> <!-- grid-template-columns: 1fr 1fr -->
  <div class="feature-card">
    <img src="..." alt="...">
    <div class="info"><h4>Title</h4><p>Description</p></div>
  </div>
</div>
```

**Three Grid** — 3-column for secondary screens
```html
<div class="three-grid"> <!-- grid-template-columns: 1fr 1fr 1fr -->
```

**Layout Strip** — 4-column horizontal for mode/variant comparison
```html
<div class="layout-strip"> <!-- grid-template-columns: repeat(4, 1fr) -->
```

**Notes Box** — Strategy callout with monospace prefix
```html
<div class="notes">
  <h5>Section Title</h5>
  <li>Note with // prefix styling</li>
</div>
```

### CSS Pattern

Each component needs its own styles. Reference the exemplar at `C:/Projects/litesuite.dev/mockups/app-screenshots-preview.html` for the full CSS implementation — adapt and extend for the specific mockup.

Key CSS patterns:
- `backdrop-filter: blur()` on nav
- `border-radius: 10-12px` on cards
- `aspect-ratio: 16/10` + `object-fit: cover` on grid images
- Monospace `letter-spacing: 0.15em` for section labels
- Gold accent borders at low opacity (`rgba(201,162,77,0.15)`)

## Section Ordering Strategy

For marketing/product mockups, order sections by impact:
1. **Hero** — the scroll-stopper, the thing nobody else has
2. **Feature grid** — capabilities that create desire
3. **Modes/variants** — depth and flexibility
4. **Compositions** — workflow examples showing panels together
5. **Emotional closer** — reward for scrolling (goes LAST, not first)

Skip utility screens (settings, terminal) unless specifically requested.

## Footer

Include a generation stamp:
```html
<div style="padding:60px 32px;text-align:center;color:var(--subtle);font-size:13px;">
  Mockup generated YYYY-MM-DD
</div>
```

---

## Data Visualization Mode

When the user wants to visualize a markdown document, research report, or structured data (tables, comparisons, timelines, metrics), use these additional components.

### Step 1: Read the Source

Read the full markdown file. Identify:
- **Hero stats** — pull out the 3-5 most impactful numbers
- **Sections** — each `##` heading becomes a visual section
- **Tables** — transform into styled comparison tables, card grids, or bar charts
- **Lists** — transform into card grids, gap analyses, or tier lists
- **Comparisons** — transform into side-by-side panels or threat maps

### Data Components

**Hero Banner** — Big serif headline + subtitle + 3-5 stat counters
```html
<div class="hero">
  <div class="hero-label">CATEGORY LABEL</div>
  <h1>Big <em>impactful</em> headline</h1>
  <p class="hero-sub">Supporting context paragraph</p>
  <div class="hero-stats">
    <div class="hero-stat"><div class="num">$251B</div><div class="label">Market by 2034</div></div>
  </div>
</div>
```

**Threat/Competitor Cards** — Color-coded grid with tier badges
```html
<div class="threat-card tier-mega"> <!-- tier-mega (red), tier-challenger (orange), tier-us (gold) -->
  <div class="threat-header">
    <span class="threat-name">Competitor</span>
    <span class="threat-badge badge-mega">Mega</span>
  </div>
  <div class="threat-stars">247K <span>GitHub stars</span></div>
  <div class="threat-desc">Description with key details.</div>
  <div class="threat-tags">
    <span class="threat-tag">tag1</span>
    <span class="threat-tag" style="color:var(--red)">warning-tag</span>
  </div>
</div>
```

Card tiers use colored top borders: red (mega threat), orange (challenger), blue (framework), purple (native/platform), gold (us).

**Side-by-Side Comparison** — Danger vs. safe, before vs. after, them vs. us
```html
<div class="security-grid"> <!-- grid-template-columns: 1fr 1fr -->
  <div class="sec-card danger">
    <h4>⚠ Their Problems</h4>
    <div class="sec-item"><span class="sec-dot"></span>Problem detail</div>
  </div>
  <div class="sec-card safe">
    <h4>☑ Our Advantages</h4>
    <div class="sec-item"><span class="sec-dot"></span>Advantage detail</div>
  </div>
</div>
```

**Comparison Table** — Highlight our column with gold background
```html
<table class="comp-table">
  <tr><th>Feature</th><th class="us-col">Us</th><th>Them</th></tr>
  <tr><td>Feature</td><td class="comp-highlight"><span class="check">✓ Yes</span></td><td><span class="cross">✗ No</span></td></tr>
</table>
```

Use `check` (green), `cross` (red), `partial` (orange) classes for status indicators.

**Gap / Priority List** — Numbered items with priority badges
```html
<div class="gap-item">
  <div class="gap-num">01</div>
  <div class="gap-info"><h4>Title</h4><p>Description</p></div>
  <span class="gap-priority priority-critical">Critical</span> <!-- or priority-high, priority-medium -->
</div>
```

**Horizontal Bar Chart** — For pricing, metrics, or ranked comparisons
```html
<div class="price-row">
  <span class="price-name">Label</span>
  <div class="price-bar-wrap">
    <div class="price-bar-fill" style="width:78%;background:var(--red);">$39/mo</div>
  </div>
  <span class="price-model">Category</span>
</div>
<div class="price-row ours"> <!-- .ours class highlights in gold -->
```

**Big Number** — For market size, revenue, or hero metrics
```html
<div class="market-num">$251B</div> <!-- Uses serif font, gold gradient -->
<div class="market-sub">Supporting context</div>
```

**Strategy Cards** — Gold-bordered cards with numbered plays
```html
<div class="strat-card">
  <div class="strat-num">PLAY 01</div>
  <h4>Strategy Title</h4>
  <p>Description of the strategic move.</p>
</div>
```

**Tier List** — Prioritized feature roadmap with status badges
```html
<div class="tier-section tier-1"> <!-- tier-1 (red), tier-2 (blue), tier-3 (purple) -->
  <div class="tier-label">Tier 1 — Must Have</div>
  <div class="tier-list">
    <div class="tier-item">
      <span class="tier-icon"></span>Feature name
      <span class="has-it">HAVE IT</span> <!-- optional, green, right-aligned -->
    </div>
  </div>
</div>
```

**Use Case Cards** — Compact cards with time-saved metric
```html
<div class="usecase-card">
  <div><h5>Use Case Title</h5><p>Brief description</p></div>
  <span class="usecase-time">10+ hrs/week</span> <!-- green, monospace -->
</div>
```

### Data Visualization Color System

Use semantic colors consistently:
- **Gold** (`--gold: #c9a24d`) — us, our advantages, accents
- **Red** (`--red: #e85450`) — threats, dangers, critical priority
- **Orange** (`--orange: #fb923c`) — warnings, challengers, high priority
- **Green** (`--green: #4ade80`) — success, advantages, "have it" badges
- **Blue** (`--blue: #60a5fa`) — neutral info, frameworks, medium priority
- **Purple** (`--purple: #a78bfa`) — platform/native tier, delight features

### Data Section Ordering

For research/intelligence documents:
1. **Hero** — the headline numbers that make someone stop scrolling
2. **Landscape/Threat Map** — who the players are (card grid)
3. **Vulnerability/Comparison** — side-by-side us vs. them
4. **Feature Table** — detailed head-to-head comparison
5. **Gap Analysis** — what's missing, prioritized
6. **Use Cases** — real-world value proof
7. **Pricing/Metrics** — bar charts and numbers
8. **Market Size** — the big opportunity number
9. **Strategy** — our plays and roadmap
10. **Tiers/Roadmap** — what to build in what order

### Font Stack for Data Mockups

```css
--mono: 'DM Mono', monospace;     /* numbers, labels, badges, tags */
--serif: 'Instrument Serif', serif; /* hero headlines, big numbers */
--sans: 'DM Sans', sans-serif;     /* body text, descriptions, cards */
```

Import: `https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap`

### Reference Exemplar

The competitive intelligence visual at `C:/Projects/LiteAgent/docs/competitive-intelligence-visual.html` is the canonical example of a data mockup. It demonstrates every component above in a real 1000+ line production file. Read it when building data visualizations to match the quality bar.
