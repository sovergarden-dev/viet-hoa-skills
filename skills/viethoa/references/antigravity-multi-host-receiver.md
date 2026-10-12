# Antigravity multi-host receiver

Dùng khi chạy nhiều **dự án riêng** đồng thời trên nhiều máy. Mỗi package/run chỉ có **one active authoring host per package/run**; tuyệt đối không cho hai máy cùng ghi một controller ledger hoặc network-shared work root.

## Không sao chép nguyên ứng dụng/profile

Dùng **official installer** tại <https://antigravity.google/download>; không nén nguyên thư mục cài đặt Antigravity rồi giải nén sang máy khác.

Lý do:

- app cài đặt gắn updater, signer, registry/shell integration và version-specific resources;
- `%APPDATA%/Antigravity` chứa cache, Local Storage, WebStorage, Network/cookie và account/session material;
- `~/.gemini/antigravity*` chứa conversation/history, artifacts, browser profile và scratch data;
- `hooks.json`, project records, launchers và authorizations chứa absolute path/machine identity;
- chép active state/event ledger tạo split-brain hoặc provenance giả.

Google công bố installer riêng cho Windows và settings phân tầng theo global/project. Tài liệu nói core preferences giữa Antigravity 2.0 và CLI dùng chung, nhưng không hứa custom hook/skill/project/account state có thể migrate bằng cách copy profile. Nguồn: <https://antigravity.google/docs/getting-started>, <https://antigravity.google/docs/settings>, <https://antigravity.google/docs/cli/overview>.

## Receiver kit an toàn

Tạo ZIP allowlist-only trên máy nguồn:

```text
python -B scripts/export_antigravity_receiver_kit.py \
  --gemini-root %USERPROFILE%/.gemini \
  --output Antigravity-Receiver-Kit.zip
```

Kit chỉ chứa:

- global `GEMINI.md`;
- skill `dichgame`;
- subagent/semantic guard **code templates**, không state;
- allowlisted non-secret `config.json` preferences;
- installer bootstrap và hash manifest.

Kit loại trừ app binary, updater, MCP config, credentials, account/session, cookies, project records, launchers, conversation/history/brain, browser profile, active authorization, state, event ledger, logs và cache.

## Thiết lập máy mới

1. Cài Antigravity từ official installer, mở một lần và đăng nhập thủ công.
2. Cài Python vào path không có khoảng trắng; semantic command phải dùng `-X utf8`.
3. Giải nén receiver kit và chạy:

```text
python -B install_receiver_kit.py --apply-settings
```

4. Installer phải thấy destination guard `idle_main_only`/`inactive`, backup file hiện có, verify manifest, sinh `hooks.json` với absolute path mới, chạy hai hook self-test và để guard idle.
5. Tạo Project mới trong UI rồi trỏ vào package/work của dự án trên máy đó. Project settings và folder permissions phải cấu hình lại vì path khác.
6. Copy **outbound translation ZIP** của dự án; extract vào thư mục mới. Không copy work/state từ run khác.
7. Chạy package validator và `prepare_guarded_handoff_host.py` trên máy đích. Materialize authorization mới theo package/work/private paths mới, receiver-shell probe sạch rồi mới arm.
8. User tự gửi prompt trong conversation mới của máy đích.

## Chạy nhiều dự án

- An toàn: máy A chạy package/run dự án A; máy B chạy package/run dự án B. Mỗi dự án có package ID, run ID, work root, host-private root và event chain riêng.
- Không an toàn: hai máy cùng chạy một package/run, sync work qua OneDrive/SMB, copy authorization đang active, hoặc merge hai event chains.
- Không mang authorization đang active sang máy mới. Authorization bind absolute package/work/controller/schedule paths và host event chain.
- Nếu cần chuyển **run đang chạy**: dừng ở verified packet boundary, retire/reset source host sau readback, tạo continuation package/run mới bind snapshot + commit head, rồi materialize fresh destination authorization. Protocol hiện không hỗ trợ live handover vô hình; nếu chưa có continuation builder thì hoàn tất run trên máy cũ hoặc restart exact run trên máy mới.

## Host identity và receipts

Tên máy chỉ là operator metadata; provenance authority là package/run + authorization SHA-256 + controller commit head + semantic event head. Receipt nên ghi `receiver_host_label` để vận hành, nhưng không dùng label thay hash binding.

## Verification

- Official app opens and account sign-in is new/manual.
- Receiver kit ZIP CRC + manifest hashes pass; không có secret/private path.
- Hooks point to destination Python/home, not source machine.
- `subagent_cap.py status`: `idle_main_only, limit=0, reserved=0`.
- `semantic_response_guard.py status`: `inactive`.
- Package host preparation creates a new authorization and exact PowerShell shell probe passes.
- Source and destination never show the same package/run active simultaneously.
