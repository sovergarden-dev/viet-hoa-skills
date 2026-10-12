namespace BienTapTay.Core;

public sealed record DialogueTurn(
    string Speaker,
    string Source,
    string Target,
    IReadOnlyList<string> Keys,
    bool IsSelected);

public static class DialogueContextBuilder
{
    public static IReadOnlyList<DialogueTurn> Build(IReadOnlyList<TranslationRow> rows, int selectedIndex, int radius = 4)
    {
        if (selectedIndex < 0 || selectedIndex >= rows.Count) throw new ArgumentOutOfRangeException(nameof(selectedIndex));
        if (radius < 0) throw new ArgumentOutOfRangeException(nameof(radius));
        var scene = Scene(rows[selectedIndex]);
        var start = selectedIndex;
        var end = selectedIndex;
        while (start > 0 && string.Equals(Scene(rows[start - 1]), scene, StringComparison.Ordinal)) start--;
        while (end + 1 < rows.Count && string.Equals(Scene(rows[end + 1]), scene, StringComparison.Ordinal)) end++;

        var builders = new List<TurnBuilder>();
        for (var index = start; index <= end; index++)
        {
            var row = rows[index];
            var speaker = SpeakerLabel(row.Speaker);
            var isSelected = index == selectedIndex;
            if (builders.Count > 0 && string.Equals(builders[^1].Speaker, speaker, StringComparison.Ordinal))
            {
                builders[^1].Add(row, isSelected);
            }
            else
            {
                builders.Add(new TurnBuilder(speaker, row, isSelected));
            }
        }

        var selectedTurn = builders.FindIndex(turn => turn.IsSelected);
        var first = Math.Max(0, selectedTurn - radius);
        var last = Math.Min(builders.Count - 1, selectedTurn + radius);
        return builders.Skip(first).Take(last - first + 1).Select(turn => turn.Build()).ToArray();
    }

    private static string Scene(TranslationRow row) => row.Group.Length > 0
        ? row.Group
        : row.Key.Split("::", 2, StringSplitOptions.None)[0];

    private static string SpeakerLabel(string speaker)
    {
        if (string.IsNullOrWhiteSpace(speaker)) return "Dẫn chuyện";
        if (speaker.StartsWith("@choice", StringComparison.Ordinal)) return "Lựa chọn";
        if (speaker.StartsWith("@printDebate", StringComparison.Ordinal)) return "Luận điểm";
        if (speaker.StartsWith("@print", StringComparison.Ordinal)) return "Dẫn chuyện";
        return speaker.StartsWith('@') ? "Hệ thống" : speaker;
    }

    private sealed class TurnBuilder
    {
        private readonly List<string> _source = [];
        private readonly List<string> _target = [];
        private readonly List<string> _keys = [];

        public TurnBuilder(string speaker, TranslationRow row, bool isSelected)
        {
            Speaker = speaker;
            Add(row, isSelected);
        }

        public string Speaker { get; }
        public bool IsSelected { get; private set; }

        public void Add(TranslationRow row, bool isSelected)
        {
            _source.Add(row.AuthoritativeSource);
            _target.Add(row.Target);
            _keys.Add(row.Key);
            IsSelected |= isSelected;
        }

        public DialogueTurn Build() => new(
            Speaker,
            string.Join("\n", _source),
            string.Join("\n", _target),
            _keys.ToArray(),
            IsSelected);
    }
}
