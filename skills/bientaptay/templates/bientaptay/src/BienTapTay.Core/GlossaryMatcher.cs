namespace BienTapTay.Core;

public sealed record GlossaryCandidate(string Term, string Translation, string Type, string Context)
{
    public string Status { get; init; } = string.Empty;
}

public static class GlossaryMatcher
{
    public static IReadOnlyList<GlossaryCandidate> Find(IEnumerable<GlossaryCandidate> candidates, string text, int limit = 12)
    {
        if (string.IsNullOrEmpty(text) || limit <= 0) return [];
        var occupied = new List<(int Start, int End)>();
        var matches = new List<GlossaryCandidate>();
        foreach (var candidate in candidates
            .Where(candidate => !IsNoise(candidate))
            .DistinctBy(candidate => candidate.Term, StringComparer.Ordinal)
            .OrderByDescending(candidate => candidate.Term.Length)
            .ThenBy(candidate => candidate.Term, StringComparer.Ordinal))
        {
            var occurrences = Occurrences(text, candidate.Term).ToArray();
            if (occurrences.Length == 0 || occurrences.All(span => Overlaps(span, occupied))) continue;
            occupied.AddRange(occurrences);
            matches.Add(candidate);
            if (matches.Count == limit) break;
        }
        return matches;
    }

    private static bool IsNoise(GlossaryCandidate candidate)
    {
        var term = candidate.Term.Trim();
        if (term.Length == 0 || candidate.Type.Equals("protected_token", StringComparison.OrdinalIgnoreCase)) return true;
        if (term.StartsWith('<') && term.EndsWith('>')) return true;
        return candidate.Type.Equals("character", StringComparison.OrdinalIgnoreCase)
            && term.Length < 3
            && term.All(IsJapaneseCharacter);
    }

    private static IEnumerable<(int Start, int End)> Occurrences(string text, string term)
    {
        for (var start = 0; start <= text.Length - term.Length;)
        {
            var index = text.IndexOf(term, start, StringComparison.Ordinal);
            if (index < 0) yield break;
            yield return (index, index + term.Length);
            start = index + 1;
        }
    }

    private static bool Overlaps((int Start, int End) span, IEnumerable<(int Start, int End)> occupied) =>
        occupied.Any(other => span.Start < other.End && other.Start < span.End);

    private static bool IsJapaneseCharacter(char value) =>
        value is >= '\u3040' and <= '\u30FF' or >= '\u3400' and <= '\u9FFF';
}
