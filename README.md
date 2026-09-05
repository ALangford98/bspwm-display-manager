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

    python -m venv .venv
    .venv/bin/pip install -e .

## Usage

    bspwm-display-manager gui              # arrange displays, assign desktops, save profiles
    bspwm-display-manager apply <name>     # instantly replay a saved profile (for keybindings)

Profiles live in `~/.config/bspwm-display-manager/profiles/*.json`.

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

       super + ctrl + w
           bspwm-display-manager apply work

       super + ctrl + h
           bspwm-display-manager apply home

4. Reload sxhkd (`pkill -USR1 -x sxhkd`, or however your config reloads it).

The original scripts are left untouched on disk as a fallback — nothing
in this project deletes or modifies them.

## Development

    .venv/bin/pip install -e ".[dev]"
    .venv/bin/pytest
