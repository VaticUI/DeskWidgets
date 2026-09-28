"""
DeskWidgets core: configuration, theme, frosted-glass backdrop, desktop-level windows.
"""

import os
import sys
import json
import time
import uuid
import ctypes
import winreg
from ctypes import wintypes

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRectF, QRect, QPointF, QPoint
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QImage, QGuiApplication, QCursor, QAction, QFontMetricsF,
)
from PySide6.QtWidgets import (
    QWidget, QMenu, QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox, QPushButton, QHBoxLayout,
    QVBoxLayout, QFileDialog, QLabel,
)

APP_NAME = "DeskWidgets"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# card sizes, in the proportions of macOS widgets
SIZES = {"small": (170, 170), "medium": (364, 170), "large": (364, 384)}
SIZE_NAMES = {"small": "Small", "medium": "Medium", "large": "Large"}
RADIUS = 22
MARGIN = 16          # room around the card for the shadow
GAP = 16             # space between widgets when snapping

user32 = ctypes.windll.user32
user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]


# --------------------------------------------------------------------------- #
#  Small helpers
# --------------------------------------------------------------------------- #
def font(size, weight=QFont.Normal, rounded=False):
    f = QFont()
    f.setFamilies(["SF Pro Rounded", "Segoe UI Variable Display", "Segoe UI", "Segoe UI Emoji"]
                  if rounded else ["Segoe UI Variable Display", "Segoe UI", "Segoe UI Emoji"])
    f.setPixelSize(max(1, int(size)))
    f.setWeight(weight)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def emoji_font(size):
    f = QFont()
    f.setFamilies(["Segoe UI Emoji"])
    f.setPixelSize(max(1, int(size)))
    return f


def elide(p, text, rect, flags=Qt.AlignLeft | Qt.AlignVCenter):
    fm = QFontMetricsF(p.font())
    p.drawText(rect, flags, fm.elidedText(text or "", Qt.ElideRight, rect.width()))


def rounded_path(rect, r):
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    return path


def blur_image(img: QImage, factor=24):
    """Cheap, good-looking blur: shrink a lot, then let the smooth upscale do the rest."""
    w, h = img.width(), img.height()
    small = img.scaled(max(1, w // factor), max(1, h // factor), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(max(1, w // 4), max(1, h // 4), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


# --------------------------------------------------------------------------- #
#  Theme (follows Windows light / dark mode)
# --------------------------------------------------------------------------- #
class Theme(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.dark = self._read()
        t = QTimer(self)
        t.timeout.connect(self._poll)
        t.start(4000)

    @staticmethod
    def _read():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except OSError:
            return True

    def _poll(self):
        d = self._read()
        if d != self.dark:
            self.dark = d
            self.changed.emit()

    @property
    def fg(self):
        return QColor(255, 255, 255) if self.dark else QColor(20, 20, 22)

    @property
    def fg2(self):
        return QColor(255, 255, 255, 150) if self.dark else QColor(20, 20, 22, 140)

    @property
    def fg3(self):
        return QColor(255, 255, 255, 60) if self.dark else QColor(20, 20, 22, 45)

    @property
    def tint(self):
        return QColor(30, 30, 34, 150) if self.dark else QColor(250, 250, 252, 165)

    @property
    def solid(self):
        return QColor(38, 38, 42) if self.dark else QColor(246, 246, 248)


theme = None  # set by init()


# --------------------------------------------------------------------------- #
#  Frosted glass: the wallpaper, blurred, behind each widget
# --------------------------------------------------------------------------- #
class Backdrop(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.sig = None
        self.screens = []       # [(QRect geometry, blurred QImage at 1/4 scale)]
        self.reload()
        t = QTimer(self)
        t.timeout.connect(self._poll)
        t.start(5000)

    @staticmethod
    def _wallpaper():
        buf = ctypes.create_unicode_buffer(1024)
        user32.SystemParametersInfoW(0x73, 1024, buf, 0)   # SPI_GETDESKWALLPAPER
        style = "10"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k:
                style = str(winreg.QueryValueEx(k, "WallpaperStyle")[0])
        except OSError:
            pass
        return buf.value, style

    def _signature(self):
        path, style = self._wallpaper()
        try:
            mtime = os.path.getmtime(path) if path else 0
        except OSError:
            mtime = 0
        geos = tuple((s.geometry().getRect()) for s in QGuiApplication.screens())
        return path, style, mtime, geos

    def _poll(self):
        if self._signature() != self.sig:
            self.reload()
            self.changed.emit()

    def reload(self):
        self.sig = self._signature()
        path, style = self.sig[0], self.sig[1]
        img = QImage(path) if path else QImage()
        self.screens = []
        for s in QGuiApplication.screens():
            g = s.geometry()
            canvas = QImage(g.width(), g.height(), QImage.Format_RGB32)
            canvas.fill(QColor(30, 40, 60))
            if not img.isNull():
                p = QPainter(canvas)
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                if style == "2":                                     # stretch
                    p.drawImage(QRectF(0, 0, g.width(), g.height()), img)
                else:
                    mode = Qt.KeepAspectRatio if style == "6" else Qt.KeepAspectRatioByExpanding  # fit / fill
                    sz = img.size().scaled(g.width(), g.height(), mode)
                    p.drawImage(QRectF((g.width() - sz.width()) / 2, (g.height() - sz.height()) / 2,
                                       sz.width(), sz.height()), img)
                p.end()
            self.screens.append((QRect(g), blur_image(canvas)))

    def paint(self, p, target: QRectF, global_rect: QRect):
        """Draw the blurred wallpaper behind global_rect into target."""
        for g, img in self.screens:
            if g.intersects(global_rect):
                src = QRectF((global_rect.x() - g.x()) / 4, (global_rect.y() - g.y()) / 4,
                             global_rect.width() / 4, global_rect.height() / 4)
                p.drawImage(target, img, src)
                return True
        return False


backdrop = None


# --------------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------------- #
class Config:
    def __init__(self):
        self.data = {"widgets": []}
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            pass
        self.first_run = not os.path.exists(CONFIG_PATH)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self.save_now)

    @property
    def widgets(self):
        return self.data.setdefault("widgets", [])

    def save(self):
        self._timer.start()

    def save_now(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONFIG_PATH)

    @staticmethod
    def new_entry(kind, size, x, y, settings=None):
        return {"id": uuid.uuid4().hex[:12], "kind": kind, "size": size, "x": x, "y": y,
                "settings": settings or {}}


def init():
    global theme, backdrop
    theme = Theme()
    backdrop = Backdrop()


# --------------------------------------------------------------------------- #
#  Shadow (cached per card size)
# --------------------------------------------------------------------------- #
_shadow_cache = {}


def shadow_image(w, h):
    key = (w, h)
    img = _shadow_cache.get(key)
    if img is None:
        W, H = w + 2 * MARGIN, h + 2 * MARGIN
        img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawRoundedRect(QRectF(MARGIN, MARGIN + 4, w, h), RADIUS, RADIUS)
        p.end()
        small = img.scaled(W // 6, H // 6, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        img = small.scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        _shadow_cache[key] = img
    return img


def paint_card(p: QPainter, card: QRectF, kind, size, global_rect=None, shadow=True):
    """Shadow + background (kind gradient, or frosted glass) + the kind's content."""
    if shadow:
        p.drawImage(QPointF(card.x() - MARGIN, card.y() - MARGIN), shadow_image(int(card.width()), int(card.height())))
    path = rounded_path(card, RADIUS)
    p.save()
    p.setClipPath(path)
    bg = kind.background(card, size)
    if bg is not None:
        p.fillRect(card, bg)
    else:
        if global_rect is None or not backdrop.paint(p, card, global_rect):
            p.fillRect(card, theme.solid)
        p.fillRect(card, theme.tint)
    kind.paint(p, card, size)
    p.restore()
    # thin border, like macOS
    p.setPen(QColor(255, 255, 255, 28) if theme.dark else QColor(0, 0, 0, 18))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)


# --------------------------------------------------------------------------- #
#  Menus / dialogs styling
# --------------------------------------------------------------------------- #
def menu_qss():
    if theme.dark:
        return ("QMenu{background:#2a2a2e;color:#fff;border:1px solid #3a3a3e;border-radius:8px;padding:5px;}"
                "QMenu::item{padding:6px 22px 6px 14px;border-radius:5px;}"
                "QMenu::item:selected{background:#0a64d6;}QMenu::item:disabled{color:#777;}"
                "QMenu::separator{height:1px;background:#3a3a3e;margin:4px 8px;}")
    return ("QMenu{background:#f4f4f6;color:#111;border:1px solid #d0d0d4;border-radius:8px;padding:5px;}"
            "QMenu::item{padding:6px 22px 6px 14px;border-radius:5px;}"
            "QMenu::item:selected{background:#0a64d6;color:#fff;}QMenu::item:disabled{color:#999;}"
            "QMenu::separator{height:1px;background:#d0d0d4;margin:4px 8px;}")


def dialog_qss():
    if theme.dark:
        return ("QDialog{background:#1f1f22;} QLabel{color:#ddd;} "
                "QLineEdit,QComboBox,QSpinBox{background:#2c2c30;color:#fff;border:1px solid #3a3a3e;"
                "border-radius:6px;padding:5px 8px;} QComboBox QAbstractItemView{background:#2c2c30;color:#fff;}"
                "QPushButton{background:#3a3a3e;color:#fff;border:none;border-radius:6px;padding:6px 14px;}"
                "QPushButton:default{background:#0a64d6;}")
    return ("QDialog{background:#f6f6f8;} QLabel{color:#222;} "
            "QLineEdit,QComboBox,QSpinBox{background:#fff;color:#111;border:1px solid #ccc;"
            "border-radius:6px;padding:5px 8px;}"
            "QPushButton{background:#e4e4e8;color:#111;border:none;border-radius:6px;padding:6px 14px;}"
            "QPushButton:default{background:#0a64d6;color:#fff;}")


class SettingsDialog(QDialog):
    """Generic form built from a kind's settings_fields():
    (key, label, "text" | "choice" | "folder" | "int", extra)."""

    def __init__(self, title, fields, values):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle(title)
        self.setStyleSheet(dialog_qss())
        self.setMinimumWidth(380)
        self.inputs = {}
        form = QFormLayout()
        form.setSpacing(10)
        for key, label, typ, extra in fields:
            val = values.get(key)
            if typ == "choice":
                w = QComboBox()
                for code, name in extra:
                    w.addItem(name, code)
                i = w.findData(val)
                w.setCurrentIndex(max(0, i))
            elif typ == "int":
                w = QSpinBox()
                w.setRange(*extra)
                w.setValue(int(val if val is not None else extra[0]))
            elif typ == "folder":
                w = QWidget()
                h = QHBoxLayout(w)
                h.setContentsMargins(0, 0, 0, 0)
                ed = QLineEdit(val or "")
                b = QPushButton("…")
                b.clicked.connect(lambda _=False, ed=ed: self._pick(ed))
                h.addWidget(ed, 1)
                h.addWidget(b)
                w.edit = ed
            else:
                w = QLineEdit(val or "")
                if extra:
                    w.setPlaceholderText(extra)
            self.inputs[key] = (typ, w)
            form.addRow(label, w)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        v = QVBoxLayout(self)
        v.addLayout(form)
        v.addSpacing(8)
        v.addLayout(row)

    def _pick(self, ed):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder", ed.text())
        if d:
            ed.setText(os.path.normpath(d))

    def values(self):
        out = {}
        for key, (typ, w) in self.inputs.items():
            if typ == "choice":
                out[key] = w.currentData()
            elif typ == "int":
                out[key] = w.value()
            elif typ == "folder":
                out[key] = w.edit.text().strip()
            else:
                out[key] = w.text().strip()
        return out


# --------------------------------------------------------------------------- #
#  The desktop-level widget window
# --------------------------------------------------------------------------- #
WM_WINDOWPOSCHANGING = 0x0046
SWP_NOZORDER = 0x0004
HWND_BOTTOM = 1


class WINDOWPOS(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND),
                ("x", ctypes.c_int), ("y", ctypes.c_int), ("cx", ctypes.c_int), ("cy", ctypes.c_int),
                ("flags", wintypes.UINT)]


class WidgetWindow(QWidget):
    def __init__(self, manager, entry, kind_cls):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnBottomHint
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.manager = manager
        self.entry = entry
        self.kind = kind_cls(self, entry.setdefault("settings", {}), preview=False)
        self.press = None
        self.dragging = False
        self.hover_remove = False
        self.apply_size()
        self.move(entry["x"] - MARGIN, entry["y"] - MARGIN)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.kind.interval)
        backdrop.changed.connect(self.update)
        theme.changed.connect(self.update)

    # --- geometry ------------------------------------------------------- #
    @property
    def size_name(self):
        return self.entry["size"]

    def card_size(self):
        return SIZES[self.size_name]

    def apply_size(self):
        w, h = self.card_size()
        self.setFixedSize(w + 2 * MARGIN, h + 2 * MARGIN)
        self.kind.layout_children(self.card_rect(), self.size_name)

    def card_rect(self):
        w, h = self.card_size()
        return QRectF(MARGIN, MARGIN, w, h)

    def global_card(self):
        w, h = self.card_size()
        return QRect(self.x() + MARGIN, self.y() + MARGIN, w, h)

    # --- keep it on the desktop ------------------------------------------ #
    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self.pin)     # after Qt has finished setting the window up

    def pin(self):
        """Owned by the desktop: stays visible with Win+D, never above other windows.
        Re-applied regularly (Explorer restarts, Qt resetting the owner)."""
        hwnd = int(self.winId())
        progman = user32.FindWindowW("Progman", None)
        if progman and user32.GetWindow(hwnd, 4) != progman:            # GW_OWNER
            user32.SetWindowLongPtrW(hwnd, -8, progman)                  # GWLP_HWNDPARENT
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def nativeEvent(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_WINDOWPOSCHANGING:
            wp = WINDOWPOS.from_address(msg.lParam)
            if not wp.flags & SWP_NOZORDER:
                wp.hwndInsertAfter = HWND_BOTTOM
        return False, 0

    # --- painting ---------------------------------------------------------- #
    def tick(self):
        self.kind.tick()
        self.update()
        if time.monotonic() - getattr(self, "_pinned_at", 0) > 5:
            self._pinned_at = time.monotonic()
            self.pin()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        card = self.card_rect()
        paint_card(p, card, self.kind, self.size_name, self.global_card())
        if self.manager.edit_mode:
            c = QPointF(card.left() + 3, card.top() + 3)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(90, 90, 96) if not self.hover_remove else QColor(230, 60, 60))
            p.drawEllipse(c, 10, 10)
            p.setBrush(QColor(255, 255, 255))
            p.drawRoundedRect(QRectF(c.x() - 5, c.y() - 1.2, 10, 2.4), 1.2, 1.2)
        p.end()

    def remove_hit(self, pos):
        c = self.card_rect().topLeft() + QPointF(3, 3)
        return self.manager.edit_mode and (QPointF(pos) - c).manhattanLength() < 16

    # --- mouse: drag anywhere, click goes to the kind ------------------- #
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.remove_hit(e.position()):
                self.manager.remove(self)
                return
            self.press = (e.globalPosition().toPoint(), self.pos())
            self.dragging = False

    def mouseMoveEvent(self, e):
        if self.press is None:
            hr = self.remove_hit(e.position())
            if hr != self.hover_remove:
                self.hover_remove = hr
                self.update()
            self.kind.hover(e.position())
            return
        start, orig = self.press
        d = e.globalPosition().toPoint() - start
        if not self.dragging and d.manhattanLength() > 5:
            self.dragging = True
        if self.dragging:
            self.move(orig + d)
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self.press is None:
            return
        self.press = None
        if self.dragging:
            self.dragging = False
            self.move(self.manager.snap(self, self.pos()))
            self.save_pos()
            self.update()
        elif self.kind.click(e.position(), self.card_rect(), self.size_name):
            self.update()

    def mouseDoubleClickEvent(self, e):
        self.kind.double_click(e.position(), self.card_rect(), self.size_name)

    def leaveEvent(self, e):
        self.hover_remove = False
        self.kind.hover(None)
        self.update()

    def save_pos(self):
        self.entry["x"], self.entry["y"] = self.x() + MARGIN, self.y() + MARGIN
        self.manager.config.save()

    # --- context menu -------------------------------------------------------- #
    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(menu_qss())
        if len(self.kind.sizes) > 1:
            for s in self.kind.sizes:
                a = QAction(SIZE_NAMES[s], m, checkable=True)
                a.setChecked(s == self.size_name)
                a.triggered.connect(lambda _=False, s=s: self.set_size(s))
                m.addAction(a)
            m.addSeparator()
        if self.kind.settings_fields():
            a = m.addAction(f"Edit \"{self.kind.title}\"…")
            a.triggered.connect(self.edit_settings)
        m.addAction("Remove widget").triggered.connect(lambda: self.manager.remove(self))
        m.addSeparator()
        m.addAction("Edit widgets…").triggered.connect(self.manager.open_gallery)
        m.exec(e.globalPos())

    def set_size(self, s):
        self.entry["size"] = s
        self.apply_size()
        self.move(self.manager.snap(self, self.pos()))
        self.save_pos()
        self.update()

    def edit_settings(self):
        dlg = SettingsDialog(self.kind.title, self.kind.settings_fields(), self.kind.s)
        if dlg.exec():
            self.kind.s.update(dlg.values())
            self.kind.settings_changed()
            self.manager.config.save()
            self.update()

    def closeEvent(self, e):
        self.kind.detach()
        super().closeEvent(e)
