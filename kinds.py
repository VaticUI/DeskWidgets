"""
The widgets. Each kind draws itself with QPainter inside its card and can react to clicks.

To add a widget: subclass Kind, then add it to KINDS at the bottom of this file.
"""

import os
import math
import time
import random
import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QLocale, QDate, QEvent
from PySide6.QtGui import (
    QPainter, QColor, QFont, QImage, QLinearGradient, QPen, QPainterPath, QFontMetricsF, QTextOption,
)
from PySide6.QtWidgets import QPlainTextEdit, QLineEdit

import core
import services
from core import font, emoji_font, elide, rounded_path

EN = QLocale(QLocale.English, QLocale.UnitedStates)
RED = QColor(255, 69, 58)
ORANGE = QColor(255, 159, 10)
GREEN = QColor(48, 209, 88)
BLUE = QColor(10, 132, 255)
PURPLE = QColor(191, 90, 242)
WHITE = QColor(255, 255, 255)


def cap(s):
    return s[:1].upper() + s[1:] if s else s


class Kind:
    id = ""
    title = ""
    desc = ""
    icon = "🧩"
    sizes = ("small", "medium", "large")
    interval = 1000          # ms between refreshes
    defaults = {}

    def __init__(self, host, settings, preview=False):
        self.host = host
        self.s = settings
        self.preview = preview
        for k, v in self.defaults.items():
            self.s.setdefault(k, v() if callable(v) else v)
        self.hits = {}
        self.hot = None

    # drawing
    def background(self, card, size):
        return None          # None = frosted glass

    def paint(self, p, r, size):
        pass

    # events
    def tick(self):
        pass

    def click(self, pos, card, size):
        for name, rect in self.hits.items():
            if rect.contains(pos):
                self.on_hit(name)
                return True
        return False

    def on_hit(self, name):
        pass

    def double_click(self, pos, card, size):
        pass

    def hover(self, pos):
        hot = None
        if pos is not None:
            hot = next((n for n, r in self.hits.items() if r.contains(pos)), None)
        if hot != self.hot:
            self.hot = hot
            self.update()

    # settings
    def settings_fields(self):
        return []

    def settings_changed(self):
        pass

    # child widgets (notes editor, reminders input)
    def layout_children(self, card, size):
        pass

    def detach(self):
        pass

    def update(self):
        if self.host is not None:
            self.host.update()

    # colors (glass follows the Windows theme)
    @property
    def fg(self):
        return core.theme.fg

    @property
    def fg2(self):
        return core.theme.fg2

    @property
    def fg3(self):
        return core.theme.fg3


# --------------------------------------------------------------------------- #
#  Clock
# --------------------------------------------------------------------------- #
CITIES = [
    ("local", "Local time"), ("Europe/Paris", "Paris"), ("Europe/London", "London"),
    ("Europe/Berlin", "Berlin"), ("Europe/Moscow", "Moscow"), ("America/New_York", "New York"),
    ("America/Chicago", "Chicago"), ("America/Los_Angeles", "Los Angeles"), ("America/Montreal", "Montreal"),
    ("America/Sao_Paulo", "São Paulo"), ("America/Martinique", "Martinique"), ("Indian/Reunion", "Réunion"),
    ("Pacific/Tahiti", "Tahiti"), ("Africa/Casablanca", "Casablanca"), ("Africa/Johannesburg", "Johannesburg"),
    ("Asia/Dubai", "Dubai"), ("Asia/Kolkata", "Mumbai"), ("Asia/Singapore", "Singapore"),
    ("Asia/Shanghai", "Beijing"), ("Asia/Tokyo", "Tokyo"), ("Australia/Sydney", "Sydney"),
    ("Pacific/Auckland", "Auckland"),
]
CITY_NAMES = dict(CITIES)


def city_now(tz):
    if tz == "local" or not tz:
        return datetime.datetime.now()
    try:
        return datetime.datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    except Exception:
        return datetime.datetime.now()


def city_label(tz):
    return "Local" if tz == "local" else CITY_NAMES.get(tz, tz.rsplit("/", 1)[-1].replace("_", " "))


def draw_dial(p, c: QPointF, R, now, dark, numbers=True):
    face, ink = (QColor(28, 28, 30), WHITE) if dark else (QColor(252, 252, 252), QColor(20, 20, 22))
    p.setPen(Qt.NoPen)
    p.setBrush(face)
    p.drawEllipse(c, R, R)
    if numbers:
        p.setFont(font(R * 0.22, QFont.DemiBold))
        p.setPen(ink)
        for n in range(1, 13):
            a = math.radians(n * 30 - 90)
            pt = QPointF(c.x() + math.cos(a) * R * 0.76, c.y() + math.sin(a) * R * 0.76)
            p.drawText(QRectF(pt.x() - R * 0.2, pt.y() - R * 0.15, R * 0.4, R * 0.3), Qt.AlignCenter, str(n))
    else:
        for n in range(12):
            a = math.radians(n * 30)
            pen = QPen(ink, max(1.5, R * 0.05), Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(c.x() + math.sin(a) * R * 0.78, c.y() - math.cos(a) * R * 0.78),
                       QPointF(c.x() + math.sin(a) * R * 0.88, c.y() - math.cos(a) * R * 0.88))

    def hand(angle, length, width, color, back=0.0):
        a = math.radians(angle)
        dx, dy = math.sin(a), -math.cos(a)
        p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(c.x() - dx * back, c.y() - dy * back), QPointF(c.x() + dx * length, c.y() + dy * length))

    h, m, s = now.hour % 12, now.minute, now.second
    hand((h + m / 60) * 30, R * 0.5, max(2.5, R * 0.075), ink)
    hand((m + s / 60) * 6, R * 0.74, max(2.0, R * 0.055), ink)
    p.setPen(Qt.NoPen)
    p.setBrush(ink)
    p.drawEllipse(c, R * 0.06, R * 0.06)
    hand(s * 6, R * 0.82, max(1.0, R * 0.022), ORANGE, back=R * 0.15)
    p.setPen(Qt.NoPen)
    p.setBrush(ORANGE)
    p.drawEllipse(c, R * 0.035, R * 0.035)


class Clock(Kind):
    id = "clock"
    title = "Clock"
    desc = "The time here or anywhere, analog or digital. The medium size shows four cities."
    icon = "🕒"
    sizes = ("small", "medium")
    defaults = {"city": "local", "style": "analog", "city1": "local", "city2": "America/New_York",
                "city3": "Asia/Tokyo", "city4": "Australia/Sydney"}

    def settings_fields(self):
        return [("style", "Style (small)", "choice", [("analog", "Analog"), ("digital", "Digital")]),
                ("city", "City (small)", "choice", CITIES),
                ("city1", "City 1 (medium)", "choice", CITIES), ("city2", "City 2 (medium)", "choice", CITIES),
                ("city3", "City 3 (medium)", "choice", CITIES), ("city4", "City 4 (medium)", "choice", CITIES)]

    def paint(self, p, r, size):
        if size == "small":
            now = city_now(self.s["city"])
            if self.s["style"] == "digital":
                p.setPen(self.fg2)
                p.setFont(font(13, QFont.DemiBold))
                p.drawText(QRectF(r.left() + 16, r.top() + 14, r.width() - 32, 20), Qt.AlignLeft,
                           city_label(self.s["city"]).upper())
                p.setPen(self.fg)
                p.setFont(font(54, QFont.Light))
                p.drawText(QRectF(r.left(), r.top() + 36, r.width(), 70), Qt.AlignCenter, now.strftime("%H:%M"))
                p.setPen(self.fg2)
                p.setFont(font(14, QFont.DemiBold))
                p.drawText(QRectF(r.left(), r.top() + 108, r.width(), 22), Qt.AlignCenter,
                           cap(EN.toString(QDate(now.year, now.month, now.day), "dddd, MMMM d")))
                # seconds as a thin progress line
                w = (r.width() - 40) * now.second / 60
                p.setPen(Qt.NoPen)
                p.setBrush(self.fg3)
                p.drawRoundedRect(QRectF(r.left() + 20, r.bottom() - 22, r.width() - 40, 3), 1.5, 1.5)
                p.setBrush(ORANGE)
                p.drawRoundedRect(QRectF(r.left() + 20, r.bottom() - 22, max(3, w), 3), 1.5, 1.5)
                return
            c = r.center()
            R = r.width() / 2 - 12
            draw_dial(p, c, R, now, core.theme.dark)
            if self.s["city"] != "local":
                p.setPen(QColor(255, 255, 255, 120) if core.theme.dark else QColor(0, 0, 0, 110))
                p.setFont(font(R * 0.13, QFont.DemiBold))
                p.drawText(QRectF(c.x() - R, c.y() + R * 0.2, 2 * R, R * 0.2), Qt.AlignCenter,
                           city_label(self.s["city"])[:3].upper())
        else:
            local = datetime.datetime.now()
            cw = r.width() / 4
            for i in range(4):
                tz = self.s[f"city{i + 1}"]
                now = city_now(tz)
                c = QPointF(r.left() + cw * i + cw / 2, r.top() + 64)
                night = now.hour < 6 or now.hour >= 19
                draw_dial(p, c, 36, now, night, numbers=False)
                p.setPen(self.fg)
                p.setFont(font(13, QFont.DemiBold))
                elide(p, city_label(tz), QRectF(c.x() - cw / 2 + 4, r.top() + 108, cw - 8, 18), Qt.AlignCenter)
                days = (now.date() - local.date()).days
                diff = round((now - local).total_seconds() / 3600)
                day = {0: "Today", 1: "Tomorrow", -1: "Yesterday"}.get(days, "")
                p.setPen(self.fg2)
                p.setFont(font(11))
                p.drawText(QRectF(c.x() - cw / 2, r.top() + 126, cw, 16), Qt.AlignCenter, day)
                p.drawText(QRectF(c.x() - cw / 2, r.top() + 141, cw, 16), Qt.AlignCenter,
                           f"{diff:+d} h" if diff else now.strftime("%H:%M"))


# --------------------------------------------------------------------------- #
#  Calendar
# --------------------------------------------------------------------------- #
def draw_month(p, r: QRectF, today: datetime.date, fg, fg2, big=False):
    first = today.replace(day=1)
    start = first - datetime.timedelta(days=first.weekday())
    head = ["M", "T", "W", "T", "F", "S", "S"]
    cw = r.width() / 7
    top = r.top()
    hh = 22 if big else 16
    p.setFont(font(12 if big else 10, QFont.Bold))
    for i, d in enumerate(head):
        p.setPen(fg2)
        p.drawText(QRectF(r.left() + i * cw, top, cw, hh), Qt.AlignCenter, d)
    rows = 6
    rh = (r.height() - hh) / rows
    p.setFont(font(14 if big else 11, QFont.DemiBold))
    for k in range(rows * 7):
        d = start + datetime.timedelta(days=k)
        if d.month != today.month:
            continue
        cell = QRectF(r.left() + (k % 7) * cw, top + hh + (k // 7) * rh, cw, rh)
        if d == today:
            rad = min(cw, rh) / 2 - 1
            p.setPen(Qt.NoPen)
            p.setBrush(RED)
            p.drawEllipse(cell.center(), rad, rad)
            p.setPen(WHITE)
        else:
            p.setPen(fg2 if k % 7 >= 5 else fg)
        p.drawText(cell, Qt.AlignCenter, str(d.day))


class Calendar(Kind):
    id = "calendar"
    title = "Calendar"
    desc = "Today's date and the current month."
    icon = "📅"
    interval = 30_000

    def paint(self, p, r, size):
        today = datetime.date.today()
        qd = QDate(today.year, today.month, today.day)
        if size == "large":
            p.setPen(RED)
            p.setFont(font(15, QFont.Bold))
            p.drawText(QRectF(r.left() + 20, r.top() + 16, r.width() - 40, 22), Qt.AlignLeft,
                       EN.toString(qd, "MMMM").upper())
            p.setPen(self.fg2)
            p.drawText(QRectF(r.left() + 20, r.top() + 16, r.width() - 40, 22), Qt.AlignRight, str(today.year))
            p.setPen(self.fg)
            p.setFont(font(24, QFont.DemiBold))
            p.drawText(QRectF(r.left() + 20, r.top() + 40, r.width() - 40, 34), Qt.AlignLeft,
                       cap(EN.toString(qd, "dddd d")))
            draw_month(p, QRectF(r.left() + 14, r.top() + 90, r.width() - 28, r.height() - 106), today,
                       self.fg, self.fg2, big=True)
            return
        left = QRectF(r.left(), r.top(), 170, r.height())
        p.setPen(RED)
        p.setFont(font(13, QFont.Bold))
        p.drawText(QRectF(left.left() + 18, left.top() + 16, 140, 18), Qt.AlignLeft, EN.toString(qd, "dddd").upper())
        p.setPen(self.fg)
        p.setFont(font(64, QFont.Light))
        p.drawText(QRectF(left.left() + 14, left.top() + 30, 150, 80), Qt.AlignLeft | Qt.AlignVCenter, str(today.day))
        p.setPen(self.fg2)
        p.setFont(font(13, QFont.DemiBold))
        p.drawText(QRectF(left.left() + 18, left.top() + 112, 140, 18), Qt.AlignLeft,
                   cap(EN.toString(qd, "MMMM yyyy")))
        p.setFont(font(12))
        p.drawText(QRectF(left.left() + 18, left.top() + 132, 140, 18), Qt.AlignLeft,
                   f"Week {today.isocalendar()[1]} · day {today.timetuple().tm_yday}")
        if size == "medium":
            draw_month(p, QRectF(r.left() + 176, r.top() + 16, r.width() - 192, r.height() - 30), today,
                       self.fg, self.fg2)


# --------------------------------------------------------------------------- #
#  Weather
# --------------------------------------------------------------------------- #
def sky(code, day):
    code = int(code or 0)
    if not day:
        return QColor(14, 27, 62), QColor(42, 66, 112)
    if code >= 95:
        return QColor(47, 52, 68), QColor(88, 96, 118)
    if code >= 51:
        return QColor(72, 92, 116), QColor(122, 142, 164)
    if code >= 3 or code in (45, 48):
        return QColor(96, 118, 142), QColor(150, 170, 190)
    return QColor(40, 124, 214), QColor(118, 184, 240)


class Weather(Kind):
    id = "weather"
    title = "Weather"
    desc = "Temperature, conditions, and hourly and daily forecasts (Open-Meteo)."
    icon = "🌤️"
    interval = 60_000
    defaults = {"city": ""}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.svc = services.get("weather")
        self.svc.updated.connect(self.update)
        self.svc.get(self.s["city"])

    @property
    def fg(self):
        return WHITE

    @property
    def fg2(self):
        return QColor(255, 255, 255, 190)

    def settings_fields(self):
        return [("city", "City", "text", "Automatic (from your connection)")]

    def settings_changed(self):
        self.svc.get(self.s["city"])

    def data(self):
        return self.svc.get(self.s["city"])

    def background(self, card, size):
        d = self.data()
        code, day = 0, 1
        if d:
            code, day = d["f"]["current"]["weather_code"], d["f"]["current"]["is_day"]
        a, b = sky(code, day)
        g = QLinearGradient(card.topLeft(), card.bottomLeft())
        g.setColorAt(0, a)
        g.setColorAt(1, b)
        return g

    def paint(self, p, r, size):
        d = self.data()
        if not d:
            p.setPen(self.fg2)
            p.setFont(font(13))
            err = self.svc.error(self.s["city"])
            p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, err or "Loading…")
            return
        f = d["f"]
        cur = f["current"]
        label, emo = services.wmo(cur["weather_code"], cur["is_day"])
        daily = f["daily"]
        hi, lo = round(daily["temperature_2m_max"][0]), round(daily["temperature_2m_min"][0])
        x, y = r.left() + 16, r.top() + 14
        p.setPen(self.fg)
        p.setFont(font(15, QFont.DemiBold))
        elide(p, d["name"] + "  ➤" if not self.s["city"] else d["name"],
              QRectF(x, y, (r.width() - 32) if size == "small" else r.width() / 2, 20))
        p.setFont(font(44 if size == "small" else 46, QFont.Light))
        p.drawText(QRectF(x - 2, y + 18, 150, 56), Qt.AlignLeft | Qt.AlignVCenter, f"{round(cur['temperature_2m'])}°")
        if size == "small":
            p.setFont(emoji_font(22))
            p.drawText(QRectF(x, y + 82, 30, 30), Qt.AlignLeft | Qt.AlignVCenter, emo)
            p.setPen(self.fg)
            p.setFont(font(13, QFont.DemiBold))
            elide(p, label, QRectF(x, y + 112, r.width() - 32, 18))
            p.setPen(self.fg2)
            p.drawText(QRectF(x, y + 130, r.width() - 32, 18), Qt.AlignLeft, f"H:{hi}°  L:{lo}°")
            return
        # right side of the header
        rx = r.right() - 16
        p.setFont(emoji_font(22))
        p.drawText(QRectF(rx - 60, y, 60, 28), Qt.AlignRight | Qt.AlignVCenter, emo)
        p.setPen(self.fg)
        p.setFont(font(13, QFont.DemiBold))
        p.drawText(QRectF(rx - 200, y + 32, 200, 18), Qt.AlignRight, label)
        p.setPen(self.fg2)
        p.drawText(QRectF(rx - 200, y + 50, 200, 18), Qt.AlignRight, f"H:{hi}°  L:{lo}°")
        # hourly
        hourly = f["hourly"]
        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
        try:
            start = hourly["time"].index(now)
        except ValueError:
            start = 0
        n = 6
        cw = (r.width() - 24) / n
        top = r.top() + 92
        for i in range(n):
            j = start + i
            if j >= len(hourly["time"]):
                break
            cx = r.left() + 12 + cw * i
            hour = "Now" if i == 0 else hourly["time"][j][11:16]
            p.setPen(self.fg2)
            p.setFont(font(11, QFont.DemiBold))
            p.drawText(QRectF(cx, top, cw, 16), Qt.AlignCenter, hour)
            p.setFont(emoji_font(18))
            p.drawText(QRectF(cx, top + 16, cw, 26), Qt.AlignCenter,
                       services.wmo(hourly["weather_code"][j], hourly["is_day"][j])[1])
            p.setPen(self.fg)
            p.setFont(font(13, QFont.DemiBold))
            p.drawText(QRectF(cx, top + 42, cw, 18), Qt.AlignCenter, f"{round(hourly['temperature_2m'][j])}°")
        if size != "large":
            return
        # daily
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawLine(QPointF(r.left() + 16, r.top() + 166), QPointF(r.right() - 16, r.top() + 166))
        days = min(6, len(daily["time"]))
        lo_all = min(daily["temperature_2m_min"][:days])
        hi_all = max(daily["temperature_2m_max"][:days])
        span = max(1.0, hi_all - lo_all)
        rh = (r.bottom() - 12 - (r.top() + 174)) / days
        for i in range(days):
            ry = r.top() + 174 + i * rh
            dd = datetime.date.fromisoformat(daily["time"][i])
            name = "Today" if i == 0 else cap(EN.toString(QDate(dd.year, dd.month, dd.day), "ddd").rstrip("."))
            p.setPen(self.fg)
            p.setFont(font(13, QFont.DemiBold))
            p.drawText(QRectF(r.left() + 16, ry, 60, rh), Qt.AlignLeft | Qt.AlignVCenter, name)
            p.setFont(emoji_font(17))
            p.drawText(QRectF(r.left() + 70, ry, 34, rh), Qt.AlignCenter,
                       services.wmo(daily["weather_code"][i], True)[1])
            mn, mx = daily["temperature_2m_min"][i], daily["temperature_2m_max"][i]
            p.setPen(self.fg2)
            p.setFont(font(13, QFont.DemiBold))
            p.drawText(QRectF(r.left() + 108, ry, 40, rh), Qt.AlignRight | Qt.AlignVCenter, f"{round(mn)}°")
            p.setPen(self.fg)
            p.drawText(QRectF(r.right() - 56, ry, 40, rh), Qt.AlignRight | Qt.AlignVCenter, f"{round(mx)}°")
            bx0, bx1 = r.left() + 158, r.right() - 66
            by = ry + rh / 2 - 2.5
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 50))
            p.drawRoundedRect(QRectF(bx0, by, bx1 - bx0, 5), 2.5, 2.5)
            a = bx0 + (mn - lo_all) / span * (bx1 - bx0)
            b = bx0 + (mx - lo_all) / span * (bx1 - bx0)
            g = QLinearGradient(bx0, 0, bx1, 0)
            g.setColorAt(0, QColor(100, 210, 255))
            g.setColorAt(0.5, QColor(255, 214, 10))
            g.setColorAt(1, QColor(255, 120, 40))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(a, by, max(5, b - a), 5), 2.5, 2.5)


# --------------------------------------------------------------------------- #
#  Now playing
# --------------------------------------------------------------------------- #
def accent_from(img: QImage) -> QColor:
    small = img.scaled(16, 16, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    best, score = QColor(90, 90, 100), -1
    for y in range(16):
        for x in range(16):
            c = small.pixelColor(x, y)
            sc = c.hsvSaturationF() ** 2 * c.valueF() + 0.05 * c.valueF()
            if sc > score:
                best, score = c, sc
    return best


def draw_icon(p, name, c: QPointF, s, color):
    p.setPen(Qt.NoPen)
    p.setBrush(color)

    def tri(x, y, w, h, left=False):
        path = QPainterPath()
        if left:
            path.moveTo(x + w, y - h / 2)
            path.lineTo(x, y)
            path.lineTo(x + w, y + h / 2)
        else:
            path.moveTo(x, y - h / 2)
            path.lineTo(x + w, y)
            path.lineTo(x, y + h / 2)
        path.closeSubpath()
        p.drawPath(path)

    cx, cy = c.x(), c.y()
    if name == "pause":
        p.drawRoundedRect(QRectF(cx - s * 0.4, cy - s / 2, s * 0.3, s), 2, 2)
        p.drawRoundedRect(QRectF(cx + s * 0.1, cy - s / 2, s * 0.3, s), 2, 2)
    elif name == "play":
        tri(cx - s * 0.38, cy, s * 0.9, s)
    elif name == "next":
        tri(cx - s * 0.7, cy, s * 0.7, s * 0.85)
        tri(cx - s * 0.05, cy, s * 0.7, s * 0.85)
    elif name == "prev":
        tri(cx + s * 0.0, cy, s * 0.7, s * 0.85, left=True)
        tri(cx - s * 0.65, cy, s * 0.7, s * 0.85, left=True)


class Music(Kind):
    id = "music"
    title = "Music"
    desc = "What's playing right now (Spotify, YouTube, NotchIsland…), with the controls."
    icon = "🎵"
    sizes = ("small", "medium")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.svc = services.get("media")
        self.svc.updated.connect(self._on_media)
        self.art = None
        self.accent = None
        self._thumb = None
        self._on_media()

    def _on_media(self):
        t = self.svc.thumb
        if t is not self._thumb:
            self._thumb = t
            img = QImage.fromData(t) if t else QImage()
            if img.isNull():
                self.art, self.accent = None, None
            else:
                side = min(img.width(), img.height())
                self.art = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
                self.accent = accent_from(self.art)
        self.update()

    @property
    def fg(self):
        return WHITE if self.accent is not None else core.theme.fg

    @property
    def fg2(self):
        return QColor(255, 255, 255, 170) if self.accent is not None else core.theme.fg2

    def background(self, card, size):
        if self.accent is None:
            return None
        a = QColor(self.accent)
        top = QColor.fromHsvF(max(0.0, a.hsvHueF()), min(1.0, a.hsvSaturationF() * 0.8), 0.42)
        bottom = QColor.fromHsvF(max(0.0, a.hsvHueF()), min(1.0, a.hsvSaturationF() * 0.9), 0.2)
        g = QLinearGradient(card.topLeft(), card.bottomRight())
        g.setColorAt(0, top)
        g.setColorAt(1, bottom)
        return g

    def draw_art(self, p, rect, radius):
        p.save()
        p.setClipPath(rounded_path(rect, radius), Qt.IntersectClip)
        if self.art is not None:
            p.drawImage(rect, self.art)
        else:
            g = QLinearGradient(rect.topLeft(), rect.bottomRight())
            g.setColorAt(0, QColor(252, 60, 90))
            g.setColorAt(1, QColor(250, 110, 60))
            p.fillRect(rect, g)
            p.setPen(WHITE)
            p.setFont(font(rect.height() * 0.45))
            p.drawText(rect, Qt.AlignCenter, "♪")
        p.restore()

    def button(self, p, name, icon, c, s, hit_r):
        self.hits[name] = QRectF(c.x() - hit_r, c.y() - hit_r, 2 * hit_r, 2 * hit_r)
        if self.hot == name:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 40))
            p.drawEllipse(c, hit_r, hit_r)
        draw_icon(p, icon, c, s, self.fg)

    def on_hit(self, name):
        self.svc.command(name)

    def paint(self, p, r, size):
        self.hits = {}
        i = self.svc.info
        has = i.get("has_media")
        playing = i.get("playing")
        if size == "small":
            self.draw_art(p, QRectF(r.left() + 16, r.top() + 16, 64, 64), 12)
            if has:
                self.button(p, "toggle", "pause" if playing else "play", QPointF(r.right() - 34, r.top() + 34), 16, 20)
            p.setPen(self.fg2)
            p.setFont(font(11, QFont.DemiBold))
            p.drawText(QRectF(r.left() + 16, r.top() + 90, r.width() - 32, 16), Qt.AlignLeft,
                       (i.get("app") or "").upper() if has else "")
            p.setPen(self.fg)
            p.setFont(font(14, QFont.DemiBold))
            elide(p, i.get("title") if has else "Not playing", QRectF(r.left() + 16, r.top() + 106, r.width() - 32, 20))
            p.setPen(self.fg2)
            p.setFont(font(13))
            elide(p, i.get("artist", "") if has else "", QRectF(r.left() + 16, r.top() + 126, r.width() - 32, 18))
            return
        art = QRectF(r.left() + 16, r.top() + 16, r.height() - 32, r.height() - 32)
        self.draw_art(p, art, 14)
        x = art.right() + 16
        w = r.right() - 16 - x
        p.setPen(self.fg2)
        p.setFont(font(11, QFont.DemiBold))
        p.drawText(QRectF(x, r.top() + 18, w, 16), Qt.AlignLeft, (i.get("app") or "").upper() if has else "MUSIC")
        p.setPen(self.fg)
        p.setFont(font(16, QFont.DemiBold))
        elide(p, i.get("title") if has else "Not playing", QRectF(x, r.top() + 36, w, 22))
        p.setPen(self.fg2)
        p.setFont(font(13))
        elide(p, i.get("artist", "") if has else "Play some music in any app", QRectF(x, r.top() + 58, w, 18))
        if not has:
            return
        dur = i.get("duration", 0)
        if dur > 0:
            pos = self.svc.position()
            by = r.top() + 92
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 50) if self.accent is not None else self.fg3)
            p.drawRoundedRect(QRectF(x, by, w, 4), 2, 2)
            p.setBrush(self.fg)
            p.drawRoundedRect(QRectF(x, by, max(4, w * pos / dur), 4), 2, 2)
            p.setPen(self.fg2)
            p.setFont(font(10, QFont.DemiBold))
            p.drawText(QRectF(x, by + 6, 60, 14), Qt.AlignLeft, f"{int(pos) // 60}:{int(pos) % 60:02d}")
            p.drawText(QRectF(x + w - 60, by + 6, 60, 14), Qt.AlignRight,
                       f"-{int(dur - pos) // 60}:{int(dur - pos) % 60:02d}")
        cy = r.bottom() - 30
        cx = x + w / 2
        self.button(p, "prev", "prev", QPointF(cx - 52, cy), 14, 18)
        self.button(p, "toggle", "pause" if playing else "play", QPointF(cx, cy), 20, 22)
        self.button(p, "next", "next", QPointF(cx + 52, cy), 14, 18)


# --------------------------------------------------------------------------- #
#  System
# --------------------------------------------------------------------------- #
def fmt_rate(b):
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if b < 1000:
            return f"{b:.0f} {unit}" if unit == "B/s" else f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB/s"


def ring(p, c, R, frac, color, width, track):
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(track, width, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(c, R, R)
    if frac > 0.003:
        p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R), 90 * 16, int(-360 * 16 * min(1.0, frac)))


class System(Kind):
    id = "system"
    title = "System"
    desc = "Live CPU, memory, disk and network usage."
    icon = "📊"
    sizes = ("small", "medium")
    interval = 2000

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.svc = services.get("system")

    def items(self):
        v = self.svc.values
        out = [("CPU", v["cpu"], GREEN, f"{v['cpu'] * 100:.0f}%", f"{self.svc.ps.cpu_count()} threads"),
               ("RAM", v["ram"], BLUE, f"{v['ram'] * 100:.0f}%", f"{v['ram_used']:.1f} / {v['ram_total']:.0f} GB"),
               ("C:", v["disk"], ORANGE, f"{v['disk'] * 100:.0f}%", f"{v['disk_free']:.0f} GB free")]
        if v["battery"] is not None:
            b, plugged = v["battery"]
            out.append(("BAT", b, GREEN if b > 0.2 else RED, f"{b * 100:.0f}%", "Plugged in" if plugged else "On battery"))
        return out

    def paint(self, p, r, size):
        v = self.svc.values
        items = self.items()
        track = self.fg3
        if size == "small":
            cells = [QRectF(r.left() + 12 + (k % 2) * 73, r.top() + 12 + (k // 2) * 73, 73, 73) for k in range(4)]
            for k, cell in enumerate(cells):
                c = cell.center()
                if k < len(items):
                    name, frac, col, val, _ = items[k]
                    ring(p, c, 27, frac, col, 6, track)
                    p.setPen(self.fg)
                    p.setFont(font(13, QFont.Bold))
                    p.drawText(QRectF(c.x() - 26, c.y() - 12, 52, 16), Qt.AlignCenter, val)
                    p.setPen(self.fg2)
                    p.setFont(font(9, QFont.Bold))
                    p.drawText(QRectF(c.x() - 26, c.y() + 3, 52, 12), Qt.AlignCenter, name)
                else:
                    p.setPen(self.fg)
                    p.setFont(font(11, QFont.DemiBold))
                    p.drawText(QRectF(cell.left(), c.y() - 18, cell.width(), 16), Qt.AlignCenter,
                               "↓ " + fmt_rate(v["down"]))
                    p.setPen(self.fg2)
                    p.drawText(QRectF(cell.left(), c.y() + 2, cell.width(), 16), Qt.AlignCenter,
                               "↑ " + fmt_rate(v["up"]))
            return
        n = 4
        cw = (r.width() - 24) / n
        for k in range(n):
            cx = r.left() + 12 + cw * k + cw / 2
            c = QPointF(cx, r.top() + 62)
            if k < len(items):
                name, frac, col, val, sub = items[k]
                ring(p, c, 34, frac, col, 7, track)
                p.setPen(self.fg)
                p.setFont(font(15, QFont.Bold))
                p.drawText(QRectF(cx - 34, c.y() - 11, 68, 22), Qt.AlignCenter, val)
                p.setFont(font(13, QFont.DemiBold))
                p.drawText(QRectF(cx - cw / 2, r.top() + 110, cw, 18), Qt.AlignCenter,
                           {"CPU": "Processor", "RAM": "Memory", "C:": "Disk C:", "BAT": "Battery"}[name])
                p.setPen(self.fg2)
                p.setFont(font(11))
                elide(p, sub, QRectF(cx - cw / 2 + 2, r.top() + 128, cw - 4, 16), Qt.AlignCenter)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(self.fg3)
                p.drawEllipse(c, 37, 37)
                p.setPen(self.fg)
                p.setFont(font(11, QFont.DemiBold))
                p.drawText(QRectF(cx - 36, c.y() - 16, 72, 16), Qt.AlignCenter, "↓ " + fmt_rate(v["down"]))
                p.setPen(self.fg2)
                p.drawText(QRectF(cx - 36, c.y() + 1, 72, 16), Qt.AlignCenter, "↑ " + fmt_rate(v["up"]))
                p.setPen(self.fg)
                p.setFont(font(13, QFont.DemiBold))
                p.drawText(QRectF(cx - cw / 2, r.top() + 110, cw, 18), Qt.AlignCenter, "Network")


# --------------------------------------------------------------------------- #
#  Notes
# --------------------------------------------------------------------------- #
class Notes(Kind):
    id = "notes"
    title = "Notes"
    desc = "A sticky note you edit right on the desktop: click to write."
    icon = "📝"
    defaults = {"text": "My note\nClick here to write.", "color": "yellow"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.editor = None

    def settings_fields(self):
        return [("color", "Color", "choice", [("yellow", "Yellow"), ("glass", "Glass"), ("pink", "Pink"),
                                                ("green", "Green"), ("blue", "Blue")])]

    COLORS = {"yellow": (QColor(255, 231, 128), QColor(254, 214, 90)),
              "pink": (QColor(255, 190, 206), QColor(252, 160, 186)),
              "green": (QColor(190, 240, 170), QColor(160, 226, 140)),
              "blue": (QColor(180, 216, 255), QColor(146, 196, 252))}

    @property
    def colored(self):
        return self.s["color"] in self.COLORS

    @property
    def fg(self):
        return QColor(40, 34, 20) if self.colored else core.theme.fg

    @property
    def fg2(self):
        return QColor(40, 34, 20, 160) if self.colored else core.theme.fg2

    def background(self, card, size):
        if not self.colored:
            return None
        a, b = self.COLORS[self.s["color"]]
        g = QLinearGradient(card.topLeft(), card.bottomLeft())
        g.setColorAt(0, a)
        g.setColorAt(1, b)
        return g

    def paint(self, p, r, size):
        if self.editor is not None and self.editor.isVisible():
            return
        lines = (self.s["text"] or "").split("\n")
        title, body = lines[0], "\n".join(lines[1:]).strip()
        p.setPen(self.fg)
        p.setFont(font(16, QFont.Bold))
        elide(p, title or "New note", QRectF(r.left() + 16, r.top() + 14, r.width() - 32, 22))
        p.setPen(self.fg2 if not body else self.fg)
        p.setFont(font(13))
        p.drawText(QRectF(r.left() + 16, r.top() + 42, r.width() - 32, r.height() - 56),
                   Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, body)

    def click(self, pos, card, size):
        if self.preview:
            return False
        if self.editor is None:
            self.editor = NoteEditor(self)
        self.layout_children(card, size)
        self.editor.setPlainText(self.s["text"])
        self.editor.show()
        self.host.activateWindow()
        self.editor.setFocus()
        self.editor.moveCursor(self.editor.textCursor().MoveOperation.End)
        return True

    def layout_children(self, card, size):
        if self.editor is not None:
            self.editor.setGeometry(card.adjusted(10, 8, -10, -10).toRect())
            c = self.fg
            self.editor.setStyleSheet(
                f"QPlainTextEdit{{background:transparent;border:none;color:rgba({c.red()},{c.green()},{c.blue()},255);"
                f"font-size:14px;selection-background-color:rgba(10,100,214,120);}}")

    def finish(self):
        self.s["text"] = self.editor.toPlainText()
        self.editor.hide()
        self.host.manager.config.save()
        self.update()


class NoteEditor(QPlainTextEdit):
    def __init__(self, kind):
        super().__init__(kind.host)
        self.kind = kind
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        f = font(14)
        self.setFont(f)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.kind.finish()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clearFocus()
            return
        super().keyPressEvent(e)


# --------------------------------------------------------------------------- #
#  Photos
# --------------------------------------------------------------------------- #
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
_scan_cache = {}


def default_pictures():
    return os.path.join(os.path.expanduser("~"), "Pictures")


class Photos(Kind):
    id = "photos"
    title = "Photos"
    desc = "A slideshow of your photos. Double-click to open the photo shown."
    icon = "🖼️"
    interval = 30_000
    defaults = {"folder": default_pictures, "minutes": 10}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.img = None
        self.path = None
        self.shown_at = 0
        self.loading = False
        self.next_photo()

    def settings_fields(self):
        return [("folder", "Folder", "folder", None), ("minutes", "Change every (min)", "int", (1, 1440))]

    def settings_changed(self):
        self.next_photo()

    def tick(self):
        if time.time() - self.shown_at > self.s["minutes"] * 60:
            self.next_photo()

    def next_photo(self):
        if self.loading:
            return
        self.loading = True
        folder = self.s["folder"]
        w, h = core.SIZES["large"]

        def work():
            files, t = _scan_cache.get(folder, (None, 0))
            if files is None or time.time() - t > 600:
                files = []
                for root, _, names in os.walk(folder):
                    files += [os.path.join(root, n) for n in names if n.lower().endswith(IMG_EXT)]
                    if len(files) > 5000:
                        break
                _scan_cache[folder] = (files, time.time())
            if not files:
                return None, None
            for _ in range(5):
                path = random.choice(files)
                img = QImage(path)
                if not img.isNull():
                    return path, img.scaled(w * 2, h * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            return None, None

        def done(r, err):
            self.loading = False
            self.shown_at = time.time()
            if err is None and r and r[1] is not None:
                self.path, self.img = r
            self.update()

        services.bg(work, done)

    def paint(self, p, r, size):
        if self.img is None:
            p.setPen(self.fg2)
            p.setFont(font(13))
            p.drawText(r.adjusted(14, 0, -14, 0), Qt.AlignCenter | Qt.TextWordWrap,
                       "Loading…" if self.loading else "No photos.\nRight-click → Edit \"Photos\"")
            return
        iw, ih = self.img.width(), self.img.height()
        scale = max(r.width() / iw, r.height() / ih)
        sw, sh = r.width() / scale, r.height() / scale
        p.drawImage(r, self.img, QRectF((iw - sw) / 2, (ih - sh) / 2, sw, sh))

    def double_click(self, pos, card, size):
        if self.path:
            os.startfile(self.path)

    def click(self, pos, card, size):
        return False


# --------------------------------------------------------------------------- #
#  Reminders
# --------------------------------------------------------------------------- #
class Reminders(Kind):
    id = "reminders"
    title = "Reminders"
    desc = "A to-do list: tick to complete, \"+\" to add."
    icon = "✅"
    defaults = {"items": lambda: [{"text": "Buy groceries", "done": False},
                                  {"text": "Call the garage", "done": False}]}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.input = None

    @property
    def items(self):
        return self.s["items"]

    def paint(self, p, r, size):
        self.hits = {}
        todo = [it for it in self.items if not it.get("gone")]
        count = sum(1 for it in todo if not it["done"])
        x = r.left() + 16
        # header
        p.setPen(Qt.NoPen)
        p.setBrush(ORANGE)
        p.drawEllipse(QPointF(x + 13, r.top() + 29), 13, 13)
        p.setPen(WHITE)
        p.setFont(font(15, QFont.Bold))
        p.drawText(QRectF(x, r.top() + 16, 26, 26), Qt.AlignCenter, "≡")
        p.setPen(self.fg)
        p.setFont(font(26, QFont.DemiBold))
        p.drawText(QRectF(r.right() - 16 - 60, r.top() + 12, 60, 34), Qt.AlignRight | Qt.AlignVCenter, str(count))
        if size != "small":
            plus = QRectF(r.right() - 16 - 60 - 36, r.top() + 16, 26, 26)
            self.hits["add"] = plus
            if self.hot == "add":
                p.setPen(Qt.NoPen)
                p.setBrush(self.fg3)
                p.drawEllipse(plus.center(), 13, 13)
            p.setPen(ORANGE)
            p.setFont(font(22, QFont.Normal))
            p.drawText(plus.adjusted(0, -2, 0, -2), Qt.AlignCenter, "+")
        p.setPen(ORANGE)
        p.setFont(font(15, QFont.Bold))
        p.drawText(QRectF(x, r.top() + 48, r.width() - 32, 20), Qt.AlignLeft, "Reminders")
        # rows
        top = r.top() + 76
        rh = 26
        max_rows = int((r.bottom() - 12 - top) // rh)
        if self.input is not None and self.input.isVisible():
            max_rows -= 1
        for i, it in enumerate(todo[:max_rows]):
            y = top + i * rh
            c = QPointF(x + 9, y + rh / 2)
            circle = QRectF(c.x() - 11, c.y() - 11, 22, 22)
            self.hits[f"item{self.items.index(it)}"] = QRectF(x - 4, y, r.width() - 24, rh) \
                if size == "small" else circle
            if it["done"]:
                p.setPen(Qt.NoPen)
                p.setBrush(ORANGE)
                p.drawEllipse(c, 8.5, 8.5)
                p.setPen(QPen(WHITE, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPolyline([QPointF(c.x() - 4, c.y()), QPointF(c.x() - 1, c.y() + 3), QPointF(c.x() + 4, c.y() - 3)])
            else:
                p.setPen(QPen(self.fg2, 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(c, 8, 8)
            p.setPen(self.fg2 if it["done"] else self.fg)
            f = font(13)
            f.setStrikeOut(it["done"])
            p.setFont(f)
            elide(p, it["text"], QRectF(x + 26, y, r.width() - 32 - 26, rh))
        if not todo:
            p.setPen(self.fg2)
            p.setFont(font(13))
            p.drawText(QRectF(x, top, r.width() - 32, rh), Qt.AlignLeft | Qt.AlignVCenter,
                       "All done 🎉" if size == "small" else "All done 🎉  \"+\" to add one")
        elif len(todo) > max_rows:
            p.setPen(self.fg2)
            p.setFont(font(11, QFont.DemiBold))
            p.drawText(QRectF(x, r.bottom() - 22, r.width() - 32, 14), Qt.AlignRight, f"+ {len(todo) - max_rows} more")

    def on_hit(self, name):
        if self.preview:
            return
        if name == "add":
            self.open_input()
        elif name.startswith("item"):
            it = self.items[int(name[4:])]
            it["done"] = not it["done"]
            if it["done"]:
                # like on macOS: a checked reminder disappears after a moment
                QTimer.singleShot(2500, lambda it=it: self._clear(it))
            self.host.manager.config.save()

    def _clear(self, it):
        if it.get("done") and it in self.items:
            self.items.remove(it)
            self.host.manager.config.save()
            self.update()

    def open_input(self):
        if self.input is None:
            self.input = QLineEdit(self.host)
            self.input.setPlaceholderText("New reminder")
            self.input.returnPressed.connect(self._add)
            self.input.editingFinished.connect(lambda: QTimer.singleShot(0, self._close_input))
        self.layout_children(self.host.card_rect(), self.host.size_name)
        self.input.clear()
        self.input.show()
        self.host.activateWindow()
        self.input.setFocus()
        self.update()

    def _add(self):
        text = self.input.text().strip()
        if text:
            self.items.append({"text": text, "done": False})
            self.host.manager.config.save()
        self.input.clear()
        self.update()

    def _close_input(self):
        if self.input is not None and not self.input.hasFocus():
            self.input.hide()
            self.update()

    def layout_children(self, card, size):
        if self.input is not None:
            self.input.setGeometry(int(card.left() + 14), int(card.bottom() - 42), int(card.width() - 28), 30)
            c = self.fg
            self.input.setStyleSheet(
                f"QLineEdit{{background:rgba(127,127,127,40);border:none;border-radius:8px;padding:4px 10px;"
                f"color:rgb({c.red()},{c.green()},{c.blue()});font-size:13px;}}")


KINDS = [Clock, Calendar, Weather, Music, System, Notes, Photos, Reminders]
BY_ID = {k.id: k for k in KINDS}
