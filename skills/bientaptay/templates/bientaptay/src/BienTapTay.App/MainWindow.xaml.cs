using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using BienTapTay.Core;
using Microsoft.Win32;

namespace BienTapTay.App;

public partial class MainWindow : Window
{
    private readonly string _configPath;
    private readonly DispatcherTimer _filterTimer;
    private readonly DispatcherTimer _watchTimer;
    private ProjectConfig _projectConfig = null!;
    private ProjectConfig _config = null!;
    private CanonicalStore _store = null!;
    private IReadOnlyList<TranslationFileConfig> _translationFiles = [];
    private string _activeTranslationId = string.Empty;
    private bool _changingDataset;
    private ObservableCollection<TranslationRowViewModel> _rows = [];
    private List<TranslationRowViewModel> _filteredRows = [];
    private int _page;
    private int _pageSize = PageWindow.DefaultSize;
    private bool _changingPageSize;
    private bool _changingFontScale;
    private double _fontScale = 1;
    private SessionState? _session;
    private bool _externalConflict;
    private bool _restoringSession;
    private readonly ObservableCollection<ReplacePreviewRowViewModel> _replacePreviewRows = [];
    private readonly ObservableCollection<TranslationSearchResultViewModel> _projectSearchRows = [];
    private readonly ObservableCollection<BookmarkViewModel> _bookmarks = [];
    private bool _bookmarksLoaded;
    private bool _changingBookmarkSelection;
    private TranslationReplacePlan? _replacePlan;
    private readonly ObservableCollection<ExternalChangeViewModel> _externalDiffRows = [];

    private TranslationReplaceUndo? _lastReplaceUndo;
    private readonly ObservableCollection<ConsistencyIssueViewModel> _consistencyIssues = [];
    private readonly ObservableCollection<QaRelatedRowViewModel> _consistencyRelatedRows = [];
    private readonly ICollectionView? _consistencyIssueView;
    private QaDecisionStore _qaDecisionStore = null!;
    private bool _changingConsistencyFilters;
    private bool _consistencyNeedsRefresh = true;
    private bool _consistencyHasScanned;
    private bool _referencesLoaded;

    private readonly Dictionary<string, CsvTableStore> _referenceStores = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, CanonicalStore> _translationStores = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, WatchedProjectFile> _watchedProjectFiles = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _pendingExternalFileIds = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, ObservableCollection<ReferenceRowViewModel>> _referenceRows = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, ICollectionView> _referenceViews = new(StringComparer.OrdinalIgnoreCase);

    public MainWindow(string configPath)
    {
        InitializeComponent();
        ReplacePreviewGrid.ItemsSource = _replacePreviewRows;
        ProjectSearchGrid.ItemsSource = _projectSearchRows;
        BookmarkPicker.ItemsSource = _bookmarks;
        ExternalDiffGrid.ItemsSource = _externalDiffRows;
        _consistencyIssueView = CollectionViewSource.GetDefaultView(_consistencyIssues);
        ConsistencyQaGrid.ItemsSource = _consistencyIssueView;
        ConsistencyQaRelatedGrid.ItemsSource = _consistencyRelatedRows;
        StateChanged += (_, _) => SyncWindowStateVisual();
        Loaded += (_, _) => SyncWindowStateVisual();
        _configPath = Path.GetFullPath(configPath);
        _session = SessionState.Load(_configPath);
        _session?.ApplyWindow(this);
        SetFontScale(_session?.FontScale ?? 1);
        ApplyLayoutSession();
        _filterTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(220) };
        _filterTimer.Tick += (_, _) => { _filterTimer.Stop(); ApplyTranslationFilter(); };
        _watchTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
        _watchTimer.Tick += WatchTimer_Tick;
        LoadProject(_session?.SelectedKey, _session?.TranslationId, restoreSession: true);
        _watchTimer.Start();
    }

    private void LoadProject(string? selectedKey = null, string? translationId = null, bool restoreSession = false)
    {
        if (_store is not null) CaptureLayoutState(_session ??= new SessionState());
        _lastReplaceUndo = null;
        _projectConfig = ProjectConfig.Load(_configPath);
        _qaDecisionStore = QaDecisionStore.Open(QaDecisionPath(_configPath));
        _translationFiles = _projectConfig.GetTranslationFiles();
        LoadBookmarks();
        _translationStores.Clear();
        foreach (var file in _translationFiles)
        {
            var fileConfig = _projectConfig.ForTranslationFile(file);
            _translationStores[file.Id] = CanonicalStore.Open(fileConfig);
        }
        var requestedId = translationId ?? (_activeTranslationId.Length > 0 ? _activeTranslationId : _translationFiles[0].Id);
        var translationFile = _translationFiles.FirstOrDefault(item => item.Id.Equals(requestedId, StringComparison.OrdinalIgnoreCase))
            ?? _translationFiles[0];
        _activeTranslationId = translationFile.Id;
        _config = _projectConfig.ForTranslationFile(translationFile);
        _store = _translationStores[translationFile.Id];
        _rows = new ObservableCollection<TranslationRowViewModel>(_store.Rows.Select(row => new TranslationRowViewModel(row, _store)));
        foreach (var row in _rows) row.PropertyChanged += TranslationRow_Changed;
        EditorStatusCombo.ItemsSource = _config.Statuses.Select(status => new FilterOption(StatusDisplay.Label(status), status)).ToArray();

        _changingDataset = true;
        DatasetFilter.ItemsSource = _translationFiles;
        DatasetFilter.SelectedItem = _translationFiles.First(item => item.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase));
        _changingDataset = false;

        StatusFilter.ItemsSource = new[] { new FilterOption("Mọi trạng thái", null) }
            .Concat(_config.Statuses.Select(status => new FilterOption(StatusDisplay.Label(status), status))).ToArray();
        StatusFilter.SelectedIndex = 0;
        GroupFilter.ItemsSource = new[] { new FilterOption("Mọi nhóm", null) }
            .Concat(_rows.Select(row => row.Group).Where(group => group.Length > 0).Distinct(StringComparer.Ordinal)
                .OrderBy(group => group, StringComparer.OrdinalIgnoreCase).Select(group => new FilterOption(group, group))).ToArray();
        GroupFilter.SelectedIndex = 0;
        SetPageSize(restoreSession ? _session?.PageSize ?? PageWindow.DefaultSize : _pageSize);

        if (restoreSession && _session is not null)
        {
            _restoringSession = true;
            MainTabs.SelectedIndex = Math.Clamp(_session.TabIndex, 0, MainTabs.Items.Count - 1);
            SearchBox.Text = _session.Search ?? string.Empty;
            OnlyIssuesCheck.IsChecked = _session.OnlyIssues;
            if (_session.Status is not null)
                StatusFilter.SelectedItem = StatusFilter.Items.Cast<FilterOption>().FirstOrDefault(item => item.Value == _session.Status) ?? StatusFilter.Items[0];
            if (_session.Group is not null)
                GroupFilter.SelectedItem = GroupFilter.Items.Cast<FilterOption>().FirstOrDefault(item => item.Value == _session.Group) ?? GroupFilter.Items[0];
            _page = Math.Max(0, _session.Page);
            _restoringSession = false;
        }

        ProjectNameText.Text = $"{_projectConfig.ProjectName} / {translationFile.Label}";
        _externalConflict = false;
        _pendingExternalFileIds.Clear();
        _consistencyNeedsRefresh = true;
        _consistencyHasScanned = false;
        _consistencyIssues.Clear();
        ConsistencyQaTab.Header = "QA nhất quán";
        SaveButton.IsEnabled = true;
        LoadReferences();
        UpdateExternalDiffState();
        UpdateSummary();
        UpdateProjectInfo();
        ApplyTranslationFilter(selectedKey);
        UpdateDirtyTitle();
        if (ReferenceEquals(MainTabs.SelectedItem, ConsistencyQaTab)) ScanConsistencyQa();
        SetStatus("Đã nạp canonical trực tiếp từ CSV.");
        ApplyQaDecisionAvailability();
    }

    private void ApplyQaDecisionAvailability()
    {
        if (_qaDecisionStore.CanMutate)
        {
            ConsistencyQaSidecarErrorText.Visibility = Visibility.Collapsed;
            ConsistencyQaSidecarErrorText.Text = string.Empty;
            ConsistencyQaTriageCombo.IsEnabled = true;
            ConsistencyQaDecisionNoteBox.IsEnabled = true;
            return;
        }

        ConsistencyQaSidecarErrorText.Text = _qaDecisionStore.UnavailableReason;
        ConsistencyQaSidecarErrorText.Visibility = Visibility.Visible;
        ConsistencyQaSaveDecisionButton.IsEnabled = false;
        ConsistencyQaSaveNextButton.IsEnabled = false;
        ConsistencyQaTriageCombo.IsEnabled = false;
        ConsistencyQaDecisionNoteBox.IsEnabled = false;
        SetStatus(_qaDecisionStore.UnavailableReason, error: true);
    }

    private void LoadBookmarks()
    {
        if (_bookmarksLoaded) return;
        foreach (var bookmark in _session?.Bookmarks ?? [])
        {
            if (string.IsNullOrWhiteSpace(bookmark.TranslationId) || string.IsNullOrWhiteSpace(bookmark.Key)
                || _bookmarks.Any(item => item.TranslationId.Equals(bookmark.TranslationId, StringComparison.OrdinalIgnoreCase)
                    && item.Key.Equals(bookmark.Key, StringComparison.Ordinal))) continue;
            var label = _translationFiles.FirstOrDefault(file => file.Id.Equals(bookmark.TranslationId, StringComparison.OrdinalIgnoreCase))?.Label
                ?? bookmark.TranslationId;
            _bookmarks.Add(new BookmarkViewModel(bookmark.TranslationId, label, bookmark.Key));
        }
        _bookmarksLoaded = true;
        UpdateBookmarkControls(null);
    }

    private void LoadReferences()
    {
        _referencesLoaded = false;
        _referenceStores.Clear();
        _referenceRows.Clear();
        _referenceViews.Clear();
        GlossaryGrid.Columns.Clear();
        PronounsGrid.Columns.Clear();

        foreach (var reference in _config.References)
            LoadReference(reference);
        _referencesLoaded = true;
        RefreshWatchedProjectFiles();
    }

    private void LoadReference(ReferenceFileConfig reference)
    {
        var path = _config.Resolve(reference.Path);
        if (!File.Exists(path)) return;
        var canonicalKeys = _translationStores.Values.SelectMany(item => item.Rows).Select(row => row.Key);
        var store = CsvTableStore.Open(path, reference.KeyColumn, reference.Id, canonicalKeys);
        var rows = new ObservableCollection<ReferenceRowViewModel>(store.Rows.Select(row => new ReferenceRowViewModel(row)));
        foreach (var row in rows) row.PropertyChanged += ReferenceRow_Changed;
        var view = CollectionViewSource.GetDefaultView(rows);
        _referenceStores[reference.Id] = store;
        _referenceRows[reference.Id] = rows;
        _referenceViews[reference.Id] = view;
        if (reference.Id.Equals("glossary", StringComparison.OrdinalIgnoreCase)) ConfigureReferenceGrid(GlossaryGrid, store, view, $"reference:{reference.Id}");
        if (reference.Id.Equals("pronouns", StringComparison.OrdinalIgnoreCase)) ConfigureReferenceGrid(PronounsGrid, store, view, $"reference:{reference.Id}");
    }

    private void ReloadReference(string id)
    {
        var reference = _config.References.FirstOrDefault(item => item.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
        if (reference is null) return;
        var grid = ReferenceGrid(id);
        if (grid is not null) CaptureGridColumnWidths(_session ??= new SessionState(), grid, $"reference:{id}");
        _referenceStores.Remove(id);
        _referenceRows.Remove(id);
        _referenceViews.Remove(id);
        LoadReference(reference);
        if (_watchedProjectFiles.TryGetValue($"reference:{id}", out var watched)) watched.MarkCurrent();
    }

    private void RefreshWatchedProjectFiles()
    {
        _watchedProjectFiles.Clear();
        foreach (var file in _translationFiles)
        {
            var fileConfig = _projectConfig.ForTranslationFile(file);
            _watchedProjectFiles[$"translation:{file.Id}"] = new WatchedProjectFile(
                $"translation:{file.Id}", file.Label, false, fileConfig.ResolvedCanonicalPath);
        }
        foreach (var reference in _config.References)
        {
            _watchedProjectFiles[$"reference:{reference.Id}"] = new WatchedProjectFile(
                $"reference:{reference.Id}", reference.Label, true, _config.Resolve(reference.Path));
        }
    }

    private void ConfigureReferenceGrid(DataGrid grid, CsvTableStore store, ICollectionView view, string scope)
    {
        grid.Columns.Clear();
        foreach (var header in store.Headers)
        {
            grid.Columns.Add(new DataGridTextColumn
            {
                Header = HeaderLabel(header),
                SortMemberPath = header,
                Binding = new Binding($"[{header}]") { Mode = BindingMode.TwoWay, UpdateSourceTrigger = UpdateSourceTrigger.PropertyChanged },
                Width = header is "context" or "notes" or "rule" ? new DataGridLength(2, DataGridLengthUnitType.Star) : new DataGridLength(1, DataGridLengthUnitType.Star),
                MinWidth = 110,
            });
        }
        grid.ItemsSource = view;
        ApplySavedColumnWidths(grid, scope);
    }

    private void TranslationRow_Changed(object? sender, PropertyChangedEventArgs e)
    {
        if (_restoringSession) return;
        if (e.PropertyName is nameof(TranslationRowViewModel.Target)
            or nameof(TranslationRowViewModel.Status)
            or nameof(TranslationRowViewModel.Notes))
            _consistencyNeedsRefresh = true;
        if (sender is TranslationRowViewModel changed && ReferenceEquals(CanonicalGrid.SelectedItem, changed))
            UpdateRevertButton(changed);
        if (!_store.HasUnsavedChanges && !_referenceStores.Values.Any(store => store.HasUnsavedChanges)) return;
        UpdateDirtyTitle();
        SetStatus("Có thay đổi chưa lưu.", warning: true);
        if (e.PropertyName is nameof(TranslationRowViewModel.Target) or nameof(TranslationRowViewModel.Status))
        {
            _filterTimer.Stop();
            _filterTimer.Start();
        }
    }

    private void ReferenceRow_Changed(object? sender, PropertyChangedEventArgs e)
    {
        _consistencyNeedsRefresh = true;
        UpdateDirtyTitle();
        SetStatus("Có thay đổi reference chưa lưu.", warning: true);
    }

    private bool RowMatchesFilters(TranslationRowViewModel row)
    {
        var status = (StatusFilter.SelectedItem as FilterOption)?.Value;
        if (status is not null && !string.Equals(row.Status, status, StringComparison.Ordinal)) return false;
        var group = (GroupFilter.SelectedItem as FilterOption)?.Value;
        if (group is not null && !string.Equals(row.Group, group, StringComparison.Ordinal)) return false;
        if (OnlyIssuesCheck.IsChecked == true && !row.HasValidationError) return false;
        var query = SearchBox.Text.Trim();
        if (query.Length == 0) return true;
        return Contains(row.Key, query) || Contains(row.Speaker, query) || Contains(row.Group, query)
            || Contains(row.Target, query) || Contains(row.SourceSearchText, query) || Contains(row.Notes, query);
    }

    private static bool Contains(string value, string query) => value.Contains(query, StringComparison.OrdinalIgnoreCase);

    private void ApplyTranslationFilter(string? selectedKey = null)
    {
        var anchorToSelectedKey = selectedKey is not null;
        selectedKey ??= (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
        _filteredRows = _rows.Where(RowMatchesFilters).ToList();
        if (anchorToSelectedKey && selectedKey is not null)
        {
            var selectedIndex = _filteredRows.FindIndex(row => string.Equals(row.Key, selectedKey, StringComparison.Ordinal));
            if (selectedIndex >= 0) _page = selectedIndex / _pageSize;
        }
        var window = PageWindow.Clamp(_page, _filteredRows.Count, _pageSize);
        _page = window.Page;
        var pageRows = _filteredRows.Skip(window.Skip).Take(window.Take).ToList();
        CanonicalGrid.ItemsSource = pageRows;
        FilteredCountText.Text = $"{_filteredRows.Count:N0} dòng";
        PageText.Text = $"Trang {_page + 1} / {window.PageCount}";
        PageRangeText.Text = pageRows.Count == 0
            ? "Không có dòng"
            : $"Dòng {window.Skip + 1:N0}-{window.Skip + pageRows.Count:N0} / {_filteredRows.Count:N0}";
        PrevPageButton.IsEnabled = _page > 0;
        NextPageButton.IsEnabled = _page < window.PageCount - 1;
        NoRowsText.Visibility = pageRows.Count == 0 ? Visibility.Visible : Visibility.Collapsed;

        TranslationRowViewModel? selected = null;
        if (selectedKey is not null) selected = pageRows.FirstOrDefault(row => row.Key == selectedKey);
        selected ??= pageRows.FirstOrDefault();
        if (selected is not null)
        {
            CanonicalGrid.SelectedItem = selected;
            BuildGuidance(selected);
        }
        else
        {
            RevertRowButton.IsEnabled = false;
            UpdateBookmarkControls(null);
        }
        UpdateSummary();
    }

    private void ShowRow(TranslationRowViewModel row)
    {
        if (!RowMatchesFilters(row))
        {
            SearchBox.Text = string.Empty;
            StatusFilter.SelectedIndex = 0;
            GroupFilter.SelectedIndex = 0;
            OnlyIssuesCheck.IsChecked = false;
            _filteredRows = _rows.Where(RowMatchesFilters).ToList();
        }
        var index = _filteredRows.FindIndex(item => item.Key == row.Key);
        if (index < 0) return;
        _page = index / _pageSize;
        ApplyTranslationFilter(row.Key);
    }

    private void UpdateSummary()
    {
        var total = _rows.Count;
        var pending = _rows.Count(row => row.Status == "pending" || row.Target.Length == 0);
        var needsContext = _rows.Count(row => row.Status == "needs_context");
        var issues = _rows.Count(row => row.HasValidationError);
        SummaryText.Text = $"Tổng {total:N0}   Chưa dịch {pending:N0}   Cần ngữ cảnh {needsContext:N0}   Lỗi QA {issues:N0}";
    }

    private void CanonicalGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (CanonicalGrid.SelectedItem is not TranslationRowViewModel row)
        {
            RevertRowButton.IsEnabled = false;
            return;
        }
        BuildGuidance(row);
        UpdateRevertButton(row);
    }

    private void UpdateRevertButton(TranslationRowViewModel row) =>
        RevertRowButton.IsEnabled = _store.IsDirty(row.Model);

    private void BuildGuidance(TranslationRowViewModel row)
    {
        row.DialogueTurns = DialogueContextBuilder.Build(_store.Rows, row.Index)
            .Select(turn => new DialogueTurnViewModel(turn)).ToArray();
        row.MatchingGlossary = BuildGlossary(row);
        row.PronounGuidance = BuildPronouns(row);
        row.RefreshGuidance();
        UpdateBookmarkControls(row);
    }

    private void UpdateBookmarkControls(TranslationRowViewModel? row)
    {
        BookmarksCountText.Text = $"Dấu trang ({_bookmarks.Count:N0})";
        BookmarkPicker.IsEnabled = _bookmarks.Count > 0;
        BookmarkToggleButton.IsEnabled = row is not null;
        var isBookmarked = row is not null && _bookmarks.Any(item =>
            item.TranslationId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)
            && item.Key.Equals(row.Key, StringComparison.Ordinal));
        BookmarkToggleButton.Content = isBookmarked ? "★ Bỏ dấu" : "☆ Đánh dấu";
    }

    private string BuildGlossary(TranslationRowViewModel row)
    {
        if (!_referenceStores.TryGetValue("glossary", out var store)) return "Chưa cấu hình glossary.csv.";
        var headers = store.Headers;
        var termColumn = FindHeader(headers, "term", "source", "source_term");
        var translationColumn = FindHeader(headers, "translation", "vi", "target");
        var typeColumn = FindHeader(headers, "type", "category");
        var contextColumn = FindHeader(headers, "context", "rule", "notes");
        var statusColumn = FindHeader(headers, "status", "state");
        if (termColumn is null || translationColumn is null) return "Glossary thiếu cột term/translation.";
        var haystack = row.SourceSearchText;
        var matches = GlossaryMatcher.Find(store.Rows.Select(item => new GlossaryCandidate(
                item[termColumn],
                item[translationColumn],
                typeColumn is null ? string.Empty : item[typeColumn],
                contextColumn is null ? string.Empty : item[contextColumn])
            {
                Status = statusColumn is null ? string.Empty : item[statusColumn]
            }), haystack)
            .Select(item => $"{item.Term} = {item.Translation}" + (item.Context.Length == 0 ? "" : $" ({item.Context})"))
            .ToArray();
        return matches.Length == 0 ? "Không có thuật ngữ khớp." : string.Join("\n", matches);
    }

    private string BuildPronouns(TranslationRowViewModel row)
    {
        if (row.Speaker.Length == 0) return "Dòng không có người nói.";
        if (!_referenceStores.TryGetValue("pronouns", out var store)) return "Chưa cấu hình pronouns.csv.";
        var speakerColumn = FindHeader(store.Headers, "speaker", "character", "name");
        if (speakerColumn is null) return "Bảng xưng hô thiếu cột speaker.";
        var matches = store.Rows.Where(item => string.Equals(item[speakerColumn], row.Speaker, StringComparison.CurrentCultureIgnoreCase)).Take(8).ToArray();
        if (matches.Length == 0) return $"Chưa có quy tắc xưng hô cho {row.Speaker}.";
        return string.Join("\n", matches.Select(item => string.Join(" | ", store.Headers.Where(header => item[header].Length > 0).Select(header => $"{HeaderLabel(header)}: {item[header]}"))));
    }

    private void ScanConsistencyQa(string? selectedDecisionId = null, bool autoSelectFirst = true)
    {
        if (_store is null) return;
        var referenceData = ConsistencyQaReferenceData.From(
            _referenceStores.GetValueOrDefault("glossary"),
            _referenceStores.GetValueOrDefault("pronouns"));
        var issues = ConsistencyQaAnalyzer.Analyze(_store.Rows, referenceData.Glossary, referenceData.Pronouns);
        _consistencyIssues.Clear();
        foreach (var issue in issues)
            _consistencyIssues.Add(new ConsistencyIssueViewModel(issue, _qaDecisionStore.Resolve(_activeTranslationId, issue)));
        RefreshConsistencyQaSpeakerFilter();
        ApplyConsistencyQaFilter();
        _consistencyNeedsRefresh = false;
        _consistencyHasScanned = true;
        ConsistencyQaTab.Header = $"QA nhất quán ({issues.Count:N0})";
        UpdateConsistencyQaSummary();
        ConsistencyIssueViewModel? selected = null;
        if (selectedDecisionId is not null)
            selected = _consistencyIssueView!.Cast<ConsistencyIssueViewModel>()
                .FirstOrDefault(item => item.DecisionId.Equals(selectedDecisionId, StringComparison.Ordinal));
        else if (autoSelectFirst)
            selected = _consistencyIssueView!.Cast<ConsistencyIssueViewModel>().FirstOrDefault();
        ConsistencyQaGrid.SelectedItem = selected;
        ConsistencyQaGoToButton.IsEnabled = selected is not null;
    }

    private void RefreshConsistencyQaSpeakerFilter()
    {
        var selected = (ConsistencyQaSpeakerFilter.SelectedItem as FilterOption)?.Value;
        _changingConsistencyFilters = true;
        ConsistencyQaSpeakerFilter.ItemsSource = new[] { new FilterOption("Mọi speaker", null) }
            .Concat(_consistencyIssues.Select(item => item.SpeakerValue)
                .Distinct(StringComparer.Ordinal)
                .OrderBy(item => item, StringComparer.OrdinalIgnoreCase)
                .Select(item => new FilterOption(item.Length == 0 ? "(không speaker)" : item, item)))
            .ToArray();
        ConsistencyQaSpeakerFilter.SelectedItem = ConsistencyQaSpeakerFilter.Items.Cast<FilterOption>()
            .FirstOrDefault(item => item.Value == selected) ?? ConsistencyQaSpeakerFilter.Items[0];
        _changingConsistencyFilters = false;
    }

    private void ApplyConsistencyQaFilter()
    {
        if (_consistencyIssueView is null) return;
        var kind = (ConsistencyQaKindFilter.SelectedItem as ComboBoxItem)?.Tag?.ToString();
        var speaker = (ConsistencyQaSpeakerFilter.SelectedItem as FilterOption)?.Value;
        var triage = (ConsistencyQaDecisionFilter.SelectedItem as ComboBoxItem)?.Tag?.ToString();
        _consistencyIssueView.Filter = item => item is ConsistencyIssueViewModel issue
            && (string.IsNullOrEmpty(kind) || issue.KindValue.ToString().Equals(kind, StringComparison.Ordinal))
            && (speaker is null || issue.SpeakerValue.Equals(speaker, StringComparison.Ordinal))
            && (string.IsNullOrEmpty(triage) || issue.TriageStatus.ToString().Equals(triage, StringComparison.Ordinal));
        _consistencyIssueView.Refresh();
        UpdateConsistencyQaSummary();
    }

    private void UpdateConsistencyQaSummary()
    {
        if (_consistencyIssueView is null) return;
        if (_consistencyIssues.Count == 0)
        {
            ConsistencyQaSummaryText.Text = "Không phát hiện cảnh báo trong bảng hiện tại. Đây là bộ gợi ý review, không thay thế validator.";
            return;
        }
        var visible = _consistencyIssueView.Cast<object>().Count();
        ConsistencyQaSummaryText.Text = $"Hiện {visible:N0}/{_consistencyIssues.Count:N0} · "
            + $"chưa phân loại {_consistencyIssues.Count(item => item.TriageStatus == QaTriageStatus.Unreviewed):N0} · "
            + $"cần sửa {_consistencyIssues.Count(item => item.TriageStatus == QaTriageStatus.NeedsFix):N0} · "
            + $"chấp nhận khác biệt {_consistencyIssues.Count(item => item.TriageStatus == QaTriageStatus.AcceptedDifference):N0} · "
            + $"đã xử lý {_consistencyIssues.Count(item => item.TriageStatus == QaTriageStatus.Resolved):N0} · "
            + $"quyết định cũ {_consistencyIssues.Count(item => item.IsDecisionStale):N0}.";
    }


    private static string? FindHeader(IEnumerable<string> headers, params string[] candidates) =>
        candidates.Select(candidate => headers.FirstOrDefault(header => header.Equals(candidate, StringComparison.OrdinalIgnoreCase))).FirstOrDefault(header => header is not null);

    private void SaveCanonical()
    {
        if (_externalConflict || _pendingExternalFileIds.Count > 0)
        {
            SetStatus("Project có file đổi hoặc thiếu bên ngoài. Nạp lại trước khi lưu.", error: true);
            return;
        }
        try
        {
            var key = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
            _store.Save();
            _lastReplaceUndo = null;
            ReplaceUndoButton.IsEnabled = false;
            if (_watchedProjectFiles.TryGetValue($"translation:{_activeTranslationId}", out var watched)) watched.MarkCurrent();
            UpdateDirtyTitle();
            UpdateProjectInfo();
            ApplyTranslationFilter(key);
            if (CanonicalGrid.SelectedItem is TranslationRowViewModel selected) UpdateRevertButton(selected);
            SetStatus("Đã lưu canonical nguyên tử và tạo checkpoint .bientaptay.bak.", success: true);
        }
        catch (Exception ex) when (ex is CanonicalValidationException or StaleCanonicalException or IOException)
        {
            if (ex is StaleCanonicalException)
            {
                _externalConflict = true;
                SaveButton.IsEnabled = false;
            }
            SetStatus(ex.Message, error: true);
            MessageBox.Show(ex.Message, "Không thể lưu", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private bool ConfirmDiscardUnsaved()
    {
        var hasReferenceChanges = _referenceStores.Values.Any(store => store.HasUnsavedChanges);
        if (!_store.HasUnsavedChanges && !hasReferenceChanges) return true;
        return MessageBox.Show("Có thay đổi chưa lưu. Bỏ các thay đổi và nạp lại?", "bientaptay", MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes;
    }

    private bool ReloadProject()
    {
        if (!ConfirmDiscardUnsaved()) return false;
        var key = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
        LoadProject(key, _activeTranslationId);
        return true;
    }

    private void WatchTimer_Tick(object? sender, EventArgs e)
    {
        CheckExternalChanges();
    }

    private void CheckExternalChanges()
    {
        foreach (var file in _watchedProjectFiles.Values.ToArray())
        {
            var isPresent = File.Exists(file.Path);
            if (!isPresent)
            {
                if (!file.WasPresent) continue;
                file.WasPresent = false;
                file.LastWriteTimeUtc = DateTime.MinValue;
                var missingFileHasLocalEdits = file.IsReference
                    ? _referenceStores.Values.Any(store => store.HasUnsavedChanges)
                    : file.LocalId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)
                        && (_store.HasUnsavedChanges || _referenceStores.Values.Any(store => store.HasUnsavedChanges));
                SetExternalDiff(file,
                [new ExternalCanonicalChange(
                    ExternalChangeKind.Removed,
                    "(file)",
                    "(file)",
                    "Đang tồn tại",
                    missingFileHasLocalEdits ? "Có edit local" : "Đang tồn tại",
                    "Không tồn tại",
                    missingFileHasLocalEdits)],
                    blocksSave: true);
                _pendingExternalFileIds.Add(file.FileId);
                _externalConflict |= missingFileHasLocalEdits;
                SaveButton.IsEnabled = false;
                MainTabs.SelectedItem = ExternalDiffTab;
                SetStatus($"File {file.Label} đã bị xóa hoặc chuyển chỗ. Lưu bị khóa.", error: true);
                continue;
            }

            var wasMissing = !file.WasPresent;
            DateTime writeTime;
            try
            {
                writeTime = File.GetLastWriteTimeUtc(file.Path);
                if (file.WasPresent && writeTime == file.LastWriteTimeUtc) continue;
            }
            catch (IOException)
            {
                continue;
            }

            IReadOnlyList<ExternalCanonicalChange> changes;
            bool hasLocalEdits;
            try
            {
                if (file.IsReference)
                {
                    if (!_referenceStores.TryGetValue(file.LocalId, out var referenceStore)) continue;
                    changes = referenceStore.CompareWithDisk();
                    hasLocalEdits = _referenceStores.Values.Any(store => store.HasUnsavedChanges);
                }
                else
                {
                    if (!_translationStores.TryGetValue(file.LocalId, out var translationStore)) continue;
                    changes = translationStore.CompareWithDisk();
                    hasLocalEdits = file.LocalId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)
                        && (_store.HasUnsavedChanges || _referenceStores.Values.Any(store => store.HasUnsavedChanges));
                }
            }
            catch (Exception ex) when (ex is IOException or InvalidDataException or FormatException)
            {
                SetStatus($"Chưa đọc được thay đổi ngoài ở {file.Label}; sẽ thử lại: {ex.Message}", warning: true);
                continue;
            }

            file.WasPresent = true;
            file.LastWriteTimeUtc = writeTime;
            if (wasMissing && changes.Count == 0)
            {
                var restoredChange = new ExternalCanonicalChange(
                    ExternalChangeKind.Modified,
                    "(file)",
                    "(file)",
                    "Không tồn tại",
                    hasLocalEdits ? "Có edit local" : "Không tồn tại",
                    "Đã khôi phục",
                    hasLocalEdits);
                SetExternalDiff(file, [restoredChange], hasLocalEdits);
                if (hasLocalEdits)
                {
                    MainTabs.SelectedItem = ExternalDiffTab;
                    SetStatus($"File {file.Label} đã khôi phục nhưng còn edit local; lưu vẫn bị khóa.", error: true);
                    return;
                }
                _pendingExternalFileIds.Remove(file.FileId);
                if (file.IsReference)
                {
                    ReloadReference(file.LocalId);
                }
                else if (file.LocalId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase))
                {
                    var key = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
                    LoadProject(key, _activeTranslationId);
                }
                else if (_translationStores.TryGetValue(file.LocalId, out var restoredStore))
                {
                    restoredStore.ReloadFromDisk();
                }
                UpdateExternalDiffState();
                SetStatus($"File {file.Label} đã khôi phục nguyên trạng; đã gỡ khóa lưu.", success: true);
                continue;
            }
            if (changes.Count > 0) SetExternalDiff(file, changes, hasLocalEdits);
            if (changes.Count == 0) continue;

            if (file.IsReference)
            {
                if (hasLocalEdits)
                {
                    _pendingExternalFileIds.Add(file.FileId);
                    SaveButton.IsEnabled = false;
                    MainTabs.SelectedItem = ExternalDiffTab;
                    SetStatus($"Reference {file.Label} đã đổi ngoài trong lúc đang sửa. Nạp lại trước khi lưu.", error: true);
                    return;
                }
                _pendingExternalFileIds.Remove(file.FileId);
                ReloadReference(file.LocalId);
                SetStatus($"Reference {file.Label} vừa được cập nhật; đã nạp lại và giữ diff.", success: true);
                return;
            }

            if (file.LocalId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase))
            {
                if (hasLocalEdits)
                {
                    _externalConflict = true;
                    SaveButton.IsEnabled = false;
                    MainTabs.SelectedItem = ExternalDiffTab;
                    SetStatus("Canonical đã đổi bên ngoài trong lúc đang sửa. Lưu bị khóa; diff toàn project đã mở.", error: true);
                    return;
                }
                var key = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
                LoadProject(key, _activeTranslationId);
                SetStatus($"Bảng {file.Label} vừa được cập nhật; đã đồng bộ và giữ diff.", success: true);
                return;
            }

            if (_translationStores.TryGetValue(file.LocalId, out var otherStore))
                otherStore.ReloadFromDisk();
        }
    }

    private void SetExternalDiff(WatchedProjectFile file, IReadOnlyList<ExternalCanonicalChange> changes, bool blocksSave)
    {
        foreach (var old in _externalDiffRows.Where(item => item.FileId.Equals(file.FileId, StringComparison.OrdinalIgnoreCase)).ToArray())
            _externalDiffRows.Remove(old);
        foreach (var change in changes)
        {
            _externalDiffRows.Add(new ExternalChangeViewModel(change with
            {
                FileId = file.FileId,
                FileLabel = file.Label,
                IsReference = file.IsReference,
            }));
        }
        if (blocksSave) _pendingExternalFileIds.Add(file.FileId);
        UpdateExternalDiffState();
    }

    private void UpdateExternalDiffState()
    {
        var conflicts = _externalDiffRows.Count(item => item.IsConflict);
        var files = _externalDiffRows.Select(item => item.FileId).Distinct(StringComparer.OrdinalIgnoreCase).Count();
        ExternalDiffTab.Header = _externalDiffRows.Count == 0
            ? "Thay đổi ngoài"
            : $"Thay đổi ngoài ({_externalDiffRows.Count:N0})";
        ExternalDiffSummaryText.Text = _externalDiffRows.Count == 0
            ? "Chưa ghi nhận thay đổi ngoài trong phiên này."
            : conflicts == 0
                ? $"{_externalDiffRows.Count:N0} thay đổi ở {files:N0} file; không có field đụng edit local."
                : $"{_externalDiffRows.Count:N0} thay đổi ở {files:N0} file; {conflicts:N0} field xung đột với edit local.";
        ExternalDiffClearButton.IsEnabled = _externalDiffRows.Count > 0
            && !_externalConflict && _pendingExternalFileIds.Count == 0;
    }

    private void ClearExternalDiff()
    {
        if (_externalConflict || _pendingExternalFileIds.Count > 0) return;
        _externalDiffRows.Clear();
        UpdateExternalDiffState();
    }

    private void SaveReference(string id, DataGrid grid)
    {
        if (!_referenceStores.TryGetValue(id, out var store)) return;
        if (_externalConflict || _pendingExternalFileIds.Count > 0)
        {
            SetStatus("Project có file đổi hoặc thiếu bên ngoài. Nạp lại trước khi lưu reference.", error: true);
            return;
        }
        grid.CommitEdit(DataGridEditingUnit.Cell, true);
        grid.CommitEdit(DataGridEditingUnit.Row, true);
        try
        {
            store.Save();
            ReloadReference(id);
            _pendingExternalFileIds.Remove($"reference:{id}");
            if (CanonicalGrid.SelectedItem is TranslationRowViewModel selected) BuildGuidance(selected);
            _consistencyNeedsRefresh = true;
            UpdateDirtyTitle();
            UpdateExternalDiffState();
            SetStatus($"Đã lưu {id}.csv nguyên tử.", success: true);
        }
        catch (Exception ex)
        {
            SetStatus(ex.Message, error: true);
            MessageBox.Show(ex.Message, "Không thể lưu", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private void AddReferenceRow(string id, DataGrid grid)
    {
        if (!_referenceStores.TryGetValue(id, out var store) || !_referenceRows.TryGetValue(id, out var rows)) return;
        var row = store.AddRow();
        var viewModel = new ReferenceRowViewModel(row);
        rows.Add(viewModel);
        grid.SelectedItem = viewModel;
        grid.ScrollIntoView(viewModel);
        SetStatus($"Đã thêm dòng {id}; Ctrl+S hoặc nút Lưu để ghi vào CSV.", warning: true);
    }

    private void DeleteReferenceRow(string id, DataGrid grid)
    {
        if (grid.SelectedItem is not ReferenceRowViewModel selected || !_referenceStores.TryGetValue(id, out var store) || !_referenceRows.TryGetValue(id, out var rows)) return;
        if (MessageBox.Show("Xóa dòng đang chọn? Thao tác chỉ ghi xuống đĩa khi bấm Lưu.", "bientaptay", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
        var index = rows.IndexOf(selected);
        store.RemoveAt(index);
        rows.RemoveAt(index);
        SetStatus($"Đã đánh dấu xóa dòng {id}; chưa ghi xuống đĩa.", warning: true);
    }

    private void FilterReference(string id, string query)
    {
        if (!_referenceViews.TryGetValue(id, out var view) || !_referenceStores.TryGetValue(id, out var store)) return;
        var needle = query.Trim();
        view.Filter = item => item is ReferenceRowViewModel row && (needle.Length == 0 || store.Headers.Any(header => Contains(row[header], needle)));
        view.Refresh();
    }

    private void UpdateProjectInfo()
    {
        var builder = new StringBuilder();
        builder.AppendLine($"Dự án: {_projectConfig.ProjectName}");
        builder.AppendLine($"Cấu hình: {_config.ConfigPath}");
        builder.AppendLine($"Bảng đang mở: {_translationFiles.First(item => item.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)).Label}");
        builder.AppendLine($"CSV authoritative: {_config.ResolvedCanonicalPath}");
        builder.AppendLine($"SHA-256 đã nạp: {_store.LoadedHash}");
        builder.AppendLine($"Số dòng: {_store.Rows.Count:N0}");
        builder.AppendLine();
        builder.AppendLine("Toàn bộ bảng dịch:");
        foreach (var file in _translationFiles) builder.AppendLine($"  - {file.Label}: {_projectConfig.Resolve(file.Path)}");
        builder.AppendLine();
        builder.AppendLine("Nguồn hiển thị:");
        foreach (var field in _config.SourceFields) builder.AppendLine($"  - {field.Label}: {field.Column}");
        builder.AppendLine();
        builder.AppendLine("Bảng tham chiếu:");
        foreach (var reference in _config.References) builder.AppendLine($"  - {reference.Label}: {_config.Resolve(reference.Path)}");
        if (_projectConfig.Resources.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine("Tài nguyên liên quan:");
            foreach (var resource in _projectConfig.Resources)
            {
                var path = _projectConfig.Resolve(resource.Path);
                builder.AppendLine($"  - {resource.Label}: {path} [{(File.Exists(path) || Directory.Exists(path) ? "có" : "thiếu")}] ");
            }
        }
        builder.AppendLine();
        builder.AppendLine("Quy tắc lưu:");
        builder.AppendLine("  - Chỉ target, status và notes được sửa trong canonical.");
        builder.AppendLine("  - Toàn bộ dòng trong CSV đang mở phải qua validator; chỉ dòng dirty được normalize status.");
        builder.AppendLine("  - Protected tokens phải khớp trước khi lưu; reference dùng keyColumn và validator riêng.");
        builder.AppendLine("  - Ghi bằng temp + File.Replace và giữ checkpoint .bientaptay.bak.");
        builder.AppendLine("  - Shared writer lock và stale hash guard chặn ghi đè từ tiến trình ngoài.");
        ProjectInfoText.Text = builder.ToString();
    }

    private void SetStatus(string message, bool success = false, bool warning = false, bool error = false)
    {
        StatusMessageText.Text = message;
        StatusMessageText.Foreground = error ? (Brush)FindResource("DangerBrush")
            : success ? (Brush)FindResource("SuccessBrush")
            : warning ? (Brush)FindResource("WarningBrush")
            : (Brush)FindResource("MutedBrush");
    }

    private void UpdateDirtyTitle()
    {
        var dirty = HasUnsavedEdits();
        var title = dirty
            ? $"* bientaptay - {_projectConfig.ProjectName}"
            : $"bientaptay - {_projectConfig.ProjectName}";
        Title = title;
        WindowTitleText.Text = title;
        SaveButton.Content = dirty ? "Lưu canonical *" : "Lưu canonical";
        SaveButton.IsEnabled = !_externalConflict && _pendingExternalFileIds.Count == 0;
    }

    private bool HasUnsavedEdits() =>
        _store.HasUnsavedChanges || _referenceStores.Values.Any(store => store.HasUnsavedChanges);

    private static string HeaderLabel(string header) => header switch
    {
        "term" => "Thuật ngữ gốc",
        "translation" or "vi" => "Bản dịch chỉ định",
        "type" => "Loại",
        "context" => "Quy tắc / ngữ cảnh",
        "status" => "Trạng thái",
        "speaker" => "Người nói",
        "addressee" => "Đối tượng",
        "self_reference" => "Tự xưng",
        "address_form" => "Gọi đối phương",
        "notes" => "Ghi chú",
        "evidence_keys" => "Key bằng chứng",
        "relationship" => "Quan hệ",
        _ => header.Replace('_', ' '),
    };

    private void Save_Click(object sender, RoutedEventArgs e) => SaveCanonical();
    private void Reload_Click(object sender, RoutedEventArgs e) => ReloadProject();
    private void RevertRow_Click(object sender, RoutedEventArgs e)
    {
        if (CanonicalGrid.SelectedItem is not TranslationRowViewModel row || !_store.IsDirty(row.Model)) return;
        _store.Revert(row.Model);
        row.RefreshFromModel();
        BuildGuidance(row);
        _filterTimer.Stop();
        ApplyTranslationFilter(row.Key);
        UpdateDirtyTitle();
        if (CanonicalGrid.SelectedItem is TranslationRowViewModel selected) UpdateRevertButton(selected);
        SetStatus($"Đã hoàn tác {row.Key} về bản vừa lưu; canonical trên đĩa không đổi.", success: true);
    }

    private void BookmarkToggle_Click(object sender, RoutedEventArgs e)
    {
        if (CanonicalGrid.SelectedItem is not TranslationRowViewModel row) return;
        var existing = _bookmarks.FirstOrDefault(item =>
            item.TranslationId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)
            && item.Key.Equals(row.Key, StringComparison.Ordinal));
        if (existing is null)
        {
            var label = _translationFiles.First(item => item.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)).Label;
            _bookmarks.Add(new BookmarkViewModel(_activeTranslationId, label, row.Key));
            SetStatus($"Đã đánh dấu {label} / {row.Key}.", success: true);
        }
        else
        {
            _bookmarks.Remove(existing);
            SetStatus($"Đã bỏ dấu {existing.FileLabel} / {existing.Key}.", success: true);
        }
        UpdateBookmarkControls(row);
        PersistBookmarksNow();
    }

    private void BookmarkPicker_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_changingBookmarkSelection || BookmarkPicker.SelectedItem is not BookmarkViewModel bookmark) return;
        try
        {
            if (!_translationFiles.Any(file => file.Id.Equals(bookmark.TranslationId, StringComparison.OrdinalIgnoreCase)))
            {
                SetStatus($"Dấu trang thuộc bảng không còn trong project: {bookmark.TranslationId}.", warning: true);
                return;
            }
            if (!bookmark.TranslationId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase))
            {
                if (HasUnsavedEdits())
                {
                    SetStatus($"Dấu trang nằm trong {bookmark.FileLabel}. Hãy lưu hoặc hoàn tác edit hiện tại trước khi đổi bảng.", warning: true);
                    return;
                }
                LoadProject(bookmark.Key, bookmark.TranslationId);
            }
            var row = _rows.FirstOrDefault(item => item.Key.Equals(bookmark.Key, StringComparison.Ordinal));
            if (row is null)
            {
                SetStatus($"Exact key bookmark không còn tồn tại: {bookmark.Key}", warning: true);
                return;
            }
            MainTabs.SelectedIndex = 0;
            ShowRow(row);
            CanonicalGrid.Focus();
            SetStatus($"Đã tới dấu trang {bookmark.FileLabel} / {bookmark.Key}.", success: true);
        }
        finally
        {
            _changingBookmarkSelection = true;
            BookmarkPicker.SelectedIndex = -1;
            _changingBookmarkSelection = false;
        }
    }

    private void DialogueTurn_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { DataContext: DialogueTurnViewModel turn }) return;
        var row = _rows.FirstOrDefault(item => item.Key.Equals(turn.PrimaryKey, StringComparison.Ordinal));
        if (row is null)
        {
            SetStatus($"Không tìm thấy exact key context: {turn.PrimaryKey}", warning: true);
            return;
        }
        ShowRow(row);
        CanonicalGrid.Focus();
        SetStatus($"Đã tới lượt hội thoại {turn.PrimaryKey}.", success: true);
    }

    private void PersistBookmarksNow()
    {
        try
        {
            PersistSession();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            SetStatus($"Bookmark chỉ còn trong RAM vì không ghi được session.json: {ex.Message}", warning: true);
        }
    }

    private void FindReplaceButton_Click(object sender, RoutedEventArgs e) => OpenFindReplace();
    private void FindReplaceClose_Click(object sender, RoutedEventArgs e) => FindReplaceOverlay.Visibility = Visibility.Collapsed;
    private void FindReplacePreview_Click(object sender, RoutedEventArgs e) => BuildReplacePreview();
    private void FindReplaceNext_Click(object sender, RoutedEventArgs e) => FindNextReplacement();
    private void FindReplaceApply_Click(object sender, RoutedEventArgs e) => ApplyReplacementPlan();
    private void ReplaceUndo_Click(object sender, RoutedEventArgs e) => UndoLastReplacementBatch();

    private void OpenFindReplace()
    {
        ProjectSearchOverlay.Visibility = Visibility.Collapsed;
        FindReplaceOverlay.Visibility = Visibility.Visible;
        InvalidateReplacePreview();
        ReplaceUndoButton.IsEnabled = _lastReplaceUndo is not null;
        Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() =>
        {
            FindReplaceFindTextBox.Focus();
            FindReplaceFindTextBox.SelectAll();
        }));
    }

    private IEnumerable<TranslationRowViewModel> ReplaceScope()
    {
        if (FindReplaceFilteredOnlyCheck.IsChecked != true) return _rows;
        _filterTimer.Stop();
        ApplyTranslationFilter((CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key);
        return _filteredRows;
    }

    private bool BuildReplacePreview()
    {
        try
        {
            _replacePlan = TranslationReplacePlanner.Create(
                _store,
                ReplaceScope().Select(row => row.Model),
                FindReplaceFindTextBox.Text,
                FindReplaceReplacementTextBox.Text,
                FindReplaceMatchCaseCheck.IsChecked == true);
            _replacePreviewRows.Clear();
            foreach (var item in _replacePlan.Items) _replacePreviewRows.Add(new ReplacePreviewRowViewModel(item));
            var errors = _replacePlan.Items.Count(item => item.ValidationMessage.Length > 0);
            ReplacePreviewSummaryText.Text = _replacePlan.Items.Count == 0
                ? "Không có kết quả trong phạm vi đã chọn."
                : $"{_replacePlan.Items.Count:N0} dòng · {_replacePlan.TotalOccurrences:N0} lần thay · {errors:N0} lỗi QA";
            ReplaceApplyButton.IsEnabled = _replacePlan.CanApply;
            return true;
        }
        catch (ArgumentException ex)
        {
            _replacePlan = null;
            _replacePreviewRows.Clear();
            ReplacePreviewSummaryText.Text = ex.Message;
            ReplaceApplyButton.IsEnabled = false;
            FindReplaceFindTextBox.Focus();
            return false;
        }
    }

    private void InvalidateReplacePreview()
    {
        _replacePlan = null;
        _replacePreviewRows.Clear();
        ReplacePreviewSummaryText.Text = "Bấm Xem trước để kiểm số dòng và lỗi QA trước khi thay.";
        ReplaceApplyButton.IsEnabled = false;
    }

    private void FindReplaceInput_Changed(object sender, TextChangedEventArgs e) => InvalidateReplacePreview();
    private void FindReplaceOption_Changed(object sender, RoutedEventArgs e) => InvalidateReplacePreview();

    private void FindNextReplacement()
    {
        var find = FindReplaceFindTextBox.Text;
        if (find.Length == 0)
        {
            ReplacePreviewSummaryText.Text = "Chuỗi cần tìm không được trống.";
            return;
        }
        var scope = ReplaceScope().ToList();
        var current = CanonicalGrid.SelectedItem as TranslationRowViewModel;
        var start = current is null ? -1 : scope.IndexOf(current);
        var comparison = FindReplaceMatchCaseCheck.IsChecked == true ? StringComparison.Ordinal : StringComparison.OrdinalIgnoreCase;
        for (var offset = 1; offset <= scope.Count; offset++)
        {
            var row = scope[(start + offset + scope.Count) % scope.Count];
            if (row.Target.IndexOf(find, comparison) < 0) continue;
            FindReplaceOverlay.Visibility = Visibility.Collapsed;
            ShowRow(row);
            Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() => TargetEditor.Focus()));
            SetStatus($"Đã tới kết quả trong {row.Key}.", success: true);
            return;
        }
        ReplacePreviewSummaryText.Text = "Không có kết quả trong phạm vi đã chọn.";
    }

    private void ApplyReplacementPlan()
    {
        if (!BuildReplacePreview() || _replacePlan is null || !_replacePlan.CanApply) return;
        if (MessageBox.Show(
                $"Áp dụng {_replacePlan.TotalOccurrences:N0} lần thay trên {_replacePlan.Items.Count:N0} dòng?\nThay đổi chỉ ở RAM cho tới khi bấm Lưu canonical.",
                "Tìm/thay bản dịch",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
        try
        {
            var selectedKey = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
            _lastReplaceUndo = TranslationReplacePlanner.Apply(_replacePlan);
            foreach (var item in _replacePlan.Items) _rows[item.Row.Index].RefreshFromModel();
            var rowCount = _replacePlan.Items.Count;
            var occurrenceCount = _replacePlan.TotalOccurrences;
            FindReplaceOverlay.Visibility = Visibility.Collapsed;
            UpdateSummary();
            ApplyTranslationFilter(selectedKey);
            UpdateDirtyTitle();
            SetStatus($"Đã thay {occurrenceCount:N0} lần trên {rowCount:N0} dòng; chưa ghi xuống CSV.", warning: true);
        }
        catch (Exception ex) when (ex is CanonicalValidationException or InvalidOperationException)
        {
            ReplacePreviewSummaryText.Text = ex.Message;
            ReplaceApplyButton.IsEnabled = false;
        }
    }

    private void UndoLastReplacementBatch()
    {
        if (_lastReplaceUndo is null) return;
        try
        {
            var selectedKey = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
            _lastReplaceUndo.Undo();
            foreach (var item in _lastReplaceUndo.Items) _rows[item.Row.Index].RefreshFromModel();
            var rowCount = _lastReplaceUndo.Items.Count;
            _lastReplaceUndo = null;
            ReplaceUndoButton.IsEnabled = false;
            UpdateSummary();
            ApplyTranslationFilter(selectedKey);
            UpdateDirtyTitle();
            SetStatus($"Đã hoàn tác batch thay trên {rowCount:N0} dòng; chưa ghi xuống CSV.", success: true);
        }
        catch (InvalidOperationException ex)
        {
            _lastReplaceUndo = null;
            ReplaceUndoButton.IsEnabled = false;
            SetStatus(ex.Message, warning: true);
        }
    }

    private void ExternalDiffGoTo_Click(object sender, RoutedEventArgs e)
    {
        if (ExternalDiffGrid.SelectedItem is not ExternalChangeViewModel change) return;
        if (change.FileId.StartsWith("translation:", StringComparison.OrdinalIgnoreCase))
        {
            var translationId = change.FileId["translation:".Length..];
            if (!translationId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase))
            {
                if (HasUnsavedEdits())
                {
                    SetStatus("Hãy lưu hoặc nạp lại thay đổi hiện tại trước khi mở diff bảng khác.", warning: true);
                    return;
                }
                LoadProject(translationId: translationId);
            }
            var row = _rows.FirstOrDefault(item => string.Equals(item.Key, change.Key, StringComparison.Ordinal));
            if (row is null)
            {
                SetStatus($"{change.Key} đã bị xóa khỏi file ngoài.", warning: true);
                return;
            }
            MainTabs.SelectedIndex = 0;
            ShowRow(row);
            return;
        }

        if (!change.FileId.StartsWith("reference:", StringComparison.OrdinalIgnoreCase)) return;
        var referenceId = change.FileId["reference:".Length..];
        var grid = ReferenceGrid(referenceId);
        if (grid is not null)
        {
            MainTabs.SelectedIndex = referenceId.Equals("glossary", StringComparison.OrdinalIgnoreCase) ? 1 : 2;
            if (_referenceStores.TryGetValue(referenceId, out var store)
                && _referenceRows.TryGetValue(referenceId, out var rows)
                && store.Headers.Count > 0 && change.Key is not "(file)")
            {
                var keyColumn = store.KeyColumn;
                var row = rows.FirstOrDefault(item => string.Equals(item[keyColumn], change.Key, StringComparison.Ordinal));
                if (row is not null)
                {
                    grid.SelectedItem = row;
                    grid.ScrollIntoView(row);
                    grid.Focus();
                }
            }
        }
        SetStatus($"Đã mở tab reference {change.FileLabel}; xem exact key {change.Key} trong diff.", success: true);
    }

    private void ExternalDiffReload_Click(object sender, RoutedEventArgs e)
    {
        if (ReloadProject()) SetStatus("Đã nạp file ngoài; diff vẫn được giữ để đối chiếu.", success: true);
    }

    private void ExternalDiffClear_Click(object sender, RoutedEventArgs e) => ClearExternalDiff();

    private void MainTabs_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!ReferenceEquals(e.Source, MainTabs) || !ReferenceEquals(MainTabs.SelectedItem, ConsistencyQaTab)) return;
        if (_referencesLoaded && _consistencyNeedsRefresh) ScanConsistencyQa();
    }

    private void ConsistencyQaScan_Click(object sender, RoutedEventArgs e) => ScanConsistencyQa();

    private void ConsistencyQaExportReport_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new SaveFileDialog
        {
            Title = "Xuất báo cáo QA",
            Filter = "Báo cáo QA JSON (*.json)|*.json|Báo cáo QA CSV (*.csv)|*.csv",
            DefaultExt = ".json",
            AddExtension = true,
            FileName = "qa-report"
        };
        if (dialog.ShowDialog(this) != true) return;
        ExportQaReportWithStatus(dialog.FileName);
    }

    private void ExportQaReportWithStatus(string destination)
    {
        try
        {
            ExportQaReportTo(destination);
            SetStatus("Đã xuất báo cáo QA chỉ đọc; canonical không đổi.", success: true);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException or InvalidOperationException)
        {
            DiagnosticsLog.TryWriteError(_projectConfig, "qa_report_export", ex.Message, ex);
            SetStatus($"Không xuất được báo cáo QA: {ex.Message}", error: true);
        }
    }

    private void ExportQaReportTo(string destination)
    {
        var selectedId = (ConsistencyQaGrid.SelectedItem as ConsistencyIssueViewModel)?.DecisionId;
        if (!_consistencyHasScanned) ScanConsistencyQa(selectedId);
        var file = _translationFiles.First(item => item.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase));
        var canonicalPath = _config.ResolvedCanonicalPath;
        var report = QaReportBuilder.Build(
            _projectConfig.ProjectName,
            _activeTranslationId,
            file.Label,
            canonicalPath,
            Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(canonicalPath))).ToLowerInvariant(),
            _store.Rows.Count,
            _consistencyIssues.Select(item => item.Issue).ToArray(),
            _qaDecisionStore);
        QaReportBuilder.Write(destination, report, _projectConfig);
        if (selectedId is not null)
        {
            ConsistencyQaGrid.SelectedItem = _consistencyIssueView!.Cast<ConsistencyIssueViewModel>()
                .FirstOrDefault(item => item.DecisionId.Equals(selectedId, StringComparison.Ordinal));
        }
    }

    private void ConsistencyQaFilter_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_changingConsistencyFilters) return;
        ApplyConsistencyQaFilter();
    }

    private void ConsistencyQaGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        var issue = ConsistencyQaGrid.SelectedItem as ConsistencyIssueViewModel;
        ConsistencyQaGoToButton.IsEnabled = issue is not null;
        ConsistencyQaSaveDecisionButton.IsEnabled = issue is not null && _qaDecisionStore.CanMutate;
        ConsistencyQaSaveNextButton.IsEnabled = issue is not null && _qaDecisionStore.CanMutate;
        if (issue is null)
        {
            _consistencyRelatedRows.Clear();
            ConsistencyQaTriageCombo.SelectedIndex = 0;
            ConsistencyQaDecisionNoteBox.Text = string.Empty;
            ConsistencyQaStaleText.Visibility = Visibility.Collapsed;
            UpdateConsistencyRelatedButtons();
            return;
        }
        ConsistencyQaTriageCombo.SelectedItem = ConsistencyQaTriageCombo.Items.OfType<ComboBoxItem>()
            .FirstOrDefault(item => item.Tag?.ToString() == issue.TriageStatus.ToString())
            ?? ConsistencyQaTriageCombo.Items[0];
        ConsistencyQaDecisionNoteBox.Text = issue.DecisionNote;
        ConsistencyQaStaleText.Visibility = issue.IsDecisionStale ? Visibility.Visible : Visibility.Collapsed;
        PopulateConsistencyRelatedRows(issue);
    }

    private void PopulateConsistencyRelatedRows(ConsistencyIssueViewModel issue)
    {
        _consistencyRelatedRows.Clear();
        foreach (var key in issue.RelatedKeyList)
        {
            var row = _rows.FirstOrDefault(item => item.Key.Equals(key, StringComparison.Ordinal));
            if (row is not null) _consistencyRelatedRows.Add(new QaRelatedRowViewModel(row, key.Equals(issue.Key, StringComparison.Ordinal)));
        }
        ConsistencyQaRelatedGrid.SelectedItem = _consistencyRelatedRows.FirstOrDefault(item => item.Key.Equals(issue.Key, StringComparison.Ordinal))
            ?? _consistencyRelatedRows.FirstOrDefault();
        UpdateConsistencyRelatedButtons();
    }

    private void ConsistencyQaRelatedGrid_SelectionChanged(object sender, SelectionChangedEventArgs e) => UpdateConsistencyRelatedButtons();

    private void UpdateConsistencyRelatedButtons()
    {
        var selected = ConsistencyQaRelatedGrid.SelectedItem is QaRelatedRowViewModel;
        ConsistencyQaRelatedPreviousButton.IsEnabled = selected && _consistencyRelatedRows.Count > 1;
        ConsistencyQaRelatedNextButton.IsEnabled = selected && _consistencyRelatedRows.Count > 1;
        ConsistencyQaRelatedGoToButton.IsEnabled = selected;
    }

    private void ConsistencyQaRelatedPrevious_Click(object sender, RoutedEventArgs e) => ShiftConsistencyRelated(-1);
    private void ConsistencyQaRelatedNext_Click(object sender, RoutedEventArgs e) => ShiftConsistencyRelated(1);

    private void ShiftConsistencyRelated(int delta)
    {
        if (_consistencyRelatedRows.Count == 0) return;
        var current = Math.Max(0, ConsistencyQaRelatedGrid.SelectedIndex);
        var index = (current + delta + _consistencyRelatedRows.Count) % _consistencyRelatedRows.Count;
        ConsistencyQaRelatedGrid.SelectedIndex = index;
        ConsistencyQaRelatedGrid.ScrollIntoView(_consistencyRelatedRows[index]);
    }

    private void ConsistencyQaRelatedGoTo_Click(object sender, RoutedEventArgs e)
    {
        if (ConsistencyQaRelatedGrid.SelectedItem is not QaRelatedRowViewModel related) return;
        MainTabs.SelectedIndex = 0;
        ShowRow(related.Row);
        CanonicalGrid.Focus();
        SetStatus($"Đã tới related exact key {related.Key}.", success: true);
    }

    private void ConsistencyQaCopyContext_Click(object sender, RoutedEventArgs e) => CopyQaContextWithStatus(Clipboard.SetText);

    private void CopyQaContextWithStatus(Action<string> setter)
    {
        if (ConsistencyQaGrid.SelectedItem is not ConsistencyIssueViewModel issue) return;
        try
        {
            var rows = issue.RelatedKeyList.Select(key =>
            {
                var row = _rows.Single(item => item.Key.Equals(key, StringComparison.Ordinal));
                return new QaContextPacketRow(
                    row.Key,
                    row.Speaker,
                    row.Model.Sources.Select(source => new QaContextSource(source.Label, source.Value)).ToArray(),
                    row.Target,
                    BuildGlossary(row),
                    BuildPronouns(row));
            }).ToArray();
            var file = _translationFiles.First(item => item.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase));
            var packet = QaContextPacketBuilder.Build(_projectConfig.ProjectName, _activeTranslationId, file.Label, issue.Issue, rows);
            ClipboardText.SetWithRetry(packet, setter, Thread.Sleep);
            SetStatus($"Đã sao chép context packet cho {rows.Length:N0} exact key; không tạo file phụ.", success: true);
        }
        catch (Exception ex) when (ex is ExternalException or InvalidOperationException or ArgumentException)
        {
            DiagnosticsLog.TryWriteError(_projectConfig, "clipboard_copy", ex.Message, ex);
            SetStatus($"Không sao chép được context packet: {ex.Message}", error: true);
        }
    }

    private void ConsistencyQaSaveDecision_Click(object sender, RoutedEventArgs e) => SaveQaDecision(advance: false);

    private void ConsistencyQaSaveNext_Click(object sender, RoutedEventArgs e) => SaveQaDecision(advance: true);

    private void SaveQaDecision(bool advance)
    {
        if (ConsistencyQaGrid.SelectedItem is not ConsistencyIssueViewModel issue
            || ConsistencyQaTriageCombo.SelectedItem is not ComboBoxItem option
            || !Enum.TryParse<QaTriageStatus>(option.Tag?.ToString(), out var status)) return;
        if (!_qaDecisionStore.CanMutate)
        {
            DiagnosticsLog.TryWriteError(
                _projectConfig,
                "qa_decision_save",
                _qaDecisionStore.UnavailableReason,
                new InvalidOperationException(_qaDecisionStore.UnavailableReason));
            SetStatus(_qaDecisionStore.UnavailableReason, error: true);
            return;
        }
        var visible = _consistencyIssueView?.Cast<ConsistencyIssueViewModel>().ToList() ?? [];
        var index = visible.FindIndex(item => item.DecisionId.Equals(issue.DecisionId, StringComparison.Ordinal));
        var savedId = issue.DecisionId;
        var savedKey = issue.Key;
        try
        {
            _qaDecisionStore.Set(_activeTranslationId, issue.Issue, status, ConsistencyQaDecisionNoteBox.Text, DateTimeOffset.UtcNow);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException or InvalidOperationException)
        {
            DiagnosticsLog.TryWriteError(_projectConfig, "qa_decision_save", ex.Message, ex);
            SetStatus($"Không lưu được quyết định QA: {ex.Message}", error: true);
            return;
        }

        if (!advance)
        {
            ScanConsistencyQa(savedId);
            SetStatus(status == QaTriageStatus.Unreviewed
                ? $"Đã xóa quyết định QA cho {savedKey}; canonical không đổi."
                : $"Đã lưu quyết định QA cho {savedKey}; canonical không đổi.", success: true);
            return;
        }

        ScanConsistencyQa(autoSelectFirst: false);
        var remaining = _consistencyIssueView?.Cast<ConsistencyIssueViewModel>().ToList() ?? [];
        if (remaining.Count == 0)
        {
            ConsistencyQaGrid.SelectedItem = null;
            SetStatus("Đã xong hàng đợi QA hiện tại.");
            return;
        }

        ConsistencyIssueViewModel? next = null;
        if (index >= 0)
        {
            for (var step = 1; step <= visible.Count; step++)
            {
                var candidateId = visible[(index + step) % visible.Count].DecisionId;
                next = remaining.FirstOrDefault(item => item.DecisionId.Equals(candidateId, StringComparison.Ordinal));
                if (next is not null) break;
            }
        }
        ConsistencyQaGrid.SelectedItem = next ?? remaining[0];
        SetStatus($"Đã lưu quyết định QA cho {savedKey}; đã tới cảnh báo kế tiếp.", success: true);
    }

    private void ConsistencyQaGoTo_Click(object sender, RoutedEventArgs e)
    {
        if (ConsistencyQaGrid.SelectedItem is not ConsistencyIssueViewModel issue) return;
        var row = _rows.FirstOrDefault(item => item.Key.Equals(issue.Key, StringComparison.Ordinal));
        if (row is null)
        {
            SetStatus($"Không tìm thấy exact key QA: {issue.Key}", warning: true);
            return;
        }
        MainTabs.SelectedIndex = 0;
        ShowRow(row);
        CanonicalGrid.Focus();
        SetStatus($"Đã tới exact key QA {issue.Key}.", success: true);
    }

    private static string QaDecisionPath(string configPath) =>
        Path.Combine(Path.GetDirectoryName(configPath) ?? ".", "qa-decisions.json");

    private void DatasetFilter_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_changingDataset || DatasetFilter.SelectedItem is not TranslationFileConfig selected
            || selected.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)) return;
        if (_store.HasUnsavedChanges || _referenceStores.Values.Any(store => store.HasUnsavedChanges))
        {
            _changingDataset = true;
            DatasetFilter.SelectedItem = _translationFiles.First(item => item.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase));
            _changingDataset = false;
            SetStatus("Hãy lưu hoặc nạp lại thay đổi hiện tại trước khi đổi bảng dịch.", warning: true);
            return;
        }
        LoadProject(translationId: selected.Id);
    }
    private void TranslationFilter_Changed(object sender, RoutedEventArgs e)
    {
        if (_restoringSession) return;
        _page = 0;
        _filterTimer.Stop();
        _filterTimer.Start();
    }
    private void TranslationFilter_Changed(object sender, TextChangedEventArgs e)
    {
        if (_restoringSession) return;
        _page = 0;
        _filterTimer.Stop();
        _filterTimer.Start();
    }
    private void TranslationFilter_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_restoringSession) return;
        _page = 0;
        _filterTimer.Stop();
        _filterTimer.Start();
    }

    private void RowsPerPage_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_changingPageSize || _store is null || RowsPerPageCombo.SelectedItem is not ComboBoxItem item
            || !int.TryParse(item.Tag?.ToString(), out var requestedSize)) return;
        var firstVisibleRow = _page * _pageSize;
        _pageSize = PageWindow.NormalizePageSize(requestedSize);
        _page = firstVisibleRow / _pageSize;
        ApplyTranslationFilter();
    }

    private void SetPageSize(int requestedSize)
    {
        _pageSize = PageWindow.NormalizePageSize(requestedSize);
        _changingPageSize = true;
        RowsPerPageCombo.SelectedItem = RowsPerPageCombo.Items.OfType<ComboBoxItem>()
            .FirstOrDefault(item => string.Equals(item.Tag?.ToString(), _pageSize.ToString(), StringComparison.Ordinal));
        _changingPageSize = false;
    }

    private void FontScale_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_changingFontScale || FontScaleCombo.SelectedItem is not ComboBoxItem item
            || !int.TryParse(item.Tag?.ToString(), out var percent)) return;
        SetFontScale(percent / 100d);
        SetStatus($"Cỡ chữ {percent}%.", success: true);
    }

    private void SetFontScale(double requested)
    {
        var allowed = new[] { 0.9, 1.0, 1.15, 1.3 };
        _fontScale = allowed.Any(value => Math.Abs(value - requested) < 0.001) ? requested : 1;
        FontSize = 13 * _fontScale;
        _changingFontScale = true;
        FontScaleCombo.SelectedItem = FontScaleCombo.Items.OfType<ComboBoxItem>()
            .FirstOrDefault(item => int.TryParse(item.Tag?.ToString(), out var percent)
                && Math.Abs(percent / 100d - _fontScale) < 0.001);
        _changingFontScale = false;
    }

    private void ChangeFontScale(int delta)
    {
        var scales = new[] { 0.9, 1.0, 1.15, 1.3 };
        var index = Array.FindIndex(scales, value => Math.Abs(value - _fontScale) < 0.001);
        SetFontScale(scales[Math.Clamp(index + delta, 0, scales.Length - 1)]);
    }

    private void ApplyLayoutSession()
    {
        var ratio = _session?.ListPaneRatio ?? 0.55;
        if (!double.IsFinite(ratio) || ratio < 0.3 || ratio > 0.75) ratio = 0.55;
        ListPaneColumn.Width = new GridLength(ratio, GridUnitType.Star);
        EditorPaneColumn.Width = new GridLength(1 - ratio, GridUnitType.Star);
        ApplySavedColumnWidths(CanonicalGrid, "canonical", 3);
    }

    private void CaptureLayoutState(SessionState session)
    {
        var total = ListPaneColumn.ActualWidth + EditorPaneColumn.ActualWidth;
        if (total > 0)
        {
            var ratio = ListPaneColumn.ActualWidth / total;
            if (double.IsFinite(ratio) && ratio is >= 0.3 and <= 0.75) session.ListPaneRatio = ratio;
        }
        CaptureGridColumnWidths(session, CanonicalGrid, "canonical", 3);
        foreach (var reference in _config?.References ?? [])
        {
            var grid = ReferenceGrid(reference.Id);
            if (grid is not null) CaptureGridColumnWidths(session, grid, $"reference:{reference.Id}");
        }
    }

    private void ApplySavedColumnWidths(DataGrid grid, string scope, int maxColumns = int.MaxValue)
    {
        var widths = _session?.ColumnWidths;
        if (widths is null) return;
        for (var index = 0; index < Math.Min(grid.Columns.Count, maxColumns); index++)
        {
            var key = ColumnWidthKey(scope, grid.Columns[index], index);
            if (widths.TryGetValue(key, out var width) && double.IsFinite(width) && width is >= 60 and <= 1200)
                grid.Columns[index].Width = new DataGridLength(width);
        }
    }

    private static void CaptureGridColumnWidths(SessionState session, DataGrid grid, string scope, int maxColumns = int.MaxValue)
    {
        session.ColumnWidths ??= new Dictionary<string, double>(StringComparer.Ordinal);
        for (var index = 0; index < Math.Min(grid.Columns.Count, maxColumns); index++)
        {
            var width = grid.Columns[index].ActualWidth;
            if (!double.IsFinite(width) || width <= 0) continue;
            session.ColumnWidths[ColumnWidthKey(scope, grid.Columns[index], index)] = Math.Clamp(width, 60, 1200);
        }
    }

    private static string ColumnWidthKey(string scope, DataGridColumn column, int index) =>
        $"{scope}:{(column.SortMemberPath.Length > 0 ? column.SortMemberPath : index.ToString())}";

    private DataGrid? ReferenceGrid(string id) => id.ToLowerInvariant() switch
    {
        "glossary" => GlossaryGrid,
        "pronouns" => PronounsGrid,
        _ => null,
    };

    private void ProjectSearchButton_Click(object sender, RoutedEventArgs e) => OpenProjectSearch();
    private void ProjectSearchClose_Click(object sender, RoutedEventArgs e) => ProjectSearchOverlay.Visibility = Visibility.Collapsed;
    private void ProjectSearchRun_Click(object sender, RoutedEventArgs e) => RunProjectSearch();
    private void ProjectSearchGoTo_Click(object sender, RoutedEventArgs e) => GoToProjectSearchResult();
    private void ProjectSearchGrid_MouseDoubleClick(object sender, MouseButtonEventArgs e) => GoToProjectSearchResult();
    private void ProjectSearchGrid_SelectionChanged(object sender, SelectionChangedEventArgs e) =>
        ProjectSearchGoToButton.IsEnabled = ProjectSearchGrid.SelectedItem is TranslationSearchResultViewModel;

    private void OpenProjectSearch()
    {
        FindReplaceOverlay.Visibility = Visibility.Collapsed;
        ProjectSearchOverlay.Visibility = Visibility.Visible;
        if (SearchBox.Text.Trim().Length > 0)
        {
            ProjectSearchInput.Text = SearchBox.Text;
            RunProjectSearch();
        }
        Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() =>
        {
            ProjectSearchInput.Focus();
            ProjectSearchInput.SelectAll();
        }));
    }

    private void RunProjectSearch()
    {
        var query = ProjectSearchInput.Text.Trim();
        _projectSearchRows.Clear();
        ProjectSearchGoToButton.IsEnabled = false;
        if (query.Length == 0)
        {
            ProjectSearchSummaryText.Text = "Nhập từ khóa cần tìm trong mọi bảng dịch.";
            return;
        }

        var datasets = _translationFiles.Select(file => new TranslationSearchDataset(
            file.Id,
            file.Label,
            _translationStores[file.Id].Rows));
        var results = TranslationProjectSearch.Find(datasets, query);
        foreach (var result in results) _projectSearchRows.Add(new TranslationSearchResultViewModel(result));
        ProjectSearchSummaryText.Text = results.Count == TranslationProjectSearch.DefaultLimit
            ? $"Hiện tối đa {results.Count:N0} kết quả; hãy thu hẹp từ khóa."
            : $"{results.Count:N0} kết quả trong {_translationFiles.Count:N0} bảng dịch.";
        if (_projectSearchRows.Count > 0) ProjectSearchGrid.SelectedIndex = 0;
    }

    private void ProjectSearchInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            RunProjectSearch();
            e.Handled = true;
        }
        else if (e.Key == Key.Escape)
        {
            ProjectSearchOverlay.Visibility = Visibility.Collapsed;
            e.Handled = true;
        }
    }

    private void GoToProjectSearchResult()
    {
        if (ProjectSearchGrid.SelectedItem is not TranslationSearchResultViewModel result) return;
        if (!result.FileId.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase))
        {
            if (HasUnsavedEdits())
            {
                ProjectSearchSummaryText.Text = $"Kết quả nằm trong {result.FileLabel}. Hãy lưu hoặc hoàn tác edit hiện tại trước khi đổi bảng.";
                return;
            }
            LoadProject(result.Key, result.FileId);
        }

        var row = _rows.FirstOrDefault(item => item.Key.Equals(result.Key, StringComparison.Ordinal));
        if (row is null)
        {
            ProjectSearchSummaryText.Text = $"Kết quả {result.Key} đã stale; hãy tìm lại.";
            return;
        }
        ProjectSearchOverlay.Visibility = Visibility.Collapsed;
        MainTabs.SelectedIndex = 0;
        ShowRow(row);
        CanonicalGrid.Focus();
        SetStatus($"Đã tới {result.FileLabel} / {result.Key}.", success: true);
    }

    private void GoToKeyButton_Click(object sender, RoutedEventArgs e) => OpenGoToKey();
    private void GoToKeyConfirm_Click(object sender, RoutedEventArgs e) => GoToExactKey();

    private void OpenGoToKey()
    {
        GoToKeyInput.Text = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key ?? string.Empty;
        GoToKeyPopup.IsOpen = true;
        Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() =>
        {
            GoToKeyInput.Focus();
            GoToKeyInput.SelectAll();
        }));
    }

    private void GoToKeyInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            GoToExactKey();
            e.Handled = true;
        }
        else if (e.Key == Key.Escape)
        {
            GoToKeyPopup.IsOpen = false;
            e.Handled = true;
        }
    }

    private void GoToExactKey()
    {
        var key = GoToKeyInput.Text;
        if (key.Length == 0)
        {
            SetStatus("Nhập full canonical key cần tới.", error: true);
            return;
        }

        var currentRow = _rows.FirstOrDefault(row => string.Equals(row.Key, key, StringComparison.Ordinal));
        if (currentRow is not null)
        {
            GoToKeyPopup.IsOpen = false;
            MainTabs.SelectedIndex = 0;
            ShowRow(currentRow);
            CanonicalGrid.Focus();
            SetStatus($"Đã tới exact key {key}.", success: true);
            return;
        }

        try
        {
            var matches = new List<TranslationFileConfig>();
            foreach (var file in _translationFiles.Where(file => !file.Id.Equals(_activeTranslationId, StringComparison.OrdinalIgnoreCase)))
            {
                var store = CanonicalStore.Open(_projectConfig.ForTranslationFile(file));
                if (store.Rows.Any(row => string.Equals(row.Key, key, StringComparison.Ordinal))) matches.Add(file);
            }
            if (matches.Count == 0)
            {
                SetStatus($"Không tìm thấy exact key: {key}", error: true);
                GoToKeyInput.Focus();
                GoToKeyInput.SelectAll();
                return;
            }
            if (matches.Count > 1)
            {
                SetStatus($"Key xuất hiện ở nhiều bảng: {string.Join(", ", matches.Select(file => file.Label))}.", error: true);
                return;
            }
            if (HasUnsavedEdits())
            {
                SetStatus($"Key nằm trong {matches[0].Label}. Hãy lưu hoặc hoàn tác edit hiện tại trước khi đổi bảng.", warning: true);
                return;
            }
            GoToKeyPopup.IsOpen = false;
            MainTabs.SelectedIndex = 0;
            LoadProject(key, matches[0].Id);
            CanonicalGrid.Focus();
            SetStatus($"Đã tới exact key {key} trong {matches[0].Label}.", success: true);
        }
        catch (Exception ex) when (ex is IOException or InvalidDataException)
        {
            SetStatus($"Không thể tìm key: {ex.Message}", error: true);
        }
    }

    private void PrevPage_Click(object sender, RoutedEventArgs e) => ChangePage(-1);
    private void NextPage_Click(object sender, RoutedEventArgs e) => ChangePage(1);
    private void PageJumpButton_Click(object sender, RoutedEventArgs e)
    {
        PageJumpInput.Text = (_page + 1).ToString();
        PageJumpPopup.IsOpen = true;
        Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() =>
        {
            PageJumpInput.Focus();
            PageJumpInput.SelectAll();
        }));
    }

    private void PageJumpConfirm_Click(object sender, RoutedEventArgs e) => JumpToRequestedPage();

    private void PageJumpInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            JumpToRequestedPage();
            e.Handled = true;
        }
        else if (e.Key == Key.Escape)
        {
            PageJumpPopup.IsOpen = false;
            e.Handled = true;
        }
    }

    private void JumpToRequestedPage()
    {
        var window = PageWindow.Clamp(_page, _filteredRows.Count, _pageSize);
        if (!int.TryParse(PageJumpInput.Text, out var requestedPage) || requestedPage < 1 || requestedPage > window.PageCount)
        {
            SetStatus($"Nhập trang từ 1 đến {window.PageCount:N0}.", error: true);
            PageJumpInput.Focus();
            PageJumpInput.SelectAll();
            return;
        }
        _page = requestedPage - 1;
        PageJumpPopup.IsOpen = false;
        ApplyTranslationFilter();
    }

    private void ChangePage(int delta)
    {
        var window = PageWindow.Clamp(_page + delta, _filteredRows.Count, _pageSize);
        if (window.Page == _page) return;
        _page = window.Page;
        ApplyTranslationFilter();
    }

    private void JumpNextWorkItem()
    {
        var current = CanonicalGrid.SelectedItem as TranslationRowViewModel;
        var start = current is null ? -1 : _rows.ToList().FindIndex(row => row.Key == current.Key);
        for (var offset = 1; offset <= _rows.Count; offset++)
        {
            var row = _rows[(start + offset + _rows.Count) % _rows.Count];
            if (row.Status is "pending" or "needs_context" || row.HasValidationError)
            {
                ShowRow(row);
                SetStatus($"Đến {row.Key}.", success: true);
                return;
            }
        }
        SetStatus("Không còn dòng chưa dịch hoặc lỗi QA.");
    }

    private void Minimize_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    private void Maximize_Click(object sender, RoutedEventArgs e)
    {
        WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
    }

    private void SyncWindowStateVisual() =>
        MaximizeButton.Content = WindowState == WindowState.Maximized ? "❐" : "□";
    private void Close_Click(object sender, RoutedEventArgs e) => Close();

    private void GlossaryAdd_Click(object sender, RoutedEventArgs e) => AddReferenceRow("glossary", GlossaryGrid);
    private void GlossaryDelete_Click(object sender, RoutedEventArgs e) => DeleteReferenceRow("glossary", GlossaryGrid);
    private void GlossaryReload_Click(object sender, RoutedEventArgs e) => ReloadProject();
    private void GlossarySave_Click(object sender, RoutedEventArgs e) => SaveReference("glossary", GlossaryGrid);
    private void GlossarySearch_Changed(object sender, TextChangedEventArgs e) => FilterReference("glossary", GlossarySearchBox.Text);
    private void PronounAdd_Click(object sender, RoutedEventArgs e) => AddReferenceRow("pronouns", PronounsGrid);
    private void PronounDelete_Click(object sender, RoutedEventArgs e) => DeleteReferenceRow("pronouns", PronounsGrid);
    private void PronounReload_Click(object sender, RoutedEventArgs e) => ReloadProject();
    private void PronounSave_Click(object sender, RoutedEventArgs e) => SaveReference("pronouns", PronounsGrid);
    private void PronounSearch_Changed(object sender, TextChangedEventArgs e) => FilterReference("pronouns", PronounSearchBox.Text);

    private void Window_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (ProcessShortcut(e.Key, Keyboard.Modifiers))
            e.Handled = true;
    }

    private bool ProcessShortcut(Key key, ModifierKeys modifiers)
    {
        if (key == Key.Escape && ProjectSearchOverlay.Visibility == Visibility.Visible)
        {
            ProjectSearchOverlay.Visibility = Visibility.Collapsed;
            return true;
        }
        if (key == Key.Escape && FindReplaceOverlay.Visibility == Visibility.Visible)
        {
            FindReplaceOverlay.Visibility = Visibility.Collapsed;
            return true;
        }
        if (modifiers.HasFlag(ModifierKeys.Control) && key is Key.Add or Key.OemPlus)
        {
            ChangeFontScale(1);
            SetStatus($"Cỡ chữ {_fontScale:P0}.", success: true);
            return true;
        }
        if (modifiers.HasFlag(ModifierKeys.Control) && key is Key.Subtract or Key.OemMinus)
        {
            ChangeFontScale(-1);
            SetStatus($"Cỡ chữ {_fontScale:P0}.", success: true);
            return true;
        }
        if (modifiers == ModifierKeys.Control && key is Key.D0 or Key.NumPad0)
        {
            SetFontScale(1);
            SetStatus("Cỡ chữ 100%.", success: true);
            return true;
        }
        if (key == Key.F5)
        {
            ReloadProject();
            return true;
        }
        if (modifiers == (ModifierKeys.Control | ModifierKeys.Shift) && key == Key.F)
        {
            OpenProjectSearch();
            return true;
        }
        if (modifiers == ModifierKeys.Control && key == Key.H)
        {
            MainTabs.SelectedIndex = 0;
            OpenFindReplace();
            return true;
        }
        if (modifiers == ModifierKeys.Control && key == Key.G)
        {
            OpenGoToKey();
            return true;
        }
        if (ReferenceEquals(MainTabs.SelectedItem, ConsistencyQaTab)
            && modifiers == (ModifierKeys.Control | ModifierKeys.Shift)
            && key == Key.Enter)
        {
            SaveQaDecision(advance: true);
            return true;
        }
        if (key == Key.F3 || (modifiers == ModifierKeys.Control && key == Key.Enter))
        {
            JumpNextWorkItem();
            return true;
        }
        if (key is Key.Left or Key.Right && MainTabs.SelectedIndex == 0 && SearchBox.IsKeyboardFocusWithin == false
            && GlossarySearchBox.IsKeyboardFocusWithin == false && PronounSearchBox.IsKeyboardFocusWithin == false
            && Keyboard.FocusedElement is not TextBox)
        {
            ChangePage(key == Key.Left ? -1 : 1);
            return true;
        }
        if (modifiers == ModifierKeys.Control && key == Key.F)
        {
            ProjectSearchOverlay.Visibility = Visibility.Collapsed;
            MainTabs.SelectedIndex = 0;
            SearchBox.Focus();
            SearchBox.SelectAll();
            return true;
        }
        if (modifiers == ModifierKeys.Control && key == Key.S)
        {
            if (ReferenceEquals(MainTabs.SelectedItem, ConsistencyQaTab))
                SaveQaDecision(advance: false);
            else if (MainTabs.SelectedIndex == 1) SaveReference("glossary", GlossaryGrid);
            else if (MainTabs.SelectedIndex == 2) SaveReference("pronouns", PronounsGrid);
            else SaveCanonical();
            return true;
        }
        return false;
    }

    private void PersistSession()
    {
        var session = _session ?? new SessionState();
        CaptureLayoutState(session);
        session.Capture(this);
        session.TabIndex = MainTabs.SelectedIndex;
        session.TranslationId = _activeTranslationId;
        session.Status = (StatusFilter.SelectedItem as FilterOption)?.Value;
        session.Group = (GroupFilter.SelectedItem as FilterOption)?.Value;
        session.Search = SearchBox.Text;
        session.OnlyIssues = OnlyIssuesCheck.IsChecked == true;
        session.Page = _page;
        session.PageSize = _pageSize;
        session.FontScale = _fontScale;
        session.SelectedKey = (CanonicalGrid.SelectedItem as TranslationRowViewModel)?.Key;
        session.Bookmarks = _bookmarks.Select(item => new SessionBookmark
        {
            TranslationId = item.TranslationId,
            Key = item.Key,
        }).ToList();
        session.Save(_configPath);
        _session = session;
    }

    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (HasUnsavedEdits()
            && MessageBox.Show("Đóng ứng dụng và bỏ các thay đổi chưa lưu?", "bientaptay", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
        {
            e.Cancel = true;
            return;
        }
        try
        {
            PersistSession();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            MessageBox.Show($"Không thể lưu bố cục phiên làm việc:\n{ex.Message}", "bientaptay", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }
}
