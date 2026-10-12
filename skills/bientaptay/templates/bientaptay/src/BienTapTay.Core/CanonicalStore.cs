using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace BienTapTay.Core;

public sealed class CanonicalValidationException(string message) : Exception(message);
public sealed class StaleCanonicalException(string message) : IOException(message);

public sealed class TranslationRow
{
    private readonly CsvRow _row;
    private readonly ProjectConfig _config;

    internal TranslationRow(CsvRow row, ProjectConfig config, int index)
    {
        _row = row;
        _config = config;
        Index = index;
    }

    public int Index { get; }
    public string Key => _row[_config.KeyColumn];
    public string Speaker => Read(_config.SpeakerColumn);
    public string Group => Read(_config.GroupColumn);
    public string AuthoritativeSource => _row[_config.SourceFields[0].Column];
    public IEnumerable<(string Label, string Value)> Sources => _config.SourceFields
        .Select(item => (string.IsNullOrWhiteSpace(item.Label) ? item.Column : item.Label, _row[item.Column]));
    public string Target { get => _row[_config.TargetColumn]; set => _row[_config.TargetColumn] = value; }
    public string Status { get => _row[_config.StatusColumn]; set => _row[_config.StatusColumn] = value; }
    public string Notes { get => Read(_config.NotesColumn); set => Write(_config.NotesColumn, value); }
    public string ProtectedTokens => Read(_config.ProtectedTokensColumn);

    internal CsvRow Raw => _row;

    private string Read(string? column) => string.IsNullOrWhiteSpace(column) ? string.Empty : _row[column];
    private void Write(string? column, string value)
    {
        if (!string.IsNullOrWhiteSpace(column)) _row[column] = value;
    }
}

public sealed class CanonicalStore
{
    private readonly ProjectConfig _config;
    private readonly string _path;
    private CsvDocument _document;
    private List<string[]> _originalValues;
    private string _loadedHash;

    private CanonicalStore(ProjectConfig config, string path, CsvDocument document, string hash)
    {
        _config = config;
        _path = path;
        _document = document;
        _loadedHash = hash;
        _originalValues = Snapshot(document);
        Rows = document.Rows.Select((row, index) => new TranslationRow(row, config, index)).ToList();
        ValidateSchema();
    }

    public ProjectConfig Config => _config;
    public IReadOnlyList<TranslationRow> Rows { get; private set; }
    public string LoadedHash => _loadedHash;
    public bool HasUnsavedChanges => DirtyIndexes().Any();

    public bool IsDirty(TranslationRow row)
    {
        var index = RowIndex(row);
        return !_document.Rows[index].Values.SequenceEqual(_originalValues[index], StringComparer.Ordinal);
    }

    public void Revert(TranslationRow row)
    {
        var index = RowIndex(row);
        for (var column = 0; column < _document.Headers.Count; column++)
            _document.Rows[index][_document.Headers[column]] = _originalValues[index][column];
    }

    public static CanonicalStore Open(string configPath)
    {
        var config = ProjectConfig.Load(configPath);
        return Open(config.ForTranslationFile(config.GetTranslationFiles()[0]));
    }

    public static CanonicalStore Open(ProjectConfig config)
    {
        var path = config.ResolvedCanonicalPath;
        var bytes = File.ReadAllBytes(path);
        return new CanonicalStore(config, path, CsvDocument.ParseBytes(bytes), Hash(bytes));
    }

    public string Validate(TranslationRow row)
    {
        RowIndex(row);
        return ValidateValues(row, row.Target);
    }

    public string ValidateTarget(TranslationRow row, string target)
    {
        RowIndex(row);
        return ValidateValues(row, target);
    }

    private string ValidateValues(TranslationRow row, string target)
    {
        var status = row.Status;
        if (!_config.Statuses.Contains(status, StringComparer.Ordinal)) return $"Trạng thái không hợp lệ: {status}";
        var whitespaceIdentity = row.AuthoritativeSource.Length > 0
            && string.IsNullOrWhiteSpace(row.AuthoritativeSource)
            && string.Equals(target, row.AuthoritativeSource, StringComparison.Ordinal);
        if (string.IsNullOrWhiteSpace(target) && !whitespaceIdentity && status is "translated" or "reviewed")
            return "Bản dịch trống nhưng trạng thái đã hoàn thành.";
        if (!string.IsNullOrWhiteSpace(target) && status is "pending" or "needs_context")
            return "Bản dịch có nội dung nhưng trạng thái vẫn chờ xử lý.";
        var source = row.AuthoritativeSource;
        var expected = Regex.Matches(source, _config.TokenPattern, RegexOptions.CultureInvariant)
            .Select(match => match.Value).ToArray();
        var actual = Regex.Matches(target, _config.TokenPattern, RegexOptions.CultureInvariant)
            .Select(match => match.Value).ToArray();
        if (!MultisetEqual(expected, actual))
            return $"Protected token khác nguồn. Cần [{string.Join(", ", expected)}], hiện có [{string.Join(", ", actual)}].";
        return string.Empty;
    }

    public IReadOnlyList<ExternalCanonicalChange> CompareWithDisk()
    {
        var external = CsvDocument.ParseBytes(File.ReadAllBytes(_path));
        if (!external.Headers.SequenceEqual(_document.Headers, StringComparer.Ordinal))
            throw new InvalidDataException("Schema canonical bên ngoài khác bản đã nạp.");
        var keyIndex = _document.Headers.Select((header, index) => (header, index))
            .Single(item => item.header == _config.KeyColumn).index;
        var externalKeys = external.Rows.Select(row => row[_config.KeyColumn]).ToArray();
        if (externalKeys.Any(string.IsNullOrWhiteSpace)
            || externalKeys.Distinct(StringComparer.Ordinal).Count() != externalKeys.Length)
            throw new InvalidDataException("Canonical bên ngoài có key trống hoặc trùng.");
        var externalByKey = external.Rows.ToDictionary(row => row[_config.KeyColumn], StringComparer.Ordinal);
        var baselineKeys = _originalValues.Select(values => values[keyIndex]).ToArray();
        var baselineKeySet = baselineKeys.ToHashSet(StringComparer.Ordinal);
        var changes = new List<ExternalCanonicalChange>();

        for (var index = 0; index < baselineKeys.Length; index++)
        {
            var key = baselineKeys[index];
            var baseline = _originalValues[index];
            var local = _document.Rows[index].Values;
            if (!externalByKey.TryGetValue(key, out var externalRow))
            {
                changes.Add(new ExternalCanonicalChange(
                    ExternalChangeKind.Removed,
                    key,
                    "(dòng bị xóa)",
                    Describe(baseline),
                    Describe(local),
                    string.Empty,
                    !local.SequenceEqual(baseline, StringComparer.Ordinal)));
                continue;
            }

            for (var column = 0; column < _document.Headers.Count; column++)
            {
                var externalValue = externalRow.Values[column];
                if (string.Equals(externalValue, baseline[column], StringComparison.Ordinal)) continue;
                var localValue = local[column];
                changes.Add(new ExternalCanonicalChange(
                    ExternalChangeKind.Modified,
                    key,
                    _document.Headers[column],
                    baseline[column],
                    localValue,
                    externalValue,
                    !string.Equals(localValue, baseline[column], StringComparison.Ordinal)
                        && !string.Equals(localValue, externalValue, StringComparison.Ordinal)));
            }
        }

        foreach (var row in external.Rows.Where(row => !baselineKeySet.Contains(row[_config.KeyColumn])))
        {
            changes.Add(new ExternalCanonicalChange(
                ExternalChangeKind.Added,
                row[_config.KeyColumn],
                "(dòng mới)",
                string.Empty,
                string.Empty,
                Describe(row.Values),
                false));
        }
        return changes;
    }

    public void ReloadFromDisk()
    {
        var bytes = File.ReadAllBytes(_path);
        var document = CsvDocument.ParseBytes(bytes);
        _document = document;
        _loadedHash = Hash(bytes);
        _originalValues = Snapshot(document);
        Rows = document.Rows.Select((row, index) => new TranslationRow(row, _config, index)).ToList();
        ValidateSchema();
    }

    public void Save()
    {
        var dirty = DirtyIndexes().ToArray();
        if (dirty.Length == 0) return;
        var currentBytes = File.ReadAllBytes(_path);
        if (!string.Equals(Hash(currentBytes), _loadedHash, StringComparison.Ordinal))
            throw new StaleCanonicalException("Canonical đã thay đổi bên ngoài. Nạp lại trước khi lưu.");

        foreach (var index in dirty)
        {
            ValidateImmutableColumns(index);
            NormalizeStatus(Rows[index]);
        }
        foreach (var row in Rows)
        {
            var error = Validate(row);
            if (error.Length > 0) throw new CanonicalValidationException($"{row.Key}: {error}");
        }

        var temp = _path + ".bientaptay.tmp";
        var backup = _path + ".bientaptay.bak";
        try
        {
            var bytes = new UTF8Encoding(false).GetBytes(_document.Serialize());
            using (var stream = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes);
                stream.Flush(true);
            }
            if (File.Exists(backup)) File.Delete(backup);
            File.Replace(temp, _path, backup, true);

            var savedBytes = File.ReadAllBytes(_path);
            var saved = CsvDocument.ParseBytes(savedBytes);
            if (!saved.Headers.SequenceEqual(_document.Headers, StringComparer.Ordinal)
                || saved.Rows.Count != _document.Rows.Count
                || !saved.Rows.Select(row => row[_config.KeyColumn]).SequenceEqual(Rows.Select(row => row.Key), StringComparer.Ordinal))
                throw new IOException("Readback canonical không khớp sau khi lưu.");
            _loadedHash = Hash(savedBytes);
            _originalValues = Snapshot(_document);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }

    private IEnumerable<int> DirtyIndexes()
    {
        for (var index = 0; index < _document.Rows.Count; index++)
            if (!_document.Rows[index].Values.SequenceEqual(_originalValues[index], StringComparer.Ordinal))
                yield return index;
    }

    private int RowIndex(TranslationRow row)
    {
        var index = row.Index;
        if (index < 0 || index >= Rows.Count || !ReferenceEquals(Rows[index], row))
            throw new ArgumentException("Dòng không thuộc canonical store này.", nameof(row));
        return index;
    }

    private void ValidateSchema()
    {
        var required = new[] { _config.KeyColumn, _config.TargetColumn, _config.StatusColumn }
            .Concat(_config.SourceFields.Select(item => item.Column))
            .Concat(new[] { _config.SpeakerColumn, _config.GroupColumn, _config.NotesColumn, _config.ProtectedTokensColumn }
                .Where(item => !string.IsNullOrWhiteSpace(item))!)
            .Distinct(StringComparer.Ordinal);
        var missing = required.Where(column => !_document.Headers.Contains(column, StringComparer.Ordinal)).ToArray();
        if (missing.Length > 0) throw new InvalidDataException($"Canonical thiếu cột: {string.Join(", ", missing)}");
        var keys = Rows.Select(row => row.Key).ToArray();
        if (keys.Any(string.IsNullOrWhiteSpace) || keys.Distinct(StringComparer.Ordinal).Count() != keys.Length)
            throw new InvalidDataException("Canonical có key trống hoặc trùng.");
    }

    private void ValidateImmutableColumns(int index)
    {
        var mutable = new HashSet<string>(StringComparer.Ordinal) { _config.TargetColumn, _config.StatusColumn };
        if (!string.IsNullOrWhiteSpace(_config.NotesColumn)) mutable.Add(_config.NotesColumn);
        var original = _originalValues[index];
        for (var column = 0; column < _document.Headers.Count; column++)
        {
            var header = _document.Headers[column];
            if (!mutable.Contains(header) && _document.Rows[index][header] != original[column])
                throw new CanonicalValidationException($"{Rows[index].Key}: cột bất biến {header} đã bị sửa.");
        }
    }

    private static void NormalizeStatus(TranslationRow row)
    {
        if (row.Target.Length > 0 && row.Status == "pending") row.Status = "translated";
        if (row.Target.Length == 0 && row.Status is "translated" or "reviewed") row.Status = "pending";
    }

    private string Describe(IReadOnlyList<string> values)
    {
        var indexes = _document.Headers.Select((header, index) => (header, index))
            .ToDictionary(item => item.header, item => item.index, StringComparer.Ordinal);
        var target = values[indexes[_config.TargetColumn]];
        var status = values[indexes[_config.StatusColumn]];
        return target.Length == 0 ? $"[{status}]" : $"{target} [{status}]";
    }


    private static List<string[]> Snapshot(CsvDocument document) =>
        document.Rows.Select(row => row.Values.ToArray()).ToList();

    private static bool MultisetEqual(IEnumerable<string> left, IEnumerable<string> right) =>
        left.GroupBy(value => value).ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal)
            .OrderBy(item => item.Key, StringComparer.Ordinal)
            .SequenceEqual(right.GroupBy(value => value).ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal)
                .OrderBy(item => item.Key, StringComparer.Ordinal));

    private static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
}
