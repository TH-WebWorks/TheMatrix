# Unity architecture

Recommended project structure, rendering stack, and systems for TRACE PROTOCOL.

## Tech stack

| Choice | Reason |
|--------|--------|
| **Unity 6** | Current LTS feature set, URP defaults |
| **URP** | Bloom, post-processing, shader graph rain |
| **TextMeshPro** | Katakana, `0`/`1`, monospace UI |
| **C#** | Gameplay; no pygame port |
| **Optional Python sidecar** | Spotify Jack In mode only |

Target resolution: **1920×1080** (matches TheMatrix TV use case).

## Project layout

```
Assets/
  Scenes/
    Attract.unity
    Game.unity
  Game/
    GameManager.cs          # State machine, score, waves
    TraceMeter.cs           # 0–100% trace timer
    RainController.cs       # Column spawn / shader params
    PlayerController.cs     # Move + bullet-time
    WaveDirector.cs         # Wave timing and difficulty curve
  Minigames/
    ConduitPuzzle.cs        # Bit-flip grid
    HexStrike.cs            # Tap changed bytes
    LyricBurst.cs           # Ordered lane input
    AgentChase.cs           # Bullet-time set-piece
  Rendering/
    MatrixRain.shader       # GPU rain (URP Shader Graph)
    PostProcessProfile.asset
  UI/
    PanelFrame.cs           # Dock-aesthetic chrome
    HighScoreTable.cs
    TraceBar.cs
  Audio/
    Sfx/
    MusicReactive.cs        # Optional beat detection
  Data/
    WaveConfig.asset        # ScriptableObject wave defs
    PuzzleLibrary.asset     # Offline puzzle seeds
```

## Core systems

### GameManager state machine

```
Attract → Playing → Minigame → Playing → … → GameOver → Attract
```

Responsibilities:

- Score and combo tracking
- Wave index and difficulty scaling
- Scene transitions (attract ↔ play)
- High score persistence (`PlayerPrefs` or JSON file)

### RainController

Two implementation tiers:

=== "Phase 1 — Good enough"

    Spawn pooled TextMeshPro glyphs in columns (mirror `RainColumn` logic).

=== "Phase 2 — Production"

    Full-screen URP shader with scrolling UVs, glyph atlas, and depth fade.

Column parameters from Python reference:

| Property | Range |
|----------|-------|
| `speed` | 2.5 – 9.0 |
| `length` | 8 – height/3 |
| `bright_head` | ~65% chance |
| Glyph mutation | ~2% per frame per column |

### ConduitPuzzle

```csharp
// Pseudocode — port of _bytes_to_bits + flip logic
public class ConduitPuzzle : MonoBehaviour
{
    int[] targetBits;
    int[] playerBits;
    float hammingThreshold;

  public void InitFromTexture(Texture2D art, int gridW, int gridH) { ... }
  public void FlipCell(int index) { ... }
  public bool IsSolved() => HammingDistance(playerBits, targetBits) <= hammingThreshold;
}
```

### TraceMeter

- Fills passively during gameplay
- Minigame outcomes modify rate
- Emits `OnTraceComplete` at 100%

## Rendering pipeline

```
Rain shader (background)
    ↓
Gameplay layer (player, obstacles, packets)
    ↓
UI overlay (panel chrome, trace bar, score)
    ↓
Post-process (bloom, green tint, film grain, CRT optional)
```

### Post-processing

| Effect | Purpose |
|--------|---------|
| Bloom | Green glyph glow |
| Color grading | Matrix green palette |
| Chromatic aberration | Bullet-time feedback |
| Vignette | Arcade cabinet feel |

Palette reference from `matrix_display.py`:

| Name | RGB |
|------|-----|
| HEAD | `(185, 255, 185)` |
| BRIGHT | `(80, 255, 120)` |
| MID | `(0, 170, 70)` |
| DIM | `(0, 55, 28)` |

## Panel UI reuse

Map `PanelDef` titles from `panels/registry.py` to in-game screens:

| Panel id | In-game use |
|----------|-------------|
| `conduit` | Decode minigame frame |
| `hex` | Hex strike frame |
| `status` | Trace / telemetry HUD |
| `log` | Run summary / game over |
| `lyrics` | Lyric burst overlay |

`draw_panel_shell()` chrome → `PanelFrame.cs` (veil, border, title, subtitle, minimize button optional).

## Spotify sidecar (optional)

```
┌─────────────┐     HTTP JSON      ┌──────────────┐
│ Python      │ ◄────────────────  │ Unity        │
│ spotify_    │   localhost:8765   │ JackInClient │
│ source.py   │                    │ .cs          │
└─────────────┘                    └──────────────┘
```

Expose: `track`, `artist`, `progress_ms`, `album_art_url`, `playing`.

Unity polls every 1–2s; never block gameplay on API failures.

## Build targets

| Platform | Priority |
|----------|----------|
| PC (Windows) | Primary arcade / itch.io |
| macOS | Secondary (matches TheMatrix audience) |
| WebGL | Defer (shader + sidecar complexity) |
