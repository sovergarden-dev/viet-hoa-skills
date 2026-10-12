using System.IO;
using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Automation;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shell;
using BienTapTay.App;

internal static class Program
{
    [DllImport("user32.dll")]
    private static extern nint GetThreadDpiAwarenessContext();

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool AreDpiAwarenessContextsEqual(nint dpiContextA, nint dpiContextB);

    [STAThread]
    private static void Main()
    {
        var root = Path.Combine(Path.GetTempPath(), "bientaptay-app-smoke-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            File.WriteAllText(Path.Combine(root, "canonical.csv"),
                "key,speaker,source_ja,source_ref,translation_vi,protected_tokens,asset,status,review_note\r\n" +
                string.Concat(Enumerable.Range(1, 20).Select(i =>
                    $"k{i},{(i % 2 == 0 ? "Hiro" : "Ema")},こんにちは,Xin chào,Xin chào {i},,scene,translated,\r\n")),
                new UTF8Encoding(true));
            File.WriteAllText(Path.Combine(root, "ui.csv"),
                "key,document,source_ja,source_ref,translation_vi,status,review_note\r\n" +
                "ui1,Options,設定,设置,Cài đặt,reviewed,\r\n" +
                "ui2,Options,終了,退出,Thoát,reviewed,\r\n",
                new UTF8Encoding(true));
            File.WriteAllText(Path.Combine(root, "glossary.csv"), "term,translation,type,context,status\r\n", new UTF8Encoding(true));
            File.WriteAllText(Path.Combine(root, "pronouns.csv"), "speaker,addressee,relationship,self_reference,address_form,notes,status\r\nHiro,,narrator,,,,reviewed\r\n", new UTF8Encoding(true));
            File.WriteAllText(Path.Combine(root, "release.json"), "{}\n", new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(root, "project.json"), """
            {
              "projectName":"Smoke",
              "canonicalPath":"canonical.csv",
              "keyColumn":"key",
              "sourceFields":[
                {"column":"source_ja","label":"Nguồn"},
                {"column":"source_ref","label":"Tham khảo"}
              ],
              "targetColumn":"translation_vi",
              "statusColumn":"status",
              "notesColumn":"review_note",
              "speakerColumn":"speaker",
              "groupColumn":"asset",
              "protectedTokensColumn":"protected_tokens",
              "statuses":["pending","translated","reviewed","needs_context","rejected"],
              "translationFiles":[
                {"id":"scripts","label":"Kịch bản","path":"canonical.csv"},
                {
                  "id":"ui","label":"UI","path":"ui.csv",
                  "groupColumn":"document","speakerColumn":"",
                  "protectedTokensColumn":"",
                  "sourceFields":[
                    {"column":"source_ja","label":"Nguồn"},
                    {"column":"source_ref","label":"Tham khảo"}
                  ]
                }
              ],
              "references":[
                {"id":"glossary","label":"Thuật ngữ","path":"glossary.csv","keyColumn":"term"},
                {"id":"pronouns","label":"Xưng hô","path":"pronouns.csv","keyColumn":"speaker"}
              ],
              "resources":[
                {"label":"Release receipt","path":"release.json"}
              ]
            }
            """, new UTF8Encoding(false));

            using (var firstLock = ProjectInstanceLock.TryAcquire(Path.Combine(root, "project.json")))
            {
                if (firstLock is null) throw new InvalidOperationException("Instance đầu phải lấy được project lock.");
                using var secondLock = ProjectInstanceLock.TryAcquire(Path.Combine(root, "PROJECT.json"));
                if (secondLock is not null) throw new InvalidOperationException("Cùng project không được có instance thứ hai.");
                var probe = RunWriterLock("probe", Path.Combine(root, "project.json"));
                if (probe.ExitCode != 2 || !probe.Output.Contains("LOCK-REFUSED", StringComparison.Ordinal))
                    throw new InvalidOperationException("ProjectInstanceLock phải chặn writer Python/Hermes.");
            }
            using (var reopenedLock = ProjectInstanceLock.TryAcquire(Path.Combine(root, "project.json")))
            {
                if (reopenedLock is null) throw new InvalidOperationException("Dispose project lock phải cho phép mở lại.");
            }

            using (var holder = StartWriterLockHolder(Path.Combine(root, "project.json")))
            {
                var ready = holder.StandardOutput.ReadLine() ?? string.Empty;
                if (!ready.StartsWith("LOCKED ", StringComparison.Ordinal))
                    throw new InvalidOperationException("Writer Python không lấy được lock test: " + ready + holder.StandardError.ReadToEnd());
                using var blockedByExternalWriter = ProjectInstanceLock.TryAcquire(Path.Combine(root, "project.json"));
                if (blockedByExternalWriter is not null)
                    throw new InvalidOperationException("App phải từ chối project khi writer Python/Hermes đang giữ lock.");
                holder.Kill(entireProcessTree: true);
                holder.WaitForExit(10_000);
            }
            using (var afterExternalWriter = ProjectInstanceLock.TryAcquire(Path.Combine(root, "project.json")))
            {
                if (afterExternalWriter is null) throw new InvalidOperationException("Writer bị dừng phải tự giải phóng shared lock.");
            }

            var app = new App();
            app.InitializeComponent();
            app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
            if (!AreDpiAwarenessContextsEqual(GetThreadDpiAwarenessContext(), new nint(-4)))
                throw new InvalidOperationException("WPF thread phải dùng PerMonitorV2 để render đúng ở DPI 125-200%.");
            var canvasBrush = app.Resources["CanvasBrush"] as SolidColorBrush
                ?? throw new InvalidOperationException("Thiếu CanvasBrush.");
            if (AccessibilityPalette.ColorFor("Canvas", true) != SystemColors.WindowColor ||
                AccessibilityPalette.ColorFor("Selection", true) != SystemColors.HighlightColor ||
                AccessibilityPalette.ColorFor("HighlightText", true) != SystemColors.HighlightTextColor)
                throw new InvalidOperationException("Palette High Contrast không dùng màu hệ thống.");
            if (canvasBrush.Color != AccessibilityPalette.ColorFor("Canvas", SystemParameters.HighContrast))
                throw new InvalidOperationException("App.xaml không áp palette theo High Contrast lúc parse.");
            var sourceRoot = Path.GetDirectoryName(FindAncestorFile(AppContext.BaseDirectory, "writer_lock.py"))
                ?? throw new InvalidOperationException("Không xác định được thư mục source bientaptay.");
            foreach (var xamlPath in new[]
                     {
                         Path.Combine(sourceRoot, "src", "BienTapTay.App", "App.xaml"),
                         Path.Combine(sourceRoot, "src", "BienTapTay.App", "MainWindow.xaml"),
                     })
            {
                var literal = Regex.Match(File.ReadAllText(xamlPath), "#[0-9A-Fa-f]{6,8}");
                if (literal.Success)
                    throw new InvalidOperationException($"Màu literal {literal.Value} bỏ qua High Contrast trong {Path.GetFileName(xamlPath)}.");
            }
            foreach (var role in new[] { "Warning", "DangerSurface", "DangerBorder", "DangerText", "WarningSurface", "Overlay" })
            {
                _ = AccessibilityPalette.ColorFor(role, false);
                _ = AccessibilityPalette.ColorFor(role, true);
                if (app.Resources[role + "Brush"] is not SolidColorBrush)
                    throw new InvalidOperationException($"Thiếu semantic brush {role}Brush.");
            }
            var highlightTextBrush = app.Resources["HighlightTextBrush"];
            var selectionBrush = app.Resources["SelectionBrush"];
            foreach (var styleKey in new[] { typeof(DataGridRow), typeof(DataGridCell) })
            {
                var style = app.Resources[styleKey] as Style
                    ?? throw new InvalidOperationException($"Thiếu style {styleKey.Name}.");
                var selectedTrigger = style.Triggers.OfType<Trigger>().Single(trigger =>
                    trigger.Property.Name == "IsSelected" && Equals(trigger.Value, true));
                var foreground = selectedTrigger.Setters.OfType<Setter>().Single(setter =>
                    setter.Property == Control.ForegroundProperty);
                var background = selectedTrigger.Setters.OfType<Setter>().Single(setter =>
                    setter.Property == Control.BackgroundProperty);
                if (!ReferenceEquals(foreground.Value, highlightTextBrush))
                    throw new InvalidOperationException($"{styleKey.Name} được chọn phải dùng HighlightTextBrush để giữ cặp màu High Contrast hệ thống.");
                if (!ReferenceEquals(background.Value, selectionBrush))
                    throw new InvalidOperationException($"{styleKey.Name} được chọn phải dùng SelectionBrush để giữ cặp màu High Contrast hệ thống.");
            }
            var codeBehind = File.ReadAllText(Path.Combine(sourceRoot, "src", "BienTapTay.App", "MainWindow.xaml.cs"));
            if (codeBehind.Contains("Color.From", StringComparison.Ordinal))
                throw new InvalidOperationException("MainWindow code-behind còn tạo màu trực tiếp, bỏ qua High Contrast.");
            AssertCorruptQaSidecarDoesNotBlockEditor(root);

            var window = new MainWindow(Path.Combine(root, "project.json"));
            window.Show();
            window.UpdateLayout();
            var chrome = WindowChrome.GetWindowChrome(window);
            if (chrome is null || chrome.CaptionHeight != 36 || chrome.GlassFrameThickness.Top != 0)
                throw new InvalidOperationException("Title bar phải dùng WindowChrome tối không có dải kính trắng.");
            var scrollBarStyle = app.Resources[typeof(ScrollBar)] as Style;
            if (scrollBarStyle is null || scrollBarStyle.Triggers.Count == 0)
                throw new InvalidOperationException("Thiếu style scrollbar tối.");
            var maximizeButton = window.FindName("MaximizeButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút maximize.");
            if (AutomationProperties.GetName(maximizeButton) != "Phóng to hoặc khôi phục cửa sổ")
                throw new InvalidOperationException("Nút icon maximize thiếu accessible name.");
            var datasetForTab = window.FindName("DatasetFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu phạm vi cho tab-order test.");
            var searchForTab = window.FindName("SearchBox") as TextBox
                ?? throw new InvalidOperationException("Thiếu tìm kiếm cho tab-order test.");
            var statusForTab = window.FindName("StatusFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu trạng thái cho tab-order test.");
            if (!(KeyboardNavigation.GetTabIndex(datasetForTab) < KeyboardNavigation.GetTabIndex(searchForTab)
                && KeyboardNavigation.GetTabIndex(searchForTab) < KeyboardNavigation.GetTabIndex(statusForTab)))
                throw new InvalidOperationException("Tab order bộ lọc không theo Phạm vi → Tìm kiếm → Trạng thái.");
            window.WindowState = WindowState.Normal;
            window.Width = window.MinWidth;
            window.Height = window.MinHeight;
            var minimumFontScale = window.FindName("FontScaleCombo") as ComboBox
                ?? throw new InvalidOperationException("Thiếu bộ chọn cỡ chữ cho minimum-layout test.");
            minimumFontScale.SelectedItem = minimumFontScale.Items.Cast<ComboBoxItem>().Single(item => item.Tag?.ToString() == "130");
            window.UpdateLayout();
            foreach (var controlName in new[]
                     {
                         "DatasetFilter", "SearchBox", "StatusFilter", "GroupFilter", "FindReplaceButton",
                         "ReloadButton", "SaveButton", "PrevPageButton", "PageJumpButton", "NextPageButton",
                     })
            {
                AssertFullyVisible(window, (FrameworkElement)(window.FindName(controlName)
                    ?? throw new InvalidOperationException($"Thiếu control {controlName} cho minimum-layout test.")));
            }
            minimumFontScale.SelectedItem = minimumFontScale.Items.Cast<ComboBoxItem>().Single(item => item.Tag?.ToString() == "100");
            window.Width = 1440;
            window.Height = 900;
            window.UpdateLayout();
            var scriptsGrid = window.FindName("CanonicalGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới canonical.");
            if (scriptsGrid.Items.Count != 17) throw new InvalidOperationException($"Trang đầu phải 17 hàng, nhận {scriptsGrid.Items.Count}.");
            var dialogueContext = window.FindName("DialogueContextItems") as ItemsControl
                ?? throw new InvalidOperationException("Thiếu context dạng hội thoại.");
            if (dialogueContext.Items.Count < 2) throw new InvalidOperationException("Context phải có nhiều lượt speaker, không phải text phẳng ±2 dòng.");
            var selectedTurn = dialogueContext.Items.Cast<DialogueTurnViewModel>().Single(item => item.IsSelected);
            var selectedPresenter = dialogueContext.ItemContainerGenerator.ContainerFromItem(selectedTurn) as ContentPresenter
                ?? throw new InvalidOperationException("Thiếu presenter cho lượt hội thoại đang chọn.");
            selectedPresenter.ApplyTemplate();
            var selectedCard = FindDescendant<Border>(selectedPresenter)
                ?? throw new InvalidOperationException("Thiếu card cho lượt hội thoại đang chọn.");
            if (!Equals(selectedCard.BorderBrush, app.Resources["AccentBrush"]))
                throw new InvalidOperationException("Card hội thoại đang chọn phải dùng viền accent.");
            var bookmarkToggle = window.FindName("BookmarkToggleButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút đánh dấu exact key.");
            bookmarkToggle.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var bookmarkPicker = window.FindName("BookmarkPicker") as ComboBox
                ?? throw new InvalidOperationException("Thiếu danh sách bookmark.");
            if (bookmarkPicker.Items.Count != 1) throw new InvalidOperationException("Đánh dấu phải thêm đúng một bookmark.");
            var nextTurn = dialogueContext.Items.Cast<DialogueTurnViewModel>().First(item => !item.IsSelected);
            var nextPresenter = dialogueContext.ItemContainerGenerator.ContainerFromItem(nextTurn) as ContentPresenter
                ?? throw new InvalidOperationException("Thiếu presenter cho lượt hội thoại kế tiếp.");
            nextPresenter.ApplyTemplate();
            var nextTurnButton = FindDescendant<Button>(nextPresenter)
                ?? throw new InvalidOperationException("Card hội thoại phải bấm được.");
            nextTurnButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (scriptsGrid.SelectedItem is not TranslationRowViewModel contextRow || contextRow.Key != nextTurn.PrimaryKey)
                throw new InvalidOperationException("Bấm card hội thoại không tới exact key của lượt.");
            var findReplaceButton = window.FindName("FindReplaceButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút tìm/thay.");
            findReplaceButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var findReplaceOverlay = window.FindName("FindReplaceOverlay") as Grid
                ?? throw new InvalidOperationException("Thiếu overlay tìm/thay.");
            if (findReplaceOverlay.Visibility != Visibility.Visible) throw new InvalidOperationException("Tìm/thay không mở overlay.");
            if (!ContainsText(findReplaceOverlay, "Tìm chuỗi nguyên văn"))
                throw new InvalidOperationException("Hướng dẫn an toàn tìm/thay phải hoàn toàn bằng tiếng Việt.");
            (window.FindName("FindReplaceFindTextBox") as TextBox)!.Text = "Xin chào 20";
            (window.FindName("FindReplaceReplacementTextBox") as TextBox)!.Text = "Chào 20";
            var previewButton = FindButton(findReplaceOverlay, "Xem trước");
            previewButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var replacePreview = window.FindName("ReplacePreviewGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu preview tìm/thay.");
            if (replacePreview.Items.Count != 1) throw new InvalidOperationException("Preview literal phải tìm đúng một dòng.");
            if ((window.FindName("ReplaceApplyButton") as Button)?.IsEnabled != true)
                throw new InvalidOperationException("Batch sạch phải cho phép Thay tất cả.");
            if ((window.FindName("ReplaceUndoButton") as Button)?.IsEnabled == true)
                throw new InvalidOperationException("Chưa có batch thì nút hoàn tác phải tắt.");
            findReplaceOverlay.Visibility = Visibility.Collapsed;

            var projectSearchButton = window.FindName("ProjectSearchButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút tìm mọi bảng.");
            projectSearchButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var projectSearchOverlay = window.FindName("ProjectSearchOverlay") as Grid
                ?? throw new InvalidOperationException("Thiếu overlay tìm mọi bảng.");
            if (projectSearchOverlay.Visibility != Visibility.Visible)
                throw new InvalidOperationException("Tìm mọi bảng không mở overlay.");
            (window.FindName("ProjectSearchInput") as TextBox)!.Text = "Cài đặt";
            (window.FindName("ProjectSearchRunButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var projectSearchGrid = window.FindName("ProjectSearchGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới kết quả mọi bảng.");
            if (projectSearchGrid.Items.Count != 1
                || projectSearchGrid.Items[0] is not TranslationSearchResultViewModel searchResult
                || searchResult.FileId != "ui" || searchResult.Key != "ui1")
                throw new InvalidOperationException("Tìm mọi bảng không trả đúng UI/ui1.");
            projectSearchGrid.SelectedIndex = 0;
            (window.FindName("ProjectSearchGoToButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            var projectSearchDatasetFilter = window.FindName("DatasetFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu bộ chọn bảng sau tìm toàn project.");
            if ((projectSearchDatasetFilter.SelectedItem as BienTapTay.Core.TranslationFileConfig)?.Id != "ui"
                || scriptsGrid.SelectedItem is not TranslationRowViewModel searchedRow || searchedRow.Key != "ui1")
                throw new InvalidOperationException("Kết quả mọi bảng không điều hướng đúng dataset + exact key.");
            projectSearchDatasetFilter.SelectedIndex = 0;
            window.UpdateLayout();

            var consistencyTab = window.FindName("ConsistencyQaTab") as TabItem
                ?? throw new InvalidOperationException("Thiếu tab QA nhất quán.");
            var consistencyGrid = window.FindName("ConsistencyQaGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới QA nhất quán.");
            if (!consistencyGrid.IsReadOnly) throw new InvalidOperationException("QA nhất quán phải chỉ đọc.");
            var consistencyScan = window.FindName("ConsistencyQaScanButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút quét QA nhất quán.");
            var targetBeforeConsistencyScan = (scriptsGrid.Items[0] as TranslationRowViewModel)?.Target;
            consistencyTab.IsSelected = true;
            consistencyScan.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if ((scriptsGrid.Items[0] as TranslationRowViewModel)?.Target != targetBeforeConsistencyScan)
                throw new InvalidOperationException("Quét QA nhất quán không được sửa target.");
            if (consistencyGrid.Items.Count < 2)
                throw new InvalidOperationException("Fixture phải tạo ít nhất hai cảnh báo QA để test triage/filter.");
            var qaKindFilter = window.FindName("ConsistencyQaKindFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu filter loại QA.");
            var qaSpeakerFilter = window.FindName("ConsistencyQaSpeakerFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu filter speaker QA.");
            var qaDecisionFilter = window.FindName("ConsistencyQaDecisionFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu filter quyết định QA.");
            if (qaDecisionFilter.SelectedItem is not ComboBoxItem initialDecisionFilter
                || !string.Equals(initialDecisionFilter.Content?.ToString(), "Chưa phân loại", StringComparison.Ordinal)
                || !string.Equals(initialDecisionFilter.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.Unreviewed), StringComparison.Ordinal))
                throw new InvalidOperationException("Lần đầu mở tab QA phải mặc định lọc Chưa phân loại. Got: "
                    + (qaDecisionFilter.SelectedItem as ComboBoxItem)?.Content);
            var qaSummary = window.FindName("ConsistencyQaSummaryText") as TextBlock
                ?? throw new InvalidOperationException("Thiếu tóm tắt QA nhất quán.");
            var visibleIssues = consistencyGrid.Items.Count;
            if (visibleIssues != 2)
                throw new InvalidOperationException($"Fixture QA phải hiện 2 cảnh báo chưa phân loại, nhận {visibleIssues}.");
            foreach (var required in new[]
                     {
                         $"{visibleIssues}/2",
                         "chưa phân loại 2",
                         "cần sửa 0",
                         "chấp nhận khác biệt 0",
                         "đã xử lý 0",
                         "quyết định cũ 0",
                     })
            {
                if (qaSummary.Text.IndexOf(required, StringComparison.Ordinal) < 0)
                    throw new InvalidOperationException($"Tóm tắt QA thiếu '{required}'. Got: {qaSummary.Text}");
            }
            var qaTriageCombo = window.FindName("ConsistencyQaTriageCombo") as ComboBox
                ?? throw new InvalidOperationException("Thiếu bộ chọn quyết định QA.");
            var qaNote = window.FindName("ConsistencyQaDecisionNoteBox") as TextBox
                ?? throw new InvalidOperationException("Thiếu ghi chú quyết định QA.");
            var qaSave = window.FindName("ConsistencyQaSaveDecisionButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút lưu quyết định QA.");
            var qaSaveNext = window.FindName("ConsistencyQaSaveNextButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút Lưu & kế tiếp.");
            if (!string.Equals(qaSaveNext.Content?.ToString(), "Lưu & kế tiếp", StringComparison.Ordinal))
                throw new InvalidOperationException("Nút Lưu & kế tiếp phải hiện đúng nhãn. Got: " + qaSaveNext.Content);
            var qaExport = window.FindName("ConsistencyQaExportReportButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút Xuất báo cáo.");
            if (!string.Equals(qaExport.Content?.ToString(), "Xuất báo cáo", StringComparison.Ordinal))
                throw new InvalidOperationException("Nút Xuất báo cáo phải hiện đúng nhãn. Got: " + qaExport.Content);
            var sidecarPath = Path.Combine(root, "qa-decisions.json");
            consistencyGrid.SelectedIndex = 0;
            var firstIssue = consistencyGrid.SelectedItem as ConsistencyIssueViewModel
                ?? throw new InvalidOperationException("Thiếu cảnh báo QA đầu hàng đợi.");
            var firstDecisionId = firstIssue.DecisionId;
            var exportDirtyRow = scriptsGrid.Items.Cast<TranslationRowViewModel>().First();
            var exportDirtyOriginal = exportDirtyRow.Target;
            exportDirtyRow.Target = exportDirtyOriginal + " draft";
            var filterBeforeExport = (qaDecisionFilter.SelectedItem as ComboBoxItem)?.Tag?.ToString();
            var canonicalBeforeExport = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
            var glossaryBeforeExport = File.ReadAllBytes(Path.Combine(root, "glossary.csv"));
            var sessionPath = Path.Combine(root, "session.json");
            var sessionBeforeExport = File.Exists(sessionPath) ? File.ReadAllBytes(sessionPath) : null;
            var reportPath = Path.Combine(root, "qa-report.json");
            InvokeExportQaReport(window, reportPath);
            window.UpdateLayout();
            if (!File.Exists(reportPath))
                throw new InvalidOperationException("Xuất báo cáo phải ghi file đã chọn.");
            if (!File.ReadAllText(reportPath).Contains("bientaptay-qa-report/v1", StringComparison.Ordinal))
                throw new InvalidOperationException("Báo cáo JSON phải dùng schema v1.");
            if ((qaDecisionFilter.SelectedItem as ComboBoxItem)?.Tag?.ToString() != filterBeforeExport)
                throw new InvalidOperationException("Xuất báo cáo không được đổi filter quyết định.");
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel afterExport
                || !afterExport.DecisionId.Equals(firstDecisionId, StringComparison.Ordinal))
                throw new InvalidOperationException("Xuất báo cáo không được đổi cảnh báo đang chọn.");
            if (exportDirtyRow.Target != exportDirtyOriginal + " draft")
                throw new InvalidOperationException("Xuất báo cáo không được lưu target dirty.");
            if (!canonicalBeforeExport.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("Xuất báo cáo không được đổi canonical.");
            if (!glossaryBeforeExport.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "glossary.csv"))))
                throw new InvalidOperationException("Xuất báo cáo không được đổi glossary.");
            if (File.Exists(sidecarPath))
                throw new InvalidOperationException("Xuất báo cáo không được tạo sidecar QA.");
            var sessionAfterExport = File.Exists(sessionPath) ? File.ReadAllBytes(sessionPath) : null;
            if (!((sessionBeforeExport is null && sessionAfterExport is null)
                || (sessionBeforeExport is not null && sessionAfterExport is not null && sessionBeforeExport.SequenceEqual(sessionAfterExport))))
                throw new InvalidOperationException("Xuất báo cáo không được đổi session.json.");
            exportDirtyRow.Target = exportDirtyOriginal;
            File.Delete(reportPath);
            qaTriageCombo.SelectedItem = qaTriageCombo.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            qaNote.Text = "Sửa ở lượt review sau.";
            window.UpdateLayout();
            if (File.Exists(sidecarPath))
                throw new InvalidOperationException("Đổi triage/ghi chú không được tự ghi sidecar QA.");
            var canonicalBeforeQueue = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
            var secondIssue = consistencyGrid.Items[1] as ConsistencyIssueViewModel
                ?? throw new InvalidOperationException("Thiếu cảnh báo QA thứ hai.");
            var secondDecisionId = secondIssue.DecisionId;
            qaSaveNext.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (!File.Exists(sidecarPath))
                throw new InvalidOperationException("Lưu & kế tiếp phải ghi sidecar QA.");
            if (!canonicalBeforeQueue.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("Lưu & kế tiếp không được đổi canonical.");
            if (consistencyGrid.Items.Cast<ConsistencyIssueViewModel>().Any(item => item.DecisionId.Equals(firstDecisionId, StringComparison.Ordinal)))
                throw new InvalidOperationException("Hàng đợi Chưa phân loại phải ẩn cảnh báo vừa lưu.");
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel advanced
                || !advanced.DecisionId.Equals(secondDecisionId, StringComparison.Ordinal))
                throw new InvalidOperationException("Lưu & kế tiếp phải chọn cảnh báo kế tiếp trong hàng đợi.");
            qaTriageCombo.SelectedItem = qaTriageCombo.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            qaNote.Text = "Sửa ở lượt review sau.";
            window.UpdateLayout();
            qaSaveNext.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (consistencyGrid.Items.Count != 0 || consistencyGrid.SelectedItem is not null)
                throw new InvalidOperationException("Hết hàng đợi phải xóa selection.");
            var statusMessage = window.FindName("StatusMessageText") as TextBlock
                ?? throw new InvalidOperationException("Thiếu thanh trạng thái QA/clipboard.");
            if (statusMessage.Text.IndexOf("hàng đợi", StringComparison.OrdinalIgnoreCase) < 0)
                throw new InvalidOperationException("Hết hàng đợi phải báo hoàn thành. Got: " + statusMessage.Text);
            File.Delete(sidecarPath);
            (window.FindName("ReloadButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            qaDecisionFilter.SelectedItem = qaDecisionFilter.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.Unreviewed), StringComparison.Ordinal));
            window.UpdateLayout();
            if (consistencyGrid.Items.Count != 2)
                throw new InvalidOperationException("Reload sidecar phải trả lại 2 cảnh báo chưa phân loại.");
            consistencyGrid.SelectedIndex = 1;
            window.UpdateLayout();
            var wrapLast = consistencyGrid.SelectedItem as ConsistencyIssueViewModel
                ?? throw new InvalidOperationException("Thiếu cảnh báo cuối để test wrap.");
            var wrapFirstRemaining = (ConsistencyIssueViewModel)consistencyGrid.Items[0];
            qaTriageCombo.SelectedItem = qaTriageCombo.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            qaSaveNext.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel wrapped
                || !wrapped.DecisionId.Equals(wrapFirstRemaining.DecisionId, StringComparison.Ordinal)
                || consistencyGrid.Items.Cast<ConsistencyIssueViewModel>().Any(item => item.DecisionId.Equals(wrapLast.DecisionId, StringComparison.Ordinal)))
                throw new InvalidOperationException("Cảnh báo cuối phải wrap về cảnh báo còn lại đầu hàng đợi.");
            File.Delete(sidecarPath);
            (window.FindName("ReloadButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            consistencyTab.IsSelected = true;
            window.UpdateLayout();
            qaDecisionFilter.SelectedItem = qaDecisionFilter.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), "", StringComparison.Ordinal));
            window.UpdateLayout();
            consistencyGrid.SelectedIndex = 0;
            window.UpdateLayout();
            qaTriageCombo.SelectedItem = qaTriageCombo.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            qaNote.Text = "Ctrl+S trên tab QA.";
            qaNote.Focus();
            window.UpdateLayout();
            var shortcutCanonical = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
            var shortcutStayId = ((ConsistencyIssueViewModel)consistencyGrid.SelectedItem).DecisionId;
            var dirtyRow = scriptsGrid.Items.Cast<TranslationRowViewModel>().First();
            var dirtyOriginal = dirtyRow.Target;
            dirtyRow.Target = dirtyOriginal + " dirty";
            InvokeShortcut(window, Key.S, ModifierKeys.Control);
            if (!File.Exists(sidecarPath))
                throw new InvalidOperationException("Ctrl+S trên tab QA phải lưu quyết định QA.");
            if (!shortcutCanonical.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("Ctrl+S trên tab QA không được ghi canonical.");
            if (dirtyRow.Target != dirtyOriginal + " dirty")
                throw new InvalidOperationException("Ctrl+S trên tab QA không được lưu bản dịch đang dirty.");
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel savedByShortcut
                || !savedByShortcut.DecisionId.Equals(shortcutStayId, StringComparison.Ordinal))
                throw new InvalidOperationException("Ctrl+S trên tab QA phải giữ nguyên cảnh báo đang chọn.");
            dirtyRow.Target = dirtyOriginal;
            var beforeF3 = ((ConsistencyIssueViewModel)consistencyGrid.SelectedItem).DecisionId;
            qaNote.Focus();
            window.UpdateLayout();
            InvokeShortcut(window, Key.F3, ModifierKeys.None);
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel afterF3
                || !afterF3.DecisionId.Equals(beforeF3, StringComparison.Ordinal))
                throw new InvalidOperationException("F3 trên tab QA không được đổi hàng đợi QA.");
            if (!shortcutCanonical.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("F3 trên tab QA không được ghi canonical.");
            if (statusMessage.Text.IndexOf("Không còn dòng chưa dịch", StringComparison.Ordinal) < 0)
                throw new InvalidOperationException("F3 trên tab QA phải giữ next-work-item. Got: " + statusMessage.Text);
            InvokeShortcut(window, Key.Enter, ModifierKeys.Control);
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel afterCtrlEnter
                || !afterCtrlEnter.DecisionId.Equals(beforeF3, StringComparison.Ordinal))
                throw new InvalidOperationException("Ctrl+Enter trên tab QA không được đổi hàng đợi QA.");
            if (!shortcutCanonical.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("Ctrl+Enter trên tab QA không được ghi canonical.");
            File.Delete(sidecarPath);
            (window.FindName("ReloadButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            consistencyTab.IsSelected = true;
            qaDecisionFilter.SelectedItem = qaDecisionFilter.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.Unreviewed), StringComparison.Ordinal));
            window.UpdateLayout();
            consistencyGrid.SelectedIndex = 0;
            window.UpdateLayout();
            var shiftFirst = ((ConsistencyIssueViewModel)consistencyGrid.SelectedItem).DecisionId;
            var shiftNext = ((ConsistencyIssueViewModel)consistencyGrid.Items[1]).DecisionId;
            qaTriageCombo.SelectedItem = qaTriageCombo.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            qaNote.Text = "Ctrl+Shift+Enter.";
            qaNote.Focus();
            window.UpdateLayout();
            InvokeShortcut(window, Key.Enter, ModifierKeys.Control | ModifierKeys.Shift);
            window.UpdateLayout();
            if (consistencyGrid.Items.Cast<ConsistencyIssueViewModel>().Any(item => item.DecisionId.Equals(shiftFirst, StringComparison.Ordinal)))
                throw new InvalidOperationException("Ctrl+Shift+Enter phải ẩn cảnh báo vừa lưu khỏi hàng đợi Chưa phân loại.");
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel shiftAdvanced
                || !shiftAdvanced.DecisionId.Equals(shiftNext, StringComparison.Ordinal))
                throw new InvalidOperationException("Ctrl+Shift+Enter phải lưu và tới cảnh báo kế tiếp.");
            File.Delete(sidecarPath);
            (window.FindName("ReloadButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            qaDecisionFilter.SelectedItem = qaDecisionFilter.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), "", StringComparison.Ordinal));
            window.UpdateLayout();
            consistencyGrid.SelectedIndex = 0;
            window.UpdateLayout();
            qaTriageCombo.SelectedItem = qaTriageCombo.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            qaNote.Text = "Sửa ở lượt review sau.";
            window.UpdateLayout();
            window.UpdateLayout();
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel stillFirst
                || !stillFirst.DecisionId.Equals(firstDecisionId, StringComparison.Ordinal))
                throw new InvalidOperationException("Đổi sang Mọi quyết định không được mất cảnh báo đang chọn.");
            var canonicalBeforeQaDecision = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
            qaSave.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (!File.Exists(sidecarPath))
                throw new InvalidOperationException("Lưu triage phải tạo sidecar qa-decisions.json.");
            if (!canonicalBeforeQaDecision.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("Lưu triage QA không được đổi canonical.");
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel savedStay
                || !savedStay.DecisionId.Equals(firstDecisionId, StringComparison.Ordinal)
                || savedStay.TriageStatus != BienTapTay.Core.QaTriageStatus.NeedsFix)
                throw new InvalidOperationException("Lưu quyết định phải giữ nguyên cảnh báo đang chọn.");
            qaDecisionFilter.SelectedItem = qaDecisionFilter.Items.OfType<ComboBoxItem>()
                .Single(item => string.Equals(item.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal));
            window.UpdateLayout();
            if (consistencyGrid.Items.Count != 1)
                throw new InvalidOperationException("Filter Cần sửa phải giữ đúng cảnh báo đã triage.");
            consistencyScan.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (qaDecisionFilter.SelectedItem is not ComboBoxItem persistedFilter
                || !string.Equals(persistedFilter.Tag?.ToString(), nameof(BienTapTay.Core.QaTriageStatus.NeedsFix), StringComparison.Ordinal))
                throw new InvalidOperationException("Quét lại không được reset filter quyết định người dùng đã chọn.");
            if (consistencyGrid.Items.Count != 1)
                throw new InvalidOperationException("Quét lại phải giữ hàng đợi theo filter hiện tại.");
            qaDecisionFilter.SelectedIndex = 0;
            qaSpeakerFilter.SelectedItem = qaSpeakerFilter.Items.Cast<FilterOption>()
                .First(item => string.Equals(item.Value, savedStay.SpeakerValue, StringComparison.Ordinal));
            window.UpdateLayout();
            if (consistencyGrid.Items.Count != 1)
                throw new InvalidOperationException("Filter speaker phải giữ đúng nhóm cảnh báo.");
            qaSpeakerFilter.SelectedIndex = 0;
            qaKindFilter.SelectedIndex = 0;
            consistencyGrid.SelectedIndex = -1;
            window.UpdateLayout();
            if (qaSave.IsEnabled || qaSaveNext.IsEnabled)
                throw new InvalidOperationException("Không có cảnh báo chọn thì Lưu quyết định và Lưu & kế tiếp phải tắt.");
            consistencyGrid.SelectedIndex = 0;
            window.UpdateLayout();
            var selectedQaIssue = consistencyGrid.SelectedItem as ConsistencyIssueViewModel
                ?? throw new InvalidOperationException("Thiếu cảnh báo QA được chọn cho compare/context.");
            var relatedGrid = window.FindName("ConsistencyQaRelatedGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới so sánh key liên quan.");
            if (relatedGrid.Items.Count != selectedQaIssue.RelatedKeyList.Count || relatedGrid.Items.Count < 2)
                throw new InvalidOperationException("Lưới compare phải chứa đúng mọi full related key.");
            var relatedPrevious = window.FindName("ConsistencyQaRelatedPreviousButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút key liên quan trước.");
            var relatedNext = window.FindName("ConsistencyQaRelatedNextButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút key liên quan sau.");
            var relatedGoTo = window.FindName("ConsistencyQaRelatedGoToButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút tới key liên quan.");
            var copyContext = window.FindName("ConsistencyQaCopyContextButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút sao chép context packet.");
            relatedGrid.SelectedIndex = 0;
            relatedNext.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if (relatedGrid.SelectedIndex != 1) throw new InvalidOperationException("Nút sau không chuyển compare key.");
            relatedPrevious.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if (relatedGrid.SelectedIndex != 0) throw new InvalidOperationException("Nút trước không chuyển compare key.");
            var copyFailedBeforeSuccess = false;
            for (var attempt = 0; ; attempt++)
            {
                copyContext.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                if (statusMessage.Text.StartsWith("Đã sao chép context packet", StringComparison.Ordinal)) break;
                copyFailedBeforeSuccess = true;
                if (attempt == 39) throw new InvalidOperationException("Clipboard vẫn bận sau 2 giây: " + statusMessage.Text);
                Thread.Sleep(50);
            }
            var contextPacket = ReadClipboardTextWithRetry();
            foreach (var required in new[] { "BIENTAPTAY-QA-CONTEXT/1", "translation_id: scripts", "exact_key: k1", "target: Xin chào 1", "Nguồn: こんにちは", "Tham khảo: Xin chào", "glossary:", "pronouns:" })
                if (!contextPacket.Contains(required, StringComparison.Ordinal))
                    throw new InvalidOperationException("Context packet thiếu evidence: " + required);
            if (!string.Equals(copyContext.Content?.ToString(), "Sao chép context", StringComparison.Ordinal))
                throw new InvalidOperationException("Nút sao chép context phải giữ nhãn tiếng Việt. Got: " + copyContext.Content);
            if (!codeBehind.Contains("ClipboardText.SetWithRetry", StringComparison.Ordinal))
                throw new InvalidOperationException("Sao chép context phải đi qua seam ClipboardText.SetWithRetry.");
            if (codeBehind.Contains("Clipboard.SetText(", StringComparison.Ordinal))
                throw new InvalidOperationException("Sao chép context không được gọi Clipboard.SetText một phát ăn ngay.");
            if (!copyFailedBeforeSuccess && Directory.Exists(Path.Combine(root, "diagnostics")))
                throw new InvalidOperationException("Sao chép thành công không được tạo diagnostics/.");
            if (Directory.Exists(Path.Combine(root, "app")))
                throw new InvalidOperationException("Sao chép context không được tạo app/.");
            if (copyFailedBeforeSuccess)
                AssertRedactedJsonlOnly(Path.Combine(root, "diagnostics"), "clipboard_copy");

            AssertClipboardExhaustionIsLoggedSafely(window, root, statusMessage);
            AssertExportFailureWritesRedactedDiagnostics(window, root, statusMessage);
            relatedGrid.SelectedIndex = 1;
            var relatedTarget = relatedGrid.SelectedItem as QaRelatedRowViewModel
                ?? throw new InvalidOperationException("Thiếu related row được chọn.");
            relatedGoTo.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (scriptsGrid.SelectedItem is not TranslationRowViewModel relatedCanonical || relatedCanonical.Key != relatedTarget.Key)
                throw new InvalidOperationException("Tới key liên quan không điều hướng bằng full exact key.");

            var uiPath = Path.Combine(root, "ui.csv");
            RewriteField(uiPath, "key", "ui1", "translation_vi", "UI ngoài");
            InvokeExternalCheck(window);
            var globalDiffGrid = window.FindName("ExternalDiffGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới diff toàn project.");
            if (!globalDiffGrid.Items.Cast<ExternalChangeViewModel>().Any(item => item.FileId == "translation:ui"))
                throw new InvalidOperationException("Watcher phải giữ diff của bảng dịch không đang mở.");

            var glossaryPath = Path.Combine(root, "glossary.csv");
            File.WriteAllText(glossaryPath, "term,translation,type,context,status\r\n魔女,Phù thủy,term,,locked\r\n", new UTF8Encoding(true));
            File.SetLastWriteTimeUtc(glossaryPath, File.GetLastWriteTimeUtc(glossaryPath).AddSeconds(2));
            InvokeExternalCheck(window);
            if (!globalDiffGrid.Items.Cast<ExternalChangeViewModel>().Any(item => item.FileId == "reference:glossary"))
                throw new InvalidOperationException("Watcher phải giữ diff của reference glossary.");
            var pronounGrid = window.FindName("PronounsGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu bảng xưng hô cho cross-reference test.");
            var pronounLocal = pronounGrid.Items[0] as ReferenceRowViewModel
                ?? throw new InvalidOperationException("Thiếu dòng xưng hô fixture.");
            pronounLocal["self_reference"] = "私";
            File.WriteAllText(glossaryPath, "term,translation,type,context,status\r\n魔女,Phù thủy 2,term,,locked\r\n", new UTF8Encoding(true));
            File.SetLastWriteTimeUtc(glossaryPath, File.GetLastWriteTimeUtc(glossaryPath).AddSeconds(2));
            InvokeExternalCheck(window);
            if (pronounLocal["self_reference"] != "私" || (window.FindName("SaveButton") as Button)?.IsEnabled != false)
                throw new InvalidOperationException("Diff glossary không được làm mất edit local ở pronouns.");
            pronounLocal["self_reference"] = "";
            InvokeExternalCheck(window);

            var canonicalPath = Path.Combine(root, "canonical.csv");
            RewriteTarget(canonicalPath, "k1", "Hermes sửa 1");
            InvokeExternalCheck(window);
            var externalDiffGrid = window.FindName("ExternalDiffGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới diff ngoài.");
            if (externalDiffGrid.Items.Count == 0) throw new InvalidOperationException("Hermes sửa file sạch phải để lại diff.");
            if ((scriptsGrid.Items[0] as TranslationRowViewModel)?.Target != "Hermes sửa 1")
                throw new InvalidOperationException("App sạch phải auto-reload target ngoài.");

            var localRow = scriptsGrid.Items[0] as TranslationRowViewModel
                ?? throw new InvalidOperationException("Thiếu dòng local cho conflict test.");
            localRow.Target = "Local chưa lưu";
            RewriteTarget(canonicalPath, "k1", "Hermes sửa lần hai");
            InvokeExternalCheck(window);
            if ((window.FindName("SaveButton") as Button)?.IsEnabled != false)
                throw new InvalidOperationException("Có edit local + file ngoài phải khóa Lưu.");
            if (!externalDiffGrid.Items.Cast<ExternalChangeViewModel>().Any(item => item.IsConflict))
                throw new InvalidOperationException("Diff ba phía phải đánh dấu field xung đột.");
            localRow.Target = "Hermes sửa 1";
            (window.FindName("ReloadButton") as Button)!.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if ((window.FindName("SaveButton") as Button)?.IsEnabled != true)
                throw new InvalidOperationException("Nạp file ngoài phải gỡ khóa Lưu.");
            var restoredCanonical = File.ReadAllText(canonicalPath);
            File.Delete(canonicalPath);
            InvokeExternalCheck(window);
            if ((window.FindName("SaveButton") as Button)?.IsEnabled != false)
                throw new InvalidOperationException("File bị xóa phải khóa Lưu.");
            File.WriteAllText(canonicalPath, restoredCanonical, new UTF8Encoding(false));
            File.SetLastWriteTimeUtc(canonicalPath, File.GetLastWriteTimeUtc(canonicalPath).AddSeconds(2));
            InvokeExternalCheck(window);
            if ((window.FindName("SaveButton") as Button)?.IsEnabled != true)
                throw new InvalidOperationException("File khôi phục nguyên trạng phải gỡ pending lock.");
            var goToKeyButton = window.FindName("GoToKeyButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút tới exact key.");
            goToKeyButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var goToKeyInput = window.FindName("GoToKeyInput") as TextBox
                ?? throw new InvalidOperationException("Thiếu ô exact key.");
            goToKeyInput.Text = "k20";
            var goToKeyConfirm = window.FindName("GoToKeyConfirmButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút xác nhận exact key.");
            goToKeyConfirm.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (scriptsGrid.SelectedItem is not TranslationRowViewModel keyedRow || keyedRow.Key != "k20")
                throw new InvalidOperationException("Ctrl+G không tới đúng exact key.");

            var canonicalBeforeRevert = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
            var originalTarget = keyedRow.Target;
            keyedRow.Target = "Bản nháp chưa lưu";
            var revertRowButton = window.FindName("RevertRowButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút hoàn tác dòng.");
            if (!revertRowButton.IsEnabled) throw new InvalidOperationException("Hoàn tác dòng phải bật khi dòng dirty.");
            revertRowButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (keyedRow.Target != originalTarget) throw new InvalidOperationException("Hoàn tác không trả bản vừa lưu.");
            if (!canonicalBeforeRevert.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
                throw new InvalidOperationException("Hoàn tác một dòng không được ghi hoặc reload canonical.");
            var rowsPerPage = window.FindName("RowsPerPageCombo") as ComboBox
                ?? throw new InvalidOperationException("Thiếu bộ chọn số hàng mỗi trang.");
            rowsPerPage.SelectedIndex = 2;
            window.UpdateLayout();
            if (scriptsGrid.Items.Count != 20) throw new InvalidOperationException($"Chọn 25 hàng phải hiện 20 dòng fixture, nhận {scriptsGrid.Items.Count}.");
            rowsPerPage.SelectedIndex = 1;
            var pageJumpButton = window.FindName("PageJumpButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút nhảy trang.");
            pageJumpButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            var pageJumpInput = window.FindName("PageJumpInput") as TextBox
                ?? throw new InvalidOperationException("Thiếu ô nhập trang.");
            pageJumpInput.Text = "2";
            var pageJumpConfirm = window.FindName("PageJumpConfirmButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút xác nhận nhảy trang.");
            pageJumpConfirm.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (scriptsGrid.Items.Count != 3) throw new InvalidOperationException($"Nhảy trang 2 phải hiện 3 hàng, nhận {scriptsGrid.Items.Count}.");
            var validationBorder = window.FindName("ValidationBorder") as Border;
            if (validationBorder is null || validationBorder.Visibility != Visibility.Collapsed)
                throw new InvalidOperationException("Dòng hợp lệ không được hiện khung lỗi trống.");
            var datasetFilter = window.FindName("DatasetFilter") as ComboBox
                ?? throw new InvalidOperationException("Thiếu bộ chọn bảng dịch.");
            if (datasetFilter.Items.Count != 2) throw new InvalidOperationException("Không nạp đủ bảng dịch.");
            datasetFilter.SelectedIndex = 1;
            window.UpdateLayout();
            var grid = window.FindName("CanonicalGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới canonical.");
            if (grid.Items.Count != 2) throw new InvalidOperationException("Đổi bảng dịch không nạp đúng CSV UI.");
            var pageText = window.FindName("PageText") as TextBlock
                ?? throw new InvalidOperationException("Thiếu nhãn trang.");
            if (!pageText.Text.Contains("Trang 1 / 1", StringComparison.Ordinal))
                throw new InvalidOperationException($"Phân trang sai: {pageText.Text}");
            var projectInfo = window.FindName("ProjectInfoText") as TextBox
                ?? throw new InvalidOperationException("Thiếu thông tin dự án.");
            if (!projectInfo.Text.Contains("Release receipt", StringComparison.Ordinal))
                throw new InvalidOperationException("Không hiển thị resource liên quan của dự án.");

            datasetFilter.SelectedIndex = 0;
            rowsPerPage.SelectedIndex = 0;
            pageJumpButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            pageJumpInput.Text = "2";
            pageJumpConfirm.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            scriptsGrid.SelectedItem = scriptsGrid.Items.Cast<TranslationRowViewModel>().Single(row => row.Key == "k15");
            (window.FindName("SearchBox") as TextBox)!.Text = "k";
            (window.FindName("StatusFilter") as ComboBox)!.SelectedIndex = 2;
            (window.FindName("GroupFilter") as ComboBox)!.SelectedIndex = 1;
            (window.FindName("MainTabs") as TabControl)!.SelectedIndex = 2;
            var fontScale = window.FindName("FontScaleCombo") as ComboBox
                ?? throw new InvalidOperationException("Thiếu bộ chọn cỡ chữ.");
            fontScale.SelectedItem = fontScale.Items.Cast<ComboBoxItem>().Single(item => item.Tag?.ToString() == "115");
            if (!CloseEnough(13 * 1.15, window.FontSize))
                throw new InvalidOperationException($"Cỡ chữ 115% sai: {window.FontSize}.");
            var listPane = window.FindName("ListPaneColumn") as ColumnDefinition
                ?? throw new InvalidOperationException("Thiếu cột pane danh sách.");
            var editorPane = window.FindName("EditorPaneColumn") as ColumnDefinition
                ?? throw new InvalidOperationException("Thiếu cột pane biên tập.");
            listPane.Width = new GridLength(3, GridUnitType.Star);
            editorPane.Width = new GridLength(2, GridUnitType.Star);
            scriptsGrid.Columns[2].Width = new DataGridLength(310);
            window.UpdateLayout();
            window.Left = 120;
            window.Top = 140;
            window.Width = 1180;
            window.Height = 760;
            window.Close();

            var restored = new MainWindow(Path.Combine(root, "project.json"));
            restored.Show();
            restored.UpdateLayout();
            if (!CloseEnough(120, restored.Left) || !CloseEnough(140, restored.Top)
                || !CloseEnough(1180, restored.Width) || !CloseEnough(760, restored.Height))
                throw new InvalidOperationException($"Không khôi phục bounds: {restored.Left},{restored.Top} {restored.Width}x{restored.Height}.");
            if ((restored.FindName("MainTabs") as TabControl)?.SelectedIndex != 2)
                throw new InvalidOperationException("Không khôi phục tab đang mở.");
            if ((restored.FindName("DatasetFilter") as ComboBox)?.SelectedIndex != 0)
                throw new InvalidOperationException("Không khôi phục bảng dịch đang mở.");
            if ((restored.FindName("SearchBox") as TextBox)?.Text != "k")
                throw new InvalidOperationException("Không khôi phục tìm kiếm.");
            if (((restored.FindName("StatusFilter") as ComboBox)?.SelectedItem as FilterOption)?.Value != "translated")
                throw new InvalidOperationException("Không khôi phục lọc trạng thái.");
            if (((restored.FindName("GroupFilter") as ComboBox)?.SelectedItem as FilterOption)?.Value != "scene")
                throw new InvalidOperationException("Không khôi phục lọc nhóm.");
            if (((restored.FindName("RowsPerPageCombo") as ComboBox)?.SelectedItem as ComboBoxItem)?.Tag?.ToString() != "10")
                throw new InvalidOperationException("Không khôi phục số hàng mỗi trang.");
            if (!(restored.FindName("PageText") as TextBlock)!.Text.Contains("Trang 2 / 2", StringComparison.Ordinal))
                throw new InvalidOperationException("Không khôi phục trang đang mở.");
            if ((restored.FindName("CanonicalGrid") as DataGrid)?.SelectedItem is not TranslationRowViewModel selected || selected.Key != "k15")
                throw new InvalidOperationException("Không khôi phục exact key đang chọn.");
            if ((restored.FindName("BookmarkPicker") as ComboBox)?.Items.Count != 1)
                throw new InvalidOperationException("Không khôi phục bookmark exact key từ session.");
            if (!CloseEnough(13 * 1.15, restored.FontSize)
                || ((restored.FindName("FontScaleCombo") as ComboBox)?.SelectedItem as ComboBoxItem)?.Tag?.ToString() != "115")
                throw new InvalidOperationException("Không khôi phục cỡ chữ 115% từ session.");
            var restoredListPane = restored.FindName("ListPaneColumn") as ColumnDefinition
                ?? throw new InvalidOperationException("Thiếu pane danh sách sau restore.");
            var restoredEditorPane = restored.FindName("EditorPaneColumn") as ColumnDefinition
                ?? throw new InvalidOperationException("Thiếu pane biên tập sau restore.");
            var restoredRatio = restoredListPane.ActualWidth / (restoredListPane.ActualWidth + restoredEditorPane.ActualWidth);
            if (Math.Abs(restoredRatio - 0.6) > 0.03)
                throw new InvalidOperationException($"Không khôi phục splitter 60/40: {restoredRatio:P1}.");
            var restoredGrid = restored.FindName("CanonicalGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu canonical grid sau restore.");
            if (!CloseEnough(310, restoredGrid.Columns[2].ActualWidth))
                throw new InvalidOperationException($"Không khôi phục cột Key 310px: {restoredGrid.Columns[2].ActualWidth}.");
            restored.WindowState = WindowState.Maximized;
            restored.Close();

            var maximized = new MainWindow(Path.Combine(root, "project.json"));
            maximized.Show();
            maximized.UpdateLayout();
            if (maximized.WindowState != WindowState.Maximized)
                throw new InvalidOperationException("Không khôi phục trạng thái maximize.");
            if ((maximized.FindName("MaximizeButton") as Button)?.Content?.ToString() != "❐")
                throw new InvalidOperationException("Glyph maximize không đồng bộ với trạng thái cửa sổ.");
            maximized.Close();
            app.Shutdown();
            Console.WriteLine("PASS: app startup and first layout");
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static bool CloseEnough(double expected, double actual) => Math.Abs(expected - actual) < 1.5;

    private static void AssertFullyVisible(Window window, FrameworkElement element)
    {
        var bounds = element.TransformToAncestor(window).TransformBounds(new Rect(element.RenderSize));
        if (element.ActualWidth <= 0 || element.ActualHeight <= 0 || bounds.Left < -0.5 || bounds.Top < -0.5
            || bounds.Right > window.ActualWidth + 0.5 || bounds.Bottom > window.ActualHeight + 0.5)
            throw new InvalidOperationException(
                $"{element.Name} bị cắt ở minimum layout: {bounds}; window={window.ActualWidth}x{window.ActualHeight}.");
    }

    private static string ReadClipboardTextWithRetry()
    {
        for (var attempt = 0; ; attempt++)
        {
            try { return Clipboard.GetText(); }
            catch (COMException) when (attempt < 9) { Thread.Sleep(50); }
        }
    }

    private static (int ExitCode, string Output) RunWriterLock(string command, string project)
    {
        using var process = StartWriterLockProcess(command, project);
        var output = process.StandardOutput.ReadToEnd();
        var error = process.StandardError.ReadToEnd();
        process.WaitForExit();
        return (process.ExitCode, output + error);
    }

    private static Process StartWriterLockHolder(string project) => StartWriterLockProcess("hold", project, "--seconds", "30");

    private static Process StartWriterLockProcess(string command, string project, params string[] extra)
    {
        var tool = FindAncestorFile(AppContext.BaseDirectory, "writer_lock.py");
        var start = new ProcessStartInfo("python")
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add(tool);
        start.ArgumentList.Add(command);
        start.ArgumentList.Add("--project");
        start.ArgumentList.Add(project);
        foreach (var item in extra) start.ArgumentList.Add(item);
        return Process.Start(start) ?? throw new InvalidOperationException("Không khởi động được writer_lock.py.");
    }

    private static string FindAncestorFile(string start, string name)
    {
        for (var directory = new DirectoryInfo(start); directory is not null; directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, name);
            if (File.Exists(candidate)) return candidate;
        }
        throw new FileNotFoundException($"Không tìm thấy {name} từ {start}.");
    }

    private static T? FindDescendant<T>(DependencyObject root) where T : DependencyObject
    {
        for (var index = 0; index < System.Windows.Media.VisualTreeHelper.GetChildrenCount(root); index++)
        {
            var child = System.Windows.Media.VisualTreeHelper.GetChild(root, index);
            if (child is T match) return match;
            var nested = FindDescendant<T>(child);
            if (nested is not null) return nested;
        }
        return null;
    }

    private static Button FindButton(DependencyObject root, string content)
    {
        for (var index = 0; index < System.Windows.Media.VisualTreeHelper.GetChildrenCount(root); index++)
        {
            var child = System.Windows.Media.VisualTreeHelper.GetChild(root, index);
            if (child is Button button && string.Equals(button.Content?.ToString(), content, StringComparison.Ordinal)) return button;
            try { return FindButton(child, content); }
            catch (InvalidOperationException) { }
        }
        throw new InvalidOperationException($"Không tìm thấy button {content}.");
    }

    private static bool ContainsText(DependencyObject root, string text)
    {
        if (root is TextBlock textBlock && textBlock.Text.Contains(text, StringComparison.Ordinal)) return true;
        for (var index = 0; index < System.Windows.Media.VisualTreeHelper.GetChildrenCount(root); index++)
        {
            if (ContainsText(System.Windows.Media.VisualTreeHelper.GetChild(root, index), text)) return true;
        }
        return false;
    }

    private static void AssertClipboardExhaustionIsLoggedSafely(MainWindow window, string root, TextBlock statusMessage)
    {
        var canonicalBefore = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
        var method = typeof(MainWindow).GetMethod("CopyQaContextWithStatus", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Thiếu seam CopyQaContextWithStatus để test clipboard bận.");
        Action<string> alwaysBusy = _ => throw new ExternalException("Clipboard đang bận.", BienTapTay.Core.ClipboardText.ClipboardCantOpen);
        method.Invoke(window, [alwaysBusy]);
        window.UpdateLayout();

        if (!statusMessage.Text.StartsWith("Không sao chép được context packet", StringComparison.Ordinal))
            throw new InvalidOperationException("Clipboard bận hết lượt phải báo lỗi tiếng Việt. Got: " + statusMessage.Text);
        if (!canonicalBefore.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
            throw new InvalidOperationException("Clipboard bận hết lượt không được đổi canonical.");
        if (Directory.Exists(Path.Combine(root, "app")))
            throw new InvalidOperationException("Chẩn đoán clipboard không được ghi vào app/.");
        AssertRedactedJsonlOnly(Path.Combine(root, "diagnostics"), "clipboard_copy");
    }

    private static void AssertExportFailureWritesRedactedDiagnostics(MainWindow window, string root, TextBlock statusMessage)
    {
        var canonicalBefore = File.ReadAllBytes(Path.Combine(root, "canonical.csv"));
        var method = typeof(MainWindow).GetMethod("ExportQaReportWithStatus", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Thiếu seam ExportQaReportWithStatus để test xuất báo cáo lỗi.");
        method.Invoke(window, [Path.Combine(root, "app", "qa-report.json")]);
        window.UpdateLayout();

        if (!statusMessage.Text.StartsWith("Không xuất được báo cáo QA", StringComparison.Ordinal))
            throw new InvalidOperationException("Xuất báo cáo thất bại phải báo lỗi tiếng Việt. Got: " + statusMessage.Text);
        if (Directory.Exists(Path.Combine(root, "app")))
            throw new InvalidOperationException("Xuất báo cáo bị từ chối không được tạo app/.");
        if (!canonicalBefore.SequenceEqual(File.ReadAllBytes(Path.Combine(root, "canonical.csv"))))
            throw new InvalidOperationException("Xuất báo cáo thất bại không được đổi canonical.");
        AssertRedactedJsonlOnly(Path.Combine(root, "diagnostics"), "qa_report_export");
    }

    private static void AssertRedactedJsonlOnly(string diagnosticsDirectory, string expectedOperation)
    {
        var logPath = Path.Combine(diagnosticsDirectory, "app.log");
        if (!File.Exists(logPath))
            throw new InvalidOperationException("Lỗi đã hiện cho người dùng phải ghi diagnostics/app.log.");
        var names = Directory.GetFiles(diagnosticsDirectory).Select(item => Path.GetFileName(item)).ToArray();
        foreach (var name in names)
            if (name is not ("app.log" or "app.log.1" or "app.log.2"))
                throw new InvalidOperationException("diagnostics/ chỉ được giữ app.log và 2 bản xoay vòng. Got: " + name);

        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var sawOperation = false;
        foreach (var line in File.ReadAllLines(logPath))
        {
            using var parsed = System.Text.Json.JsonDocument.Parse(line);
            var root = parsed.RootElement;
            if (root.GetProperty("result").GetString() != "error")
                throw new InvalidOperationException("Chỉ được ghi sự kiện lỗi vào diagnostics.");
            foreach (var field in new[] { "utc", "operation", "message", "exception_type" })
                if (!root.TryGetProperty(field, out _))
                    throw new InvalidOperationException("Dòng JSONL chẩn đoán thiếu trường " + field);
            if (root.EnumerateObject().Count() != 5)
                throw new InvalidOperationException("Dòng JSONL chẩn đoán không được kèm dump ngoài 5 trường đã thống nhất.");
            var message = root.GetProperty("message").GetString() ?? string.Empty;
            if (home.Length > 0 && message.Contains(home, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Chẩn đoán phải che đường dẫn thư mục người dùng.");
            if (message.Contains("Xin chào 1", StringComparison.Ordinal) || message.Contains("BIENTAPTAY-QA-CONTEXT", StringComparison.Ordinal))
                throw new InvalidOperationException("Chẩn đoán không được chứa nội dung canonical hoặc packet clipboard.");
            if (root.GetProperty("operation").GetString() == expectedOperation) sawOperation = true;
        }
        if (!sawOperation)
            throw new InvalidOperationException("Thiếu sự kiện chẩn đoán cho operation " + expectedOperation);
    }

    private static void AssertCorruptQaSidecarDoesNotBlockEditor(string templateRoot)
    {
        var corruptRoot = Path.Combine(Path.GetTempPath(), "bientaptay-app-smoke-qa-corrupt-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(corruptRoot);
        foreach (var name in new[] { "canonical.csv", "ui.csv", "glossary.csv", "pronouns.csv", "release.json", "project.json" })
            File.Copy(Path.Combine(templateRoot, name), Path.Combine(corruptRoot, name));
        var sidecar = Path.Combine(corruptRoot, "qa-decisions.json");
        var corruptBytes = "{not-json"u8.ToArray();
        File.WriteAllBytes(sidecar, corruptBytes);
        MainWindow? window = null;
        try
        {
            window = new MainWindow(Path.Combine(corruptRoot, "project.json"));
            window.Show();
            window.UpdateLayout();
            if (window.FindName("CanonicalGrid") is not DataGrid grid || grid.Items.Count == 0)
                throw new InvalidOperationException("Sidecar QA hỏng không được chặn nạp canonical.");
            var status = window.FindName("StatusMessageText") as TextBlock
                ?? throw new InvalidOperationException("Thiếu thanh trạng thái khi sidecar QA hỏng.");
            if (status.Text.IndexOf("biên tập canonical", StringComparison.Ordinal) < 0
                || status.Text.IndexOf("chỉ đọc", StringComparison.Ordinal) < 0)
                throw new InvalidOperationException("Phải hiện lỗi tiếng Việt: canonical vẫn sửa được, QA chỉ đọc. Got: " + status.Text);
            var banner = window.FindName("ConsistencyQaSidecarErrorText") as TextBlock
                ?? throw new InvalidOperationException("Thiếu cảnh báo cố định trên tab QA khi sidecar hỏng.");
            if (banner.Visibility != Visibility.Visible
                || banner.Text.IndexOf("sửa bên ngoài", StringComparison.Ordinal) < 0)
                throw new InvalidOperationException("Cảnh báo QA sidecar hỏng phải hiện trên tab QA.");
            var consistencyTab = window.FindName("ConsistencyQaTab") as TabItem
                ?? throw new InvalidOperationException("Thiếu tab QA khi sidecar hỏng.");
            var consistencyGrid = window.FindName("ConsistencyQaGrid") as DataGrid
                ?? throw new InvalidOperationException("Thiếu lưới QA khi sidecar hỏng.");
            var consistencyScan = window.FindName("ConsistencyQaScanButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút quét QA khi sidecar hỏng.");
            var qaSave = window.FindName("ConsistencyQaSaveDecisionButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút lưu quyết định QA khi sidecar hỏng.");
            var qaSaveNext = window.FindName("ConsistencyQaSaveNextButton") as Button
                ?? throw new InvalidOperationException("Thiếu nút Lưu & kế tiếp khi sidecar hỏng.");
            consistencyTab.IsSelected = true;
            consistencyScan.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (consistencyGrid.Items.Count == 0)
                throw new InvalidOperationException("Quét QA vẫn phải chạy khi sidecar hỏng.");
            consistencyGrid.SelectedIndex = 0;
            window.UpdateLayout();
            var readOnlyId = (consistencyGrid.SelectedItem as ConsistencyIssueViewModel)?.DecisionId
                ?? throw new InvalidOperationException("Thiếu cảnh báo QA khi sidecar hỏng.");
            if (qaSave.IsEnabled || qaSaveNext.IsEnabled)
                throw new InvalidOperationException("Nút lưu quyết định QA phải tắt khi sidecar hỏng.");
            qaSave.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            qaSaveNext.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (consistencyGrid.SelectedItem is not ConsistencyIssueViewModel stillSelected
                || !stillSelected.DecisionId.Equals(readOnlyId, StringComparison.Ordinal))
                throw new InvalidOperationException("Lưu thất bại/chỉ đọc không được chuyển cảnh báo QA.");
            if (!corruptBytes.SequenceEqual(File.ReadAllBytes(sidecar)))
                throw new InvalidOperationException("Không được ghi đè sidecar QA hỏng khi mở app hoặc bấm lưu.");
            if (Directory.GetFiles(corruptRoot, "qa-decisions.json*").Length != 1)
                throw new InvalidOperationException("Không được tạo bản sao/temp sidecar QA khi file hỏng.");
            var reportPath = Path.Combine(corruptRoot, "qa-report.json");
            InvokeExportQaReport(window, reportPath);
            window.UpdateLayout();
            if (!File.Exists(reportPath))
                throw new InvalidOperationException("Sidecar hỏng vẫn phải xuất được báo cáo QA.");
            if (!File.ReadAllText(reportPath).Contains("\"qa_decisions_available\": false", StringComparison.Ordinal))
                throw new InvalidOperationException("Báo cáo khi sidecar hỏng phải qa_decisions_available=false.");
            if (qaSave.IsEnabled || qaSaveNext.IsEnabled)
                throw new InvalidOperationException("Xuất báo cáo không được bật nút lưu khi sidecar hỏng.");
            if (!corruptBytes.SequenceEqual(File.ReadAllBytes(sidecar)))
                throw new InvalidOperationException("Xuất báo cáo không được đổi sidecar hỏng.");
            var corruptDiagnostics = Path.Combine(corruptRoot, "diagnostics");
            if (Directory.Exists(corruptDiagnostics))
            {
                AssertRedactedJsonlOnly(corruptDiagnostics, "qa_decision_save");
                if (!corruptBytes.SequenceEqual(File.ReadAllBytes(sidecar)))
                    throw new InvalidOperationException("Ghi chẩn đoán lỗi lưu không được đổi sidecar QA hỏng.");
                if (Directory.GetFiles(corruptRoot, "qa-decisions.json*").Length != 1)
                    throw new InvalidOperationException("Ghi chẩn đoán không được tạo bản sao sidecar QA.");
            }
            if (Directory.Exists(Path.Combine(corruptRoot, "app")))
                throw new InvalidOperationException("Chẩn đoán lỗi lưu QA không được ghi vào app/.");
        }
        finally
        {
            window?.Close();
            Directory.Delete(corruptRoot, true);
        }
    }

    private static void RewriteTarget(string path, string key, string target)
    {
        var document = BienTapTay.Core.CsvDocument.ParseBytes(File.ReadAllBytes(path));
        document.Rows.Single(row => row["key"] == key)["translation_vi"] = target;
        File.WriteAllText(path, document.Serialize(), new UTF8Encoding(false));
        File.SetLastWriteTimeUtc(path, File.GetLastWriteTimeUtc(path).AddSeconds(2));
    }

    private static void RewriteField(string path, string keyColumn, string key, string field, string value)
    {
        var document = BienTapTay.Core.CsvDocument.ParseBytes(File.ReadAllBytes(path));
        document.Rows.Single(row => row[keyColumn] == key)[field] = value;
        File.WriteAllText(path, document.Serialize(), new UTF8Encoding(false));
        File.SetLastWriteTimeUtc(path, File.GetLastWriteTimeUtc(path).AddSeconds(2));
    }

    private static void InvokeExportQaReport(MainWindow window, string destination)
    {
        var method = typeof(MainWindow).GetMethod("ExportQaReportTo", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Thiếu ExportQaReportTo.");
        method.Invoke(window, [destination]);
        window.UpdateLayout();
    }

    private static void InvokeShortcut(MainWindow window, Key key, ModifierKeys modifiers)
    {
        var method = typeof(MainWindow).GetMethod("ProcessShortcut", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Thiếu ProcessShortcut để gõ tắt QA khi TextBox đang focus.");
        method.Invoke(window, [key, modifiers]);
        window.UpdateLayout();
    }

    private static void InvokeExternalCheck(MainWindow window)
    {
        var method = typeof(MainWindow).GetMethod("CheckExternalChanges", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Thiếu external-change check.");
        method.Invoke(window, null);
        window.UpdateLayout();
    }
}
