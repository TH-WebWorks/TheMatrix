# Display & monitors

TheMatrix supports windowed, borderless fullscreen, and legacy exclusive fullscreen on any connected monitor.

## Default behavior

- **Windowed** at 1920×1080 by default
- Auto-scales rain glyph size on 4K displays
- Borderless fullscreen recommended for TV / second monitor use

## List monitors

```bash
python3 main.py --list-displays
```

Output shows each monitor index and resolution. Your TV is often index `1` or `2`.

## Target a specific monitor

=== "Borderless fullscreen (recommended)"

    ```bash
    python3 main.py --display 1 --mode borderless
    ```

=== "Windowed on a monitor"

    ```bash
    python3 main.py --display 1 --mode windowed --window-size 1920x1080
    ```

=== "Exclusive fullscreen (legacy)"

    ```bash
    python3 main.py --display 1 --exclusive
    ```

## Toggle fullscreen in-app

Press ++f11++ to switch between windowed and borderless fullscreen without restarting.

## Settings launcher

Open the GUI launcher to pick monitor, mode, and resolution:

```bash
python3 main.py --settings
```

Use this to quickly target a third monitor — choose monitor `[2]` if listed that way.

## Display modes

| Mode | Flag | Description |
|------|------|-------------|
| Windowed | `--mode windowed` | Resizable window at `--window-size` |
| Borderless | `--mode borderless` | Borderless fullscreen on chosen monitor |
| Exclusive | `--exclusive` | Legacy exclusive fullscreen |

## Custom window size

```bash
python3 main.py --window-size 1600x900
```

## Rain glyph size

Override auto-scaling:

```bash
python3 main.py --size 18
```

## macOS Retina notes

Matrix rain uses a system TTF on macOS (Arial Unicode / Hiragino) because pygame's default font path cannot render Japanese glyphs on Retina displays. See [macOS](../platforms/macos.md).

## Windows DPI

`display_setup.py` enables Windows DPI awareness so monitor coordinates and scaling are correct on high-DPI displays.
