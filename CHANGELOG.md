# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- **fonttv**: Streamlined `SKILL.md` from 14.9 KB to 8.3 KB (below 10 KB budget, C19) by extracting detailed specifications into modular references:
  - `references/unity-tmp-fallback-and-weight-policy.md`: Unity TMP mixed-weight & ransom-note fallback prevention rules.
  - `references/tool-inventory-and-verdicts.md`: Full 7-script audit capability inventory, exit codes `0..4`, and isolated test execution requirements.
  - `references/workflow-and-route-lifecycle.md`: Detailed 10-step font engineering lifecycle, route classification (A/B/C), and release proof acceptance gates.

### Added
- Status badges in `README.md` (CI passing, Dynamic Release, and MIT License).
- `.gitignore` rule for release distribution build directory (`dist/`).
- This `CHANGELOG.md` tracking project evolution.

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
