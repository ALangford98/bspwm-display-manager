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
7. **Profile Store** — JSON files keyed by a hash of the connected
   outputs' EDID identifiers (sorted), storing full per-output
   geometry/mode/scale plus the session DPI setting.
8. **Hotplug Daemon** — watches for RandR screen-change events, fingerprints
   the new monitor set, replays a matching saved profile through the same
   Command Builder. If no profile matches, it leaves the current layout
   untouched and sends a `notify-send` notification (dunst is already
   configured) rather than guessing.
9. **bspwm Hook** — after any apply (manual or auto), triggers bspwm to
   reconcile monitor/desktop state (`bspc wm -r` or the documented
   equivalent), since bspwm does not notice output changes it didn't
   initiate.

## Data flow

`xrandr --verbose` → State Reader → in-memory Output objects → Canvas/Panels
render from that state → user edits stay in-memory until **Apply** →
Command Builder diffs against last-applied state → executes `xrandr` +
writes DPI/env → confirm/revert countdown → on confirm, optional profile
save → Daemon (separate long-running process) watches for hotplug →
fingerprint match → replay through the same Command Builder → bspwm hook.

## Error handling

- `xrandr` failure (bad args/rejected mode): exit code/stderr captured and
  shown in the GUI; state is not marked known-good, no profile save is
  offered.
- Bad geometry that "succeeds" but produces a wrong/blank screen: the
  confirm/revert countdown fires unconditionally after every apply — this
  is the actual safety mechanism, not error detection.
- `--verbose` output fails to parse (xrandr version differences): surfaced
  as a GUI dialog, never a crash; the canvas refuses to build from partial
  state.
- Daemon finds no matching profile on hotplug: leaves the current layout
  untouched and notifies; never auto-applies a guess.

## Testing

- Backend (parser, command builder, EDID fingerprinting, profile store) is
  pure Python — unit-tested with pytest against captured real `xrandr
  --verbose` fixtures, including this machine's actual output as one
  fixture.
- GUI interaction (drag/snap/apply) has no realistic headless X11 CI for a
  personal desktop tool — verified manually against real hardware, this
  laptop first and the target dual-monitor office setup as the real test.
- Daemon hotplug logic tested by simulating connect/disconnect via `xrandr
  --output X --off` / `--auto`, since real hotplug needs physical monitor
  changes.

## Scope

**In scope (v1):** everything described above — canvas arrangement,
mode/refresh selection, global-scale and per-output-scale mechanisms,
apply/revert safety net, EDID-keyed profiles with hotplug auto-apply,
bspwm reconciliation hook.

**Out of scope (v1):** AUR packaging, system tray icon, non-EDID fallback
fingerprinting for monitors with broken/missing EDID. None of these require
restructuring the architecture above to add later.

## License

MIT, intended for open source release.
