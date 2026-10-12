using System.Text;
using System.Text.Json;

namespace BienTapTay.Core;

public sealed class QaReportTotals
{
    public int All { get; set; }
    public int Unreviewed { get; set; }
    public int NeedsFix { get; set; }
    public int AcceptedDifference { get; set; }
    public int Resolved { get; set; }
    public int Stale { get; set; }
    public int Orphan { get; set; }
}

public sealed class QaReportIssue
{
    public string DecisionId { get; set; } = string.Empty;
    public string ContentFingerprint { get; set; } = string.Empty;
    public string Kind { get; set; } = string.Empty;
    public string ExactKey { get; set; } = string.Empty;
    public IReadOnlyList<string> RelatedKeys { get; set; } = [];
    public string Speaker { get; set; } = string.Empty;
    public string Severity { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public string Source { get; set; } = string.Empty;
    public string Target { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string Note { get; set; } = string.Empty;
    public bool Stale { get; set; }
    public bool Orphan { get; set; }
}

public sealed class QaReportDocument
{
    public string Schema { get; set; } = QaReportBuilder.Schema;
    public string Project { get; set; } = string.Empty;
    public string TranslationId { get; set; } = string.Empty;
    public string TranslationLabel { get; set; } = string.Empty;
    public string CanonicalPath { get; set; } = string.Empty;
    public string CanonicalSha256 { get; set; } = string.Empty;
    public int CanonicalRowCount { get; set; }
    public bool QaDecisionsAvailable { get; set; }
    public string QaDecisionsUnavailableReason { get; set; } = string.Empty;
    public QaReportTotals Totals { get; set; } = new();
    public Dictionary<string, int> ByKind { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string, int> BySpeaker { get; set; } = new(StringComparer.Ordinal);
    public List<QaReportIssue> Issues { get; set; } = [];
}

public static class QaReportBuilder
{
    public const string Schema = "bientaptay-qa-report/v1";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true
    };

    public static QaReportDocument Build(
        string projectName,
        string translationId,
        string translationLabel,
        string canonicalPath,
        string canonicalSha256,
        int canonicalRowCount,
        IReadOnlyList<ConsistencyIssue> issues,
        QaDecisionStore store)
    {
        var snapshot = store.ReportingSnapshot();
        var current = issues.Select(issue =>
        {
            var match = store.Resolve(translationId, issue);
            return new QaReportIssue
            {
                DecisionId = match.DecisionId,
                ContentFingerprint = QaDecisionStore.ContentFingerprintFor(issue),
                Kind = issue.Kind.ToString(),
                ExactKey = issue.Key,
                RelatedKeys = issue.RelatedKeys.ToArray(),
                Speaker = issue.Speaker,
                Severity = issue.Severity,
                Message = issue.Message,
                Source = issue.Source,
                Target = issue.Target,
                Status = StatusName(match.Status),
                Note = match.Note,
                Stale = match.IsStale,
                Orphan = false
            };
        })
            .OrderBy(item => item.Kind, StringComparer.Ordinal)
            .ThenBy(item => item.Speaker, StringComparer.Ordinal)
            .ThenBy(item => item.ExactKey, StringComparer.Ordinal)
            .ThenBy(item => item.DecisionId, StringComparer.Ordinal)
            .ToList();

        var currentIds = current.Select(item => item.DecisionId).ToHashSet(StringComparer.Ordinal);
        var orphans = snapshot.Available
            ? snapshot.Decisions
                .Where(item => item.TranslationId.Equals(translationId, StringComparison.Ordinal)
                    && !currentIds.Contains(item.Id))
                .OrderBy(item => item.Id, StringComparer.Ordinal)
                .Select(item => new QaReportIssue
                {
                    DecisionId = item.Id,
                    ContentFingerprint = item.ContentFingerprint,
                    Kind = item.Kind,
                    ExactKey = item.Key,
                    RelatedKeys = item.RelatedKeys,
                    Speaker = string.Empty,
                    Severity = string.Empty,
                    Message = string.Empty,
                    Source = string.Empty,
                    Target = string.Empty,
                    Status = item.Status,
                    Note = item.Note,
                    Stale = false,
                    Orphan = true
                })
                .ToList()
            : [];

        var byKind = current
            .GroupBy(item => item.Kind, StringComparer.Ordinal)
            .OrderBy(group => group.Key, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);
        var bySpeaker = current
            .GroupBy(item => item.Speaker, StringComparer.Ordinal)
            .OrderBy(group => group.Key, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);

        return new QaReportDocument
        {
            Schema = Schema,
            Project = projectName,
            TranslationId = translationId,
            TranslationLabel = translationLabel,
            CanonicalPath = Path.GetFullPath(canonicalPath),
            CanonicalSha256 = canonicalSha256,
            CanonicalRowCount = canonicalRowCount,
            QaDecisionsAvailable = snapshot.Available,
            QaDecisionsUnavailableReason = snapshot.UnavailableReason,
            Totals = new QaReportTotals
            {
                All = current.Count,
                Unreviewed = current.Count(item => item.Status == "unreviewed"),
                NeedsFix = current.Count(item => item.Status == "needs_fix"),
                AcceptedDifference = current.Count(item => item.Status == "accepted_difference"),
                Resolved = current.Count(item => item.Status == "resolved"),
                Stale = current.Count(item => item.Stale),
                Orphan = orphans.Count
            },
            ByKind = byKind,
            BySpeaker = bySpeaker,
            Issues = [.. current, .. orphans]
        };
    }

    public static byte[] SerializeJson(QaReportDocument report) =>
        JsonSerializer.SerializeToUtf8Bytes(report, JsonOptions);

    public static byte[] SerializeCsv(QaReportDocument report)
    {
        var document = CsvDocument.Parse(
            "decision_id,content_fingerprint,kind,exact_key,related_keys,speaker,severity,message,source,target,status,note,stale,orphan\r\n");
        foreach (var issue in report.Issues)
        {
            document.AddRow(new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["decision_id"] = issue.DecisionId,
                ["content_fingerprint"] = issue.ContentFingerprint,
                ["kind"] = issue.Kind,
                ["exact_key"] = issue.ExactKey,
                ["related_keys"] = JsonSerializer.Serialize(issue.RelatedKeys),
                ["speaker"] = issue.Speaker,
                ["severity"] = issue.Severity,
                ["message"] = issue.Message,
                ["source"] = issue.Source,
                ["target"] = issue.Target,
                ["status"] = issue.Status,
                ["note"] = issue.Note,
                ["stale"] = issue.Stale ? "true" : "false",
                ["orphan"] = issue.Orphan ? "true" : "false",
            });
        }
        var text = document.Serialize().TrimStart('\uFEFF');
        var body = Encoding.UTF8.GetBytes(text);
        var output = new byte[3 + body.Length];
        output[0] = 0xEF;
        output[1] = 0xBB;
        output[2] = 0xBF;
        Buffer.BlockCopy(body, 0, output, 3, body.Length);
        return output;
    }

    public static void Write(string destination, QaReportDocument report, ProjectConfig project)
    {
        var path = Path.GetFullPath(destination);
        EnsureExportDestinationAllowed(path, project);
        var bytes = Path.GetExtension(path).Equals(".csv", StringComparison.OrdinalIgnoreCase)
            ? SerializeCsv(report)
            : SerializeJson(report);
        WriteAtomic(path, bytes);
    }

    public static void EnsureExportDestinationAllowed(string destination, ProjectConfig project)
    {
        var path = Path.GetFullPath(destination);
        var extension = Path.GetExtension(path);
        if (!extension.Equals(".json", StringComparison.OrdinalIgnoreCase)
            && !extension.Equals(".csv", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Báo cáo QA chỉ xuất file .json hoặc .csv.");

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
            throw new InvalidDataException("Không được xuất báo cáo QA đè file dự án, sidecar, receipt hoặc CSV canonical/reference.");

        var appRoot = Path.GetFullPath(Path.Combine(project.BaseDirectory, "app"));
        var relative = Path.GetRelativePath(appRoot, path);
        if (!Path.IsPathRooted(relative) && !IsParentPathSegment(relative))
            throw new InvalidDataException("Không được xuất báo cáo QA vào thư mục app/.");
    }

    private static bool IsParentPathSegment(string relative)
    {
        if (relative.Equals("..", StringComparison.Ordinal)) return true;
        if (relative.StartsWith(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal)) return true;
        if (relative.StartsWith(".." + Path.AltDirectorySeparatorChar, StringComparison.Ordinal)) return true;
        return false;
    }

    private static void WriteAtomic(string path, byte[] bytes)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? ".");
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

    private static bool PathsEqual(string left, string right) =>
        string.Equals(left, right, OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal);

    private static string StatusName(QaTriageStatus status) => status switch
    {
        QaTriageStatus.NeedsFix => "needs_fix",
        QaTriageStatus.AcceptedDifference => "accepted_difference",
        QaTriageStatus.Resolved => "resolved",
        _ => "unreviewed"
    };
}
