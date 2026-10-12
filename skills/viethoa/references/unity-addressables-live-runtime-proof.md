# Unity Addressables locale patch: proving the live runtime file

## Problem pattern
A rewritten locale bundle can pass UnityPy reload and have the expected on-disk hash, yet a user screenshot still shows the previous locale text. Do not call this a cache issue without evidence.

## Evidence ladder
1. Confirm the game process is fully closed before replacing any bundle.
2. Record the installed target bundle SHA-256 and a few visible sentinel entries by stable table/ID, e.g. `SettingsPage_ru` language, screen-resolution, and back labels.
3. Start a fresh game process and record the new `Player.log` start timestamp/PID.
4. In the same process, choose the target locale and capture the corresponding UI screen.
5. Compare screenshot text with sentinels. Only then classify the result:
   - Sentinel text appears: patch is live; continue font/wrap/UI QA.
   - Old text appears with a fresh process and matching disk hash: investigate Addressables runtime path/catalog/cache or another duplicate game install.
   - Process was not restarted after replacement: result is inconclusive; restart first.

## Installer package rule
The installer input must never share its relative path with the live target after extraction. Put the patch under a dedicated `Payload/` directory, while `RoB_Data/...` remains only the runtime target path. Test install → target hash → uninstall → original hash in a disposable game-root fixture before shipping.

## Avoid
- Inferring an Addressables cache solely from a screenshot.
- Calling a structural UnityPy reload an in-game localization test.
- Publishing a ZIP before graphical target-locale screenshots prove actual loading.
