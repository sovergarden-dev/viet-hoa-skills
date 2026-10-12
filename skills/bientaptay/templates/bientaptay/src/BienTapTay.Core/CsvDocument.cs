using System.Text;

namespace BienTapTay.Core;

public sealed class CsvRow
{
    private readonly IReadOnlyDictionary<string, int> _columnIndexes;
    private readonly string[] _cells;

    internal CsvRow(IReadOnlyDictionary<string, int> columnIndexes, IEnumerable<string> values)
    {
        _columnIndexes = columnIndexes;
        _cells = values as string[] ?? values.ToArray();
        if (_cells.Length != _columnIndexes.Count)
            throw new ArgumentException($"Dòng có {_cells.Length} cột, cần {_columnIndexes.Count}.");
    }

    public string this[string header]
    {
        get => _columnIndexes.TryGetValue(header, out var index) ? _cells[index] : throw new KeyNotFoundException(header);
        set
        {
            if (!_columnIndexes.TryGetValue(header, out var index)) throw new KeyNotFoundException(header);
            _cells[index] = value ?? string.Empty;
        }
    }

    public IReadOnlyList<string> Values => _cells;

    internal CsvRow Clone() => new(_columnIndexes, _cells.ToArray());
}

public sealed class CsvDocument
{
    private readonly IReadOnlyDictionary<string, int> _columnIndexes;

    private CsvDocument(IReadOnlyList<string> headers, IReadOnlyDictionary<string, int> columnIndexes, List<CsvRow> rows, bool hasBom, string newLine)
    {
        Headers = headers;
        _columnIndexes = columnIndexes;
        Rows = rows;
        HasBom = hasBom;
        NewLine = newLine;
    }

    public IReadOnlyList<string> Headers { get; }
    public List<CsvRow> Rows { get; }
    public bool HasBom { get; }
    public string NewLine { get; }

    public CsvRow AddRow(IReadOnlyDictionary<string, string>? values = null)
    {
        if (values is not null)
        {
            var extra = values.Keys.Where(key => !_columnIndexes.ContainsKey(key)).ToArray();
            if (extra.Length > 0) throw new ArgumentException($"Cột không tồn tại: {string.Join(", ", extra)}");
        }
        var row = new CsvRow(_columnIndexes, Headers.Select(header => values is not null && values.TryGetValue(header, out var value) ? value : string.Empty));
        Rows.Add(row);
        return row;
    }

    public static CsvDocument ParseBytes(byte[] bytes)
    {
        var hasBom = bytes.AsSpan().StartsWith(new byte[] { 0xEF, 0xBB, 0xBF });
        var offset = hasBom ? 3 : 0;
        return ParseCore(Encoding.UTF8.GetString(bytes, offset, bytes.Length - offset), hasBom);
    }

    public static CsvDocument Parse(string text)
    {
        var hasBom = text.Length > 0 && text[0] == '\uFEFF';
        return ParseCore(hasBom ? text[1..] : text, hasBom);
    }

    private static CsvDocument ParseCore(string text, bool hasBom)
    {
        var newLine = text.Contains("\r\n", StringComparison.Ordinal) ? "\r\n"
            : text.Contains('\n') ? "\n"
            : text.Contains('\r') ? "\r"
            : Environment.NewLine;
        var records = new List<List<string>>();
        var record = new List<string>();
        var field = new StringBuilder();
        var quoted = false;

        for (var index = 0; index < text.Length; index++)
        {
            var character = text[index];
            if (quoted)
            {
                if (character == '"')
                {
                    if (index + 1 < text.Length && text[index + 1] == '"')
                    {
                        field.Append('"');
                        index++;
                    }
                    else quoted = false;
                }
                else field.Append(character);
                continue;
            }

            if (character == '"' && field.Length == 0)
            {
                quoted = true;
            }
            else if (character == ',')
            {
                record.Add(field.ToString());
                field.Clear();
            }
            else if (character is '\r' or '\n')
            {
                record.Add(field.ToString());
                field.Clear();
                records.Add(record);
                record = new List<string>();
                if (character == '\r' && index + 1 < text.Length && text[index + 1] == '\n') index++;
            }
            else field.Append(character);
        }

        if (quoted) throw new FormatException("CSV kết thúc giữa trường được trích dẫn.");
        if (field.Length > 0 || record.Count > 0)
        {
            record.Add(field.ToString());
            records.Add(record);
        }
        if (records.Count == 0) throw new FormatException("CSV trống.");

        var headers = records[0];
        if (headers.Count == 0 || headers.Any(string.IsNullOrWhiteSpace)) throw new FormatException("CSV có header trống.");
        if (headers.Distinct(StringComparer.Ordinal).Count() != headers.Count) throw new FormatException("CSV có header trùng.");
        var columnIndexes = headers
            .Select((header, index) => (header, index))
            .ToDictionary(item => item.header, item => item.index, StringComparer.Ordinal);

        var rows = new List<CsvRow>(Math.Max(0, records.Count - 1));
        for (var index = 1; index < records.Count; index++)
        {
            var values = records[index];
            if (values.Count == 1 && values[0].Length == 0) continue;
            if (values.Count != headers.Count)
                throw new FormatException($"Dòng CSV {index + 1} có {values.Count} cột, cần {headers.Count}.");
            rows.Add(new CsvRow(columnIndexes, values));
        }
        return new CsvDocument(headers, columnIndexes, rows, hasBom, newLine);
    }

    public string Serialize()
    {
        var output = new StringBuilder();
        if (HasBom) output.Append('\uFEFF');
        WriteRecord(output, Headers);
        foreach (var row in Rows) WriteRecord(output, row.Values);
        return output.ToString();
    }

    private void WriteRecord(StringBuilder output, IEnumerable<string> values)
    {
        var first = true;
        foreach (var value in values)
        {
            if (!first) output.Append(',');
            first = false;
            var needsQuotes = value.IndexOfAny([',', '"', '\r', '\n']) >= 0
                || value.StartsWith(' ') || value.EndsWith(' ');
            if (needsQuotes)
            {
                output.Append('"');
                output.Append(value.Replace("\"", "\"\"", StringComparison.Ordinal));
                output.Append('"');
            }
            else output.Append(value);
        }
        output.Append(NewLine);
    }
}
