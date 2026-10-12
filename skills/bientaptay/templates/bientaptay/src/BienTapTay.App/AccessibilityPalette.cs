using System.Windows;
using System.Windows.Markup;
using System.Windows.Media;

namespace BienTapTay.App;

public static class AccessibilityPalette
{
    public static Color ColorFor(string role, bool highContrast)
    {
        if (highContrast)
        {
            return role switch
            {
                "Canvas" or "Surface" or "Window" or "DangerSurface" or "WarningSurface" => SystemColors.WindowColor,
                "SurfaceRaised" or "Control" => SystemColors.ControlColor,
                "Hover" or "Accent" or "Selection" or "Success" => SystemColors.HighlightColor,
                "Border" or "Text" or "WindowText" or "DangerText" => SystemColors.WindowTextColor,
                "HighlightText" => SystemColors.HighlightTextColor,
                "Muted" => SystemColors.GrayTextColor,
                "Danger" or "DangerBorder" or "Warning" => SystemColors.HotTrackColor,
                "Overlay" => Color.FromArgb(0xD9, SystemColors.WindowColor.R, SystemColors.WindowColor.G, SystemColors.WindowColor.B),
                _ => throw new ArgumentOutOfRangeException(nameof(role), role, "Vai trò màu không hợp lệ."),
            };
        }

        return role switch
        {
            "Canvas" => Color.FromRgb(0x11, 0x13, 0x18),
            "Surface" or "Window" => Color.FromRgb(0x18, 0x1B, 0x21),
            "SurfaceRaised" or "Control" => Color.FromRgb(0x20, 0x24, 0x2C),
            "Hover" => Color.FromRgb(0x2A, 0x31, 0x40),
            "Border" => Color.FromRgb(0x3A, 0x41, 0x50),
            "Text" or "WindowText" or "HighlightText" => Color.FromRgb(0xF0, 0xF2, 0xF5),
            "Muted" => Color.FromRgb(0xA7, 0xAF, 0xBD),
            "Accent" => Color.FromRgb(0x5B, 0x8D, 0xEF),
            "Danger" => Color.FromRgb(0xEF, 0x6A, 0x77),
            "Success" => Color.FromRgb(0x67, 0xC9, 0x9A),
            "Selection" => Color.FromRgb(0x29, 0x41, 0x6D),
            "Warning" => Color.FromRgb(0xE8, 0xBC, 0x5C),
            "DangerSurface" => Color.FromRgb(0x3A, 0x22, 0x29),
            "DangerBorder" => Color.FromRgb(0x78, 0x40, 0x4C),
            "DangerText" => Color.FromRgb(0xFF, 0xB3, 0xBC),
            "WarningSurface" => Color.FromRgb(0x3A, 0x34, 0x22),
            "Overlay" => Color.FromArgb(0xB3, 0, 0, 0),
            _ => throw new ArgumentOutOfRangeException(nameof(role), role, "Vai trò màu không hợp lệ."),
        };
    }
}

[MarkupExtensionReturnType(typeof(Color))]
public sealed class AccessibilityColorExtension : MarkupExtension
{
    public string Role { get; set; } = string.Empty;

    public override object ProvideValue(IServiceProvider serviceProvider) =>
        AccessibilityPalette.ColorFor(Role, SystemParameters.HighContrast);
}
