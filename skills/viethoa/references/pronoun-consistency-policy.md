# Directional Pronoun Consistency Policy & Validation

**Version:** 1.1.0  
**Schema:** `viethoa/pronoun-consistency-validator/v1`  
**Tool:** `scripts/pronoun_validator.py`  
**Template:** `templates/pronoun-matrix-template.json`  
**Attribution:** Ý tưởng ma trận xưng hô kế thừa từ `kann420/VH-Workflow-Skill` (MIT License) và được chuẩn hóa, nâng cấp thành engine kiểm định hai chiều (speaker -> listener), hỗ trợ 6 cấp độ ưu tiên, nhận biết vai phản thân và triệt tiêu bắt nhầm từ ghép.

---

## 1. Triết lý & Sự cần thiết

Trong tiếng Việt, đại từ nhân xưng (xưng hô) mang theo:
- **Tuổi tác, giới tính, quan hệ gia đình, cấp bậc và thái độ.**
- Phân biệt sâu sắc giữa văn nói (khẩu ngữ hội thoại) và văn viết (tài liệu/UI).
- Thay đổi theo thời gian/cốt truyện (giai đoạn quan hệ: *early -> mid -> late*).
- Thay đổi đột biến theo cảm xúc (giận dữ, thù địch, nổi loạn, thân mật).

Bản dịch hỏng nặng nhất khi AI dịch từng câu riêng lẻ mà không biết **ai đang nói với ai**, dẫn tới việc câu trước nhân vật xưng *"tôi - bạn"*, câu sau nhảy sang *"anh - em"*, hoặc đệ tử gọi sư phụ là *"mày"*.

---

## 2. Cấu trúc Ma trận Xưng hô 2 Chiều (`Pronoun Matrix`)

Ma trận xưng hô được lưu dưới dạng JSON chuẩn tại `templates/pronoun-matrix-template.json` hoặc trong thư mục `05_guides/pronoun_matrix.json` của từng dự án:

```json
{
  "$schema": "viethoa/pronoun-matrix/v1",
  "project": "Tên Game",
  "characters": {
    "Protagonist": { "gender": "choice", "age_group": "young_adult", "role": "hero" },
    "Mentor": { "gender": "male", "age_group": "elder", "role": "teacher" },
    "Entity": { "gender": "unknown", "age_group": "adult", "role": "npc" }
  },
  "matrices": [
    {
      "speaker": "Protagonist",
      "listener": "Mentor",
      "stage": "all",
      "self_pronouns": ["con", "tôi"],
      "call_pronouns": ["thầy", "sư phụ", "người"],
      "emotion_exceptions": {
        "rebellious": { "self_pronouns": ["tôi"], "call_pronouns": ["ông"] }
      },
      "confidence": "high"
    }
  ],
  "special_rules": {
    "forbidden_gendered_pronouns_for_unknown": ["cô", "nàng", "chị", "bà", "anh", "chú", "ông"],
    "allowed_neutral_pronouns_for_unknown": ["người đó", "họ", "kẻ đó", "đối phương", "người"],
    "group_call_pronouns": ["các bạn", "mọi người", "các ngươi", "chúng mày", "quý vị"]
  }
}
```

---

## 3. Thứ tự Ưu tiên Phân giải Quy tắc (6-Tier Deterministic Precedence)

Khi đối chiếu một dòng thoại giữa `speaker` và `listener` ở giai đoạn `stage`:
1. Khớp chính xác: `(speaker, listener, stage)`
2. Khớp theo cặp: `(speaker, listener, "all")`
3. Khớp người nói + giai đoạn: `(speaker, "*", stage)`
4. Khớp người nói toàn cục: `(speaker, "*", "all")`
5. Khớp người nghe + giai đoạn: `("*", listener, stage)`
6. Khớp người nghe toàn cục: `("*", listener, "all")`

---

## 4. Suy luận Người nghe theo Ngữ cảnh Hội thoại (`Conversational Inference`)

Với các game không có cột `listener` riêng biệt trong bảng text (chỉ có cột `speaker` và `context_id` / `scene`):
- Validator tự động quét turn-taking trong cùng một khối `context_id`.
- Nếu trong cảnh có đúng 2 nhân vật thoại qua lại luân phiên ($A \rightarrow B \rightarrow A$), validator tự động suy luận người nghe của $A$ là $B$ và ngược lại.
- Nếu không thể suy luận (độc thoại, cảnh đông người không rõ hướng), validator áp dụng quy tắc mặc định theo nhân vật `(speaker, "*", "all")`.

---

## 5. Phân loại Đại từ & Cơ chế Miễn trừ Ngữ nghĩa (Linguistic Rules)

Để triệt tiêu báo lỗi giả (false positive) mà vẫn giữ bộ lọc khắt khe:

1. **Tách biệt chiều gọi trực tiếp (`DIRECT_CALL_PRONOUNS`) và nhắc ngôi thứ ba (`THIRD_PERSON_MENTIONS`):**
   - Đại từ gọi trực tiếp: `mày, mi, ngươi, em, anh, chị, con, cháu, cô, chú, bác, ông, bà, cậu, bạn, ngài, thầy, sư phụ...` -> Được đối chiếu nghiêm ngặt với `call_pronouns` của ma trận.
   - Đại từ chỉ bên thứ ba vắng mặt / vật thể: `hắn, nó, họ, kẻ đó, gã đó, chúng nó...` -> KHÔNG bị coi là đại từ gọi người nghe; cho phép xuất hiện trong hội thoại hoặc suy nghĩ nội tâm.
2. **Kiểm định Vị trí Token Độc lập (`Token-Window Standalone Occurrence Matching`):**
   - Khắc phục triệt để lỗi nuốt cả câu (over-suppression) hoặc bắt nhầm cụm từ khi câu xuất hiện nhiều đại từ cùng loại.
   - **Lớp lọc tiền tố (`LEFT_MODIFIERS`):** `các, mấy, đám, lũ, nhóm, lời, tiếng, theo, nhờ`. Giúp phân biệt rạch ròi giữa việc xưng/gọi trực tiếp với các cấu trúc sở hữu / trích dẫn gián tiếp (như *"nghe lời anh dặn"*, *"theo lời anh dặn"*) và đại từ số nhiều chỉ nhóm (*"dắt theo các em"*).
   - **Lớp lọc hậu tố chỉ định (`RIGHT_DEMONSTRATIVES`):** `ấy, đó, này, kia`. Tự động miễn trừ ngôi thứ ba chỉ định như *"em ấy", "anh ấy", "cô ấy"* khi dùng đại từ thân tộc, tránh nhầm lẫn với đại từ gọi trực tiếp người nghe.
   - **Lớp lọc đặc tính thân tộc (`RIGHT_KINSHIP_TRAITS`):** `trai, gái, cả, hai, ba, út, họ, dâu, rể`. Tự động nhận diện các danh từ ghép quan hệ gia đình như *"anh trai", "chị gái", "em út"*.
3. **Nhận diện Đại từ Phản thân (`Reflexive Pronoun`):**
   - Từ `mình` khi đứng sau giới từ hoặc động từ tri giác/phản thân (`thấy mình, cảm thấy mình, nghĩ mình, cho mình, với mình, về mình, của mình, ở mình, cho riêng mình, chính mình, tự mình, một mình`) được nhận diện là *myself / oneself*, không bị đánh đồng với đại từ xưng/gọi thân mật.
4. **Miễn trừ Kính ngữ Xã giao (`Polite Honorifics`):**
   - Các cụm `thưa bà, thưa ông, thưa ngài, thưa cô, thưa thầy` được tự động chấp thuận khi đối thoại với bậc trên hoặc khách hàng.
5. **Bộ lọc Cụm danh từ / Phân loại từ (`COMPOUND_FALSE_POSITIVES`):**
   - Danh từ ghép và chỉ loại: `con đường, con mắt, con dao, cô đơn, cô giáo, anh hùng, chú ý, bác sĩ, một mình, tự mình, chính mình, anh trai, chị gái, em út...`
   - Phân loại đặc thù / lăng mạ trong game 18+: `cô thỏ, con đĩ, con khốn, con ranh, con điếm, thằng cha, thằng khốn...`
   - Chuẩn hóa hai chiều C28: So khớp thông qua góc nhìn `NFKC + casefold`, nhưng báo cáo vi phạm và dữ liệu xuất luôn bảo tồn 100% dạng chuẩn `NFC` nguyên gốc.

---

## 6. Vận hành Validator

```bash
# Kiểm tra độc lập trên bảng canonical CSV
python scripts/pronoun_validator.py \
  --csv path/to/canonical.csv \
  --matrix path/to/pronoun_matrix.json \
  --out-report reports/pronoun_drift_report.json
```

- **Nguyên tắc Read-Only:** Validator không bao giờ tự ý sửa canonical CSV (`canonical_modified: false`).
- Mọi cảnh báo `pronoun_drift` hoặc `gendered_pronoun_on_unknown` được xuất ra báo cáo để biên tập viên kiểm tra và điều chỉnh có ý thức qua `bientaptay`.
