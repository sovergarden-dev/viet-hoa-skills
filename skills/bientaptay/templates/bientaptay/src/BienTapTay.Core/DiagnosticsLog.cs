using System.Collections;
using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Text.Unicode;

namespace BienTapTay.Core;

public static class DiagnosticsLog
{
    public const string DirectoryName = "diagnostics";
    public const string FileName = "app.log";
    public const long MaxFileBytes = 64 * 1024;
    public const int MaxFiles = 3;
    public const string RedactedMarker = "[đã che]";
    public const string HomeMarker = "[home]";

    private static readonly string[] SecretVariableMarkers = ["KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"];

    private static readonly Regex AssignedSecretPattern = new(
        @"(?<name>api[_-]?key|apikey|password|passwd|pwd|token|secret|auth[_-]?token|authorization)(?<separator>\s*[:=]\s*)(?<value>""[^""]*""|'[^']*'|[^\s,;""']+)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Compiled | RegexOptions.ExplicitCapture);

    private static readonly Regex BearerPattern = new(
        @"\bBearer\s+[A-Za-z0-9\-._~+/]+=*",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.Create(UnicodeRanges.All),
        WriteIndented = false
    };

    public static string PathFor(ProjectConfig project) =>
        Path.GetFullPath(Path.Combine(project.BaseDirectory, DirectoryName, FileName));

    public static bool TryWriteError(ProjectConfig project, string operation, string message, Exception exception)
    {
        ArgumentNullException.ThrowIfNull(project);
        var line = SerializeEvent(operation, message, exception);
        try
        {
            var path = PathFor(project);
            EnsureDestinationAllowed(path, project);
            Append(path, line);
            return true;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException or NotSupportedException)
        {
            return false;
        }
    }

    public static string Redact(string text)
    {
        if (string.IsNullOrEmpty(text)) return string.Empty;
        var result = BearerPattern.Replace(text, "Bearer " + RedactedMarker);
        result = AssignedSecretPattern.Replace(
            result,
            match => match.Groups["name"].Value + match.Groups["separator"].Value + RedactedMarker);
        foreach (var value in SecretEnvironmentValues())
            result = result.Replace(value, RedactedMarker, StringComparison.Ordinal);
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        if (home.Length > 0) result = result.Replace(home, HomeMarker, StringComparison.OrdinalIgnoreCase);
        result = result.Replace("%USERPROFILE%", HomeMarker, StringComparison.OrdinalIgnoreCase);
        return result;
    }

    public static void EnsureDestinationAllowed(string destination, ProjectConfig project)
    {
        var path = Path.GetFullPath(destination);
        var forbidden = new List<string>
        {
            Path.GetFullPath(project.ConfigPath),
            Path.GetFullPath(Path.Combine(project.BaseDirectory, "session.json")),
            Path.GetFullPath(Path.Combine(project.BaseDirectory, "qa-decisions.json")),
            Path.GetFullPath(Path.Combine(project.BaseDirectory, "install-receipt.json")),
            Path.GetFullPath(Path.Combine(project.BaseDirectory, "performance-baseline.json")),
        };
        foreach (var file in project.GetTranslationFiles())
            forbidden.Add(Path.GetFullPath(project.Resolve(file.Path)));
        foreach (var reference in project.References)
            forbidden.Add(Path.GetFullPath(project.Resolve(reference.Path)));

        if (forbidden.Any(item => PathsEqual(item, path)))
            throw new InvalidDataException("Không được ghi nhật ký chẩn đoán đè file dự án, sidecar, receipt hoặc CSV canonical/reference.");

        var appRoot = Path.GetFullPath(Path.Combine(project.BaseDirectory, "app"));
        var relative = Path.GetRelativePath(appRoot, path);
        if (!Path.IsPathRooted(relative) && !IsParentPathSegment(relative))
            throw new InvalidDataException("Không được ghi nhật ký chẩn đoán vào thư mục app/.");

        if (!Path.GetExtension(path).Equals(".log", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Nhật ký chẩn đoán chỉ ghi file .log.");
    }

    private static string SerializeEvent(string operation, string message, Exception exception)
    {
        var payload = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["utc"] = DateTimeOffset.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture),
            ["operation"] = operation ?? string.Empty,
            ["result"] = "error",
            ["message"] = Redact(message ?? string.Empty),
            ["exception_type"] = exception?.GetType().Name ?? string.Empty,
        };
        return JsonSerializer.Serialize(payload, JsonOptions);
    }

    private static List<string> SecretEnvironmentValues()
    {
        var values = new List<string>();
        foreach (DictionaryEntry entry in Environment.GetEnvironmentVariables())
        {
            if (entry.Key is not string name || entry.Value is not string value) continue;
            // Values shorter than 4 chars match too much unrelated Vietnamese text to replace safely.
            if (value.Length < 4) continue;
            if (!SecretVariableMarkers.Any(marker => name.Contains(marker, StringComparison.OrdinalIgnoreCase))) continue;
            values.Add(value);
        }
        values.Sort((left, right) => right.Length.CompareTo(left.Length));
        return values;
    }

    private static void Append(string path, string line)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? ".");
        var payload = Encoding.UTF8.GetBytes(line + "\n");
        var existing = File.Exists(path) ? File.ReadAllBytes(path) : [];
        if (existing.Length + payload.Length > MaxFileBytes)
        {
            Rotate(path);
            existing = [];
        }
        var content = new byte[existing.Length + payload.Length];
        Buffer.BlockCopy(existing, 0, content, 0, existing.Length);
        Buffer.BlockCopy(payload, 0, content, existing.Length, payload.Length);
        WriteAtomic(path, content);
    }

    private static void Rotate(string path)
    {
        var directory = Path.GetDirectoryName(path) ?? ".";
        var prefix = Path.GetFileName(path) + ".";
        foreach (var stale in Directory.EnumerateFiles(directory, prefix + "*").ToArray())
        {
            var name = Path.GetFileName(stale);
            if (name.Length <= prefix.Length || !name.StartsWith(prefix, StringComparison.Ordinal)) continue;
            var suffix = name[prefix.Length..];
            if (int.TryParse(suffix, NumberStyles.None, CultureInfo.InvariantCulture, out var index) && index >= MaxFiles - 1)
                File.Delete(stale);
        }
        for (var index = MaxFiles - 1; index >= 1; index--)
        {
            var source = index == 1 ? path : $"{path}.{index - 1}";
            if (File.Exists(source)) File.Move(source, $"{path}.{index}", overwrite: true);
        }
    }

    private static void WriteAtomic(string path, byte[] bytes)
    {
        var temp = $"{path}.{Environment.ProcessId}.{Guid.NewGuid():N}.tmp";
        try
        {
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes);
                stream.Flush(true);
            }
            if (File.Exists(path)) File.Replace(temp, path, null, true);
            else File.Move(temp, path);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }

    private static bool IsParentPathSegment(string relative)
    {
        if (relative.Equals("..", StringComparison.Ordinal)) return true;
        if (relative.StartsWith(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal)) return true;
        if (relative.StartsWith(".." + Path.AltDirectorySeparatorChar, StringComparison.Ordinal)) return true;
        return false;
    }

    private static bool PathsEqual(string left, string right) =>
        string.Equals(left, right, OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal);
}
