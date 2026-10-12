# English-source semantic keep policy

Dùng khi authoritative source là English, đặc biệt trước external handoff. Mục tiêu là giữ đúng **tên/thuật ngữ game** nhưng vẫn dịch đầy đủ dialogue, description và UI generic. Không suy policy từ việc chuỗi viết hoa, nằm trong UI, hoặc trông giống tên.

## Hai lớp quyết định

1. **Term-level keep:** một câu vẫn dịch sang tiếng Việt, nhưng các locked term bên trong giữ English. Ví dụ `Upgrade Shadow Strike` → `Nâng cấp Shadow Strike`.
2. **Whole-row identity keep:** toàn target bằng đúng source chỉ khi exact `(domain,key)` đã được chứng minh là một nhãn định danh. Ví dụ standalone skill key `Shadow Strike` → `Shadow Strike`.

Không biến term-level keep thành whole-row passthrough. `source`, `content_type=ui_short`, title case hoặc target trùng source ở key khác không phải bằng chứng.

## Decision matrix

| `translation_policy` | Khi dùng | Target |
|---|---|---|
| `keep_identity` | Standalone exact key là proper noun; item name; named map/location/dungeon; skill/ability; Shell/skin; hoặc game-specific term đã khóa | Bằng source từng byte; không thêm danh xưng, dấu câu, singularize/pluralize |
| `translate_with_locked_terms` | Dialogue/description/UI/action có chứa một hay nhiều locked English terms | Dịch toàn bộ phần generic; chỉ giữ các term được liệt kê |
| `translate_full` | Dialogue, description, generic UI/action/stat, generic role/label | Dịch tự nhiên đầy đủ |
| `exclude_or_keep_technical` | Identifier, asset/path, debug, placeholder-only, metadata/legal/credits/platform text mà policy yêu cầu giữ | Loại khỏi corpus nếu không player-facing; nếu phải giữ thì exact-key policy |
| `needs_policy_context` | Semantic class chưa đủ bằng chứng | Không đoán; trả một câu hỏi cụ thể |

Mặc định **không** giữ English cho rarity, generic stat, generic role, button/action hoặc quest/achievement title chỉ vì chúng là UI. Chỉ giữ nếu glossary dự án hoặc exact-key evidence khóa chúng. Chính sách dự án/người dùng có thể thêm nhóm, nhưng phải ghi thành rule có evidence.

## Schema bắt buộc

`english-policy.csv` là immutable input của handoff:

```text
domain,key,source_sha256,content_type,semantic_class,translation_policy,
locked_english_terms,identity_expected,reason,evidence,policy_status
```

- `identity_expected` chỉ được điền cho `keep_identity` và phải bằng source chính xác.
- `locked_english_terms` là danh sách có cấu trúc, không phải chuỗi prose để matcher đoán.
- `evidence`: glossary lock, table/property path, neighboring keys, screenshot, reference table hoặc user policy.
- `policy_status`: `locked`, `receiver_review`, `needs_user_decision`.

Glossary term-level dùng:

```text
term,rule,scope,match_mode,aliases,reason,evidence
```

`match_mode` mặc định `token_boundary`; tên ngắn như `SAM`, `Alter`, `Guard`, `Leap` cấm substring matching.

## Phase 0 — policy audit trước Bulk Translation

Hermes tạo inventory và candidate policy; bên nhận handoff phải kiểm lại **trước Phase 1**:

1. Audit toàn bộ `keep_identity`, mọi `needs_policy_context`, và collision có cùng source nhưng khác domain/key/content type.
2. So current key, property/table path, neighboring labels, description/name pairing và glossary; không dùng source-only classification.
3. Trả `policy-audit.csv` với `accepted`, `propose_change` hoặc `needs_context`, kèm lý do ngắn theo exact key.
4. Chỉ đặt `policy_ready_for_bulk=true` khi mọi proposal đã được Hermes/user resolve, mọi row có `policy_status=locked`, và policy file mới có hash khóa.

Routine `translate_full` có thể sampling theo domain; identity candidates phải review 100%. Phase 0 chỉ chạy một lần mỗi source/glossary version, không lặp cho từng packet.

## Required QA

- `keep_identity`: exact `(domain,key,identity_expected,reason)` allowlist; wildcard và source-only allowlist bị cấm.
- `translate_with_locked_terms`: kiểm term bằng boundary + grammatical number; phần prose còn lại phải là tiếng Việt.
- `translate_full`: target bằng source hoặc residual English không giải thích được là lỗi.
- Scanner mixed-language phải mask đúng locked terms trước khi tính residual; không hạ ngưỡng để làm gate PASS.
- Xuất collision report cho identical source dùng khác semantic class. Không dedupe translation chỉ theo source.
- Identity policy không được singularize/pluralize: `Beacons`, `Shells`, `Tarstones` giữ đúng hình thức source khi key đó đã khóa.

## Examples

| Source/context | Policy | Correct |
|---|---|---|
| `Blackridge Hamlet` — location-name key | `keep_identity` | `Blackridge Hamlet` |
| `Travel to Blackridge Hamlet` | `translate_with_locked_terms` | `Đi đến Blackridge Hamlet` |
| `Shadow Strike` — skill-name key | `keep_identity` | `Shadow Strike` |
| `Each level upgrades Shadow Strike` | `translate_with_locked_terms` | `Mỗi cấp độ nâng cấp Shadow Strike` |
| `Health` — generic stat label | `translate_full` | `Sinh lực` |
| `Guard` — generic role/action | `translate_full` unless exact evidence says named term | bản Việt theo context |

## Token efficiency

- Root handoff chứa một policy/glossary đã hash; packet chỉ mang các rows/terms liên quan.
- Gửi collision/high-risk rows cho strong review; không bắt model phân loại lại hàng nghìn generic labels mỗi packet.
- Output chỉ trả key + mutable translation/review fields; không echo source/context dài.
- Reuse chỉ khi exact source, equivalent context, same semantic class và protected tokens đều khớp; không cache theo source text toàn cục.
