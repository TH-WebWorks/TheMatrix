# TRACE PROTOCOL — game overview

A design for turning TheMatrix from a pygame ambient display into a **Unity arcade game**.

## Pitch

**TRACE PROTOCOL** is a fast arcade game where you play an operator inside the simulation. Agents are tracing your connection. Survive waves by decoding the signal before the trace completes.

> *Pac-Man meets hacking — dodge glyph rain, flip bits, match hex, jack out before the trace hits 100%.*

The pygame app is a **terminal**. Unity turns it into a **cabinet**.

## Arcade loop

Typical session: **30–90 seconds** per run.

```
ATTRACT MODE → INSERT COIN → WAVE → MINI-GAME → WAVE → … → TRACE COMPLETE → HIGH SCORE
```

| Phase | What happens |
|-------|----------------|
| **Attract** | Full-screen rain, “INSERT COIN”, high score table, panel UI flickering |
| **Wave 1–3** | Dodge falling glyphs in a code corridor; collect green packets |
| **Decode round** | CONDUIT grid — flip bits to match a target portrait |
| **Hex round** | Changed bytes pulse bright — shoot or tap corrupted offsets |
| **Lyric burst** | Lyric fragments fall; hit them in order for combo multiplier |
| **Agent chase** | Bullet-time lane: slow-mo dodge down a hallway |
| **Game over** | “TRACE COMPLETE” — score, rank, restart |

## Controls (cabinet-friendly)

| Input | Action |
|-------|--------|
| Joystick / D-pad | Move |
| **A** | Action (flip bit, shoot, confirm) |
| **B** | Bullet-time |
| **Start** | Begin / continue |
| **Coin** | Insert coin (attract mode) |

Keyboard mappings can mirror the same layout for PC builds.

## First playable scene

```
┌─────────────────────────────────────────┐
│  ░░ RAIN SHADER (fullscreen) ░░░░░░░  │
│                                         │
│     [====PLAYER====]                    │
│        ↓ dodge ↓                        │
│   ｱ  ﾀ  1  0  B  ﾘ  ← falling glyphs   │
│                                         │
│  TRACE ████████░░░░░░░░  62%            │
│  SCORE 12400    COMBO x3                │
└─────────────────────────────────────────┘
```

Press **Start** → survive 30s → trace hits 100% → **CONDUIT DECODE** minigame → repeat until death.

## Art direction

| Element | Direction |
|---------|-----------|
| **Player** | Black coat silhouette, green edge glow |
| **Agents** | Same silhouette, red tint |
| **World** | Infinite rain tunnel or 2.5D lanes |
| **UI** | Dock panel titles — `TRACE PROTOCOL`, `CONDUIT · SIGNAL DECODE` |
| **Font** | Monospace + katakana TextMeshPro sprite asset |

## Related pages

- [Mechanics & Python mapping](mechanics.md) — how existing code becomes gameplay
- [Unity architecture](architecture.md) — project structure and rendering
- [Roadmap](roadmap.md) — phased build plan and scope traps
