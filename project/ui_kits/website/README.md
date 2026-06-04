# afc.wallet — Corporate Website UI Kit

A high-fidelity interactive prototype of the afc.wallet corporate marketing website, built with React JSX components.

## Components

| File | Component | Description |
|---|---|---|
| `KitBase.jsx` | `KitButton`, `KitBadge`, `KitCard`, `kitStyles` | Base primitives — button variants, badges, cards, shared tokens |
| `NavBar.jsx` | `NavBar` | Sticky dark nav — wordmark, page links, login, CTA pill |
| `HeroBand.jsx` | `HeroBand` | Full-bleed dark hero — display headline, subline, dual CTAs |
| `FeatureGrid.jsx` | `FeatureGrid` | 3-up feature card grid on white canvas |
| `PlanSection.jsx` | `PlanSection` | 4-up plan comparison cards on dark canvas |
| `StatsBand.jsx` | `StatsBand`, `SignupModal` | Social proof stats + signup modal overlay |
| `FooterSection.jsx` | `DownloadBand`, `FooterSection` | App download tiles + multi-column footer |

## Pages

The `index.html` prototype includes three navigable pages:

- **Personal** (home) — Hero, stats, features, plan comparison, download CTA
- **Business** — Business-focused hero + feature grid
- **Company** — Mission statement + stats

## Interactive Features

- Click navigation between Personal / Business / Company pages
- "Get started" / "Log in" opens a signup modal with email + phone fields
- Plan selection opens the signup modal
- Hover states on all buttons, links, and footer items
- Submitted state in the signup modal

## Usage

Load `index.html` directly. All JSX components are loaded via Babel standalone. Requires internet for Google Fonts and React CDN.
