# bspwm-display-manager

A GUI (and CLI) for arranging bspwm's connected displays: drag to
position monitors, pick resolution/refresh rate, set a session-wide
scale factor (with a per-output blurry fallback for mismatched panel
ratios), assign bspwm desktops to specific monitors, and save/replay the
whole thing as a named profile.

Built for X11/bspwm, which has no per-monitor fractional scaling (see
`docs/superpowers/specs/2026-09-05-bspwm-display-manager-design.md` for
why, and what this tool does about it instead).

## Install

Recommended, via [pipx](https://pipx.pypa.io/) — installs an isolated
venv and puts `bspwm-display-manager` on your `PATH` (`~/.local/bin`):

    pipx install --editable .

`--editable` means future changes to this checkout take effect
immediately with no reinstall — worth keeping even if you don't plan to
modify the code, since it costs nothing and this is still an actively
developed tool. Drop `--editable` for a normal pinned install instead.

Without pipx, a plain venv works too, but nothing puts the command on
your shell's `PATH` — you'd invoke it as `.venv/bin/bspwm-display-manager`,
and any launcher that doesn't inherit your shell's `PATH` (sxhkd, a
systemd user service, most desktop launchers) needs that full path
rather than the bare command name:

    python -m venv .venv
    .venv/bin/pip install -e .

## Usage

    bspwm-display-manager gui              # arrange displays, assign desktops, save profiles
    bspwm-display-manager apply <name>     # instantly replay a saved profile (for keybindings)

Profiles live in `~/.config/bspwm-display-manager/profiles/*.json`.

## Session-wide scale

The GUI's session scale control (and each profile's saved scale) writes
`Xft.dpi` via `xrdb -merge` immediately -- that part takes effect right
away for newly-drawn X clients. GTK/Qt apps also need `GDK_SCALE`,
`QT_SCALE_FACTOR`, and `QT_AUTO_SCREEN_SCALE_FACTOR`, which are written
to `~/.config/bspwm-display-manager/env` but need to be sourced into
your session yourself -- add this to your `~/.xprofile` or the top of
`~/.config/bspwm/bspwmrc`:

    [ -f ~/.config/bspwm-display-manager/env ] && source ~/.config/bspwm-display-manager/env

## Hotplug auto-apply (optional)

`bspwm-display-manager daemon` runs in the foreground, polling the
connected monitors every few seconds. When the set of connected
displays changes (a dock connect/disconnect, a monitor power cycle) it
automatically replays whichever saved profile's fingerprint matches —
no keyboard shortcut needed. If nothing matches, it leaves your current
layout alone and sends a desktop notification rather than guessing.

To run it automatically at login via systemd:

    mkdir -p ~/.config/systemd/user
    cp packaging/bspwm-display-manager-daemon.service ~/.config/systemd/user/
    # edit the ExecStart line in that file to point at this project's
    # actual .venv/bin/bspwm-display-manager path
    systemctl --user daemon-reload
    systemctl --user enable --now bspwm-display-manager-daemon

The daemon needs `DISPLAY`/`XAUTHORITY` to talk to X, which a systemd
user service does not inherit automatically. Add this near the end of
`~/.config/bspwm/bspwmrc` (after X is actually up), alongside its other
autostart lines:

    systemctl --user import-environment DISPLAY XAUTHORITY
    systemctl --user restart bspwm-display-manager-daemon.service 2>/dev/null || true

Without this, the daemon will show as `active (running)` in
`systemctl --user status` but silently do nothing — check
`journalctl --user -u bspwm-display-manager-daemon` for a repeating
"no connected outputs reported" line, which means it's running without
a display to talk to.

Check on it with:

    systemctl --user status bspwm-display-manager-daemon
    journalctl --user -u bspwm-display-manager-daemon -f

This is entirely optional — `bspwm-display-manager apply <name>` from a
keyboard shortcut works fine without the daemon running at all.

## Desktop launcher (optional)

To launch the GUI from an application menu/launcher (rofi's `drun` mode,
a dmenu-based launcher, or a full desktop environment's app grid) instead
of a terminal or keybinding:

    mkdir -p ~/.local/share/applications
    cp packaging/bspwm-display-manager.desktop ~/.local/share/applications/
    update-desktop-database ~/.local/share/applications  # if available; harmless if not

The shipped `.desktop` file's `Exec=` is the bare `bspwm-display-manager`
command, which relies on it being on `PATH` — true for a pipx install,
but if you installed into a plain venv instead, edit the `Exec=` line to
the venv's absolute path (`/path/to/bspwm-display-manager/.venv/bin/bspwm-display-manager gui`)
first, the same PATH caveat as the systemd unit and sxhkd bindings above.

## Migrating from hand-written screenlayout scripts

If you have existing `~/.screenlayout/*.sh` + `bsp-assign-desktops` /
`bsp-retire-monitors` scripts (this project started as a generalization
of exactly that setup):

1. Launch `bspwm-display-manager gui`, arrange each layout the way the
   corresponding script did, and **Save Profile** under the same name
   (e.g. `work`, `home`).
2. Verify `bspwm-display-manager apply work` (and `home`) behave the way
   the old script did — check window placement across a few real
   monitor swaps before trusting it as a daily driver.
3. In `~/.config/bspwm/sxhkdrc`, change:

       super + ctrl + w
           bash ~/.screenlayout/work-layout.sh

       super + ctrl + h
           bash ~/.screenlayout/home-layout.sh

   to:

   (sxhkd doesn't inherit your shell's PATH, so point it at the
   binary's absolute path rather than the bare command name — run
   `which bspwm-display-manager` to find it; `~/.local/bin/bspwm-display-manager`
   for a pipx install, `/path/to/bspwm-display-manager/.venv/bin/bspwm-display-manager`
   for a plain venv one)

       super + ctrl + w
           /path/to/bspwm-display-manager apply work

       super + ctrl + h
           /path/to/bspwm-display-manager apply home

4. Reload sxhkd (`pkill -USR1 -x sxhkd`, or however your config reloads it).

The original scripts are left untouched on disk as a fallback — nothing
in this project deletes or modifies them.

## Development

    .venv/bin/pip install -e ".[dev]"
    .venv/bin/pytest
