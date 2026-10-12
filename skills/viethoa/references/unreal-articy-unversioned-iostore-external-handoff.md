# Unreal Articy + unversioned IoStore: extraction and external handoff

Dùng khi game UE5 lưu hội thoại trong một package Articy lớn, `.locres` chỉ có UI/engine text, asset dùng unversioned properties, và patch cộng đồng chứng minh static IoStore override.

## Failure signatures

- `retoc list` trả chunk/package IDs, nên grep tên `.locres` bằng output này có thể cho false negative.
- UEExtractor báo `Package has unversioned properties but mapping file is missing` dù `.usmap` nằm cạnh tool: kiểm nơi tool thực sự dò mapping; một số bản chỉ dò game root/cây nguồn.
- Mapping load thành công nhưng generated Articy classes không có schema; CUE4Parse/UEExtractor trả `0`, UAssetGUI để exports ở `RawExport`.
- Wwise `AkAudioEvent` chứa `.bnk/.wem` và scene path nhưng không chứa subtitle text. Không dùng speech-to-text để thay corpus có cấu trúc.
- Parser giả định đủ N ngôn ngữ hoặc đếm `FString` tuần tự dễ false-negative: unversioned zero-mask có thể omit property và feature có text/menu xen kẽ.

## Workflow

1. Fingerprint build, engine version, game root và container hashes. Không sửa live.
2. Inventory `.pak/.utoc/.ucas`; hiểu semantics thật của filter tool. Với `retoc`, xác minh filter bằng one-asset extraction trước full run; không giả định glob được hỗ trợ.
3. Nếu `.locres` thiếu hội thoại, tìm package dialogue database/Articy và khảo cổ patch cộng đồng offline. Community artifact là evidence cho package ID, mount path, font route và release architecture; không dùng bản dịch cộng đồng làm authoritative source.
4. Trích package gốc thành legacy `.uasset/.uexp`; dùng UAssetGUI JSON để lấy export table, object name, class/outer index và raw payload.
5. Kiểm mapping schema trước khi sửa/fork extractor. Nếu generated Articy classes không tồn tại trong `.usmap`, dừng tuyến CUE4Parse; không tiếp tục ép parser tổng quát.
6. Giải unversioned header theo implementation engine/CUE4Parse:
   - schema iterator bắt đầu đúng index `0`;
   - đọc fragments, zero masks và nonzero property slots;
   - map language/text/menu bằng property index đã chứng minh, không bằng vị trí chuỗi tình cờ;
   - metadata ngoài localization boundary phải bỏ qua có chủ đích, nhưng payload localization malformed phải hard fail;
   - empty localization component hợp lệ được phân loại `empty`, không tính failure.
7. Corpus gate: `failure_count = 0`, unique `(domain,key)`, source không rỗng, exact ordered-key hash, state counts và protected-token validation. Không gọi tập con parser được là full corpus.
8. Writer route phải được chứng minh trước handoff:
   - JSON → legacy copy-only rebuild;
   - reload JSON và so exact structure sau khi bỏ riêng trường volatile đã định danh;
   - `.uexp`/raw exports, NameMap, export count, class/outer/dependencies phải giữ nguyên;
   - legacy → Zen, `retoc verify`, rồi Zen → legacy với `global.utoc/global.ucas` để cung cấp `ScriptObjects`;
   - readback JSON exact equal và raw export mismatch `0`.
9. Context staging chỉ được gọi là graph context khi thật sự nối speaker/addressee/graph order. Context theo manifest/export order hoặc stable ID phải ghi rõ là heuristic; không tuyên bố hoàn chỉnh.
10. External ZIP chỉ tạo sau preparation gate. Gói translation-only gồm batch bất biến, prompt, plan, glossary/style/xưng hô, context, schema, example, companion skill, manifest và checksums. Khóa một filename output, batch ID, input SHA-256, row count và ordered key-set hash. Canonical master, importer/repacker, binary và private path không đưa ra ngoài.
11. File trả về là untrusted: tự hash, kiểm schema/key/source/token/state, semantic QA; không tin receipt hoặc tuyên bố hoàn tất. Canonical giữ nguyên nếu gate fail.

## Temporary mapping safety

Nếu tool bắt buộc mapping trong game root:

1. Hash mapping nguồn.
2. Copy tạm bằng transaction có cleanup trap/finally.
3. Xác minh hash bản tạm.
4. Chạy read-only extraction.
5. Xóa mapping dù lệnh thành công hay thất bại.
6. Xác minh game archives và live payload không đổi.

## Hard stops

- `failure_count > 0` chưa được phân loại.
- Mapping thiếu schema nhưng parser vẫn suy language theo số lượng/offset cố định.
- Copy-only semantic roundtrip khác raw exports/object graph.
- Zen verify pass nhưng chưa readback với ScriptObjects.
- Handoff gọi context/speaker mapping là hoàn chỉnh khi chỉ là ordinal heuristic.
- ZIP thiếu receipt hashes hoặc cho external provider sửa key/source/canonical.

## Evidence labels

- Parser sạch + canonical validator: `corpus_structurally_extracted`.
- Legacy/Zen exact semantic readback: `writer_route_structurally_proven`.
- ZIP checksum + exact key envelope: `external_handoff_ready`.
- Chỉ screenshot/checkpoints trên đúng build mới là `runtime_verified`.
