# bspwm-display-manager — Design

**Date:** 2026-09-05
**Status:** Approved for planning

## Problem

bspwm (X11-only, no Wayland port) has no first-party GUI for arranging
multiple displays. The immediate pain: a work setup with one 1440p and one 4K
monitor, where getting resolution, refresh rate, and scale configured
correctly by hand (`xrandr` + DPI/env vars) was confusing enough to get stuck
on. `arandr`/`wdisplays` cover position/mode but not scale, and neither
exposes the scale trade-offs clearly.

A second, equally real need surfaced during design: bspwm desktops must
also be assigned to specific monitors per layout (e.g. 3 desktops on each
of 2 external monitors at the office, all 9 on the laptop panel at home),
toggled by keyboard shortcut. This is a distinct mechanism from RandR
(`bspc monitor <sel> -d <names...>` / `bspc desktop <name> --to-monitor
<target>`, not `xrandr`), and the user already has a working, hand-tuned
solution for it — see "Prior art" below. This tool generalizes that
solution rather than replacing it with something naive.

## Prior art this design ports and generalizes

Before this project, the user's `~/.screenlayout/{work,home}-layout.sh` +
`~/.config/bspwm/scripts/{bsp-assign-desktops,bsp-retire-monitors}`
already solved layout switching, hardcoded to their specific 3-monitor
setup (LG + Dell + laptop). Reading them surfaced hard-won bspc behavior
that a naive reimplementation would regress:

- `bspc monitor -r` **drops** (does not merge) a monitor's windows the
  instant it's removed — every desktop must be moved off with `bspc
  desktop <name> --to-monitor <target>` *before* calling `-r` on that
  monitor.
- `bspc desktop --to-monitor` silently **refuses** to move a monitor's
  last remaining desktop (a monitor can never have zero desktops). Fix:
  add a disposable placeholder desktop to the doomed monitor first, so no
  real desktop is ever "the last one" while being moved off; the
  placeholder dies harmlessly with the monitor.
- `bspc monitor <mon> -d <fewer names>` does **not** hand the dropped
  desktops to another monitor — it silently folds them, windows included,
  into the last desktop in the new name list, on the same monitor. Lost a
  window this way once. Desktops must always be moved individually by
  identity (`--to-monitor`), never reassigned via a shrinking `-d` list.
- Monitor **retirement must happen before**, not after, the `xrandr` call
  that disables/reconfigures the losing output — bspwm drops the windows
  the instant the output loses its mode/CRTC out from under it.
- External monitors are matched by **EDID** (preferred/native resolution
  in the bash version, since parsing full EDID in awk is impractical),
  never by port name — port names shift across dock/cable swaps and even
  across boots on the same dock.
- `xrandr --listactivemonitors` is not reliable for "what's really
  active" — RandR Monitor objects can outlive the output they were
  created for. "Active" must be derived from the real output table
  (connected AND currently carrying a mode/position).
- Per-monitor padding must be reset to zero on all four edges before
  reassigning desktops, since bspwm can leave stale strut-derived padding
  behind across an off/on cycle.
- A monitor that just (re)appeared starts with one auto-created blank
  placeholder desktop, which must be swept away after real desktops are
  assigned — but only if it's empty, so nothing unexpected is destroyed.

This tool ports every one of these behaviors into the Python backend as
explicit, named, tested functions (see **Desktop Reconciliation** below),
generalized so a profile carries an arbitrary named desktop list per
monitor role instead of being hardcoded to three specific monitors.

## Platform constraints (why this is designed the way it is)

X11/RandR has no concept of true per-monitor fractional scaling. There are
exactly two scaling mechanisms available, and they behave very differently:

1. **`xrandr --scale` (per-output CRTC transform)** — a post-render stretch
   of the framebuffer. Always blurry. Can be set independently per output.
2. **Global toolkit scaling** (`Xft.dpi` + `GDK_SCALE` / `QT_SCALE_FACTOR` /
   `QT_AUTO_SCREEN_SCALE_FACTOR`) — HiDPI-aware apps (GTK3/4, Qt5/6) render
   natively at the higher pixel density, so this is **not** blurry. The
   limitation: X11 has one screen and one DPI value, so this factor is
   necessarily uniform across every connected monitor — it cannot differ per
   output.

Neither mechanism gives independent, always-crisp, per-monitor scale factors
with no trade-off — that specific capability requires a Wayland compositor
(fractional-scale-v1), which bspwm does not have and will not get (it is
deliberately X11-only). That's out of scope for this project; if a user
wants that exact capability, the fix is switching window managers entirely,
not this tool.

For a monitor pair where the native resolutions share a clean integer or
simple-fractional ratio (e.g. 3840×2160 vs 2560×1440, a clean 1.5×), the
global-scale route (mechanism 2) gives a fully crisp result on both screens
simultaneously — the only cost is reduced logical desktop area on the
lower-resolution screen, not blur. This is common enough to be worth
detecting and suggesting automatically.

RandR also only ever reports modes the driver actually negotiated with the
monitor over the physical link, so a resolution/refresh combo that requires
more link bandwidth than the cable/port/dock supports (e.g. 4K@60 4:4:4
needs ~14.9 Gbps, which HDMI 1.4 cannot deliver) simply won't appear as an
option. This tool surfaces exactly what RandR reports; it cannot add link
bandwidth that isn't physically present.

**Design implication:** the global DPI/env-var route is the primary,
recommended scaling mechanism in this tool, with a suggested value computed
from the connected outputs' resolution ratio. The per-output `--scale`
transform is kept available as a secondary, explicitly-labeled-as-blurry
fallback for mismatched ratios.

## Stack

**Python + PySide6 (Qt for Python).** Rejected building this on the C++
game engine at `Documents/EGSS`: this app is idle almost all the time — a
form with a draggable canvas — not a rendering workload, and EGSS's game
loop/renderer/ImGui immediate-mode paradigm solves a different problem.
`QGraphicsScene`/`QGraphicsView` is close to purpose-built for
draggable-rectangles-that-snap-to-each-other, which is exactly the
monitor-arrangement canvas. Python also lowers the contribution barrier for
an open source Linux desktop utility relative to a personal from-scratch
engine dependency.

Display backend talks to `xrandr` via subprocess (parsing `xrandr
--verbose` output), not direct libXrandr/python-xlib bindings — this
mirrors what `arandr`/`autorandr` already do reliably in production and is
more robust to X server version differences.

## Architecture

Three layers, split so the useful logic isn't trapped inside Qt:

- **`backend/`** — pure Python, no Qt/GUI dependency: RandR state model,
  `xrandr` output parser, command builder, EDID fingerprinting, profile
  store, DPI/scale calculator.
- **`ui/`** — PySide6: main window, drag-arrange canvas, per-output config
  panel, profile manager, apply/confirm dialog.
- **`daemon/`** — a separate, Qt-free background process for hotplug
  auto-apply, run as a `systemd --user` service. Kept out of the GUI
  process so auto-apply on hotplug works whether or not the GUI is open.

## Components

1. **RandR State Reader** — parses `xrandr --verbose` into typed
   Output/Mode dataclasses (name, connected, current mode, position,
   rotation, scale/transform, primary flag, EDID).
2. **Layout Canvas** (`QGraphicsScene`) — draggable monitor rectangles,
   drawn to scale, with edge-snapping to adjacent monitors.
3. **Output Config Panel** — per-selected-output controls: mode dropdown
   (populated from that output's available modes), refresh rate dropdown
   (populated from modes matching the selected resolution), rotation,
   primary toggle, and the per-output blurry-scale fallback (shown only
   when the user opts in, or a ratio mismatch is detected).
4. **Session Scale Control** — one global 100/125/150/175/200% control
   wired to `Xft.dpi` + `GDK_SCALE`/`QT_SCALE_FACTOR`/
   `QT_AUTO_SCREEN_SCALE_FACTOR`, with a suggested value computed from the
   connected outputs' native resolution ratio.
5. **Command Builder** — turns edited state into one `xrandr` invocation
   plus the DPI/env changes for the scaling route in use.
6. **Apply + Safety Net** — applies, then shows a confirm dialog with a
   countdown (default 15s); an unconfirmed change auto-reverts to the
   last-known-good state. Fires unconditionally after every apply,
   regardless of `xrandr`'s exit code — this is what prevents a bad
   geometry from locking the session into an unreadable state.
7. **Profile Store** — JSON files, one per named profile (e.g. `work`,
   `home`), each keyed by a hash of its target outputs' EDID identifiers
   (sorted) for hotplug matching. Stores per-output geometry/mode/scale,
   the session DPI setting, a **desktop assignment** — an ordered map of
   monitor role (EDID hash, or `eDP-*` pattern for the built-in panel) to
   an ordered list of desktop names — and an ordered list of **post-apply
   hook** shell commands (e.g. a polybar reload, a wallpaper repaint, a
   lockscreen cache regen — arbitrary, user-supplied, empty by default).
8. **Desktop Reconciliation** — ports the prior-art behavior above into
   tested Python functions, run in this order after a successful
   `xrandr` apply:
   1. `retire_monitors(surviving, overflow_target)` — for every known
      bspwm monitor not in `surviving`, add a placeholder desktop, move
      every real desktop off it by identity, then `bspc monitor -r` it.
      Called *before* the `xrandr` command that disables/reconfigures the
      losing output, not after.
   2. Re-derive the active output set from the real output table (never
      `--listactivemonitors`).
   3. Reset padding (all four edges) to zero on every active monitor.
   4. `assign_desktops(target, names)` — move each named desktop to
      `target` by identity (`--to-monitor`) if it exists anywhere, else
      add it fresh (`bspc monitor <target> -a <name>`). Never shrinks a
      monitor's desktop set via `-d`.
   5. `bspc wm -O <order...>` — reorder monitors to match the profile's
      declared order.
   6. Sweep any leftover auto-created placeholder desktop on a
      newly-appeared monitor, only if it's empty.
   7. Run the profile's post-apply hook commands, in order.
9. **Hotplug Daemon** — watches for RandR screen-change events,
   fingerprints the new monitor set, and if a saved profile matches,
   replays it through the Command Builder followed by Desktop
   Reconciliation. If no profile matches, it leaves the current layout
   untouched and sends a `notify-send` notification (dunst is already
   configured) rather than guessing.
10. **CLI** — `bspwm-display-manager apply <profile-name>` runs the same
    Command Builder + Desktop Reconciliation pipeline as the GUI's Apply
    button, non-interactively (no confirm/revert countdown — a keyboard
    shortcut needs to be instant). This is what `sxhkdrc` binds to,
    replacing `bash ~/.screenlayout/work-layout.sh` /
    `home-layout.sh`.

## Data flow

**GUI edit path:** `xrandr --verbose` → State Reader → in-memory Output
objects → Canvas/Panels render from that state → user edits stay in-memory
(including desktop assignment + hooks) until **Apply** → Command Builder
diffs against last-applied state → `retire_monitors` (pre-xrandr) →
executes `xrandr` + writes DPI/env → confirm/revert countdown → on
confirm: rest of Desktop Reconciliation runs (padding reset, assign,
reorder, placeholder sweep, hooks) → optional profile save.

**Replay path** (CLI or Daemon): saved profile → `retire_monitors`
(pre-xrandr) → Command Builder executes `xrandr` + DPI/env → full Desktop
Reconciliation (no confirm/revert gate — see Error handling) →
fingerprint match (Daemon only, before any of the above) or direct
profile-name lookup (CLI).

## Error handling

- `xrandr` failure (bad args/rejected mode): exit code/stderr captured and
  shown in the GUI (CLI: printed to stderr, nonzero exit); state is not
  marked known-good, no profile save is offered, Desktop Reconciliation
  does not run.
- Bad geometry that "succeeds" but produces a wrong/blank screen, **from
  the GUI**: the confirm/revert countdown fires unconditionally after
  every GUI apply — this is the actual safety mechanism, not error
  detection. **CLI/Daemon replays of an already-saved profile skip this
  gate deliberately** (a keyboard shortcut must be instant, and the
  profile was already vetted once through the GUI's gate when it was
  saved) — this mirrors the no-safety-net behavior of the
  `work-layout.sh`/`home-layout.sh` scripts it replaces.
- `--verbose` output fails to parse (xrandr version differences): surfaced
  as a GUI dialog (CLI: stderr + nonzero exit), never a crash; the canvas
  refuses to build from partial state.
- Desktop Reconciliation step fails partway (e.g. `bspc` not running, a
  named desktop already exists on an unexpected monitor): each step logs
  what it did before failing (retirement and assignment are both
  idempotent by construction — re-running is safe) and surfaces the error
  rather than silently continuing to the next step.
- Daemon finds no matching profile on hotplug: leaves the current layout
  untouched and notifies; never auto-applies a guess.

## Testing

- Backend (parser, command builder, EDID fingerprinting, profile store) is
  pure Python — unit-tested with pytest against captured real `xrandr
  --verbose` fixtures, including this machine's actual output as one
  fixture.
- Desktop Reconciliation functions are pure Python with a mocked `bspc`
  subprocess boundary — unit-tested by asserting the exact `bspc` argv
  sequence for each documented edge case from the prior-art section:
  retiring a monitor with its last-desktop moved via the placeholder
  trick, assigning desktops without ever calling `-d` with a shorter
  list, retirement ordered before the `xrandr` call, and the
  empty-only placeholder-desktop sweep. No real `bspc` calls run in
  automated tests — replaying against a live session is a manual step
  (see below), never CI, since it mutates the tester's actual desktops.
- GUI interaction (drag/snap/apply) has no realistic headless X11 CI for a
  personal desktop tool — verified manually against real hardware, this
  laptop first and the target dual-monitor office setup as the real test.
- Daemon hotplug logic tested by simulating connect/disconnect via `xrandr
  --output X --off` / `--auto`, since real hotplug needs physical monitor
  changes.
- CLI apply and full Desktop Reconciliation against a real `bspc` session
  are verified manually on this machine (single monitor) and at the
  office (the actual multi-monitor target), replacing one keybinding at a
  time so the existing scripts remain a fallback until the tool is
  trusted.

## Scope

**In scope (v1):** everything described above — canvas arrangement,
mode/refresh selection, global-scale and per-output-scale mechanisms,
apply/revert safety net, EDID-keyed profiles with hotplug auto-apply,
per-profile desktop-to-monitor assignment, Desktop Reconciliation
(retirement/assignment/reorder/padding/hooks), CLI apply for keybindings.

**Migration:** `sxhkdrc`'s `super+ctrl+w`/`super+ctrl+h` bindings get
repointed at `bspwm-display-manager apply work` / `apply home` once
equivalent profiles are created and manually verified — done by hand,
one binding at a time, not by an automated migration step. The existing
`~/.screenlayout/*.sh` scripts and `bsp-assign-desktops`/
`bsp-retire-monitors` stay on disk untouched as a fallback; this project
does not delete or modify them.

**Out of scope (v1):** AUR packaging, system tray icon, non-EDID fallback
fingerprinting for monitors with broken/missing EDID. None of these require
restructuring the architecture above to add later.

## License

MIT, intended for open source release.
