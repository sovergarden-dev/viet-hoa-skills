# Installer GUI — contrast, legibility, translucency, test-harness hygiene

Learned building a borderless 1024x576 artwork-backed installer (WinForms, .NET, C#).
Every rule below came from a real user rejection, not a theory.

## 1. Never let the system theme dictate control colours
On a dark Windows theme the default WinForms buttons render dark-on-dark.
Symptom the user reports: *"the text is the same colour as the background, very hard to read"*.
Always set, for every button:

```csharp
b.FlatStyle = FlatStyle.Flat;
b.BackColor = Color.FromArgb(...);           // explicit
b.ForeColor = Color.FromArgb(248, 242, 246); // near-white on a dark base
b.FlatAppearance.BorderSize = 1;
b.FlatAppearance.BorderColor = Color.FromArgb(150, 108, 132);
b.FlatAppearance.MouseOverBackColor = ...;   // hover + pressed, or the theme takes over
b.FlatAppearance.MouseDownBackColor = ...;
```

Primary action = the accent sampled from the artwork (e.g. magenta `232,74,150`) with dark text;
secondary = dark base with light text. Build a small `void Style(Button b, bool primary)` helper and
call it on every button so no control is left on the default path.

## 2. Give each label a box at least 1.5x its font size
A 10 pt label in a 14 px-high box loses the descenders of Vietnamese letters.
Symptom: *"'Sẵn sàng' is clipped at the bottom"*.
9.5 pt -> 22 px high box; 10 pt -> 24 px. Also set `AutoSize = false` when the box is fixed, and
leave at least the font height of clearance to the parent's bottom edge.

## 3. Paint the panel tint exactly once — in the form, never in the panel
A plain `Panel` with an alpha `BackColor` paints opaque. Give it a transparent background instead,
and paint the tint once, in the form, behind every control:

```csharp
sealed class GlassPanel : Panel
{
    public GlassPanel()
    {
        SetStyle(ControlStyles.SupportsTransparentBackColor | ControlStyles.OptimizedDoubleBuffer, true);
        BackColor = Color.Transparent;          // the tint is NOT painted here
    }
}

static readonly Rectangle DockRect = new(24, 378, 444, 176);   // mirrors the layout JSON
static readonly Color DockTint = Color.FromArgb(184, 10, 8, 14);
static readonly Color DockEdge = Color.FromArgb(165, 236, 92, 160);

protected override void OnPaint(PaintEventArgs e)
{
    base.OnPaint(e);                                   // artwork already painted
    using (var fill = new SolidBrush(DockTint))
        e.Graphics.FillRectangle(fill, DockRect);      // ONE alpha composite
    using var border = new Pen(DockEdge);
    e.Graphics.DrawRectangle(border, DockRect.X, DockRect.Y, DockRect.Width - 1, DockRect.Height - 1);
    using var inner = new Pen(Color.FromArgb(60, 0, 0, 0));
    e.Graphics.DrawRectangle(inner, DockRect.X + 1, DockRect.Y + 1, DockRect.Width - 3, DockRect.Height - 3);
}
```

**Do not also paint the alpha in the panel.** WinForms already composites a panel's own
translucent `BackColor` against its parent; filling the same rectangle again in `OnPaint`
composites it twice and crushes the artwork. The measured symptom: only ~23% of the artwork's
texture survived where ~56% was intended, and the panel darkened the image by ~24/255.

Verify numerically, never by opinion. Sample a strip of the panel that contains **no control**
(measure the free bands: above the first row of controls, and the panel's right margin), in both
the screenshot and the source artwork, and compare standard deviations:

```
rendered sd / artwork sd  must equal  (255 - alpha) / 255
```

A ratio far below that means the tint is being composited more than once.

### Choosing the alpha (what the user actually means)

| User says | alpha | opaque | artwork texture kept |
|---|---|---|---|
| "hơi nhìn thấy hình nền" / *slightly* see-through | **180-190** | ~70-72% | ~28% |
| clearly a glass plate | 140-160 | ~55-61% | ~40-45% |
| "hoàn toàn trong suốt" (rarely wanted) | 100-120 | ~40-47% | ~53-60% |

"Hơi trong" means a *plate you can still see the artwork through* — not a fully transparent
overlay. Two extra checks settle it:

- **Separation**: mean brightness just outside the panel minus just inside; at alpha 184 this was
  `27.8 -> 14.2`, i.e. `+13.6`. If separation is near zero, the panel melts into a dark background
  however translucent it is, and the user will ask for *less* transparency.
- **Edge**: a hairline border in the artwork accent plus a 1px dark inner line. Without it, a dark
  translucent panel over a dark artwork has no visible boundary at all.

Every label/input placed on the panel needs `BackColor = Color.Transparent`.

## 4. Text inputs inside a dark dock need both colours
Unset, a TextBox renders as a white box with dark text and breaks the contrast rhythm:
set `BackColor` (e.g. `30,20,30`) and `ForeColor` (near-white) together.

## 5. Signature sizing
8 pt reads as a faint watermark and the user calls it *"too small"*.
Accepted: **12-12.5 pt**, bottom-right, with a declared box fully inside the client margin
(`x + w <= client.w - 8`, `y + h <= client.h - 8`) so the layout gate keeps passing.
Anchor it with `AutoSize = true` and let the declared box bound it; re-check against DPI scaling.

## 6. Acceptance loop for any GUI change
1. `dotnet publish -c Release -r win-x64 --self-contained false -o publish`
2. launch, `SetForegroundWindow`, `GetWindowRect` + `CopyFromScreen`, save PNG at native client size
3. read the PNG back (zoom crops: the dock region and the signature region) and check contrast,
   clipping, translucency, and that no protected artwork region is covered
4. `verify_installer_gui_layout.py <layout.json> --csharp Program.cs --screenshot gui-1024x576.png`
   must print `screenshot_ok` after every colour/size change
5. only then re-run the installer test suite — the shipped EXE must be the tested EXE

The loop is cheap (publish + screenshot + gate is well under two minutes). Iterate on the picture,
not on the description; every complaint in this file was visible in a screenshot before it was fixed.

## 7. Test-harness hygiene: never feed the sandbox from the live install
Once the release is installed into the live game, that tree is no longer the vanilla source.
Building the sandbox by hardlinking `GAME/Pack/*` then produces bogus FAILs
(`refused after 4 steps; 1/18 files still original`) because the guard correctly rejects a
patched source. Keep the captured Steam originals in a fixed directory on the **same volume** as
the sandbox (hardlinks cannot cross volumes), e.g. `D:\vh_vanilla`, and hardlink the sandbox from
there. Recreate it from the captured originals when missing; delete it afterwards.
