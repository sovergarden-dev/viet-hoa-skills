namespace BienTapTay.Core;

public sealed record TranslationSearchDataset(
    string FileId,
    string FileLabel,
    IReadOnlyList<TranslationRow> Rows);

public sealed record TranslationSearchResult(
    string FileId,
    string FileLabel,
    string Key,
    string Speaker,
    string Group,
    string Source,
    string Target,
    string MatchField,
    string MatchedText);

public static class TranslationProjectSearch
{
    public const int DefaultLimit = 500;

    public static IReadOnlyList<TranslationSearchResult> Find(
        IEnumerable<TranslationSearchDataset> datasets,
        string query,
        int limit = DefaultLimit)
    {
        var needle = query.Trim();
        if (needle.Length == 0) return [];
        if (limit < 1) throw new ArgumentOutOfRangeException(nameof(limit));

        var results = new List<TranslationSearchResult>();
        foreach (var dataset in datasets)
        {
            foreach (var row in dataset.Rows)
            {
                var match = FindMatch(row, needle);
                if (match is null) continue;
                results.Add(new TranslationSearchResult(
                    dataset.FileId,
                    dataset.FileLabel,
                    row.Key,
                    row.Speaker,
                    row.Group,
                    row.AuthoritativeSource,
                    row.Target,
                    match.Value.Field,
                    match.Value.Text));
                if (results.Count == limit) return results;
            }
        }
        return results;
    }

    private static (string Field, string Text)? FindMatch(TranslationRow row, string query)
    {
        if (Contains(row.Key, query)) return ("Key", row.Key);
        if (Contains(row.Speaker, query)) return ("Người nói", row.Speaker);
        if (Contains(row.Group, query)) return ("Nhóm", row.Group);
        foreach (var source in row.Sources)
            if (Contains(source.Value, query)) return ("Nguồn", source.Value);
        if (Contains(row.Target, query)) return ("Bản dịch", row.Target);
        if (Contains(row.Notes, query)) return ("Ghi chú", row.Notes);
        return null;
    }

    private static bool Contains(string value, string query) =>
        value.Contains(query, StringComparison.OrdinalIgnoreCase);
}
