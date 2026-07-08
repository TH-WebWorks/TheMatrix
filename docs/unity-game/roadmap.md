# Roadmap

Phased plan to ship TRACE PROTOCOL without over-scoping.

## Phase 1 — Playable in a weekend

Prove the cabinet feel.

- [ ] Orthographic or tunnel camera, player silhouette
- [ ] Rain shader or pooled glyph background
- [ ] Move + collide with falling “bad” glyphs
- [ ] Trace meter fills over time
- [ ] Score + game over + restart
- [ ] Green palette, basic bloom post-processing

**Exit criteria:** Fun for 60 seconds with no Spotify and no panel UI.

---

## Phase 2 — Signature minigame

- [ ] **Conduit puzzle:** 16×16 or 32×32 bit grid, click to flip, match target in N seconds
- [ ] Seed puzzles from `Random` or level JSON (no Spotify yet)
- [ ] Success reduces trace meter and awards bonus points

**Exit criteria:** One mechanic that feels unique to TheMatrix.

---

## Phase 3 — Arcade structure

- [ ] Wave system with increasing speed and glyph density
- [ ] Attract mode + high score table
- [ ] Between-wave operator terminal UI (dock tab aesthetic)
- [ ] Agent chase set-piece every 5 waves

**Exit criteria:** Full attract → play → game over loop with persistence.

---

## Phase 4 — Juice and ship

- [ ] Bullet-time (`Time.timeScale` lerp + chromatic aberration)
- [ ] Screen shake, hit-stop, combo multiplier
- [ ] Sound design (synth beeps, trace alarm)
- [ ] PC/Mac builds; optional 16:9 TV fullscreen mode

**Exit criteria:** Build you’d show someone without apologizing.

---

## Phase 5 — Jack In (optional)

- [ ] Python sidecar exposing Spotify JSON on localhost
- [ ] Unity `JackInClient` polls track metadata and album art
- [ ] Puzzles seed from live track bytes; art becomes CONDUIT target
- [ ] Lyric burst uses LRCLIB sync
- [ ] Score multiplier while Jack In is active

**Exit criteria:** Spotify enhances the run but is never required to play.

---

## What not to do early

| Trap | Why |
|------|-----|
| Full 3D open world | Kills arcade scope |
| Multiplayer first | Ship single-player score chase |
| Spotify in v1 | OAuth in Unity is painful; sidecar later |
| Porting all 12 panels | Pick 2–3 as minigames |
| Physics-heavy bullet hell | Lane-based + shader rain is enough |
| Porting pygame rendering | Reimplement ideas in C# / shaders |

---

## Suggested implementation order

1. Create **Unity 6 + URP** project at `1920×1080`
2. Implement `TraceMeter` + `RainController` + `PlayerController`
3. Port `_bytes_to_bits` and grid flip logic into `ConduitPuzzle.cs`
4. Add attract mode with scrolling rain and “PRESS START”
5. Layer waves, minigames, and juice per phases above

---

## Relationship to TheMatrix (pygame)

| Layer | Stays in Python | Moves to Unity |
|-------|-----------------|----------------|
| Ambient 4K TV display | Yes — current app | No |
| Rain aesthetic | Reference / shader inspiration | GPU rain |
| CONDUIT / HEX logic | Reference implementation | C# minigames |
| Spotify OAuth | Sidecar only (Phase 5) | Poll JSON only |
| Dock panel UI | Reference chrome | `PanelFrame.cs` |

The pygame app and Unity game can coexist: the display app for ambient use, the game for arcade sessions.

---

## Open decisions

Track these before Phase 3:

| Question | Options |
|----------|---------|
| Camera | 2.5D lanes vs. top-down vs. tunnel |
| Input | Keyboard-first vs. gamepad-first |
| Puzzle source | Procedural vs. hand-authored library |
| Jack In default | Off by default vs. prompt at attract mode |
