# Custom và legacy encoding (route B)

Dùng khi lookup key tại font không phải codepoint Unicode, kể cả khi engine dùng Unicode ở tầng khác.

## 1. Encoding contract

Contract gồm: lookup key, bảng ký tự → key, normalization trước encoder, passthrough (ví dụ ASCII giữ nguyên), compose policy, và nơi encoder chạy. Ghi trong manifest ở khối `encoding`.

| Contract | Text → key | Lưu ý cho tiếng Việt |
|---|---|---|
| Unicode codepoint | codepoint | route A |
| CP1252/Latin-1 | 1 byte | không có ă â đ ê ô ơ ư và phần lớn chữ có thanh; dự án phải mượn slot, tức là thành bảng dự án (dòng dưới) |
| Windows-1258 | 1 byte; chữ gốc và biến thể (ă â ê ô ơ ư đ …) precomposed, năm thanh là byte combining: huyền `0xCC`, sắc `0xEC`, ngã `0xDE`, hỏi `0xD2`, nặng `0xF2` | encoder tách chữ có thanh thành chữ + byte thanh (`ệ` → `ê` `0xEA` + `0xF2`); font cần glyph thanh chồng được (advance 0) và renderer phải vẽ chồng |
| VNI | chữ ASCII + byte dấu theo sau (nhiều byte/chữ) | font VNI vẽ dấu ở slot riêng để chồng lên chữ trước; mapping dùng `ids` nhiều phần tử |
| TCVN3 (ABC), VISCII, VPS | 1 byte/chữ theo bảng riêng; có bảng dùng cả slot điều khiển C0 hoặc tách chữ hoa sang font riêng | lấy bảng từ nguồn chính thức hoặc dự án, không viết từ trí nhớ |
| Bảng single-byte do engine/dự án định nghĩa | 1 byte, ví dụ ASCII + `0x80–0xFF` tự gán | slot trùng nghĩa với encoding gốc của font chỉ là trùng hợp, phải đo |
| Glyph index | GID | GID đổi khi rebuild, subset hoặc reorder font |
| Atlas slot | số ô trong lưới | thứ tự ô là contract; chèn glyph làm lệch mọi ô phía sau |

Các byte Windows-1258 ở trên đã đối chiếu bằng codec `cp1258` của Python. Với VNI/TCVN3/VISCII/VPS, dùng bảng của dự án hoặc converter đã kiểm (viparse, funput) và lưu hash. Converter legacy → Unicode thuộc tầng text ingestion, không trộn vào bước dựng font.

## 2. Nguồn sự thật

- Bảng mapping mà encoder thật đang dùng (script ghi file text của game, tool build, bảng trong engine), kèm đường dẫn và SHA-256.
- Không dựng bảng bằng cách nhìn xem font đang có gì.
- Khi lấy được bytes do encoder thật sinh ra cho một corpus, so với bảng (`--encoded`). Lệch là contract drift → FAIL.

## 3. Semantic tuple

Mỗi entry kiểm `(source character, encoded ID(s), expected glyph identity, actual glyph identity, actual outline/ink)` cùng metrics.

- Expected identity: ký tự (hoặc thành phần, với mapping nhiều byte) mà contract yêu cầu slot đó vẽ.
- Actual identity: ký tự slot đó thực sự vẽ. Chuỗi `identity_source` chỉ là lời khai; identity chỉ mạnh khi chính tool kiểm được:
  - `native_encoding`: adapter khai `adapter.native_encoding` có `resolver` và hoặc `name` là codec single-byte Python (tool tự decode ID), hoặc `table_evidence` trỏ tới evidence `encoding_table` đã re-hash. Resolver cho ra ký tự khác → FAIL.
  - `build_manifest`, `reference_render_diff`, `pixel_match`, `human_review`: record phải có evidence cùng loại (adapter run: `--identity-evidence`; external inventory: `identity_evidence` trỏ tới `evidence[]`). File evidence được tool re-hash, phải là `fonttv/glyph-evidence/v1` (`templates/glyph-evidence.example.json`) có `font_sha256` bằng hash font đã audit, và `slots[id]` bằng identity. Thiếu file, sai hash, sai font → `UNVERIFIED`; slot nói ký tự khác → FAIL.
  - yếu: `ai_vision`, `ocr`, `guess`, `filename` → `UNVERIFIED`.
- Ink: đo từ outline hoặc texture đã decode. UV diện tích 0 là rỗng; UV có diện tích mà chưa đo ink là `UNVERIFIED`.
- Metrics: advance > 0 với glyph spacing; glyph thanh chồng (combining) được phép advance 0.

## 4. Quyết định cho từng slot

Áp cho từng font consumer × từng entry của bảng:

| Kết quả tuple | Hành động |
|---|---|
| PASS cả bốn chiều offline | được preserve record |
| `mapping_correct` FAIL hoặc UNVERIFIED | remap: đặt glyph đúng vào slot (dựng từ glyph cùng font hoặc nguồn đã duyệt) |
| `outline_nonempty` FAIL | remap |
| `metrics_valid` FAIL | sửa metrics theo template chữ gốc cùng font |
| `record_present` FAIL | thêm record, giữ bất biến format (thứ tự, tính duy nhất) |

File chỉ được giữ byte-identical khi toàn bộ entry PASS trên chính bytes đó. Advance và metrics của slot được remap lấy từ chữ gốc của ký tự đích trong cùng font (`đ` → `d`, `ệ` → `e`), không lấy từ record legacy đang nằm ở slot.

## 5. Round-trip

```text
Unicode text → normalization → encoder → byte stream → decode
→ font lookup → glyph identity → render
```

- Chạy cùng corpus ở NFC và NFD. Encoder phải normalize trước hoặc từ chối; NFD cho bytes khác nghĩa là pipeline text phải normalize.
- Ký tự không encode được là FAIL, không được bỏ qua.
- Decode phải trả lại đúng text; bảng phải injective.
- Tra font từng ID phải ra đúng identity.
- Screenshot runtime là bước cuối, không thay bước nào ở trên.

## 6. Không áp máy móc luật Unicode/OpenType

- Combining marks trong font chỉ cần khi contract phát ra combining (Windows-1258, VNI) hoặc engine tự tách.
- cmap, GPOS `mark`/`mkmk`, OS/2 Unicode range và code page không tham gia lookup bằng byte.
- Điều kiện giữ glyph có sẵn của route A (`architecture.md` §3) không chuyển sang đây; ở route B chỉ bảng §4 quyết định.

## 7. Định dạng dữ liệu cho helper

**Mapping** `fonttv/encoding-map/v1` (mẫu `templates/encoding-map.example.json`):

- `normalization`: `NFC` (mặc định) | `NFD` | `none`.
- `passthrough`: `none` (mặc định) | `ascii_printable` (`0x20–0x7E` giữ nguyên).
- `compose_policy`: `precomposed` (mặc định) | `base_plus_combining` (kiểu Windows-1258).
- `id_max`: giới hạn ID, ví dụ 255.
- `entries[]`: `char` hoặc `codepoint`; `id` (số hoặc `"0x.."`) hoặc `ids` + `glyphs` cho mapping nhiều byte.
- CSV cũng được: cột `char` hoặc `codepoint`, và `id`/`charID`/`byte`.

**Inventory** `fonttv/font-inventory/v1` (mẫu `templates/font-inventory.example.json`):

- `font` (và `source_path` nếu có): basename phải trùng `--font-file`.
- `sha256` và `adapter.input_sha256`: cả hai phải bằng SHA-256 mà tool tự tính trên `--font-file`. Null, sai định dạng hoặc khác → FAIL (exit 1), không bao giờ `mapping_verified`.
- `adapter.name`, `adapter.version`, `adapter.inventory_method`: không được trống. `adapter.supported`, `adapter.capabilities` ⊂ {`records`, `glyph_identity`, `ink`, `uv`, `metrics`}; `supported: false` hoặc thiếu `records` → NOT_SUPPORTED.
- `adapter.native_encoding` (tùy chọn): `name`, `resolver`, `table_evidence`.
- `evidence[]`: `id`, `type` ∈ {`build_manifest`, `reference_render_diff`, `pixel_match`, `human_review`, `encoding_table`}, `path`, `sha256`.
- `invocation`: `{id, protocol}`, bắt buộc với output adapter (§8), echo đúng nonce của lần chạy.
- `lookup`: `binary_search` (bắt buộc ID tăng dần tuyệt đối) | `hash` | `direct_index` | `unknown`.
- `records[]`: `id`, `glyph_identity`, `identity_source`, `identity_evidence`, `uv`, `ink_pixels` hoặc `ink_bbox`, `x_advance`, `height`, `y_offset`.

Hash trong inventory chỉ gắn **metadata** với bytes, không gắn **quá trình trích xuất**: một inventory viết tay vẫn có thể chép đúng hash thật. Report luôn ghi `inputs.font_sha256` (tool tự tính), `inventory.declared_font_sha256`, `font_hash_matches`, `adapter_input_matches`, `name_consistent`, `adapter_provenance_complete`, `binding_status`, trạng thái từng evidence và `identity_evidence_policy`.

## 8. Nguồn gốc inventory và adapter protocol

> **External inventory is a declaration. On encoded routes, adapter reexecution is required for both structural and semantic proof. Stored reports alone justify only inventory_only.**

| `inventory_origin` | Cách chạy | Trần proof | Exit khi mọi check sạch |
|---|---|---|---|
| `adapter_executed` | `--adapter-script A --adapter-sha256 H` | `mapping_verified` | 0 `PASS` |
| `external` | `--inventory INV` | `inventory_only` | 4 `INCOMPLETE`, hoặc 4 `PLANNING_ONLY` nếu có `--accept-external-inventory-for-planning`. Không bao giờ exit 0 |

**Protocol `fonttv-adapter/v1`:**

1. Tool re-hash adapter script và so với `--adapter-sha256`; lệch hoặc thiếu file → `INPUT_ERROR`.
2. Tool chạy `python ADAPTER --input FONT --output TEMP_JSON --invocation-id ID --protocol fonttv-adapter/v1` bằng argv list, không shell, stdin đóng, cwd là thư mục tạm mới, có timeout. `ID` là nonce ngẫu nhiên của lần chạy; `TEMP_JSON` nằm trong thư mục tạm do tool tạo.
3. Adapter đọc input read-only, parse record thật, và ghi inventory có `invocation: {id, protocol}`, `sha256` và `adapter.input_sha256` bằng hash bytes nó đã parse, cùng `adapter.name/version/inventory_method`.
4. Adapter trả exit 0 khi thành công; exit 3 cho format/version không hỗ trợ (tool báo `NOT_SUPPORTED`); mã khác → `FAIL`.
5. Tool từ chối (`FAIL`): input bị sửa trong lúc chạy; không có output mới; nonce/protocol lệch (tức là inventory cũ được tái dùng); output sai schema; binding lệch hash; adapter tự chèn `evidence[]`.
6. Adapter không đoán identity. Nó chỉ được khai `adapter.native_encoding` khi format thực sự mang thông tin đó. Identity do tool gắn: trước tiên từ `--identity-evidence TYPE=PATH` (glyph evidence được tool tự hash, `font_sha256` phải bằng font đang audit), sau đó mới tới native resolver. Evidence chỉ bổ sung nghĩa cho slot; record, UV, ink, metrics luôn là thứ adapter parse từ bytes.
7. Report ghi `inventory_origin`, `records_rederived`, `proof_cap`, `semantic_digest`, `inventory_canonical_sha256` (inventory adapter sau khi bỏ `invocation`) và `adapter_execution` (script, `script_sha256`, argv contract, `invocation_id`, `exit_code`, `generated_inventory_sha256`, `input_unchanged`, stderr tail). `--save-generated-inventory PATH` ghi đúng bytes adapter vừa tạo. So hai lần chạy bằng canonical digest, không bằng hash thô, vì invocation id đổi mỗi lần.
8. `proof_level_check.py --verify-files` không tin khối `adapter_execution` trong report. Với route B/C nó chạy lại chính lệnh audit này (`semantic_reexecution`, `adapter_reexecuted`) trước cả proof cấu trúc lẫn semantic. Report lưu chỉ là cache: digest lệch lần chạy lại thì FAIL. Thiếu `encoding.adapter_path`, adapter sai hash, không hỗ trợ hoặc không chạy được thì trần là `inventory_only`. Chỉ lần chạy lại có `structural_result.status == PASS` mới đạt `structurally_verified`; `mapping_verified` cần thêm `semantic_result.status == PASS`. Hash lại file report là `report_file_rehashed`, không phải xác minh adapter đã chạy.

`mapping_verified` = adapter đã pin được chạy lại trên đúng bytes đích trong lần audit này, rồi các check semantic PASS. Nó **không** chứng minh adapter đúng về mặt toán học. Adapter cần conformance test với fixture độc lập; mẫu là `scripts/adapters/ftvf_reference.py` (định dạng tổng hợp FTVF) cùng test trong `scripts/tests/`. Format chưa có adapter chạy được → `NOT_SUPPORTED`, hoặc tối đa `inventory_only` qua external inventory. Build manifest không bao giờ nâng proof khi không có record do adapter parse ra.

Adapter là code của dự án, mỗi adapter cho đúng một format. Adapter phải decode texture để đo ink; khi chưa decode được thì bỏ `ink_pixels` để ink ở trạng thái `UNVERIFIED`. Version hoặc header chưa biết → exit 3.

## 9. Chạy

```bash
python scripts/custom_encoding_audit.py --mapping table.json \
  --adapter-script adapters/project_adapter.py --adapter-sha256 <sha256> \
  --font-file build/Menu.font --identity-evidence build_manifest=build/glyph-manifest.json \
  --text corpus.txt --encoded corpus.bin --output audit.json
python scripts/custom_encoding_audit.py --mapping table.json --inventory planned.inventory.json \
  --font-file build/Menu.font --accept-external-inventory-for-planning
```

Thiếu `--font-file` → `INPUT_ERROR` (exit 2). `--evidence-root` chỉ dùng cho external inventory (mặc định là thư mục chứa inventory).

`--allowlist` chỉ nhận waiver `metrics_valid` theo policy waiver ở `quality-gates.md` §4 (mẫu `templates/allowlist.example.json`). Slot sai identity, rỗng hoặc thiếu record không có đường waiver; hãy remap nó theo §4 ở trên. `runtime_bound` luôn `NOT_RUN`.
