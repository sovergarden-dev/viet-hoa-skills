# Attribution & Upstream Notices

**viet-hoa-skills: Source-Faithful Vietnamese Game Localization Suite for Hermes Agent**

This project inherits concepts, workflows, and inspirations from the following open-source works:

---

## 1. Upstream Workflow & Architecture Inspiration
- **Project:** `kann420/VH-Workflow-Skill`
- **Repository:** https://github.com/kann420/VH-Workflow-Skill
- **License:** MIT License (Copyright (c) 2026 VH Workflow Skills)
- **Key Inherited Concepts:**
  - Concept of Directional Pronoun Matrix (Ma trận xưng hô hai chiều: người nói $\rightarrow$ người nghe)
  - Pre-translation deduplication and text normalization concepts
  - Contextual post-processing and glossary boundary protection

All inherited concepts have been refactored, hardened, and natively implemented in Python/CLI for Hermes Agent, with 6-tier deterministic rule resolution, compound false-positive suppression, reflexive pronoun detection, and fail-closed cross-process locking.

---

## 2. Contributions & Enhancements
- **Lead Maintainer & Author:** Rurus, Hermes Agent
- **Contributors:** `sovergarden-dev contributors`
- **Key Original Invariants & Innovations:**
  - Shared Invariants Contract (`CANONICAL-INVARIANTS-V1`: `INV-ATOM`, `INV-LOCK`, `INV-CSV`, `INV-RB`)
  - Cross-process byte-range locking with OS sentinel and atomic metadata sidecar (`hermes_io.py`)
  - Single-owner artifact state machine (`draft -> mt_done -> human_edited -> frozen`)
  - Dual-Weight SDFAA font fallback engine for Unity TextMeshPro (`fonttv`)
  - Standalone, zero-dependency vendoring mechanism (`tools/vendor_shared.py`)
