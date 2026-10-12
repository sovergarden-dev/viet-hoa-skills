using System.Runtime.InteropServices;

namespace BienTapTay.Core;

public static class ClipboardText
{
    public const int ClipboardCantOpen = unchecked((int)0x800401D0);
    public const int DefaultAttempts = 10;
    public const int DefaultDelayMilliseconds = 50;
    public const int MaxTotalWaitMilliseconds = 500;

    public static int SetWithRetry(
        string text,
        Action<string> setter,
        Action<int> sleeper,
        int attempts = DefaultAttempts,
        int delayMilliseconds = DefaultDelayMilliseconds)
    {
        ArgumentNullException.ThrowIfNull(text);
        ArgumentNullException.ThrowIfNull(setter);
        ArgumentNullException.ThrowIfNull(sleeper);
        ArgumentOutOfRangeException.ThrowIfLessThan(attempts, 1);
        ArgumentOutOfRangeException.ThrowIfNegative(delayMilliseconds);

        var waited = 0;
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                setter(text);
                return attempt;
            }
            catch (ExternalException ex) when (
                ex.ErrorCode == ClipboardCantOpen
                && attempt < attempts
                && waited + delayMilliseconds <= MaxTotalWaitMilliseconds)
            {
                sleeper(delayMilliseconds);
                waited += delayMilliseconds;
            }
        }
    }
}
