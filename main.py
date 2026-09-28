"""
DeskWidgets — macOS-style widgets on the Windows desktop.

Right-click the tray icon (or a widget) → "Edit widgets…" to open the gallery.
"""

import os
import sys
import ctypes
import winreg

from PySide6.QtCore import Qt, QRect, QRectF, QPoint
from PySide6.QtGui import QPainter, QColor, QPixmap, QIcon, QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

import core
from core import Config, WidgetWindow, SIZES, MARGIN, GAP
from kinds import BY_ID

EDGE = 24   # distance kept from the screen edges


class Manager:
    def __init__(self, config: Config):
        self.config = config
        self.windows = []
        self.edit_mode = False
        self.gallery = None
        for entry in list(config.widgets):
            if entry.get("kind") in BY_ID:
                self.create(entry)

    def create(self, entry):
        w = WidgetWindow(self, entry, BY_ID[entry["kind"]])
        w.show()
        self.windows.append(w)
        return w

    def add(self, kind, size):
        w, h = SIZES[size]
        x, y = self.free_spot(w, h)
        entry = Config.new_entry(kind, size, x, y)
        self.config.widgets.append(entry)
        self.create(entry)
        self.config.save()

    def remove(self, win):
        if win.entry in self.config.widgets:
            self.config.widgets.remove(win.entry)
        if win in self.windows:
            self.windows.remove(win)
        win.close()
        win.deleteLater()
        self.config.save()

    def set_edit(self, on):
        self.edit_mode = on
        for w in self.windows:
            w.update()

    def open_gallery(self):
        if self.gallery is None:
            from gallery import Gallery
            self.gallery = Gallery(self)
        self.gallery.open()

    # --- placement ------------------------------------------------------ #
    def cards(self, exclude=None):
        return [w.global_card() for w in self.windows if w is not exclude]

    def free_spot(self, w, h):
        """First free place, from the top right corner of the main screen (icons live on the left)."""
        g = QGuiApplication.primaryScreen().availableGeometry()
        taken = [c.adjusted(-GAP + 1, -GAP + 1, GAP - 1, GAP - 1) for c in self.cards()]
        step = 8
        x = g.right() - EDGE - w
        while x >= g.left() + EDGE:
            y = g.top() + EDGE
            while y + h <= g.bottom() - EDGE:
                r = QRect(x, y, w, h)
                hit = next((t for t in taken if t.intersects(r)), None)
                if hit is None:
                    return x, y
                y = hit.bottom() + 1 if hit.bottom() + 1 > y else y + step
            x -= step
        return g.right() - EDGE - w, g.top() + EDGE

    def snap(self, win, pos: QPoint):
        """Align with the screen edges and the other widgets (with the standard gap)."""
        w, h = win.card_size()
        x, y = pos.x() + MARGIN, pos.y() + MARGIN
        center = QPoint(x + w // 2, y + h // 2)
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        xs = [g.left() + EDGE, g.right() - EDGE - w + 1]
        ys = [g.top() + EDGE, g.bottom() - EDGE - h + 1]
        for c in self.cards(exclude=win):
            xs += [c.left(), c.right() + 1 - w, c.right() + 1 + GAP, c.left() - GAP - w]
            ys += [c.top(), c.bottom() + 1 - h, c.bottom() + 1 + GAP, c.top() - GAP - h]
        T = 14
        bx = min(xs, key=lambda v: abs(v - x))
        by = min(ys, key=lambda v: abs(v - y))
        if abs(bx - x) <= T:
            x = bx
        if abs(by - y) <= T:
            y = by
        x = max(g.left(), min(x, g.right() - w + 1))
        y = max(g.top(), min(y, g.bottom() - h + 1))
        return QPoint(x - MARGIN, y - MARGIN)


# --------------------------------------------------------------------------- #
#  Tray, autostart
# --------------------------------------------------------------------------- #
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw if os.path.exists(pyw) else sys.executable}" "{os.path.abspath(__file__)}"'


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, core.APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, core.APP_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, core.APP_NAME)
            except OSError:
                pass


def make_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    colors = [QColor(10, 132, 255), QColor(255, 159, 10), QColor(48, 209, 88), QColor(255, 69, 58)]
    for i, c in enumerate(colors):
        p.setBrush(c)
        p.drawRoundedRect(QRectF(4 + (i % 2) * 30, 4 + (i // 2) * 30, 26, 26), 8, 8)
    p.end()
    return QIcon(pm)


def main():
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\DeskWidgets_single_instance")
    if ctypes.windll.kernel32.GetLastError() == 183:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(core.APP_NAME)
    core.init()

    config = Config()
    manager = Manager(config)
    if config.first_run:
        for kind, size in (("clock", "small"), ("calendar", "small"), ("weather", "medium")):
            manager.add(kind, size)

    icon = make_icon()
    app.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("DeskWidgets")
    menu = QMenu()
    menu.setStyleSheet(core.menu_qss())
    menu.addAction("Edit widgets…").triggered.connect(manager.open_gallery)
    menu.addSeparator()
    auto = QAction("Launch at Windows startup", menu, checkable=True)
    auto.setChecked(autostart_enabled())
    auto.toggled.connect(set_autostart)
    menu.addAction(auto)
    menu.addSeparator()
    menu.addAction("Quit").triggered.connect(app.quit)
    core.theme.changed.connect(lambda: menu.setStyleSheet(core.menu_qss()))
    tray.setContextMenu(menu)
    tray.activated.connect(lambda r: manager.open_gallery() if r == QSystemTrayIcon.Trigger else None)
    tray.show()
    app.aboutToQuit.connect(config.save_now)

    if config.first_run:
        manager.open_gallery()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
