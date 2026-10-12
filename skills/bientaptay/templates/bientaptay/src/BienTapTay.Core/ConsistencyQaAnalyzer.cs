using System.Text.RegularExpressions;

namespace BienTapTay.Core;

public enum ConsistencyIssueKind
{
    DuplicateSource,
    GlossaryDrift,
    PronounDeviation
}

public sealed record PronounProfile(string Speaker, string SelfReference, string AddressForm, string Status);

public sealed record ConsistencyQaReferenceData(
    IReadOnlyList<GlossaryCandidate> Glossary,
    IReadOnlyDictionary<string, PronounProfile> Pronouns)
{
    public static ConsistencyQaReferenceData From(CsvTableStore? glossaryStore, CsvTableStore? pronounStore)
    {
        var glossary = BuildGlossary(glossaryStore);
        var pronouns = BuildPronouns(pronounStore);
        return new ConsistencyQaReferenceData(glossary, pronouns);
    }

    private static IReadOnlyList<GlossaryCandidate> BuildGlossary(CsvTableStore? store)
    {
        if (store is null) return [];
        var term = Header(store, "term", "source", "source_term");
        var translation = Header(store, "translation", "vi", "target");
        if (term is null || translation is null) return [];
        var type = Header(store, "type", "category");
        var context = Header(store, "context", "rule", "notes");
        var status = Header(store, "status", "state");
        return store.Rows.Select(row => new GlossaryCandidate(
            row[term],
            row[translation],
            type is null ? string.Empty : row[type],
            context is null ? string.Empty : row[context])
        {
            Status = status is null ? string.Empty : row[status],
        }).ToArray();
    }

    private static IReadOnlyDictionary<string, PronounProfile> BuildPronouns(CsvTableStore? store)
    {
        if (store is null) return new Dictionary<string, PronounProfile>(StringComparer.OrdinalIgnoreCase);
        var speaker = Header(store, "speaker", "character", "name");
        if (speaker is null) return new Dictionary<string, PronounProfile>(StringComparer.OrdinalIgnoreCase);
        var self = Header(store, "self_reference", "self", "first_person");
        var address = Header(store, "address_form", "address", "second_person");
        var status = Header(store, "status", "state");
        return store.Rows.Select(row => new PronounProfile(
                row[speaker],
                self is null ? string.Empty : row[self],
                address is null ? string.Empty : row[address],
                status is null ? string.Empty : row[status]))
            .Where(profile => profile.Speaker.Length > 0)
            .GroupBy(profile => profile.Speaker, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);
    }

    private static string? Header(CsvTableStore store, params string[] candidates) =>
        candidates.Select(candidate => store.Headers.FirstOrDefault(
                header => header.Equals(candidate, StringComparison.OrdinalIgnoreCase)))
            .FirstOrDefault(header => header is not null);
}

public sealed record ConsistencyIssue(
    ConsistencyIssueKind Kind,
    string Severity,
    string Key,
    string Speaker,
    string Message,
    string Source,
    string Target,
    IReadOnlyList<string> RelatedKeys);

public static class ConsistencyQaAnalyzer
{
    private static readonly string[] SelfForms =
    [
        "chúng tôi", "chúng ta", "bọn tôi", "tôi", "tớ", "mình", "tao", "ta", "tui",
        "em", "anh", "chị", "con", "cháu"
    ];

    private static readonly string[] AddressForms =
    [
        "chúng mày", "mọi người", "các bạn", "cậu", "cô", "mày", "ngươi", "ông", "bạn",
        "em", "anh", "chị", "con"
    ];

    private static readonly Regex FirstPersonSource = new(
        "(?:私|わたし|わたくし|僕|ぼく|俺|おれ|我|われ|わし|妾|余)(?:$|[はがもにのをへと、])",
        RegexOptions.Compiled);

    private static readonly Regex SecondPersonSource = new(
        "(?:あなた|あんた|君|きみ|お前|おまえ|貴様|てめえ|てめぇ|そなた|おぬし)(?:$|ら|たち|[はがもにのをへと、])",
        RegexOptions.Compiled);

    public static IReadOnlyList<ConsistencyIssue> Analyze(
        IReadOnlyList<TranslationRow> rows,
        IEnumerable<GlossaryCandidate> glossary,
        IReadOnlyDictionary<string, PronounProfile> pronouns)
    {
        var issues = new List<ConsistencyIssue>();
        AddDuplicateSourceIssues(rows, issues);
        AddGlossaryIssues(rows, glossary, issues);
        AddPronounIssues(rows, pronouns, issues);
        return issues
            .OrderBy(issue => issue.Key, StringComparer.Ordinal)
            .ThenBy(issue => issue.Kind)
            .ToArray();
    }

    private static void AddDuplicateSourceIssues(
        IEnumerable<TranslationRow> rows,
        ICollection<ConsistencyIssue> issues)
    {
        foreach (var group in rows
            .Where(row => row.AuthoritativeSource.Length > 0 && row.Target.Length > 0)
            .GroupBy(row => (row.Speaker, row.AuthoritativeSource)))
        {
            var variants = group.Select(row => row.Target).Distinct(StringComparer.Ordinal).ToArray();
            if (variants.Length < 2) continue;
            var relatedKeys = group.Select(row => row.Key).ToArray();
            var first = group.First();
            issues.Add(new ConsistencyIssue(
                ConsistencyIssueKind.DuplicateSource,
                "Cảnh báo",
                first.Key,
                first.Speaker,
                $"Cùng source + speaker có {variants.Length} bản dịch khác nhau; xem context trước khi chuẩn hóa.",
                first.AuthoritativeSource,
                string.Join(" / ", variants),
                relatedKeys));
        }
    }

    private static void AddGlossaryIssues(
        IEnumerable<TranslationRow> rows,
        IEnumerable<GlossaryCandidate> glossary,
        ICollection<ConsistencyIssue> issues)
    {
        var candidates = glossary
            .Where(candidate => candidate.Term.Trim().Length > 0
                && candidate.Translation.Trim().Length > 0
                && candidate.Translation.Trim() != "—"
                && IsEnforced(candidate.Status))
            .ToArray();
        if (candidates.Length == 0) return;

        foreach (var row in rows.Where(row => row.AuthoritativeSource.Length > 0 && row.Target.Length > 0))
        {
            foreach (var match in GlossaryMatcher.Find(candidates, row.AuthoritativeSource, int.MaxValue))
            {
                var expected = match.Translation.Trim();
                if (row.Target.Contains(expected, StringComparison.Ordinal)) continue;
                issues.Add(new ConsistencyIssue(
                    ConsistencyIssueKind.GlossaryDrift,
                    "Cảnh báo",
                    row.Key,
                    row.Speaker,
                    $"Glossary yêu cầu “{expected}” cho thuật ngữ “{match.Term}”, nhưng target hiện tại không có.",
                    row.AuthoritativeSource,
                    row.Target,
                    [row.Key]));
            }
        }
    }

    private static void AddPronounIssues(
        IEnumerable<TranslationRow> rows,
        IReadOnlyDictionary<string, PronounProfile> pronouns,
        ICollection<ConsistencyIssue> issues)
    {
        foreach (var row in rows.Where(row => row.Speaker.Length > 0 && row.Target.Length > 0))
        {
            if (!TryGetProfile(pronouns, row.Speaker, out var profile)
                || profile.Status is "not_applicable" or "mixed_context") continue;

            if (FirstPersonSource.IsMatch(row.AuthoritativeSource))
            {
                var observed = LeadingForm(row.Target, SelfForms);
                var allowed = ExtractForms(profile.SelfReference, SelfForms);
                if (observed is not null && allowed.Count > 0 && !allowed.Contains(observed, StringComparer.OrdinalIgnoreCase))
                    AddPronounIssue(issues, row, observed, allowed, "tự xưng");
            }

            if (SecondPersonSource.IsMatch(row.AuthoritativeSource))
            {
                var observed = LeadingForm(row.Target, AddressForms);
                var allowed = ExtractForms(profile.AddressForm, AddressForms);
                if (observed is not null && allowed.Count > 0 && !allowed.Contains(observed, StringComparer.OrdinalIgnoreCase))
                    AddPronounIssue(issues, row, observed, allowed, "cách gọi đối phương");
            }
        }
    }

    private static void AddPronounIssue(
        ICollection<ConsistencyIssue> issues,
        TranslationRow row,
        string observed,
        IReadOnlyList<string> allowed,
        string dimension)
    {
        issues.Add(new ConsistencyIssue(
            ConsistencyIssueKind.PronounDeviation,
            "Review",
            row.Key,
            row.Speaker,
            $"Heuristic {dimension}: target mở đầu bằng “{observed}”; profile cho phép {string.Join(", ", allowed)}. Cần đối chiếu context.",
            row.AuthoritativeSource,
            row.Target,
            [row.Key]));
    }

    private static bool TryGetProfile(
        IReadOnlyDictionary<string, PronounProfile> profiles,
        string speaker,
        out PronounProfile profile)
    {
        if (profiles.TryGetValue(speaker, out profile!)) return true;
        var match = profiles.FirstOrDefault(item => item.Key.Equals(speaker, StringComparison.OrdinalIgnoreCase));
        profile = match.Value;
        return match.Key is not null;
    }

    private static IReadOnlyList<string> ExtractForms(string text, IEnumerable<string> forms) =>
        forms.Where(form => text.Contains(form, StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(form => form.Length)
            .ToArray();

    private static string? LeadingForm(string target, IEnumerable<string> forms)
    {
        var text = Regex.Replace(target, "<br\\s*/?>", " ", RegexOptions.IgnoreCase);
        text = Regex.Replace(text, "<[^>]+>", string.Empty).TrimStart();
        text = text.TrimStart('"', '\'', '“', '”', '‘', '’', '(', '[', '{', '—', '-', '…');
        foreach (var form in forms.OrderByDescending(form => form.Length))
        {
            if (!text.StartsWith(form, StringComparison.OrdinalIgnoreCase)) continue;
            if (text.Length == form.Length || !char.IsLetter(text[form.Length])) return form;
        }
        return null;
    }

    private static bool IsEnforced(string status) =>
        string.IsNullOrWhiteSpace(status)
        || status.Equals("locked", StringComparison.OrdinalIgnoreCase)
        || status.Equals("reviewed", StringComparison.OrdinalIgnoreCase)
        || status.Equals("approved", StringComparison.OrdinalIgnoreCase)
        || status.Equals("enforced", StringComparison.OrdinalIgnoreCase);
}
