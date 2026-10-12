using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using BienTapTay.Core;

var tests = new (string Name, Action Run)[]
{
    ("Token pattern riêng từng bảng không bị kế thừa nhầm", PerTableTokenPattern),
    ("Whitespace identity giữ nguyên và không chấp nhận thay đổi", WhitespaceIdentity),
    ("CSV giữ BOM, CRLF, dấu phẩy, dấu nháy và xuống dòng", CsvRoundTrip),
    ("Lưu canonical chỉ đổi trường được phép", CanonicalSave),
    ("Lưu canonical kiểm toàn corpus và chỉ normalize dòng dirty", CanonicalSaveValidatesAllRows),
    ("Từ chối bản dịch làm mất protected token", TokenMismatchRejected),
    ("Token source là chuẩn dù cột protected token dùng delimiter cũ", ProtectedTokenDelimiterDoesNotCauseFalseError),
    ("Từ chối lưu khi canonical đã đổi bên ngoài", StaleSaveRejected),
    ("Glossary và xưng hô lưu nguyên tử như bảng CSV", ReferenceSave),
    ("Nhiều bảng dịch vẫn ghi trực tiếp đúng CSV nguồn", MultipleTranslationTablesStayAuthoritative),
    ("Tìm toàn project trả đúng file và exact key", ProjectSearchFindsAcrossTranslationTables),
    ("Tìm kiếm không đổi kết quả theo locale hệ điều hành", ProjectSearchIsCultureIndependent),
    ("Trang bản dịch mặc định 17 hàng", PageWindowDefaultsToSeventeenRows),
    ("Phân trang dùng số hàng người dùng chọn", PageWindowUsesRequestedPageSize),
    ("Glossary ưu tiên cụm dài và bỏ protected token", GlossaryPrefersLongPhrase),
    ("Glossary bỏ character term CJK quá ngắn", GlossaryRejectsShortGenericCharacter),
    ("Hoàn tác một dòng về snapshot vừa lưu", RevertRowToLastSavedSnapshot),
    ("Tìm/thay preview rồi áp dụng trong RAM", TranslationReplacePreviewAndApply),
    ("Tìm/thay làm mất protected token bị chặn toàn bộ", TranslationReplaceRejectsTokenDamage),
    ("Tìm/thay hoàn tác nguyên batch", TranslationReplaceBatchUndo),
    ("Undo batch không ghi đè edit mới", TranslationReplaceBatchUndoRejectsStale),
    ("Ngữ cảnh gộp thành lượt hội thoại trong cùng scene", DialogueContextUsesTurns),
    ("Diff ngoài hiển thị baseline local và file theo exact key", ExternalDiffShowsThreeSides),
    ("QA nhất quán phát hiện cùng source khác bản dịch", ConsistencyQaFindsDuplicateSource),
    ("QA nhất quán phát hiện lệch glossary", ConsistencyQaFindsGlossaryDrift),
    ("QA nhất quán phát hiện lệch xưng hô", ConsistencyQaFindsPronounDrift),
    ("QA xưng hô không coi tự xưng là gọi đối phương", ConsistencyQaSeparatesPronounDimensions),
    ("QA reference projection dùng chung glossary và pronouns", ConsistencyQaReferenceProjection),
    ("Quyết định QA lưu nguyên tử và đọc lại đúng fingerprint", QaDecisionRoundTrip),
    ("Quyết định QA cũ không áp dụng khi source hoặc target đổi", QaDecisionRejectsStaleContent),
    ("QA sidecar thiếu vẫn mở được và cho ghi", QaDecisionMissingSidecarRemainsWritable),
    ("QA sidecar JSON hỏng không chặn Open và giữ nguyên byte", QaDecisionCorruptJsonIsIsolated),
    ("QA sidecar schema lạ không chặn Open và giữ nguyên byte", QaDecisionInvalidSchemaIsIsolated),
    ("QA sidecar không đọc được không chặn Open và không bị đổi", QaDecisionUnreadableSidecarIsIsolated),
    ("QA sidecar shape malformed không throw và giữ nguyên byte", QaDecisionMalformedShapesAreIsolated),
    ("QA timestamp v1 Core/Python cùng một bảng hợp lệ/không hợp lệ", QaDecisionTimestampParityMatchesPython),
    ("QA snapshot báo cáo chỉ đọc và không lộ dictionary ghi", QaDecisionReportingSnapshotIsImmutable),
    ("Báo cáo QA JSON phân biệt stale orphan và sắp xếp deterministic", QaReportJsonOrdersAndDistinguishesStaleOrphan),
    ("Báo cáo QA CSV giữ Unicode BOM và JSON related_keys", QaReportCsvPreservesUnicodeAndRelatedKeys),
    ("Báo cáo QA sidecar hỏng vẫn xuất unreviewed và giữ byte", QaReportCorruptSidecarExportsUnreviewed),
    ("Xuất báo cáo QA từ chối đích cấm và ghi atomic", QaReportExportRejectsForbiddenAndWritesAtomically),
    ("Context packet QA giữ full key source reference target glossary và xưng hô", QaContextPacketContainsReviewEvidence),
    ("Clipboard bận thì thử lại rồi đặt đúng packet", ClipboardRetriesBusyThenSetsPacket),
    ("Clipboard bận hết lượt thì lỗi, không tạo file, canonical không đổi", ClipboardExhaustionFailsWithoutSideEffect),
    ("Clipboard lỗi không phải bận thì không thử lại", ClipboardDoesNotRetryNonBusyFailure),
    ("Chẩn đoán che đường dẫn nhà, biến môi trường bí mật và bearer", DiagnosticsRedactsHomeSecretsAndTokens),
    ("Chẩn đoán ghi JSONL, xoay vòng 64 KiB và giữ đúng 3 file", DiagnosticsWritesJsonlAndRotatesAtSixtyFourKiB),
    ("Chẩn đoán ghi hỏng không throw và không để lại temp", DiagnosticsWriteFailureIsSilentAndLeavesNoTemp),
    ("Chẩn đoán từ chối app/, canonical, sidecar và receipt", DiagnosticsRefusesForbiddenDestinations),
    ("Diff bảng tham chiếu phát hiện sửa thêm xóa và conflict", ReferenceTableExternalDiff),
    ("Diff reference dùng keyColumn cấu hình thay vì cột đầu", ReferenceUsesConfiguredKeyColumn),
    ("Reference từ chối key trống hoặc trùng trước khi ghi", ReferenceRejectsInvalidKeys),
    ("Glossary từ chối translation trống và status lạ", GlossaryValidationRejectsBadRows),
    ("Pronouns kiểm nội dung status và full evidence key", PronounValidationRejectsBadRows),
    ("Config bắt buộc keyColumn cho từng reference", ReferenceConfigRequiresKeyColumn),
};

var failed = 0;
foreach (var test in tests)
{
    try
    {
        test.Run();
        Console.WriteLine($"PASS {test.Name}");
    }
    catch (Exception ex)
    {
        failed++;
        Console.Error.WriteLine($"FAIL {test.Name}: {ex.Message}");
    }
}

var projectConfig = Environment.GetEnvironmentVariable("BIENTAPTAY_PROJECT_CONFIG");
if (failed == 0 && !string.IsNullOrWhiteSpace(projectConfig))
{
    try
    {
        var project = ProjectConfig.Load(projectConfig);
        var total = 0;
        foreach (var file in project.GetTranslationFiles())
        {
            var store = CanonicalStore.Open(project.ForTranslationFile(file));
            var issues = store.Rows
                .Select(row => (row.Key, Message: store.Validate(row)))
                .Where(item => !string.IsNullOrEmpty(item.Message))
                .Take(20)
                .ToArray();
            Check(issues.Length == 0, string.Join(Environment.NewLine, issues.Select(item => $"{file.Label} / {item.Key}: {item.Message}")));
            total += store.Rows.Count;
            Console.WriteLine($"PASS {file.Label}: {store.Rows.Count:N0} dòng, 0 lỗi QA");
        }
        var canonicalKeys = project.GetTranslationFiles()
            .SelectMany(file => CanonicalStore.Open(project.ForTranslationFile(file)).Rows)
            .Select(row => row.Key)
            .ToHashSet(StringComparer.Ordinal);
        foreach (var reference in project.References)
        {
            var store = CsvTableStore.Open(project.Resolve(reference.Path), reference.KeyColumn, reference.Id, canonicalKeys);
            store.Validate();
            Console.WriteLine($"PASS {reference.Label}: {store.Rows.Count:N0} dòng reference, 0 lỗi validator");
        }
        Console.WriteLine($"PASS toàn dự án: {total:N0} dòng text, 0 lỗi QA");
    }
    catch (Exception ex)
    {
        failed++;
        Console.Error.WriteLine($"FAIL canonical dự án: {ex.Message}");
    }
}

var consistencyConfig = Environment.GetEnvironmentVariable("BIENTAPTAY_CONSISTENCY_CONFIG");
if (failed == 0 && !string.IsNullOrWhiteSpace(consistencyConfig))
{
    try
    {
        var project = ProjectConfig.Load(consistencyConfig);
        var glossary = LoadGlossary(project);
        var pronouns = LoadPronouns(project);
        var totalIssues = 0;
        foreach (var file in project.GetTranslationFiles())
        {
            var config = project.ForTranslationFile(file);
            var before = Sha256(config.ResolvedCanonicalPath);
            var issues = ConsistencyQaAnalyzer.Analyze(CanonicalStore.Open(config).Rows, glossary, pronouns);
            var after = Sha256(config.ResolvedCanonicalPath);
            Check(before == after, $"QA nhất quán đã làm đổi canonical {file.Label}");
            totalIssues += issues.Count;
            Console.WriteLine($"PASS consistency {file.Label}: {issues.Count:N0} cảnh báo " +
                $"({issues.Count(item => item.Kind == ConsistencyIssueKind.DuplicateSource):N0} source, " +
                $"{issues.Count(item => item.Kind == ConsistencyIssueKind.GlossaryDrift):N0} glossary, " +
                $"{issues.Count(item => item.Kind == ConsistencyIssueKind.PronounDeviation):N0} xưng hô)");
            if (Environment.GetEnvironmentVariable("BIENTAPTAY_CONSISTENCY_SAMPLES") == "1")
                foreach (var issue in issues.GroupBy(item => item.Kind).SelectMany(group => group.Take(3)))
                    Console.WriteLine($"SAMPLE {file.Label} / {issue.Kind} / {issue.Key}: {issue.Message}");
        }
        Console.WriteLine($"PASS consistency toàn dự án: {totalIssues:N0} cảnh báo, canonical không đổi");
    }
    catch (Exception ex)
    {
        failed++;
        Console.Error.WriteLine($"FAIL consistency QA: {ex.Message}");
    }
}

return failed == 0 ? 0 : 1;

static IReadOnlyList<GlossaryCandidate> LoadGlossary(ProjectConfig project)
{
    var reference = project.References.FirstOrDefault(item => item.Id.Equals("glossary", StringComparison.OrdinalIgnoreCase));
    if (reference is null || !File.Exists(project.Resolve(reference.Path))) return [];
    var store = CsvTableStore.Open(project.Resolve(reference.Path), reference.KeyColumn, reference.Id);
    var term = FindHeader(store.Headers, "term", "source", "source_term");
    var translation = FindHeader(store.Headers, "translation", "vi", "target");
    if (term is null || translation is null) return [];
    var type = FindHeader(store.Headers, "type", "category");
    var context = FindHeader(store.Headers, "context", "rule", "notes");
    var status = FindHeader(store.Headers, "status", "state");
    return store.Rows.Select(row => new GlossaryCandidate(
        row[term],
        row[translation],
        type is null ? string.Empty : row[type],
        context is null ? string.Empty : row[context])
    {
        Status = status is null ? string.Empty : row[status]
    }).ToArray();
}

static IReadOnlyDictionary<string, PronounProfile> LoadPronouns(ProjectConfig project)
{
    var reference = project.References.FirstOrDefault(item => item.Id.Equals("pronouns", StringComparison.OrdinalIgnoreCase));
    if (reference is null || !File.Exists(project.Resolve(reference.Path)))
        return new Dictionary<string, PronounProfile>(StringComparer.OrdinalIgnoreCase);
    var canonicalKeys = project.GetTranslationFiles()
        .SelectMany(file => CanonicalStore.Open(project.ForTranslationFile(file)).Rows)
        .Select(row => row.Key);
    var store = CsvTableStore.Open(project.Resolve(reference.Path), reference.KeyColumn, reference.Id, canonicalKeys);
    var speaker = FindHeader(store.Headers, "speaker", "character", "name");
    if (speaker is null) return new Dictionary<string, PronounProfile>(StringComparer.OrdinalIgnoreCase);
    var self = FindHeader(store.Headers, "self_reference", "self", "first_person");
    var address = FindHeader(store.Headers, "address_form", "address", "second_person");
    var status = FindHeader(store.Headers, "status", "state");
    return store.Rows.Select(row => new PronounProfile(
            row[speaker],
            self is null ? string.Empty : row[self],
            address is null ? string.Empty : row[address],
            status is null ? string.Empty : row[status]))
        .Where(item => item.Speaker.Length > 0)
        .GroupBy(item => item.Speaker, StringComparer.OrdinalIgnoreCase)
        .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);
}

static string? FindHeader(IEnumerable<string> headers, params string[] candidates) =>
    candidates.Select(candidate => headers.FirstOrDefault(header => header.Equals(candidate, StringComparison.OrdinalIgnoreCase)))
        .FirstOrDefault(header => header is not null);

static void PerTableTokenPattern()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,,Hello {0},reference,Xin chào {0},,translated,\r\n", new UTF8Encoding(true));
    var config = ProjectConfig.Load(fixture.Config).ForTranslationFile(new TranslationFileConfig
    {
        Id = "dialogue", Path = fixture.Canonical, TokenPattern = @"\{[0-9]+\}"
    });
    var invalid = ProjectConfig.Load(fixture.Config);
    invalid.TokenPattern = "[";
    File.WriteAllText(fixture.Config, JsonSerializer.Serialize(invalid));
    Expect<InvalidDataException>(() => ProjectConfig.Load(fixture.Config));
    var store = CanonicalStore.Open(config);
    Equal(string.Empty, store.ValidateTarget(store.Rows[0], "Chào {0}"));
    Check(store.ValidateTarget(store.Rows[0], "Chào").Length > 0, "Missing token accepted");
    Check(store.ValidateTarget(store.Rows[0], "Chào {0} {0}").Length > 0, "Duplicate token accepted");
}

static void WhitespaceIdentity()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,,  ,reference,  ,,reviewed,\r\n", new UTF8Encoding(true));
    var store = CanonicalStore.Open(fixture.Config);
    Equal(string.Empty, store.ValidateTarget(store.Rows[0], "  "));
    Check(store.ValidateTarget(store.Rows[0], " ").Length > 0, "Changed whitespace accepted");
    store.Rows[0].Notes = "checked";
    store.Save();
    var reopened = CanonicalStore.Open(fixture.Config);
    Equal("  ", reopened.Rows[0].Target);
    Equal("reviewed", reopened.Rows[0].Status);
    Equal("checked", reopened.Rows[0].Notes);
    var savedHash = Sha256(fixture.Canonical);
    reopened.Rows[0].Target = " ";
    Expect<CanonicalValidationException>(() => reopened.Save());
    Equal(savedHash, Sha256(fixture.Canonical));
}

static void CsvRoundTrip()
{
    const string text = "\uFEFFkey,source,target\r\n1,\"A, B\",\"Dòng 1\r\nDòng 2\"\r\n2,\"Anh nói \"\"được\"\"\",OK\r\n";
    var document = CsvDocument.Parse(text);
    Equal(true, document.HasBom);
    Equal("\r\n", document.NewLine);
    Equal("A, B", document.Rows[0]["source"]);
    Equal("Dòng 1\r\nDòng 2", document.Rows[0]["target"]);
    Equal("Anh nói \"được\"", document.Rows[1]["source"]);
    var reparsed = CsvDocument.Parse(document.Serialize());
    Equal(document.Headers, reparsed.Headers);
    Equal(document.Rows[0]["target"], reparsed.Rows[0]["target"]);
}

static void CanonicalSave()
{
    using var fixture = new Fixture();
    var before = CsvDocument.Parse(File.ReadAllText(fixture.Canonical, Encoding.UTF8));
    var store = CanonicalStore.Open(fixture.Config);
    var row = store.Rows.Single(item => item.Key == "scene::001");
    row.Target = "Xin chào<br>";
    row.Status = "translated";
    row.Notes = "Sửa bằng bientaptay";
    store.Save();

    var after = CsvDocument.Parse(File.ReadAllText(fixture.Canonical, Encoding.UTF8));
    Equal(before.Headers, after.Headers);
    Equal(before.Rows.Count, after.Rows.Count);
    Equal("Xin chào<br>", after.Rows[0]["translation_vi"]);
    Equal("translated", after.Rows[0]["status"]);
    Equal("Sửa bằng bientaptay", after.Rows[0]["review_note"]);
    Equal(before.Rows[0]["source_ja"], after.Rows[0]["source_ja"]);
    Equal(before.Rows[1].Values, after.Rows[1].Values);
    Check(File.Exists(fixture.Canonical + ".bientaptay.bak"), "Thiếu checkpoint backup");
}

static void CanonicalSaveValidatesAllRows()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,Ema,Xin<br>,参考,,<br>,pending,\r\n" +
        "scene::002,,Không token,参考,,,translated,dòng lỗi có sẵn\r\n",
        new UTF8Encoding(true));
    var store = CanonicalStore.Open(fixture.Config);
    store.Rows[0].Target = "Xin chào<br>";
    var before = Sha256(fixture.Canonical);

    Expect<CanonicalValidationException>(() => store.Save());

    Equal("translated", store.Rows[0].Status);
    Equal("translated", store.Rows[1].Status);
    Equal(before, Sha256(fixture.Canonical));
}

static void TokenMismatchRejected()
{
    using var fixture = new Fixture();
    var before = Sha256(fixture.Canonical);
    var store = CanonicalStore.Open(fixture.Config);
    var row = store.Rows.Single(item => item.Key == "scene::001");
    row.Target = "Xin chào";
    row.Status = "translated";
    Expect<CanonicalValidationException>(() => store.Save());
    Equal(before, Sha256(fixture.Canonical));
}

static void ProtectedTokenDelimiterDoesNotCauseFalseError()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "a,Ema,\"<ruby=\"\"x\"\">a</ruby><br>\",ref,\"<ruby=\"\"x\"\">b</ruby><br>\",\"<ruby=\"\"x\"\">|</ruby>|<br>\",translated,\r\n",
        new UTF8Encoding(true));

    var store = CanonicalStore.Open(fixture.Config);
    Check(string.IsNullOrEmpty(store.Validate(store.Rows[0])), "delimiter legacy trong protected_tokens không được tạo lỗi giả");
}

static void StaleSaveRejected()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    store.Rows[0].Target = "Xin chào<br>";
    store.Rows[0].Status = "translated";
    File.AppendAllText(fixture.Canonical, "\r\n", Encoding.UTF8);
    Expect<StaleCanonicalException>(() => store.Save());
}

static void ReferenceSave()
{
    using var fixture = new Fixture();
    var store = CsvTableStore.Open(fixture.Glossary, "term", "glossary");
    store.Rows[0]["translation"] = "Cô gái phép thuật";
    store.AddRow(new Dictionary<string, string>
    {
        ["term"] = "Witch Trial",
        ["translation"] = "Phiên tòa Phù thủy",
        ["context"] = "Tên nghi thức",
        ["status"] = "locked",
    });
    store.Save();
    var reloaded = CsvTableStore.Open(fixture.Glossary, "term", "glossary");
    Equal(2, reloaded.Rows.Count);
    Equal("Cô gái phép thuật", reloaded.Rows[0]["translation"]);
    Equal("Phiên tòa Phù thủy", reloaded.Rows[1]["translation"]);
    Check(File.Exists(fixture.Glossary + ".bientaptay.bak"), "Thiếu backup glossary");
}

static void MultipleTranslationTablesStayAuthoritative()
{
    using var fixture = new Fixture();
    var ui = Path.Combine(Path.GetDirectoryName(fixture.Config)!, "ui.csv");
    File.WriteAllText(ui,
        "key,document,source_ja,source_zh_hans,translation_vi,status,review_note\r\n" +
        "ui::1,Options,設定,设置,Cài đặt,reviewed,\r\n",
        new UTF8Encoding(false));
    File.WriteAllText(fixture.Config,
        """
        {
          "schemaVersion": 1,
          "projectName": "Test",
          "canonicalPath": "canonical.csv",
          "sourceFields": [{"column":"source_ja","label":"Nguồn"}],
          "translationFiles": [
            {"id":"scripts","label":"Kịch bản","path":"canonical.csv"},
            {
              "id":"managed-ui","label":"UI hệ thống","path":"ui.csv",
              "sourceFields":[
                {"column":"source_ja","label":"Nguồn chuẩn"},
                {"column":"source_zh_hans","label":"Tham khảo"}
              ],
              "speakerColumn":"",
              "groupColumn":"document",
              "notesColumn":"review_note",
              "protectedTokensColumn":""
            }
          ]
        }
        """, new UTF8Encoding(false));

    var project = ProjectConfig.Load(fixture.Config);
    var files = project.GetTranslationFiles();
    Equal(2, files.Count);
    var uiConfig = project.ForTranslationFile(files[1]);
    Equal(Path.GetFullPath(ui), uiConfig.ResolvedCanonicalPath);
    Equal("document", uiConfig.GroupColumn);
    Equal("", uiConfig.SpeakerColumn);
    var store = CanonicalStore.Open(uiConfig);
    store.Rows[0].Target = "Thiết lập";
    store.Save();
    Check(File.ReadAllText(ui, Encoding.UTF8).Contains("Thiết lập", StringComparison.Ordinal), "Edit UI không ghi vào ui.csv");
    Check(!File.ReadAllText(fixture.Canonical, Encoding.UTF8).Contains("Thiết lập", StringComparison.Ordinal), "Bảng chính bị sửa nhầm");
}

static void ProjectSearchFindsAcrossTranslationTables()
{
    using var fixture = new Fixture();
    var ui = Path.Combine(Path.GetDirectoryName(fixture.Config)!, "ui.csv");
    File.WriteAllText(ui,
        "key,document,source_ja,source_zh_hans,translation_vi,status,review_note\r\n" +
        "ui::1,Options,設定,设置,Cài đặt nâng cao,reviewed,\r\n",
        new UTF8Encoding(false));
    File.WriteAllText(fixture.Config,
        """
        {
          "schemaVersion": 1,
          "projectName": "Test",
          "canonicalPath": "canonical.csv",
          "sourceFields": [{"column":"source_ja","label":"Nguồn"}],
          "translationFiles": [
            {"id":"scripts","label":"Kịch bản","path":"canonical.csv"},
            {
              "id":"ui","label":"UI","path":"ui.csv",
              "sourceFields":[{"column":"source_ja","label":"Nguồn"},{"column":"source_zh_hans","label":"Tham khảo"}],
              "speakerColumn":"","groupColumn":"document","notesColumn":"review_note","protectedTokensColumn":""
            }
          ]
        }
        """, new UTF8Encoding(false));

    var project = ProjectConfig.Load(fixture.Config);
    var datasets = project.GetTranslationFiles().Select(file => new TranslationSearchDataset(
        file.Id,
        file.Label,
        CanonicalStore.Open(project.ForTranslationFile(file)).Rows)).ToArray();
    var canonicalHash = Sha256(fixture.Canonical);
    var uiHash = Sha256(ui);

    var sourceResult = TranslationProjectSearch.Find(datasets, "设置").Single();
    Equal("ui", sourceResult.FileId);
    Equal("ui::1", sourceResult.Key);
    Equal("Nguồn", sourceResult.MatchField);
    var keyResult = TranslationProjectSearch.Find(datasets, "scene::002").Single();
    Equal("scripts", keyResult.FileId);
    Equal("scene::002", keyResult.Key);
    Equal(canonicalHash, Sha256(fixture.Canonical));
    Equal(uiHash, Sha256(ui));
}

static void ProjectSearchIsCultureIndependent()
{
    using var fixture = new Fixture();
    var originalCulture = CultureInfo.CurrentCulture;
    var originalUiCulture = CultureInfo.CurrentUICulture;
    try
    {
        CultureInfo.CurrentCulture = new CultureInfo("tr-TR");
        CultureInfo.CurrentUICulture = new CultureInfo("tr-TR");
        var project = ProjectConfig.Load(fixture.Config);
        var file = project.GetTranslationFiles()[0];
        var dataset = new TranslationSearchDataset(file.Id, file.Label, CanonicalStore.Open(project.ForTranslationFile(file)).Rows);

        Equal("scene::001", TranslationProjectSearch.Find([dataset], "XIN<BR>").Single().Key);
    }
    finally
    {
        CultureInfo.CurrentCulture = originalCulture;
        CultureInfo.CurrentUICulture = originalUiCulture;
    }
}

static string Sha256(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

static void Check(bool condition, string message)
{
    if (!condition) throw new InvalidOperationException(message);
}

static void PageWindowDefaultsToSeventeenRows()
{
    var first = PageWindow.Clamp(-3, 40);
    Equal(0, first.Page);
    Equal(3, first.PageCount);
    Equal(0, first.Skip);
    Equal(17, first.Take);

    var last = PageWindow.Clamp(99, 40);
    Equal(2, last.Page);
    Equal(34, last.Skip);
    Equal(6, last.Take);

    var empty = PageWindow.Clamp(4, 0);
    Equal(0, empty.Page);
    Equal(1, empty.PageCount);
    Equal(0, empty.Take);
}

static void PageWindowUsesRequestedPageSize()
{
    var page = PageWindow.Clamp(page: 1, filteredCount: 50, pageSize: 25);
    Equal(1, page.Page);
    Equal(2, page.PageCount);
    Equal(25, page.Skip);
    Equal(25, page.Take);
}

static void GlossaryPrefersLongPhrase()
{
    var matches = GlossaryMatcher.Find(
    [
        new("少女", "Cô gái", "character", ""),
        new("魔法少女", "Cô gái phép thuật", "system", ""),
        new("魔法", "Phép thuật", "system", ""),
        new("<br>", "<br>", "protected_token", ""),
    ], "魔法少女<br>");
    Equal(new[] { "魔法少女" }, matches.Select(match => match.Term));
}

static void GlossaryRejectsShortGenericCharacter()
{
    var matches = GlossaryMatcher.Find(
    [
        new("少女", "Cô gái", "character", ""),
        new("看守", "Cai ngục", "role", ""),
    ], "少女と看守");
    Equal(new[] { "看守" }, matches.Select(match => match.Term));
}

static void RevertRowToLastSavedSnapshot()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    var row = store.Rows[0];
    row.Target = "Bản vừa lưu<br>";
    row.Status = "translated";
    row.Notes = "mốc lưu";
    store.Save();
    var savedHash = Sha256(fixture.Canonical);

    row.Target = "Bản nháp khác<br>";
    row.Status = "reviewed";
    row.Notes = "nháp";
    Check(store.HasUnsavedChanges, "Dòng sửa phải dirty trước hoàn tác");
    store.Revert(row);

    Equal("Bản vừa lưu<br>", row.Target);
    Equal("translated", row.Status);
    Equal("mốc lưu", row.Notes);
    Check(!store.HasUnsavedChanges, "Hoàn tác dòng phải xóa dirty state");
    Equal(savedHash, Sha256(fixture.Canonical));
}

static void TranslationReplacePreviewAndApply()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    var row = store.Rows[0];
    row.Target = "Xin chào, chào nhé<br>";
    row.Status = "translated";
    var diskHash = Sha256(fixture.Canonical);

    var plan = TranslationReplacePlanner.Create(store, store.Rows, "chào", "chào bạn", matchCase: true);

    Equal(1, plan.Items.Count);
    Equal(2, plan.TotalOccurrences);
    Equal(true, plan.CanApply);
    Equal("Xin chào, chào nhé<br>", row.Target);
    TranslationReplacePlanner.Apply(plan);
    Equal("Xin chào bạn, chào bạn nhé<br>", row.Target);
    Equal(diskHash, Sha256(fixture.Canonical));
}

static void TranslationReplaceRejectsTokenDamage()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    var row = store.Rows[0];
    row.Target = "Xin chào<br>";
    row.Status = "translated";

    var plan = TranslationReplacePlanner.Create(store, [row], "<br>", "", matchCase: true);

    Equal(false, plan.CanApply);
    Check(plan.Items.Single().ValidationMessage.Contains("Protected token", StringComparison.Ordinal), "Preview phải báo token mismatch");
    Expect<CanonicalValidationException>(() => TranslationReplacePlanner.Apply(plan));
    Equal("Xin chào<br>", row.Target);
}

static void TranslationReplaceBatchUndo()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    store.Rows[0].Target = "Xin chào<br>";
    store.Rows[0].Status = "translated";
    store.Rows[1].Target = "Chào chào";
    store.Rows[1].Status = "translated";
    var beforeHash = Sha256(fixture.Canonical);

    var plan = TranslationReplacePlanner.Create(store, store.Rows, "chào", "chào bạn", matchCase: false);
    var undo = TranslationReplacePlanner.Apply(plan);
    Equal("Xin chào bạn<br>", store.Rows[0].Target);
    Equal("chào bạn chào bạn", store.Rows[1].Target);
    undo.Undo();
    Equal("Xin chào<br>", store.Rows[0].Target);
    Equal("Chào chào", store.Rows[1].Target);
    Equal(beforeHash, Sha256(fixture.Canonical));
}

static void TranslationReplaceBatchUndoRejectsStale()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    store.Rows[0].Target = "Xin chào<br>";
    store.Rows[0].Status = "translated";
    store.Rows[1].Target = "Chào chào";
    store.Rows[1].Status = "translated";
    var plan = TranslationReplacePlanner.Create(store, store.Rows, "chào", "chào bạn", matchCase: false);
    var undo = TranslationReplacePlanner.Apply(plan);
    store.Rows[1].Target = "Edit mới";

    Expect<InvalidOperationException>(() => undo.Undo());
    Equal("Xin chào bạn<br>", store.Rows[0].Target);
    Equal("Edit mới", store.Rows[1].Target);
}

static void DialogueContextUsesTurns()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,asset,status,review_note\r\n" +
        "scene::001,Ema,A1,R1,V1,,scene,translated,\r\n" +
        "scene::002,Ema,A2,R2,V2,,scene,translated,\r\n" +
        "scene::003,@print |#n| speed,Narrative,R3,Dẫn chuyện,,scene,translated,\r\n" +
        "scene::004,Hiro,H1,R4,Hiro nói,,scene,translated,\r\n" +
        "scene::005,@choice |#c| button,C1,R5,Lựa chọn,,scene,translated,\r\n" +
        "scene::006,Ema,A3,R6,V3,,scene,translated,\r\n" +
        "other::001,Ema,OUT,R7,Ngoài scene,,other,translated,\r\n",
        new UTF8Encoding(true));
    File.WriteAllText(fixture.Config,
        """
        {
          "projectName":"Test", "canonicalPath":"canonical.csv", "keyColumn":"key",
          "sourceFields":[{"column":"source_ja","label":"Nguồn"}],
          "targetColumn":"translation_vi", "speakerColumn":"speaker", "groupColumn":"asset",
          "statusColumn":"status", "notesColumn":"review_note", "protectedTokensColumn":"protected_tokens",
          "statuses":["pending","translated","reviewed","needs_context"]
        }
        """, new UTF8Encoding(false));
    var store = CanonicalStore.Open(fixture.Config);

    var turns = DialogueContextBuilder.Build(store.Rows, selectedIndex: 3, radius: 2);

    Equal(5, turns.Count);
    Equal("Ema", turns[0].Speaker);
    Equal(new[] { "scene::001", "scene::002" }, turns[0].Keys);
    Equal("Dẫn chuyện", turns[1].Speaker);
    Equal("Hiro", turns[2].Speaker);
    Equal(true, turns[2].IsSelected);
    Equal("Lựa chọn", turns[3].Speaker);
    Check(turns.All(turn => turn.Keys.All(key => key.StartsWith("scene::", StringComparison.Ordinal))), "Không được kéo dòng ngoài scene vào context");
}

static void ExternalDiffShowsThreeSides()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    store.Rows[0].Target = "Local<br>";
    store.Rows[0].Status = "translated";
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,Ema,Xin ngoài<br>,参考,Hermes<br>,<br>,translated,ngoài\r\n" +
        "scene::002,,Không token,参考,Đã dịch,,translated,giữ nguyên\r\n" +
        "scene::003,Hiro,Mới,新,Mới,,translated,\r\n",
        new UTF8Encoding(true));

    var changes = store.CompareWithDisk();

    var target = changes.Single(change => change.Key == "scene::001" && change.Field == "translation_vi");
    Equal("", target.LoadedValue);
    Equal("Local<br>", target.LocalValue);
    Equal("Hermes<br>", target.ExternalValue);
    Equal(true, target.IsConflict);
    var source = changes.Single(change => change.Key == "scene::001" && change.Field == "source_ja");
    Equal(false, source.IsConflict);
    Check(changes.Any(change => change.Key == "scene::003" && change.Kind == ExternalChangeKind.Added), "Thiếu dòng mới trong diff");
    Equal("Local<br>", store.Rows[0].Target);
}

static void ConsistencyQaFindsDuplicateSource()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,Ema,同じ,参考,A,,translated,\r\n" +
        "scene::002,Ema,同じ,参考,B,,translated,\r\n",
        new UTF8Encoding(false));
    var store = CanonicalStore.Open(fixture.Config);

    var issues = ConsistencyQaAnalyzer.Analyze(store.Rows, [], new Dictionary<string, PronounProfile>());

    var issue = issues.Single(item => item.Kind == ConsistencyIssueKind.DuplicateSource);
    Equal("scene::001", issue.Key);
    Check(issue.RelatedKeys.Any(key => key.Equals("scene::002", StringComparison.Ordinal)), "QA phải liệt kê key cùng nhóm");
    Check(issue.Message.Contains("2", StringComparison.Ordinal), "QA phải nêu số biến thể");
}

static void ConsistencyQaFindsGlossaryDrift()
{
    using var fixture = new Fixture();
    var store = CanonicalStore.Open(fixture.Config);
    store.Rows[0].Target = "Phù thủy";
    var glossary = new[] { new GlossaryCandidate("Xin", "Nữ phù thủy", "term", "locked") };

    var issues = ConsistencyQaAnalyzer.Analyze(store.Rows, glossary, new Dictionary<string, PronounProfile>());

    var issue = issues.Single(item => item.Kind == ConsistencyIssueKind.GlossaryDrift);
    Equal("scene::001", issue.Key);
    Check(issue.Message.Contains("Nữ phù thủy", StringComparison.Ordinal), "QA phải nêu bản dịch glossary");
}

static void ConsistencyQaFindsPronounDrift()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,Ema,私は学生です。,参考,Tao là học sinh.,,translated,\r\n",
        new UTF8Encoding(false));
    var store = CanonicalStore.Open(fixture.Config);
    var profiles = new Dictionary<string, PronounProfile>(StringComparer.OrdinalIgnoreCase)
    {
        ["Ema"] = new("Ema", "tôi", "cậu", "reviewed")
    };

    var issues = ConsistencyQaAnalyzer.Analyze(store.Rows, [], profiles);

    var issue = issues.Single(item => item.Kind == ConsistencyIssueKind.PronounDeviation);
    Equal("scene::001", issue.Key);
    Check(issue.Message.Contains("tao", StringComparison.OrdinalIgnoreCase), "QA phải nêu form đang dùng");
}

static void ConsistencyQaSeparatesPronounDimensions()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Canonical,
        "key,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
        "scene::001,Ema,あなたを守る。,参考,Tôi sẽ bảo vệ cậu.,,translated,\r\n",
        new UTF8Encoding(false));
    var store = CanonicalStore.Open(fixture.Config);
    var profiles = new Dictionary<string, PronounProfile>(StringComparer.OrdinalIgnoreCase)
    {
        ["Ema"] = new("Ema", "tôi", "cậu", "reviewed")
    };

    var issues = ConsistencyQaAnalyzer.Analyze(store.Rows, [], profiles);

    Check(!issues.Any(item => item.Kind == ConsistencyIssueKind.PronounDeviation), "Tự xưng tôi không được flag như address");
}

static void ConsistencyQaReferenceProjection()
{
    var root = Path.Combine(Path.GetTempPath(), "bientaptay-qa-reference-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(root);
    try
    {
        var glossaryPath = Path.Combine(root, "glossary.csv");
        var pronounsPath = Path.Combine(root, "pronouns.csv");
        File.WriteAllText(glossaryPath,
            "term,translation,type,context,status\r\n魔女,phù thủy,title,locked term,locked\r\n",
            new UTF8Encoding(true));
        File.WriteAllText(pronounsPath,
            "speaker,self_reference,address_form,status\r\nEma,tôi,cậu,reviewed\r\n",
            new UTF8Encoding(true));

        var data = ConsistencyQaReferenceData.From(
            CsvTableStore.Open(glossaryPath, "term"),
            CsvTableStore.Open(pronounsPath, "speaker"));

        Equal(1, data.Glossary.Count);
        Equal("魔女", data.Glossary[0].Term);
        Equal("locked", data.Glossary[0].Status);
        Check(data.Pronouns.TryGetValue("ema", out var profile), "Pronoun lookup phải case-insensitive");
        Equal("tôi", profile!.SelfReference);
        Equal("cậu", profile.AddressForm);
    }
    finally
    {
        Directory.Delete(root, true);
    }
}

static void QaDecisionRoundTrip()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-decisions-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(directory);
    try
    {
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        var store = QaDecisionStore.Open(path);

        store.Set(
            "scripts",
            issue,
            QaTriageStatus.NeedsFix,
            "Sửa ở lượt review sau.",
            new DateTimeOffset(2026, 9, 2, 4, 0, 0, TimeSpan.Zero));

        var match = QaDecisionStore.Open(path).Resolve("scripts", issue);
        Equal(QaTriageStatus.NeedsFix, match.Status);
        Equal("Sửa ở lượt review sau.", match.Note);
        Equal(false, match.IsStale);
        Check(match.DecisionId.Length == 64, "Decision ID phải là SHA-256 hex.");
        Check(!Directory.EnumerateFiles(directory, "*.tmp").Any(), "Không được để temp sau atomic save.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaDecisionRejectsStaleContent()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-stale-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(directory);
    try
    {
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        var store = QaDecisionStore.Open(path);
        store.Set("scripts", issue, QaTriageStatus.AcceptedDifference, "Hợp scene này.", DateTimeOffset.UtcNow);
        foreach (var changed in new[]
                 {
                     issue with { Source = "Chào buổi sáng" },
                     issue with { Target = "Nữ phù thủy" },
                 })
        {
            var match = store.Resolve("scripts", changed);
            Equal(QaTriageStatus.Unreviewed, match.Status);
            Equal(true, match.IsStale);
            Equal("Hợp scene này.", match.Note);
        }
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaDecisionMissingSidecarRemainsWritable()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-missing-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(directory);
    try
    {
        var store = QaDecisionStore.Open(path);
        Check(store.CanMutate, "Sidecar thiếu phải vẫn cho ghi quyết định QA.");
        Check(string.IsNullOrEmpty(store.UnavailableReason), "Sidecar thiếu không phải lỗi hỏng.");
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        store.Set("scripts", issue, QaTriageStatus.NeedsFix, "ghi mới", DateTimeOffset.UtcNow);
        Check(File.Exists(path), "Lần ghi đầu phải tạo sidecar.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaDecisionCorruptJsonIsIsolated()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-corrupt-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(directory);
    var corrupt = "{not-json"u8.ToArray();
    File.WriteAllBytes(path, corrupt);
    try
    {
        var store = QaDecisionStore.Open(path);
        Check(!store.CanMutate, "Sidecar hỏng phải khóa ghi quyết định QA.");
        Check(!string.IsNullOrWhiteSpace(store.UnavailableReason), "Phải có lý do tiếng Việt khi sidecar hỏng.");
        Check(store.UnavailableReason.Contains("biên tập canonical", StringComparison.Ordinal), store.UnavailableReason);
        Check(store.UnavailableReason.Contains("chỉ đọc", StringComparison.Ordinal), store.UnavailableReason);
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        var match = store.Resolve("scripts", issue);
        Equal(QaTriageStatus.Unreviewed, match.Status);
        var setRejected = false;
        try
        {
            store.Set("scripts", issue, QaTriageStatus.NeedsFix, "không được ghi", DateTimeOffset.UtcNow);
        }
        catch (InvalidOperationException)
        {
            setRejected = true;
        }
        Check(setRejected, "Set phải từ chối khi sidecar hỏng.");
        Check(corrupt.SequenceEqual(File.ReadAllBytes(path)), "Không được sửa/đổi tên/ghi đè sidecar hỏng.");
        Check(Directory.GetFiles(directory).Length == 1, "Không được tạo file phụ khi sidecar hỏng.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaDecisionInvalidSchemaIsIsolated()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-schema-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(directory);
    var bytes = """{"schema":"other/v0","decisions":[]}"""u8.ToArray();
    File.WriteAllBytes(path, bytes);
    try
    {
        var store = QaDecisionStore.Open(path);
        Check(!store.CanMutate, "Schema lạ phải khóa ghi quyết định QA.");
        Equal(QaDecisionStore.UnavailableMessage, store.UnavailableReason);
        Check(bytes.SequenceEqual(File.ReadAllBytes(path)), "Không được sửa sidecar schema lạ.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaDecisionUnreadableSidecarIsIsolated()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-unreadable-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(path);
    try
    {
        var store = QaDecisionStore.Open(path);
        Check(!store.CanMutate, "Sidecar không đọc được phải khóa ghi.");
        Equal(QaDecisionStore.UnavailableMessage, store.UnavailableReason);
        Check(Directory.Exists(path), "Không được đổi sidecar không đọc được thành file.");
        Check(Directory.GetFiles(directory).Length == 0, "Không được tạo file phụ khi sidecar không đọc được.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaDecisionMalformedShapesAreIsolated()
{
    var cases = new (string Name, byte[] Bytes)[]
    {
        ("null-schema", """{"schema":null,"decisions":[]}"""u8.ToArray()),
        ("null-decisions", """{"schema":"bientaptay-qa-decisions/v1","decisions":null}"""u8.ToArray()),
        ("null-record-fields", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":null,"translationId":"scripts","kind":"GlossaryDrift","key":null,"relatedKeys":[],"contentFingerprint":null,"status":null,"note":"","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("non-object-root", "[1,2,3]"u8.ToArray()),
        ("null-decision-element", """{"schema":"bientaptay-qa-decisions/v1","decisions":[null]}"""u8.ToArray()),
        ("duplicate-id-case-insensitive", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"},{"id":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA","translationId":"scripts","kind":"GlossaryDrift","key":"scene::002","relatedKeys":["scene::002"],"contentFingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","status":"needs_fix","note":"b","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("duplicate-id-exact", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"},{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::002","relatedKeys":["scene::002"],"contentFingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","status":"needs_fix","note":"b","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("kind-null", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":null,"key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("kind-invalid", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"NotAKind","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("related-keys-null", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":null,"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("related-keys-contains-null", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":[null],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("related-keys-blank", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":[" "],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("status-null", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":null,"note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("status-unreviewed", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"unreviewed","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("status-accepted", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"accepted","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("note-null", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":null,"updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("updated-at-missing", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a"}]}"""u8.ToArray()),
        ("updated-at-default", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"0001-01-01T00:00:00+00:00"}]}"""u8.ToArray()),
        ("updated-at-space", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02 00:00:00"}]}"""u8.ToArray()),
        ("updated-at-offset-15", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00+15:00"}]}"""u8.ToArray()),
        ("id-non-hex", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
        ("fingerprint-non-hex", """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray()),
    };
    foreach (var item in cases)
    {
        var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-shape-" + item.Name + "-" + Guid.NewGuid().ToString("N"));
        var path = Path.Combine(directory, "qa-decisions.json");
        Directory.CreateDirectory(directory);
        File.WriteAllBytes(path, item.Bytes);
        try
        {
            QaDecisionStore store;
            try
            {
                store = QaDecisionStore.Open(path);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(item.Name + " Open must not throw: " + ex);
            }
            Check(!store.CanMutate, item.Name + " phải khóa ghi.");
            Equal(QaDecisionStore.UnavailableMessage, store.UnavailableReason);
            Check(item.Bytes.SequenceEqual(File.ReadAllBytes(path)), item.Name + " phải giữ nguyên byte.");
            Check(Directory.GetFiles(directory).Length == 1, item.Name + " không được tạo file phụ.");
            var issue = new ConsistencyIssue(
                ConsistencyIssueKind.GlossaryDrift,
                "Cảnh báo",
                "scene::001",
                "Ema",
                "Glossary yêu cầu Nữ phù thủy.",
                "Xin chào",
                "Phù thủy",
                ["scene::001"]);
            var setRejected = false;
            try
            {
                store.Set("scripts", issue, QaTriageStatus.NeedsFix, "không được ghi", DateTimeOffset.UtcNow);
            }
            catch (InvalidOperationException)
            {
                setRejected = true;
            }
            Check(setRejected, item.Name + " Set phải từ chối.");
            Check(item.Bytes.SequenceEqual(File.ReadAllBytes(path)), item.Name + " Set không được đổi sidecar.");
        }
        finally
        {
            Directory.Delete(directory, true);
        }
    }

    var emptyNoteDirectory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-empty-note-" + Guid.NewGuid().ToString("N"));
    var emptyNotePath = Path.Combine(emptyNoteDirectory, "qa-decisions.json");
    Directory.CreateDirectory(emptyNoteDirectory);
    var emptyNoteBytes = """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"","updatedAtUtc":"2026-09-02T00:00:00Z"}]}"""u8.ToArray();
    File.WriteAllBytes(emptyNotePath, emptyNoteBytes);
    try
    {
        var writable = QaDecisionStore.Open(emptyNotePath);
        Check(writable.CanMutate, "Ghi chú rỗng vẫn phải cho ghi quyết định QA.");
        Check(string.IsNullOrEmpty(writable.UnavailableReason), "Ghi chú rỗng không phải sidecar hỏng.");
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        writable.Set("scripts", issue, QaTriageStatus.NeedsFix, "", DateTimeOffset.UtcNow);
        Check(File.Exists(emptyNotePath), "Set với note rỗng phải ghi được sidecar.");
    }
    finally
    {
        Directory.Delete(emptyNoteDirectory, true);
    }

    var offsetDirectory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-offset-" + Guid.NewGuid().ToString("N"));
    var offsetPath = Path.Combine(offsetDirectory, "qa-decisions.json");
    Directory.CreateDirectory(offsetDirectory);
    var offsetBytes = """{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00+00:00"}]}"""u8.ToArray();
    File.WriteAllBytes(offsetPath, offsetBytes);
    try
    {
        var writable = QaDecisionStore.Open(offsetPath);
        Check(writable.CanMutate, "DateTimeOffset UTC +00:00 của app phải hợp lệ.");
        Check(offsetBytes.SequenceEqual(File.ReadAllBytes(offsetPath)), "Open không được đổi sidecar UTC hợp lệ.");
    }
    finally
    {
        Directory.Delete(offsetDirectory, true);
    }
}

static (string Name, string Stamp, bool Valid)[] QaTimestampParityCases() =>
[
    ("z", "2026-09-02T00:00:00Z", true),
    ("offset-zero", "2026-09-02T00:00:00+00:00", true),
    ("fractional-z", "2026-09-02T00:00:00.1234567Z", true),
    ("offset-plus-14", "2026-06-15T12:00:00+14:00", true),
    ("set-produced", "2026-09-02T08:30:00.0000000Z", true),
    ("date-only", "2026-09-02", false),
    ("no-offset", "2026-09-02T00:00:00", false),
    ("space-separator", "2026-09-02 00:00:00", false),
    ("offset-plus-14-01", "2026-09-02T00:00:00+14:01", false),
    ("offset-plus-15", "2026-09-02T00:00:00+15:00", false),
    ("utc-overflow-max", "9999-12-31T23:59:59-14:00", false),
    ("utc-underflow-min", "0001-01-01T00:00:00+14:00", false),
    ("dotnet-default-z", "0001-01-01T00:00:00Z", false),
];

static byte[] SidecarWithTimestamp(string stamp)
{
    var json =
        "{\"schema\":\"bientaptay-qa-decisions/v1\",\"decisions\":[{\"id\":\""
        + new string('a', 64)
        + "\",\"translationId\":\"scripts\",\"kind\":\"GlossaryDrift\",\"key\":\"scene::001\",\"relatedKeys\":[\"scene::001\"],\"contentFingerprint\":\""
        + new string('b', 64)
        + "\",\"status\":\"needs_fix\",\"note\":\"a\",\"updatedAtUtc\":\""
        + stamp
        + "\"}]}";
    return Encoding.UTF8.GetBytes(json);
}

static void QaDecisionTimestampParityMatchesPython()
{
    foreach (var item in QaTimestampParityCases())
    {
        var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-ts-" + item.Name + "-" + Guid.NewGuid().ToString("N"));
        var path = Path.Combine(directory, "qa-decisions.json");
        Directory.CreateDirectory(directory);
        var payload = SidecarWithTimestamp(item.Stamp);
        File.WriteAllBytes(path, payload);
        try
        {
            var store = QaDecisionStore.Open(path);
            if (item.Valid)
            {
                Check(store.CanMutate, item.Name + " phải hợp lệ.");
                Check(string.IsNullOrEmpty(store.UnavailableReason), item.Name + " không phải sidecar hỏng.");
            }
            else
            {
                Check(!store.CanMutate, item.Name + " phải khóa ghi.");
                Equal(QaDecisionStore.UnavailableMessage, store.UnavailableReason);
            }
            Check(payload.SequenceEqual(File.ReadAllBytes(path)), item.Name + " phải giữ nguyên byte.");
            Check(Directory.GetFiles(directory).Length == 1, item.Name + " không được tạo file phụ.");
        }
        finally
        {
            Directory.Delete(directory, true);
        }
    }

    var setDirectory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-ts-set-" + Guid.NewGuid().ToString("N"));
    var setPath = Path.Combine(setDirectory, "qa-decisions.json");
    Directory.CreateDirectory(setDirectory);
    try
    {
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        var store = QaDecisionStore.Open(setPath);
        store.Set("scripts", issue, QaTriageStatus.NeedsFix, "a", new DateTimeOffset(2026, 9, 2, 8, 30, 0, TimeSpan.Zero));
        var written = File.ReadAllBytes(setPath);
        var reread = QaDecisionStore.Open(setPath);
        Check(reread.CanMutate, "Sidecar do Set ghi phải đọc lại được.");
        using var document = JsonDocument.Parse(written);
        var stamp = document.RootElement.GetProperty("decisions")[0].GetProperty("updatedAtUtc").GetString();
        Equal("2026-09-02T08:30:00.0000000Z", stamp);
        Check(written.SequenceEqual(File.ReadAllBytes(setPath)), "Open không được đổi sidecar do Set ghi.");
    }
    finally
    {
        Directory.Delete(setDirectory, true);
    }
}

static void QaDecisionReportingSnapshotIsImmutable()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-snapshot-" + Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "qa-decisions.json");
    Directory.CreateDirectory(directory);
    try
    {
        var issue = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::001",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::001"]);
        var store = QaDecisionStore.Open(path);
        store.Set("scripts", issue, QaTriageStatus.NeedsFix, "Sửa sau.", DateTimeOffset.UtcNow);
        var snapshot = store.ReportingSnapshot();
        Check(snapshot.Available, "Sidecar hợp lệ phải available cho báo cáo.");
        Check(string.IsNullOrEmpty(snapshot.UnavailableReason), "Sidecar hợp lệ không có lý do unavailable.");
        Check(snapshot.Decisions.Count == 1, "Snapshot phải chứa đúng một quyết định đã lưu.");
        Equal("needs_fix", snapshot.Decisions[0].Status);
        Equal("scripts", snapshot.Decisions[0].TranslationId);
        Equal("GlossaryDrift", snapshot.Decisions[0].Kind);
        Equal("scene::001", snapshot.Decisions[0].Key);
        var originalKey = snapshot.Decisions[0].RelatedKeys[0];
        var originalStatus = snapshot.Decisions[0].Status;
        var originalId = snapshot.Decisions[0].Id;
        var decisions = (IList<QaStoredDecision>)snapshot.Decisions;
        Expect<NotSupportedException>(() => decisions[0] = decisions[0] with { Status = "resolved" });
        Equal(originalStatus, snapshot.Decisions[0].Status);
        Equal(originalId, snapshot.Decisions[0].Id);
        var keys = (IList<string>)snapshot.Decisions[0].RelatedKeys;
        Expect<NotSupportedException>(() => keys[0] = "mutated");
        Equal(originalKey, snapshot.Decisions[0].RelatedKeys[0]);
        store.Set("scripts", issue, QaTriageStatus.Resolved, "Xong.", DateTimeOffset.UtcNow);
        Equal("needs_fix", snapshot.Decisions[0].Status);
        Equal(originalId, snapshot.Decisions[0].Id);
        Equal(originalKey, snapshot.Decisions[0].RelatedKeys[0]);
        var reread = QaDecisionStore.Open(path);
        Equal("scene::001", reread.ReportingSnapshot().Decisions[0].RelatedKeys[0]);
        Equal("resolved", reread.ReportingSnapshot().Decisions[0].Status);
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaReportJsonOrdersAndDistinguishesStaleOrphan()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-report-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(directory);
    var sidecar = Path.Combine(directory, "qa-decisions.json");
    var canonical = Path.Combine(directory, "canonical.csv");
    File.WriteAllText(canonical, "key,translation_vi\r\nx,y\r\n", new UTF8Encoding(false));
    try
    {
        var first = new ConsistencyIssue(
            ConsistencyIssueKind.PronounDeviation,
            "Review",
            "scene::beta",
            "Hiro",
            "Heuristic tự xưng.",
            "私は",
            "Tôi đi",
            ["scene::beta"]);
        var second = new ConsistencyIssue(
            ConsistencyIssueKind.GlossaryDrift,
            "Cảnh báo",
            "scene::alpha",
            "Ema",
            "Glossary yêu cầu Nữ phù thủy.",
            "Xin chào",
            "Phù thủy",
            ["scene::alpha", "scene::alpha-b"]);
        var store = QaDecisionStore.Open(sidecar);
        store.Set("scripts", first, QaTriageStatus.NeedsFix, "Sửa Hiro.", DateTimeOffset.UtcNow);
        store.Set("scripts", second, QaTriageStatus.AcceptedDifference, "Giữ Ema.", DateTimeOffset.UtcNow);
        var staleIssue = second with { Target = "Nữ phù thủy" };
        var orphanId = new string('a', 64);
        var live = File.ReadAllText(sidecar, Encoding.UTF8);
        var withOrphan = live.Replace(
            "\"decisions\": [",
            "\"decisions\": [\r\n    {\r\n      \"id\": \"" + orphanId + "\",\r\n      \"translationId\": \"scripts\",\r\n      \"kind\": \"DuplicateSource\",\r\n      \"key\": \"gone::001\",\r\n      \"relatedKeys\": [\"gone::001\"],\r\n      \"contentFingerprint\": \"" + new string('b', 64) + "\",\r\n      \"status\": \"resolved\",\r\n      \"note\": \"Cũ.\",\r\n      \"updatedAtUtc\": \"2026-09-02T00:00:00Z\"\r\n    },",
            StringComparison.Ordinal);
        File.WriteAllText(sidecar, withOrphan, new UTF8Encoding(false));
        store = QaDecisionStore.Open(sidecar);
        Check(store.CanMutate, "Sidecar thêm orphan hợp lệ vẫn phải đọc được.");

        var report = QaReportBuilder.Build(
            "Magical Girl Witch Trials",
            "scripts",
            "Kịch bản",
            canonical,
            Sha256(canonical),
            1,
            [staleIssue, first],
            store);
        var json = Encoding.UTF8.GetString(QaReportBuilder.SerializeJson(report));
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        Equal("bientaptay-qa-report/v1", root.GetProperty("schema").GetString());
        Equal("Magical Girl Witch Trials", root.GetProperty("project").GetString());
        Equal("scripts", root.GetProperty("translation_id").GetString());
        Equal("Kịch bản", root.GetProperty("translation_label").GetString());
        Equal(Path.GetFullPath(canonical), root.GetProperty("canonical_path").GetString());
        Equal(Sha256(canonical), root.GetProperty("canonical_sha256").GetString());
        Equal(1, root.GetProperty("canonical_row_count").GetInt32());
        Equal(true, root.GetProperty("qa_decisions_available").GetBoolean());
        Equal("", root.GetProperty("qa_decisions_unavailable_reason").GetString());
        var totals = root.GetProperty("totals");
        Equal(2, totals.GetProperty("all").GetInt32());
        Equal(1, totals.GetProperty("unreviewed").GetInt32());
        Equal(1, totals.GetProperty("needs_fix").GetInt32());
        Equal(0, totals.GetProperty("accepted_difference").GetInt32());
        Equal(0, totals.GetProperty("resolved").GetInt32());
        Equal(1, totals.GetProperty("stale").GetInt32());
        Equal(1, totals.GetProperty("orphan").GetInt32());

        var issues = root.GetProperty("issues").EnumerateArray().ToArray();
        Check(issues.Length == 3, "Hai cảnh báo hiện tại rồi một orphan.");
        Equal("GlossaryDrift", issues[0].GetProperty("kind").GetString());
        Equal("scene::alpha", issues[0].GetProperty("exact_key").GetString());
        Equal(true, issues[0].GetProperty("stale").GetBoolean());
        Equal(false, issues[0].GetProperty("orphan").GetBoolean());
        Equal("unreviewed", issues[0].GetProperty("status").GetString());
        Equal("PronounDeviation", issues[1].GetProperty("kind").GetString());
        Equal("scene::beta", issues[1].GetProperty("exact_key").GetString());
        Equal("needs_fix", issues[1].GetProperty("status").GetString());
        Equal(false, issues[1].GetProperty("stale").GetBoolean());
        Equal(true, issues[2].GetProperty("orphan").GetBoolean());
        Equal(orphanId, issues[2].GetProperty("decision_id").GetString());
        Equal("gone::001", issues[2].GetProperty("exact_key").GetString());
        Equal("resolved", issues[2].GetProperty("status").GetString());
        Equal("DuplicateSource", issues[2].GetProperty("kind").GetString());
        Check(issues[0].GetProperty("related_keys").GetArrayLength() == 2, "related_keys phải giữ đủ exact key.");
        Check(issues[0].GetProperty("content_fingerprint").GetString()!.Length == 64, "Fingerprint phải 64 hex.");
        Check(!json.Contains("session", StringComparison.OrdinalIgnoreCase) || json.Contains("\"status\"", StringComparison.Ordinal), "Không nhúng session.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static ConsistencyIssue ReportIssue(string key, string speaker, ConsistencyIssueKind kind, params string[] related) =>
    new(kind, "Cảnh báo", key, speaker, "Cảnh báo " + key, "源," + key, "dịch\n" + key, related);

static void QaReportCsvPreservesUnicodeAndRelatedKeys()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-csv-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(directory);
    var sidecar = Path.Combine(directory, "qa-decisions.json");
    var canonical = Path.Combine(directory, "canonical.csv");
    File.WriteAllText(canonical, "key\r\n", new UTF8Encoding(false));
    try
    {
        var issue = ReportIssue("scene::\"001\"", "Ema, chị", ConsistencyIssueKind.GlossaryDrift, "scene::001", "scene::002\nnext");
        var store = QaDecisionStore.Open(sidecar);
        var report = QaReportBuilder.Build("Test", "scripts", "Kịch bản", canonical, Sha256(canonical), 0, [issue], store);
        var bytes = QaReportBuilder.SerializeCsv(report);
        Check(bytes.AsSpan().StartsWith(new byte[] { 0xEF, 0xBB, 0xBF }), "CSV báo cáo phải có UTF-8 BOM.");
        var document = CsvDocument.ParseBytes(bytes);
        Equal("decision_id", document.Headers[0]);
        Equal("related_keys", document.Headers[4]);
        Equal("orphan", document.Headers[^1]);
        Check(document.Rows.Count == 1, "CSV phải có một dòng issue.");
        var row = document.Rows[0];
        Equal("scene::\"001\"", row["exact_key"]);
        Equal("Ema, chị", row["speaker"]);
        Equal("源,scene::\"001\"", row["source"]);
        Check(row["target"].Contains("dịch\nscene::\"001\"", StringComparison.Ordinal) || row["target"].Contains("dịch\r\nscene::\"001\"", StringComparison.Ordinal), row["target"]);
        var related = JsonSerializer.Deserialize<string[]>(row["related_keys"]) ?? [];
        Check(related.SequenceEqual(["scene::001", "scene::002\nnext"]), "related_keys CSV phải JSON-encode.");
        Equal("unreviewed", row["status"]);
        Equal("false", row["orphan"]);
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaReportCorruptSidecarExportsUnreviewed()
{
    var directory = Path.Combine(Path.GetTempPath(), "bientaptay-qa-report-corrupt-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(directory);
    var sidecar = Path.Combine(directory, "qa-decisions.json");
    var canonical = Path.Combine(directory, "canonical.csv");
    File.WriteAllText(canonical, "key\r\n", new UTF8Encoding(false));
    var corrupt = "{not-json"u8.ToArray();
    File.WriteAllBytes(sidecar, corrupt);
    try
    {
        var issue = ReportIssue("scene::001", "Ema", ConsistencyIssueKind.GlossaryDrift, "scene::001");
        var store = QaDecisionStore.Open(sidecar);
        var report = QaReportBuilder.Build("Test", "scripts", "Kịch bản", canonical, Sha256(canonical), 0, [issue], store);
        Check(!report.QaDecisionsAvailable, "Sidecar hỏng phải qa_decisions_available=false.");
        Equal(QaDecisionStore.UnavailableMessage, report.QaDecisionsUnavailableReason);
        Equal(1, report.Totals.All);
        Equal(1, report.Totals.Unreviewed);
        Equal(0, report.Totals.Orphan);
        Equal("unreviewed", report.Issues[0].Status);
        Check(corrupt.SequenceEqual(File.ReadAllBytes(sidecar)), "Xuất báo cáo không được đổi sidecar hỏng.");
        Check(Directory.GetFiles(directory).Length == 2, "Không được tạo file phụ khi xuất từ sidecar hỏng.");
        var missing = QaDecisionStore.Open(Path.Combine(directory, "missing.json"));
        Check(missing.CanMutate, "Sidecar thiếu vẫn writable.");
        var empty = QaReportBuilder.Build("Test", "scripts", "Kịch bản", canonical, Sha256(canonical), 0, [issue], missing);
        Check(empty.QaDecisionsAvailable, "Sidecar thiếu vẫn available với 0 quyết định.");
        Equal(0, empty.Totals.Orphan);
        Check(!File.Exists(Path.Combine(directory, "missing.json")), "Báo cáo không được tạo sidecar thiếu.");
    }
    finally
    {
        Directory.Delete(directory, true);
    }
}

static void QaReportExportRejectsForbiddenAndWritesAtomically()
{
    using var fixture = new Fixture();
    var project = ProjectConfig.Load(fixture.Config);
    var store = QaDecisionStore.Open(Path.Combine(project.BaseDirectory, "qa-decisions.json"));
    var issue = ReportIssue("scene::001", "Ema", ConsistencyIssueKind.GlossaryDrift, "scene::001");
    var report = QaReportBuilder.Build(project.ProjectName, "canonical", "Bản dịch", fixture.Canonical, Sha256(fixture.Canonical), 2, [issue], store);
    var canonicalBefore = File.ReadAllBytes(fixture.Canonical);
    var glossaryBefore = File.ReadAllBytes(fixture.Glossary);
    var configBefore = File.ReadAllBytes(fixture.Config);

    Expect<InvalidDataException>(() => QaReportBuilder.Write(fixture.Config, report, project));
    Expect<InvalidDataException>(() => QaReportBuilder.Write(fixture.Canonical, report, project));
    Expect<InvalidDataException>(() => QaReportBuilder.Write(Path.Combine(project.BaseDirectory, "qa-decisions.json"), report, project));
    Expect<InvalidDataException>(() => QaReportBuilder.Write(Path.Combine(project.BaseDirectory, "app", "BienTapTay.exe"), report, project));
    Expect<InvalidDataException>(() => QaReportBuilder.Write(Path.Combine(project.BaseDirectory, "out.txt"), report, project));

    var dotCacheReport = Path.Combine(project.BaseDirectory, "app", "..cache", "qa-report.json");
    Expect<InvalidDataException>(() => QaReportBuilder.EnsureExportDestinationAllowed(dotCacheReport, project));
    Expect<InvalidDataException>(() => QaReportBuilder.Write(dotCacheReport, report, project));
    Check(!Directory.Exists(Path.Combine(project.BaseDirectory, "app", "..cache")), "Từ chối app/..cache không được tạo thư mục.");
    Check(!File.Exists(dotCacheReport), "Từ chối app/..cache không được tạo file.");

    var appReports = Path.Combine(project.BaseDirectory, "app", "reports", "qa-report.json");
    Expect<InvalidDataException>(() => QaReportBuilder.EnsureExportDestinationAllowed(appReports, project));
    Expect<InvalidDataException>(() => QaReportBuilder.Write(appReports, report, project));
    Check(!Directory.Exists(Path.Combine(project.BaseDirectory, "app", "reports")), "Từ chối app/reports không được tạo thư mục.");

    var siblingCache = Path.Combine(project.BaseDirectory, "app-cache", "qa-report.json");
    QaReportBuilder.EnsureExportDestinationAllowed(siblingCache, project);
    QaReportBuilder.Write(siblingCache, report, project);
    Check(File.Exists(siblingCache), "app-cache sibling phải được phép xuất.");

    var destination = Path.Combine(project.BaseDirectory, "qa-report.json");
    QaReportBuilder.Write(destination, report, project);
    Check(File.Exists(destination), "Phải ghi báo cáo JSON.");
    using (var parsed = JsonDocument.Parse(File.ReadAllText(destination)))
        Equal("bientaptay-qa-report/v1", parsed.RootElement.GetProperty("schema").GetString());
    Check(canonicalBefore.SequenceEqual(File.ReadAllBytes(fixture.Canonical)), "Xuất không được đổi canonical.");
    Check(glossaryBefore.SequenceEqual(File.ReadAllBytes(fixture.Glossary)), "Xuất không được đổi glossary.");
    Check(configBefore.SequenceEqual(File.ReadAllBytes(fixture.Config)), "Xuất không được đổi project.json.");
    Check(!File.Exists(Path.Combine(project.BaseDirectory, "qa-decisions.json")), "Xuất không được tạo sidecar.");
    Check(!Directory.EnumerateFiles(project.BaseDirectory, "*.tmp").Any(), "Không để temp sau xuất thành công.");

    var csvPath = Path.Combine(project.BaseDirectory, "qa-report.csv");
    QaReportBuilder.Write(csvPath, report, project);
    Check(File.ReadAllBytes(csvPath).AsSpan().StartsWith(new byte[] { 0xEF, 0xBB, 0xBF }), "CSV xuất phải BOM.");

    var existing = Path.Combine(project.BaseDirectory, "keep.json");
    File.WriteAllText(existing, "KEEP", new UTF8Encoding(false));
    using (var locked = new FileStream(existing, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
    {
        try
        {
            QaReportBuilder.Write(existing, report, project);
            throw new InvalidOperationException("Ghi đè file đang khóa phải thất bại.");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
        }
    }
    Equal("KEEP", File.ReadAllText(existing));
    Check(!Directory.EnumerateFiles(project.BaseDirectory, "*.tmp").Any(), "Temp phải được dọn khi ghi atomic thất bại.");
}

static ExternalException ClipboardBusy() => new("Clipboard đang bận.", ClipboardText.ClipboardCantOpen);

static void ClipboardRetriesBusyThenSetsPacket()
{
    using var fixture = new Fixture();
    var directory = Path.GetDirectoryName(fixture.Config)!;
    var before = Directory.GetFileSystemEntries(directory, "*", SearchOption.AllDirectories).OrderBy(item => item, StringComparer.Ordinal).ToArray();
    var canonicalBefore = File.ReadAllBytes(fixture.Canonical);
    var calls = 0;
    var sleeps = new List<int>();
    string? stored = null;

    var attempts = ClipboardText.SetWithRetry(
        "BIENTAPTAY-QA-CONTEXT/1\npacket",
        text =>
        {
            calls++;
            if (calls <= 2) throw ClipboardBusy();
            stored = text;
        },
        sleeps.Add);

    Equal(3, calls);
    Equal(3, attempts);
    Equal("BIENTAPTAY-QA-CONTEXT/1\npacket", stored);
    Equal(2, sleeps.Count);
    Check(sleeps.All(item => item == ClipboardText.DefaultDelayMilliseconds), "Mỗi lần chờ phải đúng 50ms.");
    Check(canonicalBefore.SequenceEqual(File.ReadAllBytes(fixture.Canonical)), "Sao chép không được đổi canonical.");
    Check(before.SequenceEqual(Directory.GetFileSystemEntries(directory, "*", SearchOption.AllDirectories).OrderBy(item => item, StringComparer.Ordinal)),
        "Sao chép thành công không được tạo file phụ, kể cả diagnostics.");

    calls = 0;
    sleeps.Clear();
    stored = null;
    attempts = ClipboardText.SetWithRetry(
        "BIENTAPTAY-QA-CONTEXT/1\npacket",
        text =>
        {
            calls++;
            if (calls <= 2) throw new COMException("Clipboard đang bận.", ClipboardText.ClipboardCantOpen);
            stored = text;
        },
        sleeps.Add);
    Equal(3, calls);
    Equal(3, attempts);
    Equal("BIENTAPTAY-QA-CONTEXT/1\npacket", stored);
    Equal(2, sleeps.Count);
}

static void ClipboardExhaustionFailsWithoutSideEffect()
{
    using var fixture = new Fixture();
    var directory = Path.GetDirectoryName(fixture.Config)!;
    var before = Directory.GetFileSystemEntries(directory, "*", SearchOption.AllDirectories).OrderBy(item => item, StringComparer.Ordinal).ToArray();
    var canonicalBefore = File.ReadAllBytes(fixture.Canonical);
    var calls = 0;
    var sleeps = new List<int>();

    Expect<ExternalException>(() => ClipboardText.SetWithRetry(
        "packet",
        _ =>
        {
            calls++;
            throw ClipboardBusy();
        },
        sleeps.Add));

    Equal(ClipboardText.DefaultAttempts, calls);
    Equal(ClipboardText.DefaultAttempts - 1, sleeps.Count);
    Check(sleeps.Sum() <= ClipboardText.MaxTotalWaitMilliseconds,
        $"Tổng thời gian chờ {sleeps.Sum()}ms vượt trần {ClipboardText.MaxTotalWaitMilliseconds}ms; UI sẽ bị treo.");
    Check(canonicalBefore.SequenceEqual(File.ReadAllBytes(fixture.Canonical)), "Sao chép thất bại không được đổi canonical.");
    Check(before.SequenceEqual(Directory.GetFileSystemEntries(directory, "*", SearchOption.AllDirectories).OrderBy(item => item, StringComparer.Ordinal)),
        "Sao chép thất bại không được tự tạo file trong project.");

    var cappedSleeps = new List<int>();
    Expect<ExternalException>(() => ClipboardText.SetWithRetry("packet", _ => throw ClipboardBusy(), cappedSleeps.Add, attempts: 40, delayMilliseconds: 50));
    Check(cappedSleeps.Sum() <= ClipboardText.MaxTotalWaitMilliseconds,
        $"Trần tổng thời gian chờ phải chặn cấu hình dài: {cappedSleeps.Sum()}ms.");
}

static void ClipboardDoesNotRetryNonBusyFailure()
{
    var calls = 0;
    var sleeps = new List<int>();
    Expect<ArgumentException>(() => ClipboardText.SetWithRetry(
        "packet",
        _ =>
        {
            calls++;
            throw new ArgumentException("Chuỗi không hợp lệ.");
        },
        sleeps.Add));
    Equal(1, calls);
    Equal(0, sleeps.Count);

    calls = 0;
    sleeps.Clear();
    Expect<InvalidOperationException>(() => ClipboardText.SetWithRetry(
        "packet",
        _ =>
        {
            calls++;
            throw new InvalidOperationException("Không mở được clipboard.");
        },
        sleeps.Add));
    Equal(1, calls);
    Equal(0, sleeps.Count);

    const int oleUnrelated = unchecked((int)0x80040064);
    calls = 0;
    sleeps.Clear();
    try
    {
        ClipboardText.SetWithRetry(
            "packet",
            _ =>
            {
                calls++;
                throw new ExternalException("OLE unrelated", oleUnrelated);
            },
            sleeps.Add);
        throw new InvalidOperationException("ExternalException không-bận phải được ném lại.");
    }
    catch (ExternalException ex)
    {
        Equal(oleUnrelated, ex.ErrorCode);
        Check(ex is not COMException, "Probe ExternalException không phải COMException.");
    }
    Equal(1, calls);
    Equal(0, sleeps.Count);

    calls = 0;
    sleeps.Clear();
    try
    {
        ClipboardText.SetWithRetry(
            "packet",
            _ =>
            {
                calls++;
                throw new COMException("OLE unrelated", oleUnrelated);
            },
            sleeps.Add);
        throw new InvalidOperationException("COMException không-bận phải được ném lại.");
    }
    catch (COMException ex)
    {
        Equal(oleUnrelated, ex.ErrorCode);
    }
    Equal(1, calls);
    Equal(0, sleeps.Count);
}

static void DiagnosticsRedactsHomeSecretsAndTokens()
{
    const string variable = "BIENTAPTAY_TEST_API_KEY";
    const string environmentSecret = "env-value-9c1f4ab2d7";
    var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
    Environment.SetEnvironmentVariable(variable, environmentSecret);
    try
    {
        var message =
            $"Không xuất được báo cáo QA từ {home}\\du-an; api_key=AKIA1234567890QWERTY; password=hunter2trumpet; "
            + $"token=abcdef1234567890; Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature; profile={environmentSecret}";
        var redacted = DiagnosticsLog.Redact(message);

        Check(!redacted.Contains(home, StringComparison.OrdinalIgnoreCase), "Phải che đường dẫn thư mục người dùng.");
        Check(!redacted.Contains("AKIA1234567890QWERTY", StringComparison.Ordinal), "Phải che giá trị api_key.");
        Check(!redacted.Contains("hunter2trumpet", StringComparison.Ordinal), "Phải che giá trị password.");
        Check(!redacted.Contains("abcdef1234567890", StringComparison.Ordinal), "Phải che giá trị token.");
        Check(!redacted.Contains("eyJhbGciOiJIUzI1NiJ9.payload.signature", StringComparison.Ordinal), "Phải che bearer token.");
        Check(!redacted.Contains(environmentSecret, StringComparison.Ordinal),
            "Phải che giá trị biến môi trường có KEY/TOKEN/SECRET/PASSWORD/AUTH.");
        Check(redacted.Contains("Không xuất được báo cáo QA", StringComparison.Ordinal),
            "Câu tiếng Việt cho người vận hành phải đọc được. Got: " + redacted);

        var tokenRedacted = DiagnosticsLog.Redact(@"path=%USERPROFILE%\du-an; Không xuất được báo cáo QA");
        Check(!tokenRedacted.Contains("%USERPROFILE%", StringComparison.OrdinalIgnoreCase),
            "Phải che token %USERPROFILE% nguyên văn. Got: " + tokenRedacted);
        var mixedToken = DiagnosticsLog.Redact(@"path=%userprofile%\du-an");
        Check(!mixedToken.Contains("%USERPROFILE%", StringComparison.OrdinalIgnoreCase),
            "Phải che %USERPROFILE% không phân biệt hoa thường. Got: " + mixedToken);
        Check(tokenRedacted.Contains("Không xuất được báo cáo QA", StringComparison.Ordinal)
              && tokenRedacted.Contains("du-an", StringComparison.Ordinal),
            "Câu tiếng Việt và phần đường dẫn không bí mật phải đọc được. Got: " + tokenRedacted);
        if (Environment.GetEnvironmentVariable("BIENTAPTAY_DIAGNOSTICS_SAMPLE") == "1")
            Console.WriteLine("SAMPLE diagnostics redact: " + redacted);
    }
    finally
    {
        Environment.SetEnvironmentVariable(variable, null);
    }
}

static void DiagnosticsWritesJsonlAndRotatesAtSixtyFourKiB()
{
    using var fixture = new Fixture();
    var project = ProjectConfig.Load(fixture.Config);
    var directory = Path.Combine(project.BaseDirectory, "diagnostics");
    var logPath = Path.Combine(directory, "app.log");
    var canonicalBefore = File.ReadAllBytes(fixture.Canonical);
    Check(!Directory.Exists(directory), "Chưa có sự kiện lỗi thì không được tạo diagnostics/.");
    Equal(Path.GetFullPath(logPath), DiagnosticsLog.PathFor(project));

    Check(DiagnosticsLog.TryWriteError(project, "clipboard_copy", "Clipboard đang bận.", ClipboardBusy()),
        "Sự kiện lỗi đầu tiên phải ghi được.");
    Check(File.Exists(logPath), "Sự kiện lỗi đầu tiên phải tạo diagnostics/app.log.");

    var lines = File.ReadAllLines(logPath);
    Equal(1, lines.Length);
    if (Environment.GetEnvironmentVariable("BIENTAPTAY_DIAGNOSTICS_SAMPLE") == "1")
        Console.WriteLine("SAMPLE diagnostics jsonl: " + lines[0]);
    using (var parsed = JsonDocument.Parse(lines[0]))
    {
        var root = parsed.RootElement;
        Equal("clipboard_copy", root.GetProperty("operation").GetString());
        Equal("error", root.GetProperty("result").GetString());
        Equal(nameof(ExternalException), root.GetProperty("exception_type").GetString());
        Check(root.GetProperty("message").GetString()!.Contains("Clipboard đang bận", StringComparison.Ordinal),
            "Thông điệp tiếng Việt phải giữ nguyên.");
        var stamp = root.GetProperty("utc").GetString();
        Check(DateTimeOffset.TryParse(stamp, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out _),
            "Cần timestamp UTC hợp lệ. Got: " + stamp);
    }

    var filler = new string('x', 2048);
    for (var index = 0; index < 200; index++)
        DiagnosticsLog.TryWriteError(project, "qa_report_export", $"Không xuất được báo cáo {index} {filler}", new IOException("đĩa lỗi"));

    var files = Directory.GetFiles(directory).Select(item => Path.GetFileName(item)).OrderBy(item => item, StringComparer.Ordinal).ToArray();
    Check(files.SequenceEqual(["app.log", "app.log.1", "app.log.2"]),
        "Chỉ được giữ app.log, app.log.1, app.log.2. Got: " + string.Join(", ", files));
    foreach (var name in files)
        Check(new FileInfo(Path.Combine(directory, name)).Length <= DiagnosticsLog.MaxFileBytes, name + " vượt trần 64 KiB.");
    Check(!File.Exists(Path.Combine(directory, "app.log.3")), "Phải xóa file cũ hơn app.log.2.");
    Check(!Directory.EnumerateFiles(directory, "*.tmp").Any(), "Không được để temp sau khi ghi.");
    Check(canonicalBefore.SequenceEqual(File.ReadAllBytes(fixture.Canonical)), "Ghi chẩn đoán không được đổi canonical.");
    Check(!File.Exists(Path.Combine(project.BaseDirectory, "qa-decisions.json")), "Ghi chẩn đoán không được tạo sidecar QA.");
}

static void DiagnosticsWriteFailureIsSilentAndLeavesNoTemp()
{
    using var fixture = new Fixture();
    var project = ProjectConfig.Load(fixture.Config);
    var blocker = Path.Combine(project.BaseDirectory, "diagnostics");
    File.WriteAllText(blocker, "day la file, khong phai thu muc", new UTF8Encoding(false));
    var blockerBefore = File.ReadAllBytes(blocker);
    var canonicalBefore = File.ReadAllBytes(fixture.Canonical);

    Check(!DiagnosticsLog.TryWriteError(project, "clipboard_copy", "Clipboard đang bận.", ClipboardBusy()),
        "Ghi chẩn đoán thất bại phải trả về false thay vì throw ra editor.");
    Check(blockerBefore.SequenceEqual(File.ReadAllBytes(blocker)), "Không được ghi đè file chắn diagnostics.");
    Check(canonicalBefore.SequenceEqual(File.ReadAllBytes(fixture.Canonical)), "Ghi chẩn đoán thất bại không được đổi canonical.");
    Check(!Directory.EnumerateFiles(project.BaseDirectory, "*.tmp", SearchOption.AllDirectories).Any(),
        "Không được để temp khi ghi chẩn đoán thất bại.");
}

static void DiagnosticsRefusesForbiddenDestinations()
{
    using var fixture = new Fixture();
    var project = ProjectConfig.Load(fixture.Config);
    DiagnosticsLog.EnsureDestinationAllowed(DiagnosticsLog.PathFor(project), project);

    foreach (var forbidden in new[]
             {
                 fixture.Config,
                 fixture.Canonical,
                 Path.Combine(project.BaseDirectory, "qa-decisions.json"),
                 Path.Combine(project.BaseDirectory, "session.json"),
                 Path.Combine(project.BaseDirectory, "install-receipt.json"),
                 Path.Combine(project.BaseDirectory, "performance-baseline.json"),
                 Path.Combine(project.BaseDirectory, "app", "diagnostics", "app.log"),
                 Path.Combine(project.BaseDirectory, "app", "..cache", "app.log"),
                 Path.Combine(project.BaseDirectory, "diagnostics", "app.json"),
             })
    {
        Expect<InvalidDataException>(() => DiagnosticsLog.EnsureDestinationAllowed(forbidden, project));
    }

    Check(!Directory.Exists(Path.Combine(project.BaseDirectory, "app")), "Từ chối đích cấm không được tạo app/.");
    Check(!Directory.Exists(Path.Combine(project.BaseDirectory, "diagnostics")), "Chỉ kiểm tra đích thì không được tạo diagnostics/.");
}

static void QaContextPacketContainsReviewEvidence()
{
    var issue = new ConsistencyIssue(
        ConsistencyIssueKind.DuplicateSource,
        "Cảnh báo",
        "scene::001",
        "Ema",
        "Cùng source có hai bản dịch.",
        "こんにちは",
        "Xin chào / Chào cậu",
        ["scene::001", "scene::002"]);
    var rows = new[]
    {
        new QaContextPacketRow(
            "scene::001",
            "Ema",
            [new("Nguồn", "こんにちは"), new("Tham khảo", "你好")],
            "Xin chào",
            "魔女 = Nữ phù thủy",
            "Ema: tôi / cậu"),
        new QaContextPacketRow(
            "scene::002",
            "Ema",
            [new("Nguồn", "こんにちは"), new("Tham khảo", "您好")],
            "Chào cậu",
            "Không có thuật ngữ khớp.",
            "Ema: tôi / cậu"),
    };

    var packet = QaContextPacketBuilder.Build("Magical Girl Witch Trials", "scripts", "Kịch bản", issue, rows);

    Check(packet.StartsWith("BIENTAPTAY-QA-CONTEXT/1\n", StringComparison.Ordinal), "Context packet thiếu schema header.");
    foreach (var required in new[]
    {
        "project: Magical Girl Witch Trials",
        "translation_id: scripts",
        "translation_label: Kịch bản",
        "exact_key: scene::001",
        "exact_key: scene::002",
        "Nguồn: こんにちは",
        "Tham khảo: 你好",
        "target: Xin chào",
        "target: Chào cậu",
        "glossary: 魔女 = Nữ phù thủy",
        "pronouns: Ema: tôi / cậu",
    }) Check(packet.Contains(required, StringComparison.Ordinal), $"Context packet thiếu: {required}");
}

static void ReferenceTableExternalDiff()
{
    var path = Path.Combine(Path.GetTempPath(), "bientaptay-reference-diff-" + Guid.NewGuid().ToString("N") + ".csv");
    try
    {
        File.WriteAllText(path, "term,translation,status\r\na,A,locked\r\nb,B,locked\r\n", new UTF8Encoding(true));
        var store = CsvTableStore.Open(path, "term");
        store.Rows[0]["translation"] = "Local";
        File.WriteAllText(path, "term,translation,status\r\na,External,locked\r\nc,C,locked\r\n", new UTF8Encoding(true));
        var changes = store.CompareWithDisk();
        Check(changes.Any(item => item.Kind == ExternalChangeKind.Modified && item.Key == "a" && item.IsConflict), "Reference modified conflict thiếu");
        Check(changes.Any(item => item.Kind == ExternalChangeKind.Removed && item.Key == "b"), "Reference removed thiếu");
        Check(changes.Any(item => item.Kind == ExternalChangeKind.Added && item.Key == "c"), "Reference added thiếu");
    }
    finally
    {
        if (File.Exists(path)) File.Delete(path);
    }
}

static void ReferenceUsesConfiguredKeyColumn()
{
    var path = Path.Combine(Path.GetTempPath(), "bientaptay-reference-key-" + Guid.NewGuid().ToString("N") + ".csv");
    try
    {
        File.WriteAllText(path, "translation,status,term\r\nA,locked,a\r\n", new UTF8Encoding(true));
        var store = CsvTableStore.Open(path, "term");
        store.Rows[0]["translation"] = "Local";
        File.WriteAllText(path, "translation,status,term\r\nExternal,locked,a\r\n", new UTF8Encoding(true));

        var change = store.CompareWithDisk().Single();

        Equal("a", change.Key);
        Equal(true, change.IsConflict);
    }
    finally
    {
        if (File.Exists(path)) File.Delete(path);
    }
}

static void ReferenceRejectsInvalidKeys()
{
    foreach (var rows in new[]
    {
        ",A,locked\r\na,B,locked\r\n",
        "a,A,locked\r\na,B,locked\r\n",
    })
    {
        var path = Path.Combine(Path.GetTempPath(), "bientaptay-reference-invalid-key-" + Guid.NewGuid().ToString("N") + ".csv");
        try
        {
            File.WriteAllText(path, "term,translation,status\r\n" + rows, new UTF8Encoding(true));
            var store = CsvTableStore.Open(path, "term");
            store.Rows[0]["translation"] = "Local";
            var before = Sha256(path);

            Expect<ReferenceValidationException>(() => store.Save());

            Equal(before, Sha256(path));
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }
}

static void GlossaryValidationRejectsBadRows()
{
    foreach (var row in new[]
    {
        "a,,locked\r\n",
        "a,A,unknown\r\n",
    })
    {
        var path = Path.Combine(Path.GetTempPath(), "bientaptay-glossary-invalid-" + Guid.NewGuid().ToString("N") + ".csv");
        try
        {
            File.WriteAllText(path, "term,translation,status\r\n" + row, new UTF8Encoding(true));
            var store = CsvTableStore.Open(path, "term", "glossary");

            Expect<ReferenceValidationException>(() => store.Save());
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }
}

static void PronounValidationRejectsBadRows()
{
    using var evidenceFixture = new Fixture();
    var evidencePath = Path.Combine(Path.GetDirectoryName(evidenceFixture.Canonical)!, "evidence-ambiguity.csv");
    File.WriteAllText(evidencePath,
        "speaker,self_reference,address_form,notes,status,evidence_keys\r\nEma,tôi,cậu,Ghi chú,reviewed,k1\r\n", new UTF8Encoding(true));
    var evidenceHash = Sha256(evidencePath);
    var ambiguous = CsvTableStore.Open(evidencePath, "speaker", "pronouns", new[] { "k1", "k1" });
    Expect<ReferenceValidationException>(() => ambiguous.Save());
    Equal(evidenceHash, Sha256(evidencePath));
    var unique = CsvTableStore.Open(evidencePath, "speaker", "pronouns", new[] { "k1", "other", "other" });
    unique.Validate();
    Equal(evidenceHash, Sha256(evidencePath));
    const string header = "speaker,self_reference,address_form,notes,status,evidence_keys\r\n";
    foreach (var row in new[]
    {
        "Ema,,cậu,Ghi chú,reviewed,k1\r\n",
        "Ema,tôi,cậu,Ghi chú,unknown,k1\r\n",
        "Ema,tôi,cậu,Ghi chú,reviewed,missing\r\n",
        "Ema,tôi,cậu,Ghi chú,reviewed,\r\n",
    })
    {
        var path = Path.Combine(Path.GetTempPath(), "bientaptay-pronouns-invalid-" + Guid.NewGuid().ToString("N") + ".csv");
        try
        {
            File.WriteAllText(path, header + row, new UTF8Encoding(true));
            var store = CsvTableStore.Open(path, "speaker", "pronouns", ["k1"]);

            Expect<ReferenceValidationException>(() => store.Save());
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }

    var validPath = Path.Combine(Path.GetTempPath(), "bientaptay-pronouns-valid-" + Guid.NewGuid().ToString("N") + ".csv");
    try
    {
        File.WriteAllText(validPath, header + "CreatureEma,kế thừa Ema,kế thừa Ema,Ghi chú,inherited,inherit:Ema;k1\r\n", new UTF8Encoding(true));
        CsvTableStore.Open(validPath, "speaker", "pronouns", ["k1"]).Save();
    }
    finally
    {
        if (File.Exists(validPath)) File.Delete(validPath);
    }
}

static void ReferenceConfigRequiresKeyColumn()
{
    using var fixture = new Fixture();
    File.WriteAllText(fixture.Config,
        """
        {
          "projectName":"Test",
          "canonicalPath":"canonical.csv",
          "sourceFields":[{"column":"source_ja","label":"Nguồn"}],
          "references":[{"id":"glossary","label":"Thuật ngữ","path":"glossary.csv"}]
        }
        """, new UTF8Encoding(false));

    Expect<InvalidDataException>(() => ProjectConfig.Load(fixture.Config));
}

static void Equal<T>(T expected, T actual)
{
    if (expected is IEnumerable<string> expectedItems && actual is IEnumerable<string> actualItems)
    {
        Check(expectedItems.SequenceEqual(actualItems), $"Expected [{string.Join(",", expectedItems)}], got [{string.Join(",", actualItems)}]");
        return;
    }
    if (expected is IEnumerable<KeyValuePair<string, string>> expectedMap && actual is IEnumerable<KeyValuePair<string, string>> actualMap)
    {
        Check(expectedMap.SequenceEqual(actualMap), "Dữ liệu hàng khác nhau");
        return;
    }
    Check(EqualityComparer<T>.Default.Equals(expected, actual), $"Expected {expected}, got {actual}");
}

static void Expect<T>(Action action) where T : Exception
{
    try { action(); }
    catch (T) { return; }
    throw new InvalidOperationException($"Expected {typeof(T).Name}");
}

sealed class Fixture : IDisposable
{
    private readonly string _directory = Path.Combine(Path.GetTempPath(), "hermes-verify-" + Guid.NewGuid().ToString("N"));
    public string Canonical => Path.Combine(_directory, "canonical.csv");
    public string Config => Path.Combine(_directory, "project.json");
    public string Glossary => Path.Combine(_directory, "glossary.csv");

    public Fixture()
    {
        Directory.CreateDirectory(_directory);
        File.WriteAllText(Canonical,
            "\uFEFFkey,speaker,source_ja,source_zh_hans,translation_vi,protected_tokens,status,review_note\r\n" +
            "scene::001,Ema,Xin<br>,参考,,<br>,pending,\r\n" +
            "scene::002,,Không token,参考,Đã dịch,,translated,giữ nguyên\r\n",
            new UTF8Encoding(false));
        File.WriteAllText(Config,
            """
            {
              "schemaVersion": 1,
              "projectName": "Test",
              "canonicalPath": "canonical.csv",
              "keyColumn": "key",
              "sourceFields": [{"column":"source_ja","label":"Nguồn"},{"column":"source_zh_hans","label":"Tham khảo"}],
              "targetColumn": "translation_vi",
              "speakerColumn": "speaker",
              "statusColumn": "status",
              "notesColumn": "review_note",
              "protectedTokensColumn": "protected_tokens",
              "statuses": ["pending","translated","reviewed","needs_context"]
            }
            """, new UTF8Encoding(false));
        File.WriteAllText(Glossary,
            "\uFEFFterm,translation,context,status\r\nMagical Girl,,Tên hệ thống,proposed\r\n",
            new UTF8Encoding(false));
    }

    public void Dispose() => Directory.Delete(_directory, true);
}
