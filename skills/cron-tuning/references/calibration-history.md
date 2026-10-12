## Historical lessons

- Schrödinger's Call: completion-relative intervals caused substantial idle time; inspect scheduling semantics before choosing cadence.
- Legend of Mortal: larger batches hit a measured latency cliff; continuous sessions removed inter-tick waits. Current code seed is batch 6, pacing 0.5s, session 2400s. Those values are not universal constants.
- Village: durable heartbeat binding differs from progress logs; stale claim recovery and content-addressed quarantine prevent retry collisions.
- Shared route profile `translation_route_profiles.py` pins provider/model/temperature/timeout/retries/output cap only. Batch size was removed in 1.2.0 because dialogue 25 / UI 80 were unproven and projects already overrode them: Crimson 25/50, Withering Rooms 10/10, OPUS 15, Pass the Fear 18, Legend 6, Look Outside 12, BERSERK 35. Project worker owns batch size and must record why. Do not add batch size back to the shared profile.
- Pass the Fear receipts (`receipt_20260910_011346.json`, `011517`, `011731`): batch 18 on gemini-3.8-flash-high sometimes accepted 18 rows in ~22–26s and sometimes accepted 0 after ~23–34s. A duration receipt without accepted rows is a failed packet, not throughput. Do not copy "optimal" comments from worker source.
- Sally Face (2026-09-28): Token regex matched `[LOCKED]` and `[mumbling]` as format tokens, causing valid translations `[ĐÃ KHÓA]` and `[lẩm bẩm]` to be rejected; simultaneously `.strip()` dropped whitespace-only hotspot rows. This left 15 rows pending indefinitely and prevented auto-pause/removal. Fix: restrict token regex to true format tags/parameters; preserve whitespace-only rows as-is; enforce deadlock breaker on unprogressing batches.
- Withering Rooms `sanitize_json_response` still slices first `{`/`[` to last `}`/`]`. That violates fail-closed JSON handling. New workers must not copy it. Do not rewrite the live worker unless that project is the requested scope.
- OPUS config pins batch 15, pacing 0.5s, session 2400s, local `:9100`, and separate heartbeat/quarantine/checkpoint paths. Config presence is not a measured optimum and is not live-run proof.

These are historical lessons, not current-job measurements. Revalidate before deployment. Screenshots supplement timing/commit receipts, never replace them. A comment saying "optimal" is not evidence.

