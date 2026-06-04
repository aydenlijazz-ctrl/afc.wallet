# afc.wallet Design System

A comprehensive design system for **afc.wallet** — a corporate fintech website offering digital wallet, payment, and financial management services. This system captures the visual language, typography, color palette, spacing, and UI components needed to build on-brand interfaces and marketing surfaces.

## Product Context

**afc.wallet** is a fintech product in the digital wallet/payments space. The corporate website serves as the primary marketing surface — presenting the product's features, subscription plans, and onboarding flows to potential users. The visual language is inspired by modern fintech brands: high-contrast, editorial, product-photography-led, with a stark two-mode canvas system (black storytelling bands / white catalogue bands).

The brand identity centers on a **cobalt-violet accent** (`#494fdf`) used sparingly as a brand stamp, with the primary interaction surface being white-pill CTAs on dark backgrounds. The overall feel is confident, precise, and premium — fintech-meets-editorial-brochure.

## Sources

This design system was built from the following reference:

- **GitHub:** [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) — `design-md/revolut/` subtree at `main` branch. Contains a comprehensive DESIGN.md with full color tokens, typography scale, spacing system, component definitions, and usage guidelines. Explore this repository for deeper token definitions and iteration guides.

## Products / Surfaces

| Surface | Description |
|---|---|
| **Corporate Website** | The primary marketing site — hero bands, feature grids, plan comparison, download CTAs, footer. Dark/light band alternation. |
| **Product Pages** | Individual product feature pages with photo-led hero bands and feature card grids. |

---

## CONTENT FUNDAMENTALS

### Tone & Voice
- **Confident and direct.** Short declarative headlines. No question marks in hero copy.
- **Second-person address** — speaks to "you" the user ("Join 70+ million using…", "Choose your subscription").
- **Numbers-forward** — metrics and social proof are featured prominently (user counts, feature quantities, pricing).
- **No emoji** in marketing copy. The brand conveys premium through restraint.
- **Sentence case** for all headlines and body copy. Button labels use sentence case ("Get started", "Learn more").
- **Minimal punctuation** — hero headlines rarely use periods. Feature descriptions are concise, 1–2 sentences max.

### Copy Style
- Hero headlines: 3–6 words, aspirational but grounded ("Banking & Beyond").
- Sub-headlines: functional, describe the value proposition in one line.
- Feature card copy: 1–2 sentences, factual, benefit-focused.
- Button labels: 2–3 words, action-oriented ("Get started", "Choose your subscription", "Compare plans").
- Plan names are single words: "Standard", "Plus", "Premium", "Metal", "Ultra".

### Casing Rules
- Headlines: Sentence case (only first word + proper nouns capitalized)
- Buttons: Sentence case
- Navigation: Title Case for top-level items ("Personal", "Business", "Company")
- Badges: Sentence case ("Most popular", "New")

---

## VISUAL FOUNDATIONS

### Color System
The brand operates on a **two-mode canvas**: true black (`#000000`) for storytelling/hero sections, pure white (`#ffffff`) for catalogue/browsing sections. These switch in full-bleed bands — no soft transitions.

- **Primary accent:** Cobalt violet `#494fdf` — used sparingly: featured plan cards, brand wordmark, secondary CTAs. Never as a theme color.
- **CTA strategy:** Primary CTA is a white pill on dark canvas. The cobalt accent is reserved, not the default action color.
- **Neutral scale:** 7-step ink-to-faint ladder for text hierarchy on light surfaces.
- **Dark text:** Two-step system — `#ffffff` for primary, `rgba(255,255,255,0.72)` for secondary.
- **Accent palette:** 8 saturated colors (teal, blue, pink, green, yellow, orange, red, brown) used only inside product illustrations — never as button surfaces.

### Typography
- **Display font:** Aeonik Pro 500 (substituted with **Plus Jakarta Sans** from Google Fonts). Used 20px–136px with tight `line-height: 1.0` and negative letter-spacing at large sizes.
- **Body font:** Inter 400/600. Positive tracking (`0.24px`) on UI labels for mechanical precision.
- **Hierarchy principle:** Display sizes tighten with negative letter-spacing as they grow. Body stays open with positive tracking.
- **Weight discipline:** Display = 500 only. Body = 400 (default) or 600 (emphatic). Never 500 on body.

### Spacing
- Base unit: 4px, working scale on 4/8/16 multiples.
- Section breathing room: 88–120px between bands.
- Card internal padding: 32px consistently.
- Whitespace is generous and editorial — lets display headlines register at scale.

### Backgrounds & Surfaces
- **Full-bleed color bands** — sections slam against each other, no gradients between them.
- **No background images or patterns** on canvas. The canvas IS the design.
- **Product photography** fills hero bands — phone/card/terminal mockups ARE the section content.
- **Surface elevation** via luminance shifts, not shadows: `#000000` → `#16181a` on dark, `#ffffff` → `#f4f4f4` on light.

### Borders & Shadows
- **No drop shadows.** Elevation is color-blocking + surface-luminance.
- **Hairline dividers** replace shadow: `#e2e2e7` on light, `rgba(255,255,255,0.12)` on dark.
- **1px solid borders** on light cards and outlined buttons. Never 2px+.

### Corner Radii
- Buttons & pills: `9999px` (fully rounded)
- Feature/plan cards: `20px`
- Inputs & tiles: `12px`
- Small tags: `8px`
- Hero bands & sections: `0px`

### Animation & Interaction
- **Hover:** Subtle opacity shifts. Dark buttons lighten slightly; light buttons darken. No scale transforms on buttons.
- **Press:** `button-primary-pressed` shifts to `#c9c9cd` background. Direct color change, no spring/bounce.
- **Transitions:** CSS transitions at ~200ms ease. No bounces, no overshoots. Restrained and precise.
- **Page transitions:** Full-bleed band switches are hard cuts — no fade between sections.

### Imagery
- **Product-led photography:** Phone mockups, card mockups, terminal/POS mockups.
- **Full-bleed placement** inside dark sections — the device IS the section.
- **Color temperature:** Cool-neutral. Device screens provide the only color in hero bands.
- **No lifestyle photography** in primary marketing. Product is the hero.
- **No grain, no filters.** Clean, sharp product renders.

### Cards
- No drop shadow — ever.
- Light cards: white surface, 1px `#e2e2e7` border, 20px radius, 32px padding.
- Dark cards: `#16181a` surface on `#000000` canvas, no border, 20px radius, 32px padding.
- Featured card: `#494fdf` cobalt-violet surface — one per grid, marks the recommended option.

---

## ICONOGRAPHY

### Approach
- The brand does **not** use a custom icon font or bespoke icon set in its marketing surfaces.
- **No emoji** in any context.
- **No unicode symbol icons.**
- Product feature illustrations use custom SVG/rendered graphics within product mockups — these are product-specific, not a reusable icon system.
- Navigation and UI chrome use minimal iconography: hamburger menu (mobile), chevrons for dropdowns, arrow-right for CTAs.
- Download tiles use platform logos (Apple, Google Play) as raster/SVG marks.

### Recommended Icon Set
For extending the design system with icons, use **Lucide Icons** (CDN-available) — they match the brand's stroke weight and clean geometric style:
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lucide-static@latest/font/lucide.min.css">
```

⚠️ **Substitution note:** No original icon assets were available in the source material. Lucide is recommended as the closest match to the brand's minimal, geometric icon style (1.5px stroke, rounded joins).

### Assets Available
- `assets/` — Contains the afc.wallet logo mark and wordmark as SVG.
- No additional icon sprites or illustration assets were available from source.

---

## FILE INDEX

| Path | Description |
|---|---|
| `README.md` | This file — overview, foundations, guidelines |
| `SKILL.md` | Agent skill definition for AI-assisted design |
| `colors_and_type.css` | CSS custom properties for all tokens (colors, type, spacing, radii) |
| `assets/` | Logo SVGs and brand marks |
| `preview/` | Design System tab preview cards (colors, type, spacing, components) |
| `ui_kits/website/` | Corporate website UI kit — interactive prototype with JSX components |

---

*Built from [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (design-md/revolut/ subtree). Explore the repository for full token definitions and iteration guides.*
