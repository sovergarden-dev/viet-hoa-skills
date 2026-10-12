using System.IO;
using System.Text.Json;
using System.Windows;
using BienTapTay.Core;

namespace BienTapTay.App;

internal sealed class SessionBookmark
{
    public string TranslationId { get; set; } = string.Empty;
    public string Key { get; set; } = string.Empty;
}

internal sealed class SessionState
{
    public double Left { get; set; }
    public double Top { get; set; }
    public double Width { get; set; }
    public double Height { get; set; }
    public bool Maximized { get; set; }
    public int TabIndex { get; set; }
    public string TranslationId { get; set; } = string.Empty;
    public string? Status { get; set; }
    public string? Group { get; set; }
    public string Search { get; set; } = string.Empty;
    public bool OnlyIssues { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; } = PageWindow.DefaultSize;
    public double FontScale { get; set; } = 1;
    public double ListPaneRatio { get; set; } = 0.55;
    public Dictionary<string, double> ColumnWidths { get; set; } = new(StringComparer.Ordinal);
    public string? SelectedKey { get; set; }
    public List<SessionBookmark> Bookmarks { get; set; } = [];

    public static SessionState? Load(string configPath)
    {
        var path = Path(configPath);
        if (!File.Exists(path)) return null;
        try
        {
            return JsonSerializer.Deserialize<SessionState>(File.ReadAllText(path));
        }
        catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    public void Save(string configPath)
    {
        var path = Path(configPath);
        var temp = $"{path}.{Environment.ProcessId}.tmp";
        try
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(this, new JsonSerializerOptions { WriteIndented = true });
            using (var stream = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes);
                stream.Flush(true);
            }
            File.Move(temp, path, true);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }

    public void Capture(Window window)
    {
        var bounds = window.RestoreBounds;
        Left = bounds.Left;
        Top = bounds.Top;
        Width = bounds.Width;
        Height = bounds.Height;
        Maximized = window.WindowState == WindowState.Maximized;
    }

    public bool ApplyWindow(Window window)
    {
        var values = new[] { Left, Top, Width, Height };
        if (values.Any(value => !double.IsFinite(value)) || Width < window.MinWidth || Height < window.MinHeight)
            return false;

        var virtualLeft = SystemParameters.VirtualScreenLeft;
        var virtualTop = SystemParameters.VirtualScreenTop;
        var virtualWidth = SystemParameters.VirtualScreenWidth;
        var virtualHeight = SystemParameters.VirtualScreenHeight;
        if (virtualWidth <= 0 || virtualHeight <= 0) return false;

        var width = Math.Min(Width, virtualWidth);
        var height = Math.Min(Height, virtualHeight);
        const double visibleEdge = 64;
        var left = Math.Clamp(Left, virtualLeft - width + visibleEdge, virtualLeft + virtualWidth - visibleEdge);
        var top = Math.Clamp(Top, virtualTop, virtualTop + virtualHeight - visibleEdge);
        window.WindowStartupLocation = WindowStartupLocation.Manual;
        window.Left = left;
        window.Top = top;
        window.Width = width;
        window.Height = height;
        if (Maximized) window.WindowState = WindowState.Maximized;
        return true;
    }

    private static string Path(string configPath) =>
        System.IO.Path.Combine(System.IO.Path.GetDirectoryName(configPath) ?? ".", "session.json");
}
