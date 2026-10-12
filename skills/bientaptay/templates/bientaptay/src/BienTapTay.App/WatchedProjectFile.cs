using System.IO;

namespace BienTapTay.App;

internal sealed class WatchedProjectFile
{
    public WatchedProjectFile(string fileId, string label, bool isReference, string path)
    {
        FileId = fileId;
        Label = label;
        IsReference = isReference;
        Path = System.IO.Path.GetFullPath(path);
        LastWriteTimeUtc = ReadWriteTime(Path);
        WasPresent = File.Exists(Path);
    }

    public string FileId { get; }
    public string Label { get; }
    public bool IsReference { get; }
    public string Path { get; }
    public string LocalId => FileId[(FileId.IndexOf(':') + 1)..];
    public DateTime LastWriteTimeUtc { get; set; }
    public bool WasPresent { get; set; }

    public void MarkCurrent()
    {
        WasPresent = File.Exists(Path);
        LastWriteTimeUtc = ReadWriteTime(Path);
    }

    private static DateTime ReadWriteTime(string path)
    {
        try { return File.Exists(path) ? File.GetLastWriteTimeUtc(path) : DateTime.MinValue; }
        catch (IOException) { return DateTime.MinValue; }
    }
}
