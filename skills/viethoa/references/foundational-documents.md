# Foundational methodology for `viethoa`

Các nguyên tắc dưới đây đã được hấp thụ từ tài liệu phương pháp của người dùng và là nội dung tự đủ của reference này. Các file Desktop gốc chỉ là provenance tùy chọn nếu còn tồn tại; workflow không được phụ thuộc vào đường dẫn tuyệt đối đó.

## Key rules absorbed

- Do not treat English `I/you` as enough for Vietnamese xưng hô.
- Use a secondary language when available to infer relationship/register:
  - Japanese first for RPG/Asian games when present.
  - Chinese for Sinosphere/fantasy/cultivation contexts.
  - French/Spanish/German for Western games when Japanese/Chinese are absent, mainly for formal vs informal distinction.
- Build workbook columns for source + reference language + Vietnamese target.
- Vietnamese localization must include glossary, style guide, pronoun rules, name-provenance policy/ledger, and context QA.
- For every proper name, country of origin is the starting point: prefer the creator/original-market canonical form, not a later English localization. Creator-published Latin spelling, an explicit user/glossary lock, and a documented native-country romanization are valid authority; an unknown collision stays `needs_review`/`needs_context`. Country alone does not override an entity's own foreign/Latin provenance.
- Unity hardcoded asset patching is risky; prefer structured localization tables and validate file sizes to prevent crash.
- Always QA font/wrap/overflow and in-game UI screens, not only dialogue.

## To the Moon lesson

To the Moon SerenityForge showed a special dynamic-pronoun issue: some scenes let the player choose Eva or Neil, but the English line remains shared. A static translation like `chú` breaks when Eva is selected. For future projects, flag dynamic-protagonist scenes and avoid gendered terms unless the text is truly speaker-specific.
