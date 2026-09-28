"""
Shared data sources for the widgets: weather, now playing, system usage.
Each one is created on first use and refreshes in the background.
"""

import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal, QTimer

_pool = ThreadPoolExecutor(4, thread_name_prefix="svc")


class _Bg(QObject):
    """Run a function on a worker thread and get the result back on the GUI thread."""
    call = Signal(object)

    def __init__(self):
        super().__init__()
        self.call.connect(lambda f: f())

    def run(self, fn, done, pool=None):
        def work():
            try:
                r, err = fn(), None
            except Exception as e:
                r, err = None, e
            self.call.emit(lambda: done(r, err))
        (pool or _pool).submit(work)


_bg = None
_http = None


def bg(fn, done, pool=None):
    global _bg
    if _bg is None:
        _bg = _Bg()
    _bg.run(fn, done, pool)


def http():
    global _http
    if _http is None:
        import requests
        _http = requests.Session()
        _http.headers["User-Agent"] = "DeskWidgets/1.0"
    return _http


# --------------------------------------------------------------------------- #
#  Weather (Open-Meteo: free, no API key)
# --------------------------------------------------------------------------- #
WMO = {
    0: ("Clear", "☀️", "🌙"), 1: ("Mostly clear", "🌤️", "🌙"), 2: ("Partly cloudy", "⛅", "☁️"),
    3: ("Cloudy", "☁️", "☁️"), 45: ("Fog", "🌫️", "🌫️"), 48: ("Freezing fog", "🌫️", "🌫️"),
    51: ("Light drizzle", "🌦️", "🌧️"), 53: ("Drizzle", "🌦️", "🌧️"), 55: ("Heavy drizzle", "🌧️", "🌧️"),
    56: ("Freezing drizzle", "🌧️", "🌧️"), 57: ("Freezing drizzle", "🌧️", "🌧️"),
    61: ("Light rain", "🌦️", "🌧️"), 63: ("Rain", "🌧️", "🌧️"), 65: ("Heavy rain", "🌧️", "🌧️"),
    66: ("Freezing rain", "🌧️", "🌧️"), 67: ("Freezing rain", "🌧️", "🌧️"),
    71: ("Light snow", "🌨️", "🌨️"), 73: ("Snow", "🌨️", "🌨️"), 75: ("Heavy snow", "❄️", "❄️"),
    77: ("Snow grains", "🌨️", "🌨️"), 80: ("Showers", "🌦️", "🌧️"), 81: ("Showers", "🌧️", "🌧️"),
    82: ("Heavy showers", "🌧️", "🌧️"), 85: ("Snow showers", "🌨️", "🌨️"),
    86: ("Snow showers", "🌨️", "🌨️"), 95: ("Thunderstorm", "⛈️", "⛈️"), 96: ("Thunderstorm, hail", "⛈️", "⛈️"),
    99: ("Thunderstorm, hail", "⛈️", "⛈️"),
}


def wmo(code, day=True):
    label, d, n = WMO.get(int(code or 0), ("—", "🌡️", "🌡️"))
    return label, (d if day else n)


class Weather(QObject):
    updated = Signal()
    REFRESH = 15 * 60

    def __init__(self):
        super().__init__()
        self.data = {}        # city ("" = automatic) -> dict
        self.busy = set()
        self.errors = {}
        t = QTimer(self)
        t.timeout.connect(self._refresh_all)
        t.start(60_000)

    def get(self, city):
        city = (city or "").strip()
        d = self.data.get(city)
        if (d is None or time.time() - d["fetched"] > self.REFRESH) and city not in self.busy:
            self._fetch(city)
        return d

    def error(self, city):
        return self.errors.get((city or "").strip())

    def _refresh_all(self):
        for c in list(self.data):
            self.get(c)

    def _fetch(self, city):
        self.busy.add(city)

        def work():
            if city:
                r = http().get("https://geocoding-api.open-meteo.com/v1/search",
                               params={"name": city, "count": 1, "language": "en"}, timeout=10).json()
                if not r.get("results"):
                    raise RuntimeError("City not found")
                g = r["results"][0]
                name, lat, lon = g["name"], g["latitude"], g["longitude"]
            else:
                g = http().get("https://ipwho.is/", timeout=10).json()
                if not g.get("success", True):
                    raise RuntimeError("Unknown location")
                name, lat, lon = g["city"], g["latitude"], g["longitude"]
            f = http().get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
                "current": "temperature_2m,apparent_temperature,weather_code,is_day",
                "hourly": "temperature_2m,weather_code,is_day",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            }, timeout=10).json()
            return {"name": name, "f": f, "fetched": time.time()}

        def done(r, err):
            self.busy.discard(city)
            if err is not None:
                self.errors[city] = str(err) if isinstance(err, RuntimeError) else "Offline"
            else:
                self.errors.pop(city, None)
                self.data[city] = r
            self.updated.emit()

        bg(work, done)


# --------------------------------------------------------------------------- #
#  Now playing (Windows media controls, like NotchIsland)
# --------------------------------------------------------------------------- #
PLAYING = 4


def pretty_app_name(aumid):
    name = (aumid or "").split("!")[-1].rsplit("\\", 1)[-1]
    if name.lower().endswith(".exe"):
        name = name[:-4]
    known = {"chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "spotify": "Spotify",
             "opera": "Opera", "brave": "Brave", "vlc": "VLC", "deezer": "Deezer", "notchisland": "NotchIsland",
             "zunemusic": "Media Player", "applemusic": "Apple Music", "discord": "Discord"}
    for k, v in known.items():
        if k in name.lower():
            return v
    return name[:1].upper() + name[1:]


class Media(QObject):
    updated = Signal()
    _data = Signal(object)

    def __init__(self):
        super().__init__()
        self.info = {"has_media": False}
        self.thumb = None
        self.loop = None
        self.session = None
        self._key = None
        self._thumb_tries = 0
        self._data.connect(self._on_data)
        threading.Thread(target=self._run, daemon=True).start()

    def _on_data(self, d):
        if "thumb" in d:
            self.thumb = d.pop("thumb")
        self.info = d
        self.updated.emit()

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    async def _main(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
        mgr = None
        while True:
            try:
                if mgr is None:
                    mgr = await Manager.request_async()
                await self._poll(mgr)
            except Exception as e:
                print("media error:", e)
                self.session = None
            await asyncio.sleep(0.5)

    async def _poll(self, mgr):
        cur = mgr.get_current_session()
        s = cur
        try:
            if not (cur and cur.get_playback_info().playback_status == PLAYING):
                s = next((x for x in mgr.get_sessions() if x.get_playback_info().playback_status == PLAYING), cur)
        except Exception:
            pass
        self.session = s
        if s is None:
            self._key = None
            self._data.emit({"has_media": False})
            return
        props = await s.try_get_media_properties_async()
        title = props.title or ""
        if not title:
            self._key = None
            self._data.emit({"has_media": False})
            return
        artist = props.artist or props.album_artist or ""
        app = s.source_app_user_model_id or ""
        d = {}
        key = (app, title, artist)
        if key != self._key:
            self._key = key
            self._thumb_tries = 0
            d["thumb"] = None
        if self._thumb_tries < 10:
            data = None
            try:
                if props.thumbnail:
                    from winrt.windows.storage.streams import Buffer, InputStreamOptions
                    st = await props.thumbnail.open_read_async()
                    if st.size:
                        buf = Buffer(st.size)
                        await st.read_async(buf, st.size, InputStreamOptions.READ_AHEAD)
                        data = bytes(buf)
            except Exception:
                pass
            if data:
                d["thumb"] = data
                self._thumb_tries = 99
            else:
                self._thumb_tries += 1
        info = s.get_playback_info()
        tl = s.get_timeline_properties()
        pos = tl.position.total_seconds()
        dur = max(0.0, (tl.end_time - tl.start_time).total_seconds())
        try:
            upd = tl.last_updated_time.timestamp()
        except Exception:
            upd = time.time()
        if not (time.time() - 86400 < upd <= time.time() + 5):
            upd = time.time()
        d.update({"has_media": True, "title": title, "artist": artist, "app": pretty_app_name(app),
                  "playing": info.playback_status == PLAYING, "position": pos, "updated": upd,
                  "duration": dur})
        self._data.emit(d)

    def position(self):
        i = self.info
        pos = i.get("position", 0.0)
        if i.get("playing"):
            pos += time.time() - i.get("updated", time.time())
        dur = i.get("duration", 0.0)
        return max(0.0, min(pos, dur)) if dur > 0 else pos

    def command(self, name):
        if self.loop is None:
            return

        async def run():
            s = self.session
            if s is None:
                return
            try:
                if name == "toggle":
                    await s.try_toggle_play_pause_async()
                elif name == "next":
                    await s.try_skip_next_async()
                elif name == "prev":
                    await s.try_skip_previous_async()
            except Exception as e:
                print("media command error:", e)
        asyncio.run_coroutine_threadsafe(run(), self.loop)


# --------------------------------------------------------------------------- #
#  System usage
# --------------------------------------------------------------------------- #
class System(QObject):
    updated = Signal()

    def __init__(self):
        super().__init__()
        import psutil
        self.ps = psutil
        psutil.cpu_percent(None)
        self.net = psutil.net_io_counters()
        self.net_t = time.monotonic()
        self.values = {"cpu": 0.0, "ram": 0.0, "disk": 0.0, "down": 0.0, "up": 0.0, "battery": None,
                       "ram_used": 0.0, "ram_total": 0.0, "disk_free": 0.0}
        t = QTimer(self)
        t.timeout.connect(self.sample)
        t.start(2000)
        self.sample()

    def sample(self):
        ps = self.ps
        v = self.values
        v["cpu"] = ps.cpu_percent(None) / 100
        m = ps.virtual_memory()
        v["ram"], v["ram_used"], v["ram_total"] = m.percent / 100, m.used / 2**30, m.total / 2**30
        try:
            d = ps.disk_usage("C:\\")
            v["disk"], v["disk_free"] = d.percent / 100, d.free / 2**30
        except OSError:
            pass
        n, now = ps.net_io_counters(), time.monotonic()
        dt = max(0.1, now - self.net_t)
        v["down"] = (n.bytes_recv - self.net.bytes_recv) / dt
        v["up"] = (n.bytes_sent - self.net.bytes_sent) / dt
        self.net, self.net_t = n, now
        try:
            b = ps.sensors_battery()
            v["battery"] = None if b is None else (b.percent / 100, b.power_plugged)
        except Exception:
            v["battery"] = None
        self.updated.emit()


_instances = {}


def get(name):
    if name not in _instances:
        _instances[name] = {"weather": Weather, "media": Media, "system": System}[name]()
    return _instances[name]
