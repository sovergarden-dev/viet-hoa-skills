using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace PatchInstaller;

// Buildpatch v0.6.0 Standard Production Chassis
// Single Source of Truth layout, High-DPI PerMonitorV2 mathematical scaling, FontCache,
// and automated self-probing matrix. Wire project Engine and assets per game.

static class Engine {
    public static string Title => "Game Name - Việt hóa";
    public static string Build => "STEAM BUILD 00000000";
    public static string ExeName => "TargetGame.exe";

    public static string DetectDefaultPath() => @"C:\Program Files (x86)\Steam\steamapps\common\TargetGame";
    public static string Install(string root, Action<string>? status = null) => throw new InvalidOperationException("Wire Engine.Install for this project.");
    public static string Uninstall(string root, Action<string>? status = null) => throw new InvalidOperationException("Wire Engine.Uninstall for this project.");
}

static class FontCache {
    static readonly Dictionary<(string, float, FontStyle), Font> cache = new();
    public static Font Get(string family, float px, FontStyle style = FontStyle.Regular) {
        float rpx = (float)Math.Round(px, 1);
        var key = (family, rpx, style);
        if (!cache.TryGetValue(key, out var font)) {
            cache[key] = font = new Font(family, rpx, style, GraphicsUnit.Pixel);
        }
        return font;
    }
}

sealed class RainbowLink : LinkLabel {
    readonly System.Windows.Forms.Timer timer = new() { Interval = 32 };
    double phase;
    public RainbowLink() {
        LinkColor = ActiveLinkColor = VisitedLinkColor = FromHsv(0, .62, .96);
        timer.Tick += (_, _) => {
            phase += 0.045;
            LinkColor = FromHsv(phase * 60 % 360, .62, .96);
            ActiveLinkColor = VisitedLinkColor = LinkColor;
            Invalidate();
        };
        timer.Start();
    }
    static Color FromHsv(double h, double s, double v) {
        int hi = (int)Math.Floor(h / 60) % 6;
        double f = h / 60 - Math.Floor(h / 60);
        double p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
        var (r, g, b) = hi switch {
            0 => (v, t, p), 1 => (q, v, p), 2 => (p, v, t), 3 => (p, q, v), 4 => (t, p, v), _ => (v, p, q)
        };
        return Color.FromArgb((int)(r * 255), (int)(g * 255), (int)(b * 255));
    }
}

sealed class MainForm : Form {
    readonly Panel dock = new();
    readonly Label folder = new();
    readonly Label build = new();
    readonly TextBox path = new();
    readonly Button browse = new();
    readonly Button install = new();
    readonly Button uninstall = new();
    readonly Label status = new();
    readonly RainbowLink sig = new();
    readonly Button close = new();
    bool busy;
    float currentScale = 1.0f;
    readonly int forcedDpi;
    readonly Size? forcedWorkArea;
    bool applyingLayout;
    const int WS_MINIMIZEBOX = 0x00020000;

    [DllImport("user32.dll")] static extern bool ReleaseCapture();
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

    protected override CreateParams CreateParams {
        get {
            var cp = base.CreateParams;
            cp.Style |= WS_MINIMIZEBOX;
            return cp;
        }
    }

    public MainForm(int forcedDpi = 0, Size? forcedWorkArea = null) {
        this.forcedDpi = forcedDpi;
        this.forcedWorkArea = forcedWorkArea;

        // R1: Disable WinForms unmanaged AutoScaling completely
        AutoScaleMode = AutoScaleMode.None;
        ClientSize = new Size(1024, 576);

        Text = Engine.Title;
        FormBorderStyle = FormBorderStyle.None;
        MinimizeBox = true;
        MaximizeBox = false;
        ShowInTaskbar = true;
        StartPosition = FormStartPosition.CenterScreen;
        DoubleBuffered = true;
        KeyPreview = true;
        ResizeRedraw = true;
        BackgroundImageLayout = ImageLayout.Stretch;

        try {
            using var bsz = Assembly.GetExecutingAssembly().GetManifestResourceStream("PatchInstaller.background.png");
            if (bsz != null) BackgroundImage = Image.FromStream(bsz);
        } catch {}

        try {
            using var isz = Assembly.GetExecutingAssembly().GetManifestResourceStream("PatchInstaller.app.ico");
            if (isz != null) Icon = new Icon(isz);
        } catch {}

        close.Text = "×";
        close.FlatStyle = FlatStyle.Flat;
        close.TabStop = false;
        close.ForeColor = Color.FromArgb(230, 220, 210);
        close.BackColor = Color.FromArgb(120, 20, 20, 20);
        close.Cursor = Cursors.Hand;
        close.FlatAppearance.BorderSize = 0;
        close.Click += (_, _) => TryClose();
        Controls.Add(close);

        dock.BackColor = Color.FromArgb(236, 14, 18, 14);
        Controls.Add(dock);
        close.BringToFront();

        folder.Text = "THƯ MỤC CÀI GAME";
        folder.BackColor = Color.Transparent;
        folder.ForeColor = Color.FromArgb(224, 211, 194);
        folder.AutoSize = false;
        folder.UseMnemonic = false;

        build.Text = Engine.Build;
        build.ForeColor = Color.FromArgb(180, 195, 170);
        build.TextAlign = ContentAlignment.MiddleRight;
        build.AutoEllipsis = true;
        build.AutoSize = false;
        build.UseMnemonic = false;
        build.BackColor = Color.Transparent;

        path.BorderStyle = BorderStyle.FixedSingle;
        path.BackColor = Color.FromArgb(30, 36, 30);
        path.ForeColor = Color.FromArgb(240, 240, 240);
        path.Text = Engine.DetectDefaultPath();
        path.AutoSize = false;
        path.TextChanged += (_, _) => { path.SelectionStart = 0; path.ScrollToCaret(); };

        browse.Text = "DUYỆT";
        browse.FlatStyle = FlatStyle.Flat;
        browse.BackColor = Color.FromArgb(48, 58, 48);
        browse.ForeColor = Color.FromArgb(230, 230, 230);
        browse.Cursor = Cursors.Hand;
        browse.FlatAppearance.BorderSize = 0;
        browse.Click += (_, _) => PickFolder();

        uninstall.Text = "GỠ CÀI ĐẶT";
        uninstall.FlatStyle = FlatStyle.Flat;
        uninstall.BackColor = Color.FromArgb(70, 35, 35);
        uninstall.ForeColor = Color.FromArgb(240, 210, 210);
        uninstall.Cursor = Cursors.Hand;
        uninstall.FlatAppearance.BorderSize = 0;
        uninstall.Click += async (_, _) => await Run(false);

        install.Text = "CÀI ĐẶT";
        install.FlatStyle = FlatStyle.Flat;
        install.BackColor = Color.FromArgb(38, 92, 54);
        install.ForeColor = Color.FromArgb(255, 255, 255);
        install.Cursor = Cursors.Hand;
        install.FlatAppearance.BorderSize = 0;
        install.Click += async (_, _) => await Run(true);

        status.ForeColor = Color.FromArgb(203, 215, 196);
        status.BackColor = Color.Transparent;
        status.Text = "Sẵn sàng cài đặt";
        status.AutoSize = false;
        status.AutoEllipsis = true;
        status.UseMnemonic = false;

        sig.Text = "Syrin.online";
        sig.AutoSize = false;
        sig.BackColor = Color.Transparent;
        sig.LinkBehavior = LinkBehavior.HoverUnderline;
        sig.Cursor = Cursors.Hand;
        sig.LinkClicked += (_, _) => Process.Start(new ProcessStartInfo("https://syrin.online/") { UseShellExecute = true });

        dock.Controls.AddRange([folder, build, path, browse, install, uninstall, status, sig]);

        AcceptButton = install;
        path.TabIndex = 0;
        browse.TabIndex = 1;
        install.TabIndex = 2;
        uninstall.TabIndex = 3;

        MouseDown += Drag;
        KeyDown += (_, e) => { if (e.KeyCode == Keys.Escape && !busy) TryClose(); };

        ApplyCurrentDpiLayout();
        path.SelectionStart = 0;
        path.SelectionLength = 0;
    }

    protected override void OnHandleCreated(EventArgs e) {
        base.OnHandleCreated(e);
        if (Icon != null) {
            SendMessage(Handle, 0x0080, (IntPtr)0, Icon.Handle);
            SendMessage(Handle, 0x0080, (IntPtr)1, Icon.Handle);
        }
        ApplyCurrentDpiLayout();
        path.SelectionStart = 0;
        path.ScrollToCaret();
    }

    void ApplyCurrentDpiLayout(int? explicitDpi = null) {
        int dpi = explicitDpi ?? (forcedDpi > 0 ? forcedDpi : DeviceDpi);
        float rawScale = dpi / 96.0f;
        Rectangle workArea = forcedWorkArea.HasValue
            ? new Rectangle(Point.Empty, forcedWorkArea.Value)
            : Screen.FromControl(this).WorkingArea;

        // R2: Screen Clamping - never exceed 95% of available screen area
        float maxScaleW = (workArea.Width - 40) / 1024.0f;
        float maxScaleH = (workArea.Height - 60) / 576.0f;
        float clampedScale = Math.Min(rawScale, Math.Min(maxScaleW, maxScaleH));

        ApplyLayout(clampedScale);

        if (IsHandleCreated && !forcedWorkArea.HasValue) {
            Location = new Point(
                workArea.Left + (workArea.Width - ClientSize.Width) / 2,
                workArea.Top + (workArea.Height - ClientSize.Height) / 2
            );
        }
    }

    int S(float val) => (int)Math.Round(val * currentScale, MidpointRounding.AwayFromZero);

    public void ApplyLayout(float scale) {
        if (applyingLayout) return;
        applyingLayout = true;
        try {
            currentScale = scale;
            ClientSize = new Size(S(1024), S(576));

            close.Font = FontCache.Get("Segoe UI Semibold", 13f * scale, FontStyle.Bold);
            close.Bounds = new Rectangle(ClientSize.Width - S(44), S(8), S(36), S(34));

            // R5: Safe Action Dock 456 x 180 (generous padding for descenders and signature)
            dock.Bounds = new Rectangle(S(552), S(384), S(456), S(180));

            folder.Font = FontCache.Get("Segoe UI Semibold", 11.5f * scale, FontStyle.Bold);
            folder.Bounds = new Rectangle(S(18), S(14), S(170), S(20));

            build.Font = FontCache.Get("Segoe UI Semibold", 10.5f * scale, FontStyle.Bold);
            build.Bounds = new Rectangle(S(206), S(14), S(232), S(20));

            path.Font = FontCache.Get("Segoe UI", 12f * scale);
            path.Bounds = new Rectangle(S(18), S(38), S(314), S(30));

            browse.Font = FontCache.Get("Segoe UI Semibold", 12f * scale, FontStyle.Bold);
            browse.Bounds = new Rectangle(S(338), S(37), S(100), S(32));

            uninstall.Font = FontCache.Get("Segoe UI Semibold", 12f * scale, FontStyle.Bold);
            uninstall.Bounds = new Rectangle(S(18), S(78), S(120), S(40));

            install.Font = FontCache.Get("Segoe UI Semibold", 14f * scale, FontStyle.Bold);
            install.Bounds = new Rectangle(S(146), S(78), S(292), S(40));

            sig.Font = FontCache.Get("Segoe UI Semibold", 11.5f * scale, FontStyle.Bold);
            int sigWidth = TextRenderer.MeasureText(sig.Text, sig.Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width + S(10);
            sig.Bounds = new Rectangle(dock.Width - sigWidth - S(18), S(132), sigWidth, S(24));

            status.Font = FontCache.Get("Segoe UI", 11.5f * scale);
            int statusMaxW = Math.Max(S(96), dock.Width - S(18) - sigWidth - S(26));
            status.Bounds = new Rectangle(S(18), S(130), statusMaxW, S(28));

            Invalidate();
        } finally {
            applyingLayout = false;
        }
    }

    protected override void OnDpiChanged(DpiChangedEventArgs e) {
        base.OnDpiChanged(e);
        ApplyCurrentDpiLayout(e.DeviceDpiNew);
    }

    void TryClose() {
        if (busy) {
            MessageBox.Show(this, "Đang thực hiện thao tác cài đặt hoặc gỡ bỏ, vui lòng đợi.", Engine.Title, MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        Close();
    }

    protected override void OnFormClosing(FormClosingEventArgs e) {
        if (busy) {
            e.Cancel = true;
            MessageBox.Show(this, "Không thể đóng trong lúc đang cài đặt.", Engine.Title, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        base.OnFormClosing(e);
    }

    void Drag(object? sender, MouseEventArgs e) {
        if (e.Button == MouseButtons.Left) {
            ReleaseCapture();
            _ = SendMessage(Handle, 0xA1, (IntPtr)2, IntPtr.Zero);
        }
    }

    void PickFolder() {
        using var d = new FolderBrowserDialog {
            Description = "Chọn thư mục cài đặt game",
            ShowNewFolderButton = false,
            InitialDirectory = Directory.Exists(path.Text) ? path.Text : @"C:\Program Files (x86)\Steam\steamapps\common"
        };
        if (d.ShowDialog(this) == DialogResult.OK) {
            path.Text = d.SelectedPath;
            path.SelectionStart = 0;
            path.ScrollToCaret();
        }
    }

    async Task Run(bool isInstall) {
        string confirmMsg = isInstall ? "Cài đặt bản dịch vào thư mục game đã chọn?" : "Gỡ bỏ bản dịch và khôi phục toàn bộ tệp gốc?";
        if (MessageBox.Show(this, confirmMsg, Engine.Title, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;

        busy = true;
        install.Enabled = uninstall.Enabled = browse.Enabled = path.Enabled = false;

        try {
            var msg = await Task.Run(() => isInstall
                ? Engine.Install(path.Text, s => { try { if (IsHandleCreated && !IsDisposed) BeginInvoke(() => status.Text = s); } catch {} })
                : Engine.Uninstall(path.Text, s => { try { if (IsHandleCreated && !IsDisposed) BeginInvoke(() => status.Text = s); } catch {} }));
            status.Text = isInstall ? "Cài đặt hoàn tất" : "Đã gỡ cài đặt";
            MessageBox.Show(this, msg, "Syrin.online", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex) {
            status.Text = "Thất bại";
            MessageBox.Show(this, ex.Message, "Lỗi", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally {
            busy = false;
            install.Enabled = uninstall.Enabled = browse.Enabled = path.Enabled = true;
        }
    }

    public static string ProbeLayout(int dpi, int workW = 1920, int workH = 1080) {
        using var form = new MainForm(dpi, new Size(workW, workH));

        int clientW = form.ClientSize.Width;
        int clientH = form.ClientSize.Height;
        int dockW = form.dock.Width;
        int dockH = form.dock.Height;
        int sigRight = form.sig.Right;
        int sigBottom = form.sig.Bottom;
        int statusBottom = form.status.Bottom;
        int buildWidth = TextRenderer.MeasureText(form.build.Text, form.build.Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width;
        int buildBoxW = form.build.Width;
        float effectiveScale = form.currentScale;

        int folderTextW = TextRenderer.MeasureText(form.folder.Text, form.folder.Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width;
        int installTextW = TextRenderer.MeasureText(form.install.Text, form.install.Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width;
        int uninstallTextW = TextRenderer.MeasureText(form.uninstall.Text, form.uninstall.Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width;

        bool folderHFit = form.folder.Height >= form.folder.Font.Height + 2;
        bool buildHFit = form.build.Height >= form.build.Font.Height + 2;
        bool statusHFit = form.status.Height >= form.status.Font.Height + 2;

        // R6: Closed vocabulary check
        string[] statusVariants = [
            "Sẵn sàng cài đặt",
            "Đang kiểm tra...",
            "Đang sao lưu...",
            "Đang cài đặt...",
            "Hoàn tất cài đặt!",
            "Cài đặt hoàn tất",
            "Đang khôi phục...",
            "Đã gỡ cài đặt",
            "Thất bại"
        ];
        var statusFits = new List<object>();
        bool anyStatusClipped = false;
        foreach (var s in statusVariants) {
            int sw = TextRenderer.MeasureText(s, form.status.Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width;
            bool fits = sw <= form.status.Width;
            if (!fits) anyStatusClipped = true;
            statusFits.Add(new { text = s, width = sw, box_w = form.status.Width, fits });
        }

        bool clippedBottom = statusBottom > dockH - 4;
        bool clippedSig = sigRight > dockW - 4 || sigBottom > dockH - 4;
        bool clippedBuild = buildWidth > buildBoxW;
        bool statusIntersectsSig = form.status.Right > form.sig.Left;
        bool fitsWorkingArea = clientW <= workW && clientH <= workH;

        bool passed = !clippedBottom && !clippedSig && !clippedBuild && !anyStatusClipped && !statusIntersectsSig && fitsWorkingArea && folderHFit && buildHFit && statusHFit;

        var result = new {
            dpi = dpi,
            raw_scale = dpi / 96.0f,
            effective_scale = effectiveScale,
            working_area = new { w = workW, h = workH },
            client = new { w = clientW, h = clientH },
            dock = new { w = dockW, h = dockH },
            text_metrics = new {
                folder = new { text_w = folderTextW, box_w = form.folder.Width, fits = folderTextW <= form.folder.Width, h_fit = folderHFit },
                build = new { text_w = buildWidth, box_w = buildBoxW, fits = !clippedBuild, h_fit = buildHFit },
                install = new { text_w = installTextW, box_w = form.install.Width, fits = installTextW <= form.install.Width },
                uninstall = new { text_w = uninstallTextW, box_w = form.uninstall.Width, fits = uninstallTextW <= form.uninstall.Width },
                status_h_fit = statusHFit,
                status_variants = statusFits
            },
            status = new { bottom = statusBottom, max_allowed = dockH - 4, clipped = clippedBottom },
            signature = new { right = sigRight, bottom = sigBottom, max_w = dockW - 4, clipped = clippedSig },
            status_intersects_sig = statusIntersectsSig,
            fits_working_area = fitsWorkingArea,
            passed = passed
        };

        form.Close();
        return JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
    }

    public static void RenderProbePng(int dpi, int workW, int workH, string outPngPath) {
        using var form = new MainForm(dpi, new Size(workW, workH));
        form.Show();
        Application.DoEvents();
        using var bmp = new Bitmap(form.ClientSize.Width, form.ClientSize.Height);
        form.DrawToBitmap(bmp, new Rectangle(0, 0, form.ClientSize.Width, form.ClientSize.Height));
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPngPath))!);
        bmp.Save(outPngPath, System.Drawing.Imaging.ImageFormat.Png);
        form.Close();
    }
}

static class Program {
    [DllImport("kernel32.dll")] static extern bool AttachConsole(int dwProcessId);
    [DllImport("kernel32.dll")] static extern bool SetConsoleOutputCP(uint wCodePageID);

    [STAThread]
    static int Main(string[] args) {
        AttachConsole(-1);
        try { SetConsoleOutputCP(65001); Console.OutputEncoding = Encoding.UTF8; } catch {}

        ApplicationConfiguration.Initialize();

        if (args.Length >= 4 && args[0] == "--render-probe") {
            int dpi = int.Parse(args[1]);
            int workW = int.Parse(args[2]);
            int workH = int.Parse(args[3]);
            string outPath = args[4];
            MainForm.RenderProbePng(dpi, workW, workH, outPath);
            Console.WriteLine($"Rendered: {outPath}");
            return 0;
        }

        if (args.Length >= 2 && args[0] == "--layout-probe") {
            int dpi = int.Parse(args[1]);
            int workW = args.Length >= 3 ? int.Parse(args[2]) : 1920;
            int workH = args.Length >= 4 ? int.Parse(args[3]) : 1080;
            string json = MainForm.ProbeLayout(dpi, workW, workH);
            if (args.Length >= 5 && args[4] == "--out" && args.Length >= 6) {
                File.WriteAllText(args[5], json, new UTF8Encoding(false));
            }
            Console.WriteLine(json);
            using var doc = JsonDocument.Parse(json);
            return doc.RootElement.GetProperty("passed").GetBoolean() ? 0 : 1;
        }

        if (args.Length >= 1 && args[0] == "--layout-matrix") {
            string outReport = args.Length >= 2 ? args[1] : "dpi_matrix_report.json";
            int[] dpis = [96, 120, 144, 168, 192, 216, 240, 288];
            (int w, int h)[] resolutions = [
                (800, 600),
                (1024, 600),
                (1280, 720),
                (1366, 768),
                (1600, 900),
                (1920, 1080),
                (2560, 1440),
                (3840, 2160)
            ];

            var matrixResults = new List<JsonElement>();
            bool allPassed = true;

            foreach (var dpi in dpis) {
                foreach (var res in resolutions) {
                    string resJson = MainForm.ProbeLayout(dpi, res.w, res.h);
                    using var doc = JsonDocument.Parse(resJson);
                    bool passed = doc.RootElement.GetProperty("passed").GetBoolean();
                    if (!passed) allPassed = false;
                    matrixResults.Add(doc.RootElement.Clone());
                }
            }

            var summary = new {
                timestamp = DateTime.UtcNow.ToString("o"),
                total_cells = matrixResults.Count,
                all_passed = allPassed,
                matrix = matrixResults
            };
            string finalJson = JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(outReport, finalJson, new UTF8Encoding(false));
            Console.WriteLine($"DPI Matrix completed. Total: {matrixResults.Count}, All Passed: {allPassed}. Written to {outReport}");
            return allPassed ? 0 : 1;
        }

        if (args.Length >= 2 && args[0] is "--install" or "--uninstall") {
            try {
                Console.WriteLine(args[0] == "--install" ? Engine.Install(args[1]) : Engine.Uninstall(args[1]));
                return 0;
            }
            catch (Exception e) {
                Console.Error.WriteLine(e.Message);
                return 1;
            }
        }

        Application.Run(new MainForm());
        return 0;
    }
}
