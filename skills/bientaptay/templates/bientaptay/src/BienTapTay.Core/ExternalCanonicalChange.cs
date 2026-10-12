namespace BienTapTay.Core;

public enum ExternalChangeKind
{
    Added,
    Removed,
    Modified,
}

public sealed record ExternalCanonicalChange(
    ExternalChangeKind Kind,
    string Key,
    string Field,
    string LoadedValue,
    string LocalValue,
    string ExternalValue,
    bool IsConflict)
{
    public string FileId { get; init; } = string.Empty;
    public string FileLabel { get; init; } = string.Empty;
    public bool IsReference { get; init; }
}
