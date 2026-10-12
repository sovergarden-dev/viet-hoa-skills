using System.IO;
using System.Windows;

namespace BienTapTay.App;

public partial class App : Application
{
    private ProjectInstanceLock? _projectLock;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        var config = Path.GetFullPath(e.Args.FirstOrDefault() ?? Path.Combine(AppContext.BaseDirectory, "project.json"));
        if (!File.Exists(config))
        {
            MessageBox.Show($"Không tìm thấy cấu hình dự án:\n{config}", "bientaptay", MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(2);
            return;
        }
        _projectLock = ProjectInstanceLock.TryAcquire(config, out var lockFailure);
        if (_projectLock is null)
        {
            MessageBox.Show(
                $"{lockFailure}\n{config}\n\nĐóng writer kia trước khi mở lại.",
                "bientaptay",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            Shutdown(3);
            return;
        }
        try
        {
            new MainWindow(config).Show();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Không thể mở dự án", MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(1);
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _projectLock?.Dispose();
        _projectLock = null;
        base.OnExit(e);
    }
}
