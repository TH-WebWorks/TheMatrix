# Game mechanics

How TheMatrix pygame features map to arcade gameplay, and how each minigame works.

## Python → arcade mapping

| Existing feature | Arcade mechanic |
|------------------|-----------------|
| `RainColumn` + glyph stream | Obstacles, collectible packets, background shader |
| `_conduit_payload()` → bytes → bits | Puzzle seed — each wave gets a unique bit grid |
| Album art → `_surface_to_reveal_bits()` | “Reveal the face” — flip bits to match silhouette |
| HEX panel (bright = changed bytes) | Whack-a-mole on corrupt memory addresses |
| `_decode_answer()` / synced lyrics | Bonus round target text |
| Session log / rate-limit backoff | “TRACE AT 87%” — diegetic difficulty meter |
| Dock panel chrome | Between-wave upgrade shop UI |
| News / weather inject | Procedural glyph glitch events mid-wave |

The **CONDUIT** panel is the signature hook — live binary decode as gameplay.

## Source code references

Key logic in the current Python codebase:

| Function / module | Role |
|-------------------|------|
| `matrix_display.RainColumn` | Falling glyph columns (speed, length, mutation) |
| `matrix_display._conduit_payload()` | UTF-8 byte stream of on-screen signal |
| `matrix_display._bytes_to_bits()` | Byte stream → row-major bit array |
| `matrix_display._surface_to_reveal_bits()` | Image → brightness threshold → bits |
| `matrix_display._decode_answer()` | Target string for decode rounds |
| `panels/hex_dump.format_hex_lines()` | xxd-style rows for hex minigame |
| `lyrics_source` | Synced lyric lines for burst bonus |

Reimplement these ideas in C# — do not port pygame directly.

---

## CONDUIT flip (core minigame)

The primary skill check between waves.

| Field | Detail |
|-------|--------|
| **Target** | Album art, agent face, or symbol rendered as bits |
| **Player grid** | Tap to toggle `0` ↔ `1` |
| **Timer** | Trace meter rises while playing |
| **Win** | Hamming distance ≤ threshold |
| **Lose** | Trace hits 100% |

**Scoring:** `base × speed_bonus × (1 - errors / flips)`

### Bit conversion (port from Python)

```python
# matrix_display.py — reference for Unity port
def _bytes_to_bits(data: bytes) -> list[int]:
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits
```

```python
# Image → bits (simplified)
def _surface_to_reveal_bits(surface, gw, gh) -> list[int]:
    # Bright pixels → 1, dim → 0
    # Threshold varies slightly per cell for dithering
```

---

## HEX strike (secondary minigame)

Scroll an xxd-style hex dump. Random bytes **flash bright** (matching the HEX panel’s changed-byte highlight). Player shoots the offset before it fades.

| Action | Result |
|--------|--------|
| Hit correct offset | Points + trace meter drops |
| Hit wrong byte | Trace spike |
| Miss timeout | Small trace increase |

Row format matches `format_hex_lines()`:

```
OFFSET   HEX PART                         ASCII
000000   4a 6f 68 6e 20 44 6f 65 ...     John Doe...
```

---

## Lyric burst (bonus round)

Optional **Jack In** mode when Spotify sidecar is connected.

1. Current synced lyric line splits into 4–8 chunks
2. Chunks fall in lanes (Guitar Hero–style)
3. Hit in order → **COMBO × N**
4. Miss → agent step closer / trace bump

Uses the same lyric window logic as the **L** dock panel (`current_lyric_window`).

---

## Agent chase (set-piece)

Every 5 waves (or on trace milestones), trigger a bullet-time hallway sequence:

- `Time.timeScale` lerps down (e.g. `0.2`)
- Chromatic aberration + rain streak intensifies
- Dodge preset obstacle patterns
- Success = large trace reset + bonus

---

## Trace meter

Diegetic difficulty tied to the **S** (status) and **G** (session log) panels.

| Event | Trace change |
|-------|----------------|
| Passive (during waves) | +1–3% per second (scales with wave) |
| CONDUIT success | −15–25% |
| HEX miss | +5% |
| Lyric combo | −5% per perfect segment |
| Agent touch | +20% or instant game over |

Display as panel-style telemetry: `TRACE ████████░░░░░░░░  62%`

---

## Jack In mode (optional, Phase 5)

Arcade mode works **without** Spotify. Jack In is a score multiplier layer.

| Component | Approach |
|-----------|----------|
| **Auth** | Keep Python sidecar (`spotify_source.py`) — Unity polls `localhost` JSON |
| **Puzzle seed** | Track name / artist bytes → `_conduit_payload` equivalent |
| **Target image** | Album art URL → bit grid via `_surface_to_reveal_bits` logic |
| **Lyrics** | LRCLIB sync for burst bonus |

Avoid implementing Spotify OAuth inside Unity.
