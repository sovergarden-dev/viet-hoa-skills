---
version: alpha
name: Locked VietHoa Installer Chassis
description: Borderless 1024x576 native patch installer. Artwork is the brand; the dock is a tool.
colors:
  primary: "#140D08"
  secondary: "#B9AEA0"
  tertiary: "#D88913"
  on-tertiary: "#140D08"
  neutral: "#0B0807"
  text: "#F1E8DA"
  error: "#D94A3D"
typography:
  body-md:
    fontFamily: Segoe UI
    fontSize: 15px
    fontWeight: 400
  label:
    fontFamily: Segoe UI Semibold
    fontSize: 14px
    fontWeight: 600
  action:
    fontFamily: Segoe UI Semibold
    fontSize: 15px
    fontWeight: 600
rounded:
  sm: 4px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    rounded: "{rounded.sm}"
    height: 36px
  button-secondary:
    backgroundColor: "#302722"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: 36px
---

## Overview

Reading this as a compact native Windows patch installer, not a landing page. Artwork is the brand. The dock is a transactional tool. Composition variance 5, motion 2, density 5. Borrow token discipline and anti-slop detectors from web design systems; do not copy chart cards, dashboards, glass heroes or kit pages.

Replace `tertiary` with one accent sampled from the supplied artwork. Keep Segoe UI. Do not invent a second palette.

## Colors

One accent. Warm off-black surfaces and bone text. No purple/blue glow, no generic glass, no pure `#000000` or `#FFFFFF` as large fills.

## Typography

Segoe UI for Vietnamese glyphs and native Windows familiarity. No decorative headline. Do not repeat a game title already present in the artwork.

## Layout

Locked chassis, not a suggestion:

- Borderless client `1024 x 576`.
- Full-bleed cover crop. No extra footer bar.
- Drag only empty artwork. Controls keep the default pointer.
- `Cài` and `Gỡ` share one Y and sit adjacent with a 0-24px gap.
- Build/version uses a fixed-width right-aligned cell with explicit right padding. Never `AutoSize` against the right edge.
- Taskbar minimize/restore via `ShowInTaskbar=true` and native `WS_MINIMIZEBOX`.
- Signature `Syrin.online` rainbow phase `0.045` in the bottom-right, 8px inner margin. No second footer.

Fill project-specific protected/safe rectangles in `installer-gui-layout.json` and pass `scripts/verify_installer_gui_layout.py` before promotion.

## Shapes

One radius: 4px. No pills mixed with square inputs.

## Components

Idle dock contains: build support, visible folder label, path, browse, `Cài`, `Gỡ`. Progress exists only during a real transaction. Diagnostics stay in modal/CLI.

## Do's and Don'ts

- Do sample the accent from the artwork and keep one color system.
- Do protect logo, title, faces, chin line and the dominant focal subject.
- Do verify 100/125/150% DPI and the exact compiled GUI, not a mockup.
- Do not copy Lieflat chart cards, Glance dashboards, or Impeccable web kit chrome.
- Do not add weather strips, version pills, decorative dots, centered glass cards or duplicate CTAs.
