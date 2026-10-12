namespace BienTapTay.Core;

public static class PageWindow
{
    public const int DefaultSize = 17;
    public static IReadOnlyList<int> SupportedSizes { get; } = [10, DefaultSize, 25, 50, 100];

    public static int NormalizePageSize(int pageSize) =>
        SupportedSizes.Contains(pageSize) ? pageSize : DefaultSize;

    public static (int Page, int PageCount, int Skip, int Take) Clamp(int page, int filteredCount, int pageSize = DefaultSize)
    {
        pageSize = NormalizePageSize(pageSize);
        var pageCount = Math.Max(1, (int)Math.Ceiling(Math.Max(filteredCount, 0) / (double)pageSize));
        page = Math.Clamp(page, 0, pageCount - 1);
        var skip = page * pageSize;
        var take = Math.Max(0, Math.Min(pageSize, filteredCount - skip));
        return (page, pageCount, skip, take);
    }
}
