using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Text.RegularExpressions;
using BienTapTay.Core;

namespace BienTapTay.App;

public sealed class SourceTextViewModel(string label, string value)
{
    public string Label { get; } = label;
    public string Value { get; } = value;
}

public sealed class DialogueTurnViewModel(DialogueTurn turn)
{
    public string Speaker { get; } = turn.Speaker;
    public string Source { get; } = turn.Source;
    public string Target { get; } = turn.Target;
    public string Keys { get; } = string.Join(" · ", turn.Keys);
    public string PrimaryKey { get; } = turn.Keys[0];
    public bool IsSelected { get; } = turn.IsSelected;
}

public sealed class BookmarkViewModel(string translationId, string fileLabel, string key)
{
    public string TranslationId { get; } = translationId;
    public string FileLabel { get; } = fileLabel;
    public string Key { get; } = key;
    public string Display => $"{FileLabel} / {Key}";
}

public sealed class ReplacePreviewRowViewModel(TranslationReplacement item)
{
    public string Key { get; } = item.Key;
    public int Occurrences { get; } = item.Occurrences;
    public string Before { get; } = PreviewText.OneLine(item.Before);
    public string After { get; } = PreviewText.OneLine(item.After);
    public string ValidationMessage { get; } = item.ValidationMessage;
    public bool HasError => ValidationMessage.Length > 0;
}

public sealed class TranslationSearchResultViewModel(TranslationSearchResult result)
{
    public string FileId { get; } = result.FileId;
    public string FileLabel { get; } = result.FileLabel;
    public string Key { get; } = result.Key;
    public string Speaker { get; } = result.Speaker;
    public string Group { get; } = result.Group;
    public string Source { get; } = result.Source;
    public string Target { get; } = result.Target;
    public string MatchField { get; } = result.MatchField;
    public string MatchedText { get; } = result.MatchedText;
    public string MatchedPreview { get; } = PreviewText.OneLine(result.MatchedText);
    public string TargetPreview { get; } = PreviewText.OneLine(result.Target);
}

public sealed class ExternalChangeViewModel(ExternalCanonicalChange change)
{
    public string FileId { get; } = change.FileId;
    public string FileLabel { get; } = change.FileLabel.Length == 0 ? change.FileId : change.FileLabel;
    public bool IsReference { get; } = change.IsReference;
    public string Kind => change.Kind switch
    {
        ExternalChangeKind.Added => "Thêm",
        ExternalChangeKind.Removed => "Xóa",
        _ => "Sửa",
    };
    public string Key { get; } = change.Key;
    public string Field { get; } = change.Field;
    public string LoadedValue { get; } = change.LoadedValue;
    public string LocalValue { get; } = change.LocalValue;
    public string ExternalValue { get; } = change.ExternalValue;
    public string LoadedPreview { get; } = PreviewText.OneLine(change.LoadedValue);
    public string LocalPreview { get; } = PreviewText.OneLine(change.LocalValue);
    public string ExternalPreview { get; } = PreviewText.OneLine(change.ExternalValue);
    public bool IsConflict { get; } = change.IsConflict;
}

public sealed class ConsistencyIssueViewModel(ConsistencyIssue issue, QaDecisionMatch decision)
{
    public ConsistencyIssue Issue { get; } = issue;
    public ConsistencyIssueKind KindValue => Issue.Kind;
    public string Kind => Issue.Kind switch
    {
        ConsistencyIssueKind.DuplicateSource => "Trùng source",
        ConsistencyIssueKind.GlossaryDrift => "Glossary",
        _ => "Xưng hô",
    };
    public string Severity => Issue.Severity;
    public string Key => Issue.Key;
    public string SpeakerValue => Issue.Speaker;
    public string Speaker => Issue.Speaker.Length == 0 ? "(không speaker)" : Issue.Speaker;
    public string Message => Issue.Message;
    public string Source => Issue.Source;
    public string Target => Issue.Target;
    public string RelatedKeys => string.Join(" · ", Issue.RelatedKeys);
    public IReadOnlyList<string> RelatedKeyList => Issue.RelatedKeys;
    public string DecisionId { get; } = decision.DecisionId;
    public QaTriageStatus TriageStatus { get; } = decision.Status;
    public string TriageLabel => TriageStatus switch
    {
        QaTriageStatus.NeedsFix => "Cần sửa",
        QaTriageStatus.AcceptedDifference => "Chấp nhận khác biệt",
        QaTriageStatus.Resolved => "Đã xử lý",
        _ => "Chưa phân loại",
    };
    public string DecisionNote { get; } = decision.Note;
    public bool IsDecisionStale { get; } = decision.IsStale;
}

public sealed class QaRelatedRowViewModel(TranslationRowViewModel row, bool isPrimary)
{
    public TranslationRowViewModel Row { get; } = row;
    public string Marker { get; } = isPrimary ? "●" : string.Empty;
    public string Key => Row.Key;
    public string Speaker => Row.Speaker;
    public string Source => Row.Model.AuthoritativeSource;
    public string Target => Row.Target;
}

internal static class PreviewText
{
    public static string OneLine(string text, int limit = 120)
    {
        var value = text.Replace("\r", " ").Replace("\n", " ").Trim();
        return value.Length <= limit ? value : value[..limit] + "…";
    }
}

public sealed class TranslationRowViewModel : INotifyPropertyChanged
{
    private readonly CanonicalStore _store;
    private string _validationMessage;
    private readonly string _sourceSearchText;
    private IReadOnlyList<SourceTextViewModel>? _sources;
    private IReadOnlyList<DialogueTurnViewModel> _dialogueTurns = [];
    public TranslationRowViewModel(TranslationRow model, CanonicalStore store)
    {
        Model = model;
        _store = store;
        _sourceSearchText = string.Join("\n", model.Sources.Select(item => item.Value));
        _validationMessage = _store.Validate(Model);
    }

    public TranslationRow Model { get; }
    public int Index => Model.Index;
    public string Key => Model.Key;
    public string Speaker => Model.Speaker;
    public string Group => Model.Group;
    public string StatusLabel => StatusDisplay.Label(Status);
    public IReadOnlyList<string> SourceTokens => Regex.Matches(Model.AuthoritativeSource, _store.Config.TokenPattern, RegexOptions.CultureInvariant)
        .Select(match => match.Value)
        .Where(token => token.Length > 0)
        .Distinct(StringComparer.Ordinal)
        .ToArray();
    public IReadOnlyList<SourceTextViewModel> Sources =>
        _sources ??= Model.Sources.Select(item => new SourceTextViewModel(item.Label, item.Value)).ToArray();
    public string SourceSearchText => _sourceSearchText;
    public string TargetPreview
    {
        get
        {
            var text = Target.Replace("\r", " ").Replace("\n", " ").Replace("<br>", " ").Trim();
            return text.Length <= 72 ? text : text[..72] + "…";
        }
    }
    public string ProtectedTokens => Model.ProtectedTokens;
    public IReadOnlyList<DialogueTurnViewModel> DialogueTurns
    {
        get => _dialogueTurns;
        set
        {
            _dialogueTurns = value;
            OnPropertyChanged();
        }
    }
    public string MatchingGlossary { get; set; } = "Không có thuật ngữ khớp.";
    public string PronounGuidance { get; set; } = "Chưa có quy tắc xưng hô cho người nói này.";

    public string Target
    {
        get => Model.Target;
        set
        {
            if (Model.Target == value) return;
            Model.Target = value;
            RefreshValidation();
            OnPropertyChanged();
            OnPropertyChanged(nameof(TargetPreview));
        }
    }

    public string Status
    {
        get => Model.Status;
        set
        {
            if (Model.Status == value) return;
            Model.Status = value;
            RefreshValidation();
            OnPropertyChanged();
            OnPropertyChanged(nameof(StatusLabel));
        }
    }

    public string Notes
    {
        get => Model.Notes;
        set
        {
            if (Model.Notes == value) return;
            Model.Notes = value;
            OnPropertyChanged();
        }
    }

    public string ValidationMessage => _validationMessage;
    public bool HasValidationError => _validationMessage.Length > 0;

    public void RefreshGuidance()
    {
        OnPropertyChanged(nameof(DialogueTurns));
        OnPropertyChanged(nameof(MatchingGlossary));
        OnPropertyChanged(nameof(PronounGuidance));
        RefreshValidation();
    }

    public void RefreshFromModel()
    {
        OnPropertyChanged(nameof(Target));
        OnPropertyChanged(nameof(TargetPreview));
        OnPropertyChanged(nameof(Status));
        OnPropertyChanged(nameof(StatusLabel));
        OnPropertyChanged(nameof(Notes));
        RefreshValidation();
    }

    private void RefreshValidation()
    {
        _validationMessage = _store.Validate(Model);
        OnPropertyChanged(nameof(ValidationMessage));
        OnPropertyChanged(nameof(HasValidationError));
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    private void OnPropertyChanged([CallerMemberName] string? name = null) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

public sealed class ReferenceRowViewModel(CsvRow row) : INotifyPropertyChanged
{
    public CsvRow Row { get; } = row;
    public string this[string column]
    {
        get => Row[column];
        set
        {
            if (Row[column] == value) return;
            Row[column] = value;
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs("Item[]"));
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
}

public sealed class FilterOption(string label, string? value)
{
    public string Label { get; } = label;
    public string? Value { get; } = value;
    public override string ToString() => Label;
}

internal static class StatusDisplay
{
    public static string Label(string status) => status switch
    {
        "pending" => "Chưa dịch",
        "translated" => "Đã dịch",
        "reviewed" => "Đã duyệt",
        "needs_context" => "Cần ngữ cảnh",
        "rejected" => "Từ chối",
        _ => status,
    };
}
