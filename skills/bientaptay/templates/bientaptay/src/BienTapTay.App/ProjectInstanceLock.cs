using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace BienTapTay.App;

public sealed class ProjectInstanceLock : IDisposable
{
    private readonly Mutex _mutex;
    private readonly FileStream _writerLock;
    private readonly string _writerLockPath;
    private bool _disposed;

    private ProjectInstanceLock(Mutex mutex, FileStream writerLock, string writerLockPath)
    {
        _mutex = mutex;
        _writerLock = writerLock;
        _writerLockPath = writerLockPath;
    }

    public static ProjectInstanceLock? TryAcquire(string projectConfigPath) => TryAcquire(projectConfigPath, out _);

    public static ProjectInstanceLock? TryAcquire(string projectConfigPath, out string failureReason)
    {
        var fullPath = Path.GetFullPath(projectConfigPath);
        var normalizedPath = fullPath
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            .ToUpperInvariant();
        var identity = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(normalizedPath))).ToLowerInvariant();
        var mutex = new Mutex(initiallyOwned: true, $"Local\\BienTapTay.{identity}", out var createdNew);
        if (!createdNew)
        {
            mutex.Dispose();
            failureReason = "Dự án đang được mở bởi một instance bientaptay khác.";
            return null;
        }

        FileStream? writerLock = null;
        var writerLockPath = Path.Combine(Path.GetDirectoryName(fullPath)!, ".bientaptay.writer.lock");
        try
        {
            writerLock = new FileStream(writerLockPath, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.ReadWrite);
            if (writerLock.Length == 0) writerLock.SetLength(1);
            writerLock.Lock(0, 1);
            failureReason = string.Empty;
            return new ProjectInstanceLock(mutex, writerLock, writerLockPath);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            writerLock?.Dispose();
            try { mutex.ReleaseMutex(); }
            finally { mutex.Dispose(); }
            failureReason = $"Dự án đang được writer khác giữ hoặc không thể tạo shared lock: {writerLockPath}";
            return null;
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        try
        {
            try { _writerLock.Unlock(0, 1); }
            finally { _writerLock.Dispose(); }
        }
        finally
        {
            try { _mutex.ReleaseMutex(); }
            finally { _mutex.Dispose(); }
        }
        try { File.Delete(_writerLockPath); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
