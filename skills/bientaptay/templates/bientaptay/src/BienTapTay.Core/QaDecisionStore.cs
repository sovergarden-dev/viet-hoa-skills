using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace BienTapTay.Core;

public enum QaTriageStatus
{
    Unreviewed,
    NeedsFix,
    AcceptedDifference,
    Resolved
}

public sealed record QaDecisionMatch(
    string DecisionId,
    QaTriageStatus Status,
    string Note,
    bool IsStale);

public sealed record QaStoredDecision(
    string Id,
    string TranslationId,
    string Kind,
    string Key,
    IReadOnlyList<string> RelatedKeys,
    string ContentFingerprint,
    string Status,
    string Note,
    DateTimeOffset UpdatedAtUtc);

public sealed record QaDecisionReportingSnapshot(
    bool Available,
    string UnavailableReason,
    IReadOnlyList<QaStoredDecision> Decisions);

public sealed class QaDecisionStore
{
    private const string Schema = "bientaptay-qa-decisions/v1";
    public const string UnavailableMessage =
        "qa-decisions.json bị hỏng hoặc không đọc được. Có thể tiếp tục biên tập canonical, nhưng quyết định QA chỉ đọc cho tới khi sidecar được sửa bên ngoài.";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };
    private static readonly Regex StoredTimestampPattern = new(
        @"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled | RegexOptions.ExplicitCapture);
    private static readonly string[] StoredTimestampFormats =
    [
        "yyyy-MM-dd'T'HH:mm:sszzz",
        "yyyy-MM-dd'T'HH:mm:ss.FFFFFFFzzz"
    ];

    private readonly string _path;
    private readonly Dictionary<string, QaDecisionRecord> _decisions;
    private readonly bool _canMutate;
    private readonly string _unavailableReason;

    public bool CanMutate => _canMutate;
    public string UnavailableReason => _unavailableReason;

    public QaDecisionReportingSnapshot ReportingSnapshot()
    {
        if (!_canMutate)
            return new QaDecisionReportingSnapshot(false, _unavailableReason, Array.AsReadOnly(Array.Empty<QaStoredDecision>()));
        return new QaDecisionReportingSnapshot(
            true,
            string.Empty,
            Array.AsReadOnly(_decisions.Values
                .OrderBy(item => item.Id, StringComparer.Ordinal)
                .Select(item => new QaStoredDecision(
                    item.Id,
                    item.TranslationId,
                    item.Kind,
                    item.Key,
                    Array.AsReadOnly(item.RelatedKeys.ToArray()),
                    item.ContentFingerprint,
                    item.Status,
                    item.Note,
                    item.UpdatedAtUtc))
                .ToArray()));
    }

    private QaDecisionStore(string path, IEnumerable<QaDecisionRecord> decisions, string unavailableReason = "")
    {
        _path = path;
        _decisions = decisions.ToDictionary(item => item.Id, StringComparer.Ordinal);
        _unavailableReason = unavailableReason;
        _canMutate = unavailableReason.Length == 0;
    }

    public static QaDecisionStore Open(string path)
    {
        path = Path.GetFullPath(path);
        if (Directory.Exists(path)) return Unavailable(path);
        if (!File.Exists(path)) return new QaDecisionStore(path, []);
        byte[] bytes;
        try
        {
            bytes = File.ReadAllBytes(path);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return Unavailable(path);
        }

        try
        {
            var document = JsonSerializer.Deserialize<QaDecisionDocument>(bytes, JsonOptions);
            if (document is null
                || document.Schema is null
                || document.Decisions is null
                || !document.Schema.Equals(Schema, StringComparison.Ordinal)
                || document.Decisions.Any(item => item is null
                    || item.Id is null
                    || item.Id.Length != 64
                    || !item.Id.All(char.IsAsciiHexDigit)
                    || item.TranslationId is null
                    || item.TranslationId.Length == 0
                    || item.Kind is null
                    || !Enum.TryParse<ConsistencyIssueKind>(item.Kind, ignoreCase: false, out _)
                    || item.Key is null
                    || item.Key.Length == 0
                    || item.RelatedKeys is null
                    || item.RelatedKeys.Any(key => string.IsNullOrWhiteSpace(key))
                    || item.ContentFingerprint is null
                    || item.ContentFingerprint.Length != 64
                    || !item.ContentFingerprint.All(char.IsAsciiHexDigit)
                    || item.Status is null
                    || !TryParseStatus(item.Status, out _)
                    || item.Note is null
                    || item.UpdatedAtUtc == default))
                return Unavailable(path);
            if (document.Decisions.Select(item => item.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != document.Decisions.Count)
                return Unavailable(path);
            return new QaDecisionStore(path, document.Decisions);
        }
        catch (JsonException)
        {
            return Unavailable(path);
        }
    }

    private static QaDecisionStore Unavailable(string path) => new(path, [], UnavailableMessage);

    public QaDecisionMatch Resolve(string translationId, ConsistencyIssue issue)
    {
        var id = DecisionId(translationId, issue);
        if (!_decisions.TryGetValue(id, out var decision))
            return new QaDecisionMatch(id, QaTriageStatus.Unreviewed, string.Empty, false);
        var stale = !decision.ContentFingerprint.Equals(ContentFingerprint(issue), StringComparison.Ordinal);
        return new QaDecisionMatch(
            id,
            stale ? QaTriageStatus.Unreviewed : ParseStatus(decision.Status),
            decision.Note,
            stale);
    }

    public void Set(
        string translationId,
        ConsistencyIssue issue,
        QaTriageStatus status,
        string note,
        DateTimeOffset updatedAtUtc)
    {
        if (!_canMutate) throw new InvalidOperationException(_unavailableReason);
        if (string.IsNullOrWhiteSpace(translationId)) throw new ArgumentException("Translation ID không được trống.", nameof(translationId));
        var id = DecisionId(translationId, issue);
        if (status == QaTriageStatus.Unreviewed)
            _decisions.Remove(id);
        else
            _decisions[id] = new QaDecisionRecord
            {
                Id = id,
                TranslationId = translationId,
                Kind = issue.Kind.ToString(),
                Key = issue.Key,
                RelatedKeys = issue.RelatedKeys.ToList(),
                ContentFingerprint = ContentFingerprint(issue),
                Status = StatusName(status),
                Note = note,
                UpdatedAtUtc = updatedAtUtc.ToUniversalTime()
            };
        SaveAtomic();
    }

    private void SaveAtomic()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path) ?? ".");
        var temp = $"{_path}.{Environment.ProcessId}.{Guid.NewGuid():N}.tmp";
        try
        {
            var document = new QaDecisionDocument
            {
                Schema = Schema,
                Decisions = _decisions.Values.OrderBy(item => item.Id, StringComparer.Ordinal).ToList()
            };
            var bytes = JsonSerializer.SerializeToUtf8Bytes(document, JsonOptions);
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes);
                stream.Flush(true);
            }
            if (File.Exists(_path)) File.Replace(temp, _path, null, true);
            else File.Move(temp, _path);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }

    private static string DecisionId(string translationId, ConsistencyIssue issue) => Hash(
        new[] { translationId, issue.Kind.ToString(), issue.Key, issue.Speaker, issue.Message }
            .Concat(issue.RelatedKeys)
            .ToArray());

    public static string DecisionIdFor(string translationId, ConsistencyIssue issue) => DecisionId(translationId, issue);

    private static string ContentFingerprint(ConsistencyIssue issue) => Hash(issue.Source, issue.Target);

    public static string ContentFingerprintFor(ConsistencyIssue issue) => ContentFingerprint(issue);

    private static string Hash(params string[] values) =>
        Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(values))).ToLowerInvariant();

    private static string StatusName(QaTriageStatus status) => status switch
    {
        QaTriageStatus.NeedsFix => "needs_fix",
        QaTriageStatus.AcceptedDifference => "accepted_difference",
        QaTriageStatus.Resolved => "resolved",
        _ => "unreviewed"
    };

    private static QaTriageStatus ParseStatus(string status) => TryParseStatus(status, out var value)
        ? value
        : throw new InvalidDataException($"QA triage status không hỗ trợ: {status}");

    private static bool TryParseStatus(string status, out QaTriageStatus value)
    {
        value = status switch
        {
            "needs_fix" => QaTriageStatus.NeedsFix,
            "accepted_difference" => QaTriageStatus.AcceptedDifference,
            "resolved" => QaTriageStatus.Resolved,
            _ => QaTriageStatus.Unreviewed
        };
        return status is "needs_fix" or "accepted_difference" or "resolved";
    }

    private sealed class QaDecisionDocument
    {
        public string Schema { get; set; } = string.Empty;
        public List<QaDecisionRecord> Decisions { get; set; } = [];
    }

    private sealed class QaDecisionRecord
    {
        public string Id { get; set; } = string.Empty;
        public string TranslationId { get; set; } = string.Empty;
        public string Kind { get; set; } = string.Empty;
        public string Key { get; set; } = string.Empty;
        public List<string> RelatedKeys { get; set; } = [];
        public string ContentFingerprint { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
        public string Note { get; set; } = string.Empty;
        [JsonConverter(typeof(QaStoredTimestampJsonConverter))]
        public DateTimeOffset UpdatedAtUtc { get; set; }
    }

    private sealed class QaStoredTimestampJsonConverter : JsonConverter<DateTimeOffset>
    {
        public override DateTimeOffset Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        {
            if (reader.TokenType != JsonTokenType.String)
                throw new JsonException();
            if (!TryParseStoredTimestamp(reader.GetString(), out var value))
                throw new JsonException();
            return value;
        }

        public override void Write(Utf8JsonWriter writer, DateTimeOffset value, JsonSerializerOptions options)
        {
            writer.WriteStringValue(
                value.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture));
        }
    }

    private static bool TryParseStoredTimestamp(string? raw, out DateTimeOffset value)
    {
        value = default;
        if (raw is null || StoredTimestampPattern.IsMatch(raw) is false)
            return false;
        var offset = raw.EndsWith('Z') ? "Z" : raw[^6..];
        if (offset != "Z")
        {
            var hours = int.Parse(offset[1..3], CultureInfo.InvariantCulture);
            var minutes = int.Parse(offset[4..6], CultureInfo.InvariantCulture);
            if (hours > 14 || minutes > 59 || (hours == 14 && minutes != 0))
                return false;
        }

        var normalized = raw.EndsWith('Z') ? raw[..^1] + "+00:00" : raw;
        try
        {
            if (!DateTimeOffset.TryParseExact(
                    normalized,
                    StoredTimestampFormats,
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.None,
                    out value))
                return false;
            if (value == default)
                return false;
            _ = value.UtcDateTime;
        }
        catch (ArgumentOutOfRangeException)
        {
            return false;
        }

        return true;
    }
}
