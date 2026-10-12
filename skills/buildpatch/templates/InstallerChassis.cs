using System.Diagnostics;
using System.Runtime.InteropServices;

namespace PatchInstaller;

// Chassis only. Wire Engine.Install/Uninstall per project. Keep these numbers.
// Layout JSON: templates/installer-gui-layout.example.json
// ponytail: no payload/transaction here; add Hdp.cs + manifest after hashes freeze.

static class Engine {
 public static string Title => "Việt hóa";
 public static string Build => "STEAM BUILD  00000000";
 public static string Install(string root, Action<string>? status = null) => throw new InvalidOperationException("Wire Engine.Install for this game.");
 public static string Uninstall(string root, Action<string>? status = null) => throw new InvalidOperationException("Wire Engine.Uninstall for this game.");
}

sealed class RainbowLink : LinkLabel {
 readonly System.Windows.Forms.Timer timer = new() { Interval = 32 };
 double phase;
 public RainbowLink() {
  LinkColor = ActiveLinkColor = VisitedLinkColor = FromHsv(0, .62, .96);
  timer.Tick += (_, _) => { phase += .045; LinkColor = FromHsv(phase * 60 % 360, .62, .96); ActiveLinkColor = VisitedLinkColor = LinkColor; Invalidate(); };
  timer.Start();
 }
 static Color FromHsv(double h, double s, double v) {
  int hi = (int)Math.Floor(h / 60) % 6; double f = h / 60 - Math.Floor(h / 60), p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  var (r, g, b) = hi switch { 0 => (v, t, p), 1 => (q, v, p), 2 => (p, v, t), 3 => (p, q, v), 4 => (t, p, v), _ => (v, p, q) };
  return Color.FromArgb((int)(r * 255), (int)(g * 255), (int)(b * 255));
 }
}

sealed class MainForm : Form {
 readonly TextBox path = new();
 readonly Button install = new(), uninstall = new(), browse = new();
 readonly Label status = new(), build = new();
 bool busy;
 const int WS_MINIMIZEBOX = 0x00020000;
 [DllImport("user32.dll")] static extern bool ReleaseCapture();
 [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);
 protected override CreateParams CreateParams { get { var cp = base.CreateParams; cp.Style |= WS_MINIMIZEBOX; return cp; } }
 protected override void OnHandleCreated(EventArgs e) {
  base.OnHandleCreated(e);
  if (Icon != null) {
   SendMessage(Handle, 0x0080, (IntPtr)0, Icon.Handle);
   SendMessage(Handle, 0x0080, (IntPtr)1, Icon.Handle);
  }
 }

 public MainForm() {
  Text = Engine.Title;
  ClientSize = new(1024, 576);
  FormBorderStyle = FormBorderStyle.None;
  MinimizeBox = true; MaximizeBox = false; ShowInTaskbar = true;
  StartPosition = FormStartPosition.CenterScreen;
  Font = new Font("Segoe UI", 10f);
  AutoScaleMode = AutoScaleMode.Dpi;
  DoubleBuffered = true; KeyPreview = true;
  BackgroundImageLayout = ImageLayout.Stretch;
  try {
   using var isz = System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream("PatchInstaller.app.ico");
   if (isz != null) { Icon = new Icon(isz); }
  } catch {}

  var close = new Button { Text = "×", Bounds = new Rectangle(976, 8, 40, 36), FlatStyle = FlatStyle.Flat, TabStop = false };
  close.FlatAppearance.BorderSize = 0; close.Click += (_, _) => TryClose(); Controls.Add(close);

  var dock = new Panel { Bounds = new Rectangle(556, 400, 444, 166), BackColor = Color.FromArgb(236, 14, 10, 10) };
  Controls.Add(dock); close.BringToFront();

  var folder = new Label { Text = "THƯ MỤC GAME", AutoSize = true, Location = new Point(18, 51), BackColor = Color.Transparent, ForeColor = Color.FromArgb(224, 211, 194) };
  build.Text = Engine.Build; build.ForeColor = Color.FromArgb(178, 166, 151); build.Font = new Font("Segoe UI Semibold", 7.6f);
  build.TextAlign = ContentAlignment.MiddleRight; build.AutoEllipsis = true; build.BackColor = Color.Transparent;
  build.SetBounds(276, 51, 150, 16);
  path.SetBounds(18, 70, 302, 31); path.Font = new Font("Segoe UI", 9f); path.BorderStyle = BorderStyle.FixedSingle;
  browse.Text = "DUYỆT"; browse.SetBounds(326, 69, 100, 33); browse.Click += (_, _) => PickFolder();
  uninstall.Text = "GỠ CÀI ĐẶT"; uninstall.SetBounds(18, 109, 116, 36); uninstall.Click += async (_, _) => await Run(false);
  install.Text = "CÀI ĐẶT"; install.SetBounds(142, 109, 284, 37); install.Click += async (_, _) => await Run(true);
  status.SetBounds(18, 150, 240, 14); status.ForeColor = Color.FromArgb(203, 191, 176); status.BackColor = Color.Transparent; status.Text = "Sẵn sàng";
  var sig = new RainbowLink { Text = "Syrin.online", AutoSize = true, BackColor = Color.Transparent, Font = new Font("Segoe UI Semibold", 8.2f), Location = new Point(378, 150), LinkBehavior = LinkBehavior.HoverUnderline };
  sig.LinkClicked += (_, _) => Process.Start(new ProcessStartInfo("https://syrin.online/") { UseShellExecute = true });
  dock.Controls.AddRange([folder, build, path, browse, install, uninstall, status, sig]);

  AcceptButton = install; path.TabIndex = 0; browse.TabIndex = 1; install.TabIndex = 2; uninstall.TabIndex = 3;
  MouseDown += Drag;
  KeyDown += (_, e) => { if (e.KeyCode == Keys.Escape && !busy) TryClose(); };
 }

 void TryClose() { if (busy) { MessageBox.Show(this, "Đang có thao tác chạy.", Engine.Title); return; } Close(); }
 protected override void OnFormClosing(FormClosingEventArgs e) { if (busy) { e.Cancel = true; MessageBox.Show(this, "Không thể đóng trong lúc cài hoặc gỡ.", Engine.Title); } base.OnFormClosing(e); }
 void Drag(object? sender, MouseEventArgs e) { if (e.Button == MouseButtons.Left) { ReleaseCapture(); _ = SendMessage(Handle, 0xA1, (IntPtr)2, IntPtr.Zero); } }
 void PickFolder() { using var d = new FolderBrowserDialog { Description = "Chọn thư mục game", ShowNewFolderButton = false }; if (d.ShowDialog(this) == DialogResult.OK) path.Text = d.SelectedPath; }
 async Task Run(bool add) {
  if (MessageBox.Show(this, add ? "Cài bản dịch lên thư mục đã chọn?" : "Gỡ Việt hóa và khôi phục file gốc?", Engine.Title, MessageBoxButtons.YesNo) != DialogResult.Yes) return;
  busy = true; install.Enabled = uninstall.Enabled = browse.Enabled = false;
  try { var msg = await Task.Run(() => add ? Engine.Install(path.Text) : Engine.Uninstall(path.Text)); status.Text = add ? "Hoàn tất" : "Đã gỡ"; MessageBox.Show(this, msg, "Syrin.online"); }
  catch (Exception ex) { status.Text = "Thất bại"; MessageBox.Show(this, ex.Message, "Không thể hoàn tất"); }
  finally { busy = false; install.Enabled = uninstall.Enabled = browse.Enabled = true; }
 }
}

static class Program {
 [STAThread] static int Main(string[] args) {
  try { Console.OutputEncoding = System.Text.Encoding.UTF8; } catch {}
  if (args.Length >= 2 && args[0] is "--install" or "--uninstall") {
   try { Console.WriteLine(args[0] == "--install" ? Engine.Install(args[1]) : Engine.Uninstall(args[1])); return 0; }
   catch (Exception e) { Console.Error.WriteLine(e.Message); return 1; }
  }
  ApplicationConfiguration.Initialize(); Application.Run(new MainForm()); return 0;
 }
}
