namespace BienTapTay.Core;

public sealed class CsvTableSnapshot
{
    public CsvTableSnapshot(IReadOnlyList<string> headers, IEnumerable<IReadOnlyList<string>> rows)
    {
        Headers = headers.ToArray();
        Rows = rows.Select(row => (IReadOnlyList<string>)row.ToArray()).ToArray();
    }

    public IReadOnlyList<string> Headers { get; }
    public IReadOnlyList<IReadOnlyList<string>> Rows { get; }

    public static CsvTableSnapshot From(CsvDocument document) =>
        new(document.Headers, document.Rows.Select(row => row.Values));
}

public static class CsvTableDiff
{
    private sealed record RowRef(string Identity, string Key, IReadOnlyList<string> Values);

    public static IReadOnlyList<ExternalCanonicalChange> Compare(
        string keyColumn,
        CsvTableSnapshot baseline,
        CsvTableSnapshot local,
        CsvTableSnapshot external)
    {
        ValidateShape(baseline, local, external);
        var keyMatch = baseline.Headers
            .Select((header, index) => (header, index))
            .FirstOrDefault(item => item.header.Equals(keyColumn, StringComparison.Ordinal));
        if (keyMatch.header is null)
            throw new InvalidDataException($"Không tìm thấy cột key '{keyColumn}'.");
        var keyIndex = keyMatch.index;
        var baselineRows = IndexRows(baseline, keyIndex);
        var localRows = IndexRows(local, keyIndex);
        var externalRows = IndexRows(external, keyIndex);
        var identities = baselineRows.Keys.Concat(externalRows.Keys).Distinct(StringComparer.Ordinal);
        var changes = new List<ExternalCanonicalChange>();

        foreach (var identity in identities)
        {
            var hasBaseline = baselineRows.TryGetValue(identity, out var baselineRow);
            var hasLocal = localRows.TryGetValue(identity, out var localRow);
            var hasExternal = externalRows.TryGetValue(identity, out var externalRow);
            if (!hasBaseline)
            {
                if (!hasExternal) continue;
                changes.Add(new ExternalCanonicalChange(
                    ExternalChangeKind.Added,
                    externalRow!.Key,
                    "(dòng mới)",
                    string.Empty,
                    hasLocal ? Describe(baseline.Headers, localRow!.Values) : string.Empty,
                    Describe(baseline.Headers, externalRow.Values),
                    hasLocal && !SameRow(localRow!.Values, externalRow.Values)));
                continue;
            }

            if (!hasExternal)
            {
                changes.Add(new ExternalCanonicalChange(
                    ExternalChangeKind.Removed,
                    baselineRow!.Key,
                    "(dòng bị xóa)",
                    Describe(baseline.Headers, baselineRow.Values),
                    hasLocal ? Describe(baseline.Headers, localRow!.Values) : string.Empty,
                    string.Empty,
                    hasLocal && !SameRow(localRow!.Values, baselineRow.Values)));
                continue;
            }

            for (var column = 0; column < baseline.Headers.Count; column++)
            {
                if (string.Equals(externalRow!.Values[column], baselineRow!.Values[column], StringComparison.Ordinal)) continue;
                var localValue = hasLocal ? localRow!.Values[column] : string.Empty;
                var isConflict = !hasLocal
                    || (!string.Equals(localValue, baselineRow.Values[column], StringComparison.Ordinal)
                        && !string.Equals(localValue, externalRow.Values[column], StringComparison.Ordinal));
                changes.Add(new ExternalCanonicalChange(
                    ExternalChangeKind.Modified,
                    externalRow.Key,
                    baseline.Headers[column],
                    baselineRow.Values[column],
                    localValue,
                    externalRow.Values[column],
                    isConflict));
            }
        }

        return changes;
    }

    private static Dictionary<string, RowRef> IndexRows(CsvTableSnapshot snapshot, int keyIndex)
    {
        var rows = snapshot.Rows.Select(values =>
            new RowRef(values[keyIndex], values[keyIndex], values)).ToArray();
        if (rows.Any(row => string.IsNullOrWhiteSpace(row.Key)))
            throw new InvalidDataException("Bảng CSV ngoài có key trống; không dùng positional diff.");
        if (rows.GroupBy(row => row.Key, StringComparer.Ordinal).Any(group => group.Count() > 1))
            throw new InvalidDataException("Bảng CSV ngoài có key trùng; không dùng positional diff.");
        return rows.ToDictionary(row => row.Identity, StringComparer.Ordinal);
    }

    private static void ValidateShape(params CsvTableSnapshot[] snapshots)
    {
        var headers = snapshots[0].Headers;
        if (headers.Count == 0 || snapshots.Any(snapshot => !snapshot.Headers.SequenceEqual(headers, StringComparer.Ordinal)))
            throw new InvalidDataException("Schema CSV bên ngoài khác bản đã nạp.");
        if (snapshots.Any(snapshot => snapshot.Rows.Any(row => row.Count != headers.Count)))
            throw new InvalidDataException("Số cột CSV bên ngoài không khớp schema.");
    }

    private static bool SameRow(IReadOnlyList<string> left, IReadOnlyList<string> right) =>
        left.SequenceEqual(right, StringComparer.Ordinal);

    private static string Describe(IReadOnlyList<string> headers, IReadOnlyList<string> values) =>
        string.Join(" | ", headers.Select((header, index) => $"{header}={values[index]}"));
}
