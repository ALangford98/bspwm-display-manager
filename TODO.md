# TODO / context cache

Read this first before re-deriving project context from scratch. Update it
as work happens — it's the cache, not a changelog to append to forever.

## Shipped

- Core app: arrange outputs, resolution/refresh rate, session-wide scale
  (blurry per-output fallback), desktop-to-monitor assignment, save/replay
  profiles. (`docs/superpowers/plans/2026-09-05-bspwm-display-manager-core.md`)
- Hotplug daemon: polls connected outputs, auto-replays the matching saved
  profile on change. (`docs/superpowers/plans/2026-09-06-hotplug-daemon.md`)
- Desktop launcher: `packaging/bspwm-display-manager.desktop`, installed at
  `~/.local/share/applications/`.
- Install method: `pipx install --editable .` → binary at
  `~/.local/bin/bspwm-display-manager`.

## Fixed this session (2026-09-06)

- **App wouldn't launch from rofi/app launcher.** Root cause: rofi/bspwmrc
  never source `~/.zshrc`, so `~/.local/bin` was absent from their PATH —
  the `.desktop` file's bare `Exec=bspwm-display-manager gui` couldn't
  resolve. Fixed: `Exec=` now uses the absolute path
  `/home/anthony/.local/bin/bspwm-display-manager gui` in both the repo
  template and the installed copy. README corrected to match.
- **Windows rendered over polybar after Apply.** Root cause:
  `reconcile.reset_active_padding()` zeroes all padding on every apply
  (correctly ported from the old bash scripts), but the bash scripts always
  paired that reset with a polybar relaunch — polybar's fresh dock window
  is what makes bspwm auto-detect its EWMH strut and restore `top_padding`.
  This app's `hooks` field can carry that relaunch, but nothing populates
  it by default and there's no GUI to edit it, so the saved `Home` profile
  had `hooks: []` and padding just stayed zeroed forever. Fixed data-side:
  added `setsid -f bash ~/.config/bspwm/scripts/bspbar >/dev/null 2>&1
  </dev/null` to `~/.config/bspwm-display-manager/profiles/Home.json`'s
  `hooks`. **Only `Home.json` exists** — no `Work` profile has been created
  yet, so nothing else needs this hook right now, but any future profile
  will need it added too until there's a GUI for it (see gap below).
- **Found + fixed while verifying the above:** `hooks.run_hooks()` had no
  timeout — a hook that backgrounds a long-lived process without
  redirecting its own stdout/stderr (exactly the polybar-relaunch hook,
  before I added the redirection) hangs `subprocess.run`'s pipe read
  forever, since the detached grandchild inherits the pipe and never
  closes it. This would have frozen `apply` *and the hotplug daemon*
  (silently, forever, on the first hotplug event using such a hook). Fixed:
  10s timeout in `hooks.py`, reported as a normal failed-hook result
  instead of hanging. Tested + committed.

Both fixes are committed and pushed to `origin/master`.

## Known gaps (not yet worked)

- **No GUI to edit a profile's `hooks` list.** Only fixable today by
  hand-editing the profile JSON (as done above for Home). Any profile
  saved/re-saved through the app's Save Profile flow will silently get
  `hooks: []` and reintroduce the polybar-padding bug. Worth a small
  bounded task on its own, independent of the bigger scoping below.
- User has only one saved profile (`Home`) despite having a 3-desktops
  per-monitor "work" setup described earlier — `Work` profile not created
  yet in this app (their hand-written `~/.screenlayout/work-layout.sh` +
  `bsp-assign-desktops` scripts still exist and are untouched/unaffected).

## Next up (per user's explicit request, 2026-09-06)

User wants to scope out a **much bigger idea**: a GUI to configure the
whole "look and feel" of their desktop environment and screens — not just
display arrangement. Explicitly open to this being a separate tool rather
than extending `bspwm-display-manager`. Not yet brainstormed at all — no
approach, scope, or architecture decided. Use `superpowers:brainstorming`
(architectural path) when starting this; don't skip the design/spec gate.
