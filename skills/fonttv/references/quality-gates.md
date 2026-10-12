# Quality gates, trạng thái và proof level

## 1. Trạng thái của một kiểm tra

| Trạng thái | Nghĩa | Tính là đạt? |
|---|---|---|
| `PASS` | đã chạy thật trên đúng SHA-256 và đạt | có |
| `FAIL` | đã chạy, không đạt | không |
| `NOT_RUN` | chưa chạy, thiếu công cụ, validator không chạy được | không |
| `NOT_SUPPORTED` | input/format ngoài khả năng công cụ hoặc adapter | không |
| `UNVERIFIED` | có dữ liệu nhưng bằng chứng yếu (danh sách nguồn yếu: `custom-and-legacy-encoding.md` §3) | không |
| `NOT_APPLICABLE` | gate không áp dụng, có lý do; chỉ cho shaping khi engine không shape, và preservation diff khi font hoàn toàn mới | có, kèm lý do |
| `WAIVED` | ngoại lệ có chủ đích; **chỉ cho metrics** (§4 policy waiver) | có, luôn liệt kê trong báo cáo |

Trạng thái dự án: `BLOCKED` (thiếu quyền/input), `DRAFT`, `NEEDS_REVIEW`, `RELEASE_CANDIDATE`, `APPROVED` (chỉ khi `release_verified`), `REJECTED` (build đã chứng minh sai; không tái sử dụng bytes).

## 2. Coverage tách năm chiều

| Chiều | Câu hỏi | Bằng chứng hợp lệ |
|---|---|---|
| `record_present` | lookup key có record/glyph không? | cmap, characterTable, record table, slot table |
| `mapping_correct` | glyph ở đó có đúng ký tự contract yêu cầu không? | build manifest, native encoding đã đối chiếu, reference render diff, pixel match, người duyệt |
| `outline_nonempty` | glyph có nét thật không? | outline bounds; ink pixel sau decode texture |
| `metrics_valid` | advance/height/offset/baseline hợp lệ không? | hmtx hoặc metrics record, so với chữ gốc cùng font |
| `runtime_bound` | game thật vẽ đúng glyph này không? | archive readback + screenshot runtime |

Không gộp năm chiều thành một con số "coverage %".

## 3. Mười ba gate

| # | Gate | PASS khi | Bằng chứng tối thiểu | Không thay bằng |
|---|---|---|---|---|
| 1 | Rights | quyền sửa và quyền phân phối xác minh riêng; donor và Reserved Font Name đã xử lý | `LICENSE_AUDIT.md` | `fsType`, name record, chữ "free", license của tool |
| 2 | Input hash/baseline | mọi input có SHA-256, bản sao, đường rollback | manifest | tên file, ngày sửa |
| 3 | Encoding contract | lookup key, bảng mapping, normalization đã khóa; `encoding.mapping_source` + `mapping_sha256` là file thật | mapping file + tham chiếu encoder | suy từ nội dung font |
| 4 | Coverage | `record_present` cho toàn repertoire + ký tự thực tế | audit JSON | pangram |
| 5 | Semantic mapping | `mapping_correct` PASS mọi entry bằng bằng chứng mạnh; route B/C: checker `--verify-files` chạy lại `custom_encoding_audit.py` trên output với `encoding.adapter_path` đã pin; rerun exit 0, verdict PASS, `mapping_verified`, cùng font/mapping/adapter hash, và `semantic_digest` khớp report đã lưu | lần chạy lại, không phải trường trong report | "charID đã tồn tại"; hash inventory tự khai; external/handwritten inventory; `adapter_execution` tự khai; build manifest đứng một mình |
| 6 | Outline/ink | `outline_nonempty` PASS | bounds/ink | độ rộng UV, file size |
| 7 | Metrics | advance/baseline/height hợp lệ; không clip trong ma trận hỗ trợ | audit + multiline proof | bbox một glyph |
| 8 | Shaping | (route A có shaper) HarfBuzz NFC + NFD không `.notdef`; dấu bám đúng | `shaping_audit.py` + proof | chỉ render precomposed |
| 9 | Preservation diff | mọi record đổi được giải thích bằng remap table hoặc allowlist; record giữ nguyên có `mapping_correct` PASS | semantic diff (§5) | hash/file size |
| 10 | Structural validator | OTS/Fontspector (OpenType) hoặc adapter re-parse (format riêng) không lỗi chặn | validator log | "font mở được" |
| 11 | Archive/live readback | file extract từ container live (`readback_path`) có hash thật bằng output đã audit | file readback + hash | kiểm thư mục build; `container_sha256_after` |
| 12 | Runtime screenshots | người dùng chạy đúng `build.build_id`; mọi consumer được chụp; mỗi screenshot có path, hash thật, `font_sha256` = output; người duyệt kết luận | file screenshot + checkpoint | AI nói "looks good" |
| 13 | Human sign-off | người đọc tiếng Việt (và người duyệt typography khi phát hành font) ký trên SHA-256 cuối | file record sign-off + hash | duyệt bản render cũ |

**Cổng tự hiệu chuẩn audit (bắt buộc cho mọi luật heuristic về vị trí/khoảng cách/hình dấu):** trước khi dùng một luật để chặn hay sửa, chạy nó lên glyph có dấu do nhà phát hành dựng trong chính font (`À Á Â È É Ê …`). Luật chấm lỗi glyph gốc là luật sai; ngưỡng phải suy từ phân bố trên glyph gốc (ví dụ `tol = max(floor, worst × 1.25)`). Lớp lỗi không có đối chứng gốc thì chỉ là `UNVERIFIED`, không được dùng để sửa. Thước đo đổi chỉ số trên trục mà thay đổi không chạm tới (thay đổi dọc làm chỉ số ngang nhảy) là thước đo không ổn định; không phê duyệt bằng nó.

**Gate theo strategy:** P1 thêm `source_coverage` (font nguồn phủ đủ repertoire, không `.notdef`), `source_rights` (license cho phép nhúng/phân phối), `baseline_uniform` (spread baseline trên toàn bảng chữ trong dung sai của font gốc). P2 thêm `donor_mark_shape` (fill của mask dấu, ví dụ chấm dưới ≈ 0.785 là tròn) và cổng tự hiệu chuẩn trên.

**Digest của report phải độc lập với cách viết đường dẫn.** `semantic_digest` bỏ phần path trong các trường `*_file` (chỉ giữ basename), vì digest là bằng chứng chứ không phải log: cùng một lần chạy với đường dẫn tuyệt đối và tương đối phải cho cùng digest. Trên TWAU, `roundtrip.text_file` làm digest đổi theo chỗ đặt repo, khiến checker báo "stale report" cho một lần chạy lại byte-identical.

Proof và screenshot phải render lại sau lần sửa cuối. Mọi sửa đổi sau đó đưa gate 4–13 về `NOT_RUN`.

AI chỉ được xếp hạng ảnh nghi vấn cho người xem nhanh hơn; AI không tự cấp `PASS` cho gate 5 hay 12 và không cấp `APPROVED`.

**Gate 12 cần hai thứ ngoài ảnh.** (1) **Ảnh phải được gán đúng font** bằng bằng chứng, không bằng một dòng tài liệu: dự án từng gán ảnh menu Settings cho font slab chỉ vì tài liệu nói vậy, trong khi chữ trong ảnh là sans nét mảnh. Ảnh không gán được thì ghi nhận và không cấp bậc. (2) **Nhiều font dùng chung một thiết kế** (P1 ghép 8 font vào một font nguồn) thì một ảnh là bằng chứng cho thiết kế đó, không phải bằng chứng cho từng font.

## 4. Proof level

| Level | Yêu cầu (tích lũy) |
|---|---|
| `inventory_only` | input hash + inventory; chưa chứng minh gì |
| `structurally_verified` | file output có thật; gate 4, 6, 7, 10 đạt. Route B/C: chính checker đã chạy lại adapter và `structural_result` là PASS. Report lưu một mình chỉ đủ `inventory_only` |
| `mapping_verified` | + gate 3 (route B/C), 5, 9. Route B/C: adapter đã pin chạy trên font output trong lần audit; với `--verify-files`, checker chạy lại audit đó, không chỉ đọc `adapter_execution` trong report |
| `archive_verified` | + gate 11 |
| `runtime_verified` | + gate 12 do người duyệt |
| `release_verified` | + gate 1 (file evidence), clean install và rollback (report), gate 13 phủ mọi output hash |

Level của dự án là level thấp nhất trong các consumer. Heuristic (donor similarity, OCR, AI triage) không phải proof level.

**Bằng chứng là file, không phải status.** Gate đạt khi có `status` (`PASS`, hoặc `WAIVED` hợp lệ), `font_sha256` = output, `report` và `report_sha256`. Hash khai trong manifest mà không có file thật không phải bằng chứng. Ngoại lệ duy nhất không cần report: `NOT_APPLICABLE` hợp lệ ở §1.

`scripts/proof_level_check.py` cài đặt đúng các quy tắc này:

- `--verify-files ROOT` (`evidence_mode: files_rehashed`): re-hash mapping, adapter, output, identity evidence, mọi gate report, readback, screenshot, rights evidence, report release và record sign-off. File thiếu, không đọc được hoặc lệch hash là ERROR. Với route B/C, checker chạy lại audit một lần cho mỗi font trước khi rời `inventory_only`. `structurally_verified` cần `structural_result.status == PASS` của lần chạy lại; `mapping_verified` cần thêm `semantic_result.status == PASS` và `semantic_digest` khớp report đã lưu. Một font chưa chạy lại làm cờ `*_for_all_encoded_fonts` thành false. `report_file_rehashed` chỉ nói file report không đổi; nó không phải lần chạy adapter. Route B/C thiếu `encoding.adapter_path` thì trần là `inventory_only`. `container_path` + `container_sha256_after` chỉ là metadata.
- Không có `--verify-files` (`evidence_mode: declared_only`): chỉ kiểm tính nhất quán giữa các hash khai báo và báo kết quả ở `declared_consistent_level`; `justified_proof_level` bị giới hạn ở `inventory_only`, nên mọi claim cao hơn đều FAIL.

**Policy waiver (một policy cho cả hai helper):**

- `record_present`, `mapping_correct`, `outline_nonempty` (gate 4, 5, 6) không bao giờ được waive. Allowlist của `custom_encoding_audit.py` chứa một trong ba check này → `INPUT_ERROR`, exit 2.
- Chỉ metrics (`metrics_valid` / gate `metrics`) được waive, khi có đủ `reason`, `approved_by`, `approver_type: "human"`, `scope` (field + consumer cụ thể). Thiếu một field → allowlist bị từ chối (exit 2) hoặc gate không đạt.
- Waiver luôn nằm trong report (`waived[]`, `metrics_valid_original`, cảnh báo) và không thay được identity hay ink: `mapping_verified` chỉ đạt khi presence, identity và ink đều `PASS` thật.
- Các gate khác (kể cả structural validator) không được waive.
- Phân biệt: `allowlisted_changes` trong manifest (và "allowlist" ở gate 9) liệt kê record được phép **thay đổi** có chủ đích; nó không waive bất kỳ check nào. `--allowlist` của `custom_encoding_audit.py` là danh sách **waiver metrics** theo policy trên.

## 5. Semantic diff trước/sau

Với mỗi consumer font, so theo lookup key:

- mapping/identity; record thêm, bớt, trùng, đổi thứ tự;
- metrics: advance, height, offset, bearing; UV/rect/page;
- outline/ink: bounds, số pixel ink;
- consumer coverage: font nào sửa, font nào giữ, vì sao.

## 6. Acceptance matrix

`build × platform × locale × cache_state (cold/warm) × renderer × consumer`. Mỗi ô ghi gate status và proof level. Không suy ô chưa test từ ô đã test.

## 8. Manifest: dựng bằng công cụ, không viết tay

Manifest là nơi duy nhất khai báo proof level. Viết tay là cách để lời khai và bằng chứng trôi khỏi nhau. `scripts/p1_manifest.py` dựng nó từ artefact có thật và **từ chối** khi thiếu file, gọi tên file thiếu. Bốn cái bẫy đã gặp thật, khiến bước chạy lại của checker thất bại:

1. **Adapter ≠ encoder.** `encoding.adapter_*` là adapter theo `fonttv-adapter/v1` mà checker chạy lại; `encoding.encoder*` là module mã hoá của project. Dùng một file cho cả hai thì lần chạy lại hỏng và mức bị hạ còn `inventory_only`.
2. **Hợp đồng glyph phải lấy từ `load_byte_map`**, tức gồm cả ASCII, không phải từ file mapping (chỉ 134 ký tự Việt). Nếu không thì mọi thay đổi ở chữ ASCII bị coi là ngoài hợp đồng → `preservation_diff` FAIL → mức bị chặn.
3. **Readback là bằng chứng, không phải scratch.** Xoá thư mục readback sau khi ghi manifest làm mọi gate readback thành `FileNotFoundError`.
4. **`semantic_audit` phải có** `corpus_path/sha256` và `encoded_path/sha256` thật; thiếu thì checker không chạy lại được adapter.

Kiểm tra kết quả, không đoán: `proof_level_check.py MANIFEST --verify-files .` phải ra `justified_proof_level` đúng bằng `claimed_proof_level` và `overclaim: false`.

## 9. Gate 12: cách gắn ảnh đúng

Gate 12 cần pixel từ phiên chơi thật, nhưng pixel **không** nói được font nào đã vẽ — hai công cụ đã thử và thất bại, xem `references/screenshot-attribution-attempts.md`. Nên quy trình là: ghi citation trước, ghi ảnh sau.

```
python scripts/p1_attach_screenshot.py --image SHOT.png \
  --font ITC_Kabel_Book.font \
  --cite "uiz_ConsoleButtons.lua names ITC_Kabel_Book.font" \
  --reviewer Rurus --shots reports/p1_screenshots.json \
  --evidence-dir reports/p1_evidence/screenshots
```

Công cụ từ chối: thiếu `--cite`, ảnh dưới 200×100 (placeholder), ảnh không đọc được, hoặc font đã có ảnh mà không `--replace`. Ghi xong phải chạy lại bước dựng manifest — wrapper đọc `reports/p1_screenshots.json` nên **không** ghi đè ảnh đã gắn.

Checker xác nhận: `runtime_verified` cho đúng font đó, và `justified_proof_level` không thấp hơn `claimed_proof_level`.

## 10. Lỗi chặn phát hành

- Record tồn tại ở ID nhưng glyph sai hoặc rỗng theo contract.
- File font gốc được giữ trong khi encoding của text đã đổi, không có semantic PASS trên chính bytes đó.
- Container live chứa bytes khác bản đã audit (injector trỏ build cũ).
- Có precomposed nhưng thiếu combining marks, với renderer không compose.
- Thanh điệu bám base thay vì bám dấu phụ qua `mkmk`; acute/hook đặt máy móc giữa circumflex.
- Horn xử lý như dấu trên; Ơ/Ư lệch hình hoặc lệch cao; phá spacing `ƯT`.
- Dấu nặng chạm contour/descender; dấu chồng bị cắt.
- Donor sai weight, contrast, slant, UPM, outline flavor hoặc license.
- Dấu hoa dùng lại nguyên dấu thường; dấu chạm cap.
- Bounds, hinting hoặc kerning class hỏng sau khi thêm glyph.
- Variable master không tương thích; chỉ test default instance.
- Text legacy (VNI/TCVN3/VISCII) bị coi là Unicode.
- Tool báo thành công (exit 0) khi còn thiếu glyph, hoặc pack atlas bỏ glyph mà vẫn báo OK.

## Project readiness khác proof level

`release_readiness.py` mặc định kiểm archive-level readiness + blockers. Kết quả đó không tự nâng `runtime_verified`/`release_verified` và không thay runtime acceptance của payload do `viethoa` sở hữu. Hồ sơ ảnh từng font là tùy scope; nếu không có thì báo đúng archive level, không giả PASS gate 12.
