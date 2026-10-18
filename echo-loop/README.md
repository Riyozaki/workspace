# Echo Loop

Turn-based roguelike with a time-loop mechanic. Every death is recorded as an **echo** — an ally that
replays your previous life's moves. Use echoes to hit enemies, trigger plates that open gates, and
break through the floor. Vanilla JavaScript + Canvas 2D. No build step, no runtime dependencies.

## Run

```bash
cd echo-loop
npm start            # http://localhost:3000 (binds 0.0.0.0)
PORT=8080 npm start  # other port
npm test             # 32 unit/integration tests (node:test)
npm run bot          # heuristic bot through the real engine: node tools/bot.js [runs] [maxFloor]
```

Controls: WASD / arrows move or attack (bump) · Space / `.` wait · `R` rewind (1 shard per loop) ·
`F` potion · click a tile to take one step toward it · `M` sound on/off · `Esc` pause · `N` new run.
URL `?seed=123` fixes the run seed.

## Layout

```
src/core/      pure game logic (no DOM): engine, ai, dungeon, pathfind, fov, rng, grid, entities
src/render/    canvas renderer and procedural sprites
src/ui/        style.css
src/main.js    state machine, input, HUD, screens
src/audio.js   WebAudio synthesized sounds
tests/         node:test suites (core.test.js, features.test.js, helpers.js)
tools/         bot.js (heuristic player), shots.mjs / e2e.mjs (headless Chromium checks)
DESIGN.md (in repo root), WORKLOG.md (in repo root)
```

## Status

See the final report in the repository root `WORKLOG.md` and the feature table there.
