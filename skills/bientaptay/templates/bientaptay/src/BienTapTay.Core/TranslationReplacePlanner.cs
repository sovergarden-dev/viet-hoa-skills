namespace BienTapTay.Core;

public sealed record TranslationReplacement(
    TranslationRow Row,
    string Key,
    string Before,
    string After,
    int Occurrences,
    string ValidationMessage);

public sealed class TranslationReplacePlan(IReadOnlyList<TranslationReplacement> items)
{
    public IReadOnlyList<TranslationReplacement> Items { get; } = items;
    public int TotalOccurrences => Items.Sum(item => item.Occurrences);
    public bool CanApply => Items.Count > 0 && Items.All(item => item.ValidationMessage.Length == 0);
}

public sealed class TranslationReplaceUndo(IReadOnlyList<TranslationReplacement> items)
{
    private bool _used;

    public IReadOnlyList<TranslationReplacement> Items { get; } = items;

    public void Undo()
    {
        if (_used) throw new InvalidOperationException("Batch thay đã được hoàn tác.");
        if (Items.Any(item => !string.Equals(item.Row.Target, item.After, StringComparison.Ordinal)))
            throw new InvalidOperationException("Một dòng trong batch đã được sửa sau khi thay; không hoàn tác để tránh ghi đè edit mới.");
        foreach (var item in Items) item.Row.Target = item.Before;
        _used = true;
    }
}

public static class TranslationReplacePlanner
{
    public static TranslationReplacePlan Create(
        CanonicalStore store,
        IEnumerable<TranslationRow> scope,
        string find,
        string replacement,
        bool matchCase)
    {
        if (string.IsNullOrEmpty(find)) throw new ArgumentException("Chuỗi cần tìm không được trống.", nameof(find));
        replacement ??= string.Empty;
        var comparison = matchCase ? StringComparison.Ordinal : StringComparison.OrdinalIgnoreCase;
        var items = new List<TranslationReplacement>();
        foreach (var row in scope.DistinctBy(row => row.Index))
        {
            var occurrences = Count(row.Target, find, comparison);
            if (occurrences == 0) continue;
            var after = row.Target.Replace(find, replacement, comparison);
            if (string.Equals(after, row.Target, StringComparison.Ordinal)) continue;
            items.Add(new TranslationReplacement(
                row,
                row.Key,
                row.Target,
                after,
                occurrences,
                store.ValidateTarget(row, after)));
        }
        return new TranslationReplacePlan(items);
    }

    public static TranslationReplaceUndo Apply(TranslationReplacePlan plan)
    {
        var invalid = plan.Items.FirstOrDefault(item => item.ValidationMessage.Length > 0);
        if (invalid is not null)
            throw new CanonicalValidationException($"{invalid.Key}: {invalid.ValidationMessage}");
        if (plan.Items.Any(item => !string.Equals(item.Row.Target, item.Before, StringComparison.Ordinal)))
            throw new InvalidOperationException("Bản dịch đã đổi sau khi xem trước. Hãy tạo preview mới.");
        foreach (var item in plan.Items) item.Row.Target = item.After;
        return new TranslationReplaceUndo(plan.Items);
    }

    private static int Count(string text, string find, StringComparison comparison)
    {
        var count = 0;
        for (var start = 0; start <= text.Length - find.Length;)
        {
            var index = text.IndexOf(find, start, comparison);
            if (index < 0) break;
            count++;
            start = index + find.Length;
        }
        return count;
    }
}
