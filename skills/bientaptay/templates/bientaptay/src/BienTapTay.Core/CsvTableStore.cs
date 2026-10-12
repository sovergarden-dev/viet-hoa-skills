using System.Security.Cryptography;
using System.Text;

namespace BienTapTay.Core;

public sealed class ReferenceValidationException(string message) : Exception(message);

public sealed class CsvTableStore
{
    private readonly string _path;
    private readonly string _keyColumn;
    private readonly string _validationProfile;
    private readonly HashSet<string> _canonicalKeys;
    private CsvDocument _document;
    private string _loadedHash;
    private List<IReadOnlyList<string>> _original;

    private CsvTableStore(
        string path,
        string keyColumn,
        string validationProfile,
        IEnumerable<string>? canonicalKeys,
        CsvDocument document,
        string hash)
    {
        _path = path;
        _keyColumn = keyColumn;
        _validationProfile = validationProfile;
        var keyGroups = (canonicalKeys ?? []).GroupBy(key => key, StringComparer.Ordinal).ToArray();
        _canonicalKeys = keyGroups.Where(group => group.Count() == 1)
            .Select(group => group.Key).ToHashSet(StringComparer.Ordinal);
        _document = document;
        _loadedHash = hash;
        _original = Snapshot(document);
    }

    public IReadOnlyList<string> Headers => _document.Headers;
    public List<CsvRow> Rows => _document.Rows;
    public string KeyColumn => _keyColumn;
    public string LoadedHash => _loadedHash;
    public bool HasUnsavedChanges => !SameAsSnapshot();

    public IReadOnlyList<ExternalCanonicalChange> CompareWithDisk()
    {
        var external = CsvDocument.ParseBytes(File.ReadAllBytes(_path));
        return CsvTableDiff.Compare(
            _keyColumn,
            new CsvTableSnapshot(Headers, _original),
            new CsvTableSnapshot(Headers, _document.Rows.Select(row => row.Values)),
            CsvTableSnapshot.From(external));
    }

    public void ReloadFromDisk()
    {
        var bytes = File.ReadAllBytes(_path);
        var document = CsvDocument.ParseBytes(bytes);
        if (!document.Headers.SequenceEqual(_document.Headers, StringComparer.Ordinal))
            throw new InvalidDataException("Schema bảng tham chiếu bên ngoài khác bản đã nạp.");
        _document = document;
        _loadedHash = Hash(bytes);
        _original = Snapshot(document);
    }

    public static CsvTableStore Open(string path, string keyColumn)
    {
        var fullPath = Path.GetFullPath(path);
        var bytes = File.ReadAllBytes(fullPath);
        return new CsvTableStore(fullPath, keyColumn, string.Empty, null, CsvDocument.ParseBytes(bytes), Hash(bytes));
    }

    public static CsvTableStore Open(
        string path,
        string keyColumn,
        string validationProfile,
        IEnumerable<string>? canonicalKeys = null)
    {
        var fullPath = Path.GetFullPath(path);
        var bytes = File.ReadAllBytes(fullPath);
        return new CsvTableStore(
            fullPath,
            keyColumn,
            validationProfile,
            canonicalKeys,
            CsvDocument.ParseBytes(bytes),
            Hash(bytes));
    }

    public CsvRow AddRow(IReadOnlyDictionary<string, string>? values = null) => _document.AddRow(values);

    public void RemoveAt(int index) => _document.Rows.RemoveAt(index);

    public void Validate()
    {
        if (!_document.Headers.Contains(_keyColumn, StringComparer.Ordinal))
            throw new ReferenceValidationException($"Bảng tham chiếu thiếu keyColumn {_keyColumn}.");
        var keys = _document.Rows.Select(row => row[_keyColumn]).ToArray();
        if (keys.Any(string.IsNullOrWhiteSpace) || keys.Distinct(StringComparer.Ordinal).Count() != keys.Length)
            throw new ReferenceValidationException($"Bảng tham chiếu có {_keyColumn} trống hoặc trùng.");
        if (_validationProfile.Equals("glossary", StringComparison.OrdinalIgnoreCase)) ValidateGlossary();
        if (_validationProfile.Equals("pronouns", StringComparison.OrdinalIgnoreCase)) ValidatePronouns();
    }

    public void Save()
    {
        Validate();
        if (!HasUnsavedChanges) return;
        var current = File.ReadAllBytes(_path);
        if (!string.Equals(Hash(current), _loadedHash, StringComparison.Ordinal))
            throw new StaleCanonicalException("Bảng tham chiếu đã thay đổi bên ngoài. Nạp lại trước khi lưu.");

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
                || !saved.Rows.Select(row => row[_keyColumn]).SequenceEqual(_document.Rows.Select(row => row[_keyColumn]), StringComparer.Ordinal))
                throw new IOException("Readback bảng tham chiếu không khớp sau khi lưu.");
            _document = saved;
            _loadedHash = Hash(savedBytes);
            _original = Snapshot(saved);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }

    private bool SameAsSnapshot() => _document.Rows.Count == _original.Count
        && _document.Rows.Select(row => row.Values).Zip(_original)
            .All(pair => pair.First.SequenceEqual(pair.Second, StringComparer.Ordinal));

    private static List<IReadOnlyList<string>> Snapshot(CsvDocument document) =>
        document.Rows.Select(row => (IReadOnlyList<string>)row.Values.ToArray()).ToList();

    private void ValidateGlossary()
    {
        RequireColumns("term", "translation", "status");
        var allowedStatuses = new HashSet<string>(["proposed", "locked", "reviewed", "approved"], StringComparer.Ordinal);
        foreach (var row in _document.Rows)
        {
            if (string.IsNullOrWhiteSpace(row["translation"]))
                throw new ReferenceValidationException($"Glossary {row[_keyColumn]} thiếu translation.");
            if (!allowedStatuses.Contains(row["status"]))
                throw new ReferenceValidationException($"Glossary {row[_keyColumn]} có status không hợp lệ: {row["status"]}.");
        }
    }

    private void ValidatePronouns()
    {
        RequireColumns("speaker", "self_reference", "address_form", "notes", "status", "evidence_keys");
        var allowedStatuses = new HashSet<string>(
            ["reviewed", "inherited", "not_applicable", "mixed_context", "limited_evidence"],
            StringComparer.Ordinal);
        foreach (var row in _document.Rows)
        {
            foreach (var column in new[] { "self_reference", "address_form", "notes" })
                if (string.IsNullOrWhiteSpace(row[column]))
                    throw new ReferenceValidationException($"Pronouns {row[_keyColumn]} thiếu {column}.");
            if (!allowedStatuses.Contains(row["status"]))
                throw new ReferenceValidationException($"Pronouns {row[_keyColumn]} có status không hợp lệ: {row["status"]}.");
            var evidence = row["evidence_keys"].Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (evidence.Length == 0)
                throw new ReferenceValidationException($"Pronouns {row[_keyColumn]} thiếu evidence_keys.");
            var missing = evidence.FirstOrDefault(item =>
                !item.StartsWith("inherit:", StringComparison.Ordinal)
                && !item.StartsWith("none:", StringComparison.Ordinal)
                && !_canonicalKeys.Contains(item));
            if (missing is not null)
                throw new ReferenceValidationException($"Pronouns {row[_keyColumn]} có evidence key không tồn tại hoặc không duy nhất: {missing}.");
        }
    }

    private void RequireColumns(params string[] columns)
    {
        var missing = columns.Where(column => !_document.Headers.Contains(column, StringComparer.Ordinal)).ToArray();
        if (missing.Length > 0)
            throw new ReferenceValidationException($"Bảng {_validationProfile} thiếu cột: {string.Join(", ", missing)}.");
    }

    private static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
}
