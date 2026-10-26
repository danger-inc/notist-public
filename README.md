<!-- gh-header -->
<div align="center">

<img src="app/logo/notist.svg" width="88" alt="notist">

# notist

**notes, words and latex in one gtk4 app**

<img src="https://img.shields.io/badge/GTK-4-4A86CF?style=flat-square&logo=gtk&logoColor=white" alt="GTK"> <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="python"> <img src="https://img.shields.io/badge/platform-linux%20·%20windows-2E7D6B?style=flat-square&logo=linux&logoColor=white" alt="platform"> <img src="https://img.shields.io/badge/made%20for-wayland%20·%20hyprland-7C6BC4?style=flat-square" alt="made for">

</div>

<p align="center"><img src="docs/notist.png" width="860" alt="notist screenshot"></p>

<p align="center"><!-- gh-note --><sub>tip: the glass button (󰃝, top right) makes the window see-through, like the terminal – needs a compositor with blur, e.g. hyprland.</sub></p>

three ways to write in one gtk4 app, switch with alt+1/2/3:

* **notes** – quick notes with checklists, saved automatically
* **words** – word processor: page view, styles, tables, images. opens `.docx`/`.doc`, exports to word, pdf, text, markdown, html
* **latex** – source with live pdf preview. made for beginners: templates, a guide, cheat sheet,
command suggestions while typing and error messages in plain language

## install – linux

the repository is public – no account needed:

```bash
git clone https://github.com/danger-inc/notist-public ~/notist-src
cd ~/notist-src
./install.sh
```

the script installs dependencies (asks beforehand), copies notist to `~/.local/share/notes/app` and creates
the launcher `notist` and a menu entry. the icons are bundled (`app/fonts/notes-icons.ttf`), no extra font needed.
packages that don't exist on your distribution are skipped and listed at the end.

## install – windows 10/11

1. download the repo (on github **code → download zip** and extract, or `gh repo clone …`).
2. double-click **`install-windows.bat`** in the folder.

the script sets up **msys2** once (provides gtk 4 and python for windows, ~1 gb, asks for admin rights),
installs the packages and adds notist to the start menu. your data lives in
`%USERPROFILE%\.local\share\notes\data`. removal: `uninstall-windows.bat` (data stays).
on windows there are no reminders while the app is closed and no background mode (✕ exits notist).

## runs on

| system | status |
| --- | --- |
| ubuntu 24.04+, linux mint 22+, debian 13 | tested (ubuntu 24.04) |
| fedora 39+ | tested (fedora 44) |
| arch, endeavouros, cachyos, manjaro | tested (arch) |
| openSUSE Tumbleweed | should work (untested) |
| windows 10/11 | via msys2 – app start tested, installer on real windows still untested |

required is **gtk 4.12 or newer** (ubuntu 22.04 / mint 21 / debian 12 are too old – the installer says that).

## update

```bash
cd ~/notist-src
./update.sh
```

fetches the latest version and installs it. notes and settings are left alone, an old version running in the
background is terminated. what changed is in `app/CHANGELOG.md`.
windows: get the new version and run `install-windows.bat` again.

## usage

```bash
notist                # or via the application menu
notist letter.docx    # open a file directly (.docx, .doc, .tex, .md, .txt, .html)
notist --check        # shows what is installed and what is missing
```

## what's in there

* **backups** (daily zip, any target folder – e.g. a cloud folder) and **version history** per entry
* **folders** (nested, e.g. `uni/math`), archive, tags, colors, search across everything, **reminders** with notifications
* words: real pages, margins, header/footer, page numbers, table of contents, footnotes, docx/odt/pdf
* latex: command overview (F1), live pdf with synctex, multiple files, bibliography, formula preview,
table editor, spell check, convert words ↔ latex
* **translator** (ctrl+shift+t, bottom right): german ⇄ english dictionary offline, more languages and whole sentences on request
* **sharing:** copy, send by e-mail (with attachment), `.notes` files for friends who also have notist
* **language:** german or english (settings → language, restart afterwards)

## latex compiler

the first time you open latex mode, notist offers to set up **tectonic**
(a single program, ≈ 10 mb, no admin rights, goes to `~/.local/share/notes/tools`).
the very first compile downloads the needed latex packages (1–3 minutes),
after that a run takes about half a second.

if a tex distribution is already installed (`latexmk`, `pdflatex`, `xelatex`, `lualatex`),
notist uses that.

## what runs where

notist needs **gtk 4** (linux, or windows via msys2). on tiling window managers (hyprland, sway, …) the window
has no title bar, on gnome/kde it has a normal one. an existing **matugen** theme
(`~/.cache/matugen/colors.css`) is picked up, otherwise it uses its own color scheme.

**quick start:** after closing, notist stays hidden in the background and the next call opens the window
instantly. even faster from the first call: start `notist --daemon` on login, e.g. in hyprland
`hl.exec_cmd("notist --daemon")` or `exec-once = notist --daemon`. exit completely: `notist --quit`.

**hyprland:** to open the settings centered on screen:

```lua
hl.window_rule({ name = "notist-settings", float = true, center = true,
    match = { class = "^de\\.invincible\\.Notist$", title = "^(Einstellungen|Settings)$" } })
```

| function | needs |
| --- | --- |
| notes, words, docx import/export | gtk4, pygobject |
| pdf export and printing in words | pycairo, pangocairo |
| latex preview | poppler (gi typelib `Poppler-0.18`) |
| spell check | hunspell + dictionaries (de, en) |
| compile latex | tectonic (one click in the app) or a tex distribution |
| reminders while the app is closed | systemd (user timer), otherwise only while notist runs |
| "send by e-mail" | `xdg-email` (xdg-utils) and a mail program |

## data

everything is in `~/.local/share/notes/data` (one json file per note/document).
images of latex documents are in `~/.local/share/notes/data/latex-files/<id>/`.
`./uninstall.sh` removes the app and asks whether the data should go too.

## formerly "notes"

notist was called "notes" up to version 3.2. your data stays in the same folder (`~/.local/share/notes/data`)
and the old command `notes` still starts notist.

## problems?

* **boxes instead of symbols:** `./update.sh` – the icon font comes along and is loaded automatically.
* **`notist: command not found`:** `~/.local/bin` is missing in `PATH` (the installer shows what belongs in
`~/.bashrc`). from the application menu it starts anyway.
* **what's still missing?** `notist --check` lists all optional parts.

<!-- gh-suite -->
## the -ist suite

all apps share one look (terminal style, colors from your wallpaper via matugen), one installer and the same shortcuts.

| app | what it does |
| --- | --- |
| [scourge](https://github.com/danger-inc/scourge-public) | inspect, edit, record, cut – and installs the others |
| [filist](https://github.com/danger-inc/filist-public) | file explorer + file dialog |
| [datist](https://github.com/danger-inc/datist) | calendar |
| [mailist](https://github.com/danger-inc/mailist-public) | mail |
| [musicalist](https://github.com/danger-inc/musicalist-public) | youtube music |
| [linguist](https://github.com/danger-inc/linguist) | translator + hover corner |
| [sharist](https://github.com/danger-inc/sharist) | quick share |
| [wallist](https://github.com/danger-inc/wallist) | wallpapers |
| [inquirist](https://github.com/danger-inc/inquirist) | launcher |

dotfiles with the matching hyprland setup: [danger-inc/dotfiles](https://github.com/danger-inc/dotfiles)
