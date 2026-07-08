# Controls & keybinds

TheMatrix is designed for keyboard and mouse control from across the room (e.g. on a 4K TV).

## Global keys

| Key | Action |
|-----|--------|
| ++esc++ | Quit the application |
| ++f1++ | Open the settings launcher (monitor, Spotify, resolution) |
| ++f11++ | Toggle windowed ↔ borderless fullscreen |

## Spotify playback

Requires Spotify desktop open with music playing and a [Premium](https://www.spotify.com/premium) account for API playback control.

| Key | Action |
|-----|--------|
| ++space++ | Play / pause |
| ++left++ | Previous track |
| ++right++ | Next track |

## Dock panel keys

Press a letter key or click a tab along the bottom-left rain area. Only **one panel** is open at a time.

| Key | Panel |
|-----|-------|
| ++l++ | Lyrics |
| ++h++ | Hex dump |
| ++b++ | Conduit (binary decode) |
| ++s++ | Status / telemetry |
| ++m++ | Track metadata |
| ++t++ | Local clock |
| ++n++ | News headlines |
| ++a++ | MacRumors ads |
| ++q++ | Up next queue |
| ++d++ | Spotify Connect devices |
| ++w++ | Weather feed |
| ++g++ | Session log |

See [Dock panels](panels.md) for details on each panel.

## Panel interaction

| Input | Action |
|-------|--------|
| Mouse wheel | Scroll panel content |
| Click **−** | Minimize (close) the active panel |
| Click tab | Open that panel (closes any other) |

## On-screen keymap

A keybind table is drawn in the rain stream area. It updates based on whether Spotify mode is active.

## Rain-only mode

When running with `--no-spotify`, playback keys (++space++, ++left++, ++right++) have no effect. Panels **M**, **Q**, and **D** require Spotify; all others work without it.
