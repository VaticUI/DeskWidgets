# DeskWidgets

macOS-style widgets on the Windows desktop: pick the ones you want, in small, medium or large.

They sit on the desktop itself: always under your windows, still visible with **Win+D**,
with a frosted-glass look made from your blurred wallpaper. They follow Windows' light / dark mode.

## Widgets

| Widget | Sizes | What it shows |
|---|---|---|
| 🕒 Horloge | S, M | Analog or digital clock; medium = 4 cities (dark dial at night) |
| 📅 Calendrier | S, M, L | Today's date, week number, month grid |
| 🌤️ Météo | S, M, L | Temperature, conditions, next hours, 6-day forecast ([Open-Meteo](https://open-meteo.com), no key) |
| 🎵 Musique | S, M | What's playing (Spotify, YouTube, NotchIsland…) with the controls; colors from the album art |
| 📊 Système | S, M | CPU, RAM, disk C:, network (and battery on a laptop) |
| 📝 Notes | S, M, L | A sticky note: click to write (yellow, pink, green, blue or glass) |
| 🖼️ Photos | S, M, L | Slideshow of a folder (Pictures by default); double-click opens the photo |
| ✅ Rappels | S, M, L | To-do list: tick to complete, "+" to add |

## Usage

| Action | Result |
|---|---|
| Click the tray icon, or right-click → **Modifier les widgets…** | Opens the gallery: click a preview to add it |
| Drag a widget | Moves it (snaps to screen edges and to the other widgets) |
| Right-click a widget | Size, settings (city, time zones, folder, color…), remove |
| (−) on a widget while the gallery is open | Removes it |
| Tray icon → **Lancer au démarrage de Windows** | Autostart |

Layout and contents are saved in `%APPDATA%\DeskWidgets\config.json`.

## Run from source

```bash
python -m venv .venv
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

```bash
.venv\Scripts\pythonw main.py
```

## Build the executable

```bash
.venv\Scripts\pip install pyinstaller
```

```bash
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name DeskWidgets --collect-submodules winrt --collect-data tzdata main.py
```

## How it works

- `core.py`: desktop-level windows (owned by the desktop `Progman` window and kept at the bottom of the
  z-order through `WM_WINDOWPOSCHANGING`), frosted glass (the wallpaper rendered like Windows does, blurred,
  then the part behind each widget is drawn), shadows, configuration, settings dialog.
- `kinds.py`: the widgets, each drawn with QPainter. Add one by subclassing `Kind` and listing it in `KINDS`.
- `services.py`: shared data (weather, Windows media controls, system usage), refreshed in the background.
- `gallery.py`: the widget gallery.

The weather location is guessed from your internet connection (ipwho.is) unless you type a city in the widget's settings.
