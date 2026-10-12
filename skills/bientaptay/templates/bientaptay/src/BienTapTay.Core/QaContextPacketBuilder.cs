using System.Text;

namespace BienTapTay.Core;

public sealed record QaContextSource(string Label, string Value);

public sealed record QaContextPacketRow(
    string Key,
    string Speaker,
    IReadOnlyList<QaContextSource> Sources,
    string Target,
    string Glossary,
    string Pronouns);

public static class QaContextPacketBuilder
{
    public static string Build(
        string projectName,
        string translationId,
        string translationLabel,
        ConsistencyIssue issue,
        IReadOnlyList<QaContextPacketRow> rows)
    {
        var related = issue.RelatedKeys.Distinct(StringComparer.Ordinal).ToArray();
        var byKey = rows.GroupBy(row => row.Key, StringComparer.Ordinal).ToArray();
        if (byKey.Any(group => group.Count() != 1)
            || !byKey.Select(group => group.Key).ToHashSet(StringComparer.Ordinal).SetEquals(related))
            throw new ArgumentException("Context rows phải khớp chính xác full related keys.", nameof(rows));

        var lookup = byKey.ToDictionary(group => group.Key, group => group.Single(), StringComparer.Ordinal);
        var builder = new StringBuilder();
        builder.AppendLine("BIENTAPTAY-QA-CONTEXT/1");
        Append(builder, string.Empty, "project", projectName);
        Append(builder, string.Empty, "translation_id", translationId);
        Append(builder, string.Empty, "translation_label", translationLabel);
        Append(builder, string.Empty, "warning_kind", issue.Kind.ToString());
        Append(builder, string.Empty, "warning", issue.Message);
        Append(builder, string.Empty, "primary_key", issue.Key);
        builder.AppendLine("rows:");
        foreach (var key in related)
        {
            var row = lookup[key];
            Append(builder, "  - ", "exact_key", row.Key);
            Append(builder, "    ", "speaker", row.Speaker);
            builder.AppendLine("    sources:");
            foreach (var source in row.Sources)
                Append(builder, "      ", source.Label, source.Value);
            Append(builder, "    ", "target", row.Target);
            Append(builder, "    ", "glossary", row.Glossary);
            Append(builder, "    ", "pronouns", row.Pronouns);
        }
        return builder.ToString().Replace("\r\n", "\n", StringComparison.Ordinal);
    }

    private static void Append(StringBuilder builder, string prefix, string label, string value)
    {
        var lines = value.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n').Split('\n');
        builder.Append(prefix).Append(label).Append(": ").AppendLine(lines[0]);
        var continuation = new string(' ', prefix.Length + label.Length + 2);
        for (var index = 1; index < lines.Length; index++)
            builder.Append(continuation).AppendLine(lines[index]);
    }
}
