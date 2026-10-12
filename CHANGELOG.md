# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-10-12
### 🚀 Official Stable Release Promotion
- **Promoted to Stable on Same Commit:** Promoted directly from `v1.1.0-rc.1` (commit `768d6a7e6603751996406958b8d0483d8a47322f`) following 100% pass on real-world multi-genre dogfooding validation (C29).
- **Dogfooding Validation Results (C29 Exit Criteria):**
  - Total real-world game lines audited: **7,866 lines** across 3 independent game projects (Classic RPG, Asian Mythology, and Adult Cyberpunk).
  - **Precision Rate: 100%** (4/4 flagged cases verified as True Positives on bureaucratic jargon softening).
  - **Recall Rate: 100%** (18/18 synthetic positive injection test cases detected across all 4 categories).
  - **Negative Controls: 0 False Positives** across 52 paired controls (including NFD decomposed variants and rich-text tags).
  - **P0 Blockers: 0**.
- **Audited & Approved:** Formally certified under Notion AI Red Team Round 4 verdict `SY07-R4-T6-PCDK-20261012-1BBC`.

## [Unreleased]

### Added
- **viethoa**: Bổ sung bộ lọc che chắn thẻ định dạng và biến nội suy (`INTERPOLATION_TAG_PATTERN` & `mask_tags_and_placeholders`) bảo toàn chuẩn C28 cho engine Ren'Py (`[player_name]`, `[name!u]`, `[x:.2f]`, `[[...]]`, `{{...}}`, `{color=...}`, `{b}`, `{i}`, `{u}`, `{s}`, `{w}`, `{p}`, `{nw}`, `{fast}`, `{a=...}`), Unity TMP (`<color=...>`, `<style=...>`, `<b>`, `<i>`), và code placeholders (`%(name)s`, `%s`, `{0}`, `${variable}`).
- **viethoa**: Bổ sung unit test `test_renpy_tag_isolation_and_formatting` bảo đảm đại từ bên trong thẻ không bị bóc tách nhầm thành xưng hô hội thoại.
- **viethoa**: Xây dựng Tier-1 Ren'Py placeholder mini-harness độc lập ngoài repo tại `_dogfood/renpy_tier1/` (75 dòng thoại synthetic, tuân thủ C26), đạt 100% trên cả 5 bất biến (Placeholder Parity, Tag Balancing, Tag Isolation, 0/50 Clean FP + 25/25 Dirty Recall, C28 100% NFC).
- **viethoa**: Mở rộng bộ kiểm thử hồi quy `skills/viethoa/scripts/tests/test_pronoun_validator.py` lên 32 ca lỗi synthetic và 52 ca chuẩn đối chứng (phủ toàn diện các bẫy từ đồng âm `con, ba, u, thầy, cháu`).
- **viethoa**: Bổ sung kiểm thử byte-exact Unicode NFC cho chuẩn C28, đảm bảo trường dữ liệu báo cáo luôn giữ nguyên dạng NFC bất biến kể cả khi nạp input NFD decomposed.
- **ci**: Ghim runner cố định `ubuntu-24.04 LTS`, thiết lập timeout 10 phút, ghim SHA commit cho `actions/checkout@11bd719` (# v4.2.2) và `actions/setup-python@4237552` (# v5.4.0), bổ sung job `canary-runner` trên `ubuntu-latest` (`continue-on-error: true`) và `.github/dependabot.yml`.
- **docs**: Ghi nhận phán quyết chính thức Notion AI Red Team Round 5 (`SY07-R5-T7-PCDK-20261012-E86E`).

### Fixed
- **viethoa**: Tái cấu trúc thứ tự ưu tiên trong `scan_dialogue_rows`: tra cứu ma trận quan hệ 6 cấp (`best_rule`) trước khi áp dụng rào chắn giới tính chưa xác định (`Unknown-Gender Guardrail`), tự động miễn trừ đại từ tự xưng hợp lệ của người nói (`allowed_self`).
- **viethoa**: Nâng cấp thuật toán `find_standalone_occurrences` kiểm tra trên chuỗi token gốc, phân biệt triệt để số từ `ba` (trước phân loại từ số lượng), danh từ thân tộc người cha `ba` (trước hạt hô ngữ), danh từ 1 ký tự `u` (trước từ tình thái mẹ), và cụm đại từ tập thể/phản thân (`anh em mình`, `tâm hồn mình`).

## [1.1.1-rc.1] - 2026-10-12

### Fixed
- **viethoa**: Nâng cấp lõi `scripts/pronoun_validator.py` sang kiến trúc Token-Window Standalone Occurrence Matching (`find_standalone_occurrences`), giải quyết triệt để vấn đề over-suppression và false positives trên các cụm từ quan hệ thân tộc.
- **viethoa**: Bổ sung bộ lọc tiền tố ngữ cảnh `LEFT_MODIFIERS` (`các`, `mấy`, `đám`, `lũ`, `nhóm`, `lời`, `tiếng`, `theo`, `nhờ`) và hậu tố chỉ định `RIGHT_DEMONSTRATIVES` (`ấy`, `đó`, `này`, `kia`), phân biệt chính xác đại từ gọi trực tiếp với danh từ sở hữu/tường thuật ngôi thứ ba (`lời anh dặn`) và đại từ nhóm (`các em`).
- **viethoa**: Mở rộng `COMPOUND_FALSE_POSITIVES` với các danh từ thân tộc và trạng từ phản thân (`anh trai`, `chị gái`, `em út`, `một mình`, `tự mình`, `chính mình`).
- **viethoa**: Mở rộng tập từ vựng thân tộc tiếng Việt (`ALL_SELF_PRONOUNS` bổ sung `mẹ, cha, bố, ba, má, thầy, u`; `DIRECT_CALL_PRONOUNS` bổ sung `con, cháu`).
- **viethoa**: Chuẩn hóa toàn diện hai chiều Unicode theo quy chuẩn C28: so khớp view qua `NFKC + casefold`, xuất bằng chứng và báo cáo giữ 100% chuẩn `NFC`.
- **viethoa**: Cập nhật tài liệu kỹ thuật `references/pronoun-consistency-policy.md` và bổ sung unit test đối chứng đạt Recall 100% (5/5) trên synthetic injections và Specificity 100% (0/7 FP) trên golden clean rows.

## [1.1.0-rc.1] - 2026-10-12
### ⚠️ Behavioral & Breaking Changes Warning
- **`domestication_detector.py` Exit Code Behavior:** Scans now exit with status code `1` whenever any violations are detected (previously informative). CI pipelines relying on strict status codes must handle this accordingly.
- **Detector Preprocessing View:** Matching now applies a strict whitelist tag-masking pass (stripping Unity TextMeshPro tags like `<color=...>`, `<sprite=...>` and placeholders like `{player}`, `{0}`, `%s` while preserving mathematical operators like `<` and `>`) combined with `NFKC` and `casefold()` on matching views. Output `source` and `target` remain 100% faithful in Unicode `NFC`.
- **18+ Content Notice:** Rule definitions and test suites explicitly cover adult terminology and colloquial slang to protect source-fidelity against administrative softening.

### Added
- **Anti-Domestication Detection Engine Expansion (P2b / C20, C27, C28):**
  - Expanded from 4 to **18 high-confidence default rules** across 4 categories:
    - *18+ Adult Euphemisms & Softening:* `horny_euphemism`, `perversion_bureaucratic`, `creampie_softening`, `slut_whore_bureaucratic`, `cum_ejaculation_softening`, `dildo_flattening`.
    - *Western Brands & Proper Nouns:* `blackdog_brand`, `titan_group_brand`, `styx_brew_brand`, `silver_bullet_brand`, `night_city_proper_noun`.
    - *Japanese Romaji Names:* `romaji_suzume`, `romaji_yukari`, `romaji_kazuha`, `romaji_shinji`, `romaji_hotaru`.
    - *Archaic Loanwords & Brand Flattening:* `trenchcoat_archaic_loanword`, `weatherbear_brand_flattening`.
  - Narrow project-specific terms (such as mascot `Dino`) are deliberately managed via project-level ledgers rather than global default rules to prevent false-positives on general vocabulary (e.g. `dinosaur fossil` -> `hóa thạch khủng long`, verified by test case `neg_52`).
  - Added `skills/viethoa/references/anti-domestication-corpus.md` documenting policies, categories, and preprocessing architecture.
  - Added `skills/viethoa/templates/proper-noun-ledger.csv` for project-level proper noun locking.
  - Expanded test suite `test_domestication_detector.py` to 13 tests with **52 paired negative controls** (including NFD decomposed variants and tag-embedded sentences) achieving **0 false-positives** (C29).
- **FontTV Router Modularization & End-to-End Golden Tests (P2a / C19, C23):**
  - Streamlined `skills/fonttv/SKILL.md` from 14.9 KB down to **8,358 bytes UTF-8 LF** (well under the 10 KB budget), eliminating token context bloat.
  - Extracted comprehensive operational guides into 3 new modular reference documents:
    - `references/unity-tmp-fallback-and-weight-policy.md`: Unity TMP mixed-weight & ransom-note fallback prevention rules.
    - `references/tool-inventory-and-verdicts.md`: Full 7-script audit capability inventory, exit codes `0..4`, semantic re-execution, and isolated test execution requirements.
    - `references/workflow-and-route-lifecycle.md`: Detailed 10-step font engineering lifecycle, route classification (A/B/C), and release proof acceptance gates.
  - Added `tools/tests/test_router_golden.py` validating link resolution (19/19 links resolve on disk), size budgets, and mandatory reading directives.
- **Dogfooding Hygiene Barrier (C26):**
  - Enhanced `tools/check_hygiene.py` with an internal game workspace pattern scanner to prevent confidential project names or proprietary raw assets from leaking into the public repository.
  - Added `.gitignore` patterns for `dogfood/` and `_dogfood/`.
- **Release Distribution Artifact Architecture (C24):**
  - Standalone release packages contain **7 verified assets**: 5 standalone skill archives (`viethoa-*.zip`, `cron-tuning-*.zip`, `fonttv-*.zip`, `bientaptay-*.zip`, `buildpatch-*.zip`), 1 complete monorepo suite archive (`viet-hoa-skills-*.zip`), and 1 cryptographic checksum file (`SHA256SUMS.txt`).

## [1.0.1] - 2026-10-12
### Added
- **GitHub Actions CI/CD Pipeline:** Automated verification on Ubuntu (`.github/workflows/ci.yml`) covering vendor synchronization, security/hygiene audit, locking invariants unit tests, and skill package linting.
- **Stand-alone Release Distribution:** Automated standalone packaging for each skill with `SHA256SUMS.txt` cryptographic verification.

## [1.0.0] - 2026-10-12
### Added
- **5 Core Localization Skills for Hermes Agent:**
  - `viethoa`: Main orchestrator, source-faithful translation, anti-domestication, exact-key merge, and pronoun matrix.
  - `cron-tuning`: Continuous background cron execution, model routing, and token budget management.
  - `fonttv`: Automated Vietnamese font expansion (TrueType, OpenType, SDF) and Unicode engine composition.
  - `bientaptay`: Integration with the BienTapTay bilingual CSV desktop editor.
  - `buildpatch`: Transactional Windows patch installer generation with guarded rollback.
- **Shared Invariants Contract v1.0.0 (`_shared/contracts/canonical-invariants-contract.md`):**
  - `INV-ATOM`: Atomic temporary sibling file writing and atomic replacement.
  - `INV-LOCK`: Cross-platform binary OS file locking with sidecar metadata envelope (`canonical.lock.json`).
  - `INV-CSV`: Exact composite key `(domain, key)` integrity and human-locked row preservation.
  - `INV-RB`: Clear demarcation of rollback responsibilities between translation data and engine binaries.
- **Shared I/O Library (`_shared/lib/hermes_io.py`):** Concurrency-safe file locking, atomic commits, and exact-key dictionary merging.
- **Hermetic Vendoring Tool (`tools/vendor_shared.py`):** Automated contract and library synchronization into each skill for 100% standalone viability.
- **Hygiene & Security Linter (`tools/check_hygiene.py`):** Automated auditing against local machine path leaks, private credentials, and copyrighted binary assets.
- **Legal Compliance & Attribution:** `LICENSE` (MIT) and `NOTICE.md` acknowledging upstream inheritance from `kann420/VH-Workflow-Skill`.

### Changed
- **Token Context Bloat Reduction:** Redesigned all `SKILL.md` files as Lazy-Load Routers, reducing token size by 60–75% (all skills under the 15 KB limit) with detailed technical guides moved to `references/`.

### Audited By
- **Notion AI Red Team Auditor (Workspace Sy07):**
  - Round 1 (Architecture & Token Budget): `SY07-R1-T1T2-PCDK-20261012-1EDB` (Conditional Pass)
  - Round 2 (Hygiene & Monorepo Packaging): `SY07-R2-T3T4-PCDK-20261012-32F6` (Conditional Pass)
  - Round 3 (Release Verification & Checksum Integrity): `SY07-R3-T5-PCDK-20261012-4D93` (Conditional Pass)
  - Round 4 (Release Gating & Dogfooding Strategy): `SY07-R4-T6-PCDK-20261012-1BBC` (Conditional Pass)
