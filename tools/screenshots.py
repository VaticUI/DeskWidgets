"""Renders the README screenshots with fictional data only (generated wallpaper, cover, photo).

Usage: python tools/screenshots.py docs <empty temp folder for the config>
"""
import sys, os, time, math
os.environ["APPDATA"] = sys.argv[2]
OUT = sys.argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QTimer, QRectF, QRect, QPointF, QObject, Signal, QBuffer, QByteArray, Qt
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QRadialGradient, QPainterPath, QFont

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
import core, services, kinds

W, H = 1600, 900


def wallpaper(w, h, dark):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, w, h)
    if dark:
        g.setColorAt(0, QColor(24, 18, 64)); g.setColorAt(0.5, QColor(80, 30, 110)); g.setColorAt(1, QColor(20, 60, 120))
    else:
        g.setColorAt(0, QColor(120, 170, 255)); g.setColorAt(0.5, QColor(240, 160, 210)); g.setColorAt(1, QColor(255, 200, 140))
    p.fillRect(0, 0, w, h, g)
    blobs = [(0.2, 0.3, 0.35, QColor(255, 120, 80)), (0.75, 0.25, 0.3, QColor(80, 180, 255)),
             (0.55, 0.8, 0.4, QColor(160, 90, 255)), (0.9, 0.85, 0.25, QColor(255, 90, 160))]
    for x, y, r, c in blobs:
        rg = QRadialGradient(QPointF(x * w, y * h), r * w)
        c1 = QColor(c); c1.setAlpha(170 if dark else 150)
        c2 = QColor(c); c2.setAlpha(0)
        rg.setColorAt(0, c1); rg.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, rg)
    p.end()
    return img


def cover():
    img = QImage(400, 400, QImage.Format_RGB32)
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 400, 400); g.setColorAt(0, QColor(255, 94, 98)); g.setColorAt(1, QColor(120, 40, 200))
    p.fillRect(0, 0, 400, 400, g)
    p.setPen(Qt.NoPen)
    for i in range(6):
        p.setBrush(QColor(255, 255, 255, 30 + i * 10))
        p.drawEllipse(QPointF(200, 200), 180 - i * 28, 180 - i * 28)
    p.end()
    buf = QBuffer(); buf.open(QBuffer.WriteOnly); img.save(buf, "PNG")
    return bytes(buf.data())


def landscape():
    w, h = 800, 800
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, h); g.setColorAt(0, QColor(255, 170, 110)); g.setColorAt(0.55, QColor(255, 220, 170))
    g.setColorAt(1, QColor(255, 230, 200)); p.fillRect(0, 0, w, h, g)
    p.setPen(Qt.NoPen); p.setBrush(QColor(255, 245, 220)); p.drawEllipse(QPointF(560, 330), 70, 70)
    for k, (col, base) in enumerate([(QColor(120, 90, 140), 470), (QColor(80, 60, 110), 560), (QColor(40, 34, 70), 660)]):
        path = QPainterPath(); path.moveTo(0, h)
        for x in range(0, w + 1, 20):
            path.lineTo(x, base - 90 * abs(math.sin(x / (140 + 40 * k) + k)) - 30 * math.sin(x / 37.0 + k))
        path.lineTo(w, h); path.closeSubpath(); p.setBrush(col); p.drawPath(path)
    p.end()
    return img


class FakeMedia(QObject):
    updated = Signal()

    def __init__(self):
        super().__init__()
        self.thumb = cover()
        self.info = {"has_media": True, "title": "Midnight Drive", "artist": "The Neon Hours", "app": "Spotify",
                     "playing": True, "position": 83, "updated": time.time(), "duration": 214}

    def position(self):
        return 83.0

    def command(self, name):
        pass


services._instances["media"] = FakeMedia()
core.init()
# fictional data only: no personal folder, no guessed location
kinds.Photos.defaults = {"folder": os.path.join(sys.argv[2], "no-photos"), "minutes": 1440}
kinds.Weather.defaults = {"city": "Paris"}


class Host(QWidget):
    pass


host = Host()
host.manager = type("M", (), {"config": type("C", (), {"save": lambda self: None})()})()

PHOTO = landscape()


def make(kind, **settings):
    k = kinds.BY_ID[kind](host, dict(settings), preview=True)
    assert kind != "weather" or k.s["city"] == "Paris"
    if kind == "photos":
        k.img, k.loading = PHOTO, False
    return k


widgets = None


def build():
    global widgets
    widgets = {
        "clock_s": make("clock", city="local"),
        "clock_m": make("clock", city1="Europe/Paris", city2="America/New_York", city3="Asia/Tokyo", city4="Australia/Sydney"),
        "cal_s": make("calendar"), "cal_m": make("calendar"),
        "weather_m": make("weather", city="Paris"), "weather_s": make("weather", city="Paris"),
        "weather_l": make("weather", city="Paris"),
        "music_m": make("music"), "music_s": make("music"),
        "system_m": make("system"), "system_s": make("system"),
        "notes_s": make("notes", text="Groceries\nMilk, eggs, coffee\nBread", color="yellow"),
        "notes_m": make("notes", text="Ideas\nA widget for the moon phase 🌙", color="glass"),
        "photos_m": make("photos"), "photos_s": make("photos"), "photos_l": make("photos"),
        "rem_m": make("reminders", items=[{"text": "Book the dentist", "done": False},
                                          {"text": "Water the plants", "done": True},
                                          {"text": "Send the invoice", "done": False}]),
        "cal_l": make("calendar"),
    }


def set_wall(dark):
    core.theme.dark = dark
    wp = wallpaper(W, H, dark)
    core.backdrop.screens = [(QRect(0, 0, W, H), core.blur_image(wp))]
    return wp


M = core.MARGIN


def desktop(dark, path):
    wp = set_wall(dark)
    img = QImage(wp)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    # macOS-like layout: two columns on the right, one on the left
    G = 20
    layout = [
        ("clock_s", "small", 1600 - 40 - 364, 40), ("cal_s", "small", 1600 - 40 - 170, 40),
        ("weather_m", "medium", 1600 - 40 - 364, 40 + 170 + G),
        ("music_m", "medium", 1600 - 40 - 364, 40 + 2 * (170 + G)),
        ("rem_m", "medium", 1600 - 40 - 364, 40 + 3 * (170 + G)),
        ("photos_s", "small", 1600 - 40 - 364 - G - 170, 40), ("system_s", "small", 1600 - 40 - 364 - G - 170, 40 + 170 + G),
        ("notes_s", "small", 1600 - 40 - 364 - G - 170, 40 + 2 * (170 + G)),
        ("clock_m", "medium", 40, 40), ("cal_m", "medium", 40, 40 + 170 + G),
    ]
    for key, size, x, y in layout:
        w, h = core.SIZES[size]
        core.paint_card(p, QRectF(x, y, w, h), widgets[key], size, QRect(x, y, w, h))
    p.end()
    img.save(path)


def grid(path, dark=True):
    set_wall(dark)
    rows = [[("clock_s", "small"), ("clock_m", "medium"), ("cal_s", "small"), ("cal_m", "medium")],
            [("weather_s", "small"), ("weather_m", "medium"), ("music_s", "small"), ("music_m", "medium")],
            [("system_s", "small"), ("system_m", "medium"), ("notes_s", "small"), ("notes_m", "medium")],
            [("cal_l", "large"), ("weather_l", "large"), ("photos_l", "large"), ("rem_m", "large")]]
    G = 24
    width = 40 + 2 * (170 + G) + 2 * (364 + G) + 16
    height = 40 + 3 * (170 + G) + 384 + 40
    width = max(width, 40 + 4 * (364 + G) + 16)
    wp = wallpaper(width, height, dark)
    core.backdrop.screens = [(QRect(0, 0, width, height), core.blur_image(wp))]
    img = QImage(wp)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    y = 40
    for row in rows:
        x = 40
        rh = 0
        for key, size in row:
            w, h = core.SIZES[size]
            core.paint_card(p, QRectF(x, y, w, h), widgets[key], size, QRect(x, y, w, h))
            x += w + G
            rh = max(rh, h)
        y += rh + G
    p.end()
    img.save(path)


def gallery_shot(path):
    import gallery
    core.theme.dark = True
    set_wall(True)
    m = type("M", (), {"edit_mode": True, "add": lambda *a: None, "set_edit": lambda *a: None})()
    g = gallery.Gallery(m)
    g.list.setCurrentRow(2)
    QTimer.singleShot(1500, lambda: (g.grab().save(path), app.quit()))


def go():
    w = services.get("weather")
    if not w.get("Paris"):
        QTimer.singleShot(500, go)
        return
    desktop(True, os.path.join(OUT, "desktop-dark.png"))
    desktop(False, os.path.join(OUT, "desktop-light.png"))
    grid(os.path.join(OUT, "widgets.png"))
    gallery_shot(os.path.join(OUT, "gallery.png"))


build()
QTimer.singleShot(5000, go)
app.exec()
