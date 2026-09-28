"""
SSH widget helpers: profiles, reachability check, opening a session, profile editor.

A profile is {"name", "host", "port", "user", "key", "extra"}. Passwords are never stored:
ssh asks for them in the terminal (or uses your key / agent).
"""

import os
import re
import time
import shlex
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QListWidget, QFormLayout, QLineEdit, QSpinBox, QPushButton, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QWidget, QLabel,
)

import core

SSH_CONFIG = os.path.join(os.path.expanduser("~"), ".ssh", "config")


def new_profile(**kw):
    p = {"name": "", "host": "", "port": 22, "user": "", "key": "", "extra": ""}
    p.update(kw)
    return p


def target(p):
    return f"{p['user']}@{p['host']}" if p.get("user") else p["host"]


# --------------------------------------------------------------------------- #
#  ~/.ssh/config import
# --------------------------------------------------------------------------- #
def read_ssh_config(path=SSH_CONFIG):
    """Named hosts of an OpenSSH config file (wildcard patterns are skipped)."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return out
    cur = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"(\S+)\s*=?\s*(.*)", line)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip().strip('"')
        if key == "host":
            cur = None
            names = [n for n in val.split() if not any(c in n for c in "*?!")]
            if names:
                cur = new_profile(name=names[0], host=names[0])
                out.append(cur)
        elif key == "match":
            cur = None
        elif cur is not None:
            if key == "hostname":
                cur["host"] = val
            elif key == "user":
                cur["user"] = val
            elif key == "port" and val.isdigit():
                cur["port"] = int(val)
            elif key == "identityfile":
                cur["key"] = os.path.expanduser(val)
    return out


# --------------------------------------------------------------------------- #
#  Reachability (TCP connect to the SSH port), shared by all the SSH widgets
# --------------------------------------------------------------------------- #
CHECK_EVERY = 30
_pool = ThreadPoolExecutor(8, thread_name_prefix="ssh-ping")
_status = {}        # (host, port) -> latency ms | None (offline)
_checked = {}       # (host, port) -> time of the last check
_busy = set()


def status(host, port):
    """Latency in ms, None if offline, "?" if not known yet."""
    return _status.get((host, int(port or 22)), "?")


def refresh(profiles, on_done, force=False):
    import services
    now = time.time()
    for p in profiles:
        key = (p["host"], int(p.get("port") or 22))
        if key in _busy or (not force and now - _checked.get(key, 0) < CHECK_EVERY):
            continue
        _busy.add(key)
        _checked[key] = now

        def done(ms, err, key=key):
            _busy.discard(key)
            _status[key] = ms if err is None else None
            on_done()
        services.bg(lambda key=key: ping(*key), done, pool=_pool)


def ping(host, port, timeout=3.0):
    """Latency in ms, or None if the port does not answer."""
    t = time.perf_counter()
    try:
        with socket.create_connection((host, int(port or 22)), timeout=timeout):
            return (time.perf_counter() - t) * 1000
    except OSError:
        return None


# --------------------------------------------------------------------------- #
#  Opening a session
# --------------------------------------------------------------------------- #
def ssh_exe():
    system = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", "ssh.exe")
    return system if os.path.exists(system) else shutil.which("ssh")


def command(p):
    args = [ssh_exe() or "ssh"]
    if int(p.get("port") or 22) != 22:
        args += ["-p", str(int(p["port"]))]
    if p.get("key"):
        args += ["-i", p["key"]]
    if p.get("extra"):
        args += shlex.split(p["extra"], posix=False)
    return args + [target(p)]


def connect(p):
    """Open the session in Windows Terminal if available, otherwise in a console window."""
    if not ssh_exe():
        QMessageBox.warning(None, "SSH", "The OpenSSH client was not found.\n\n"
                            "Install it from Settings → System → Optional features → OpenSSH Client.")
        return
    args = command(p)
    wt = shutil.which("wt")
    title = p.get("name") or p["host"]
    if wt:
        # ';' separates commands for wt: escape it inside the ssh arguments
        subprocess.Popen([wt, "-w", "0", "new-tab", "--title", title] + [a.replace(";", r"\;") for a in args])
    else:
        subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)


# --------------------------------------------------------------------------- #
#  Profile editor
# --------------------------------------------------------------------------- #
class ProfilesDialog(QDialog):
    def __init__(self, profiles):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("SSH servers")
        self.setStyleSheet(core.dialog_qss() + " QListWidget{background:transparent;border:none;outline:none;}"
                           " QListWidget::item{padding:6px 8px;border-radius:6px;}"
                           " QListWidget::item:selected{background:#0a64d6;color:#fff;}")
        self.setMinimumSize(620, 360)
        self.profiles = [dict(p) for p in profiles]
        self._loading = False

        self.list = QListWidget()
        self.list.setFixedWidth(190)
        self.list.currentRowChanged.connect(self.show_profile)
        add = QPushButton("Add")
        add.clicked.connect(self.add)
        rem = QPushButton("Remove")
        rem.clicked.connect(self.remove)
        imp = QPushButton("Import ~/.ssh/config")
        imp.clicked.connect(self.import_config)
        imp.setEnabled(os.path.exists(SSH_CONFIG))
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(rem)
        left.addLayout(row)
        left.addWidget(imp)

        self.name = QLineEdit()
        self.name.setPlaceholderText("My server")
        self.host = QLineEdit()
        self.host.setPlaceholderText("example.com or 192.168.1.10")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.user = QLineEdit()
        self.user.setPlaceholderText("root")
        self.key = QLineEdit()
        self.key.setPlaceholderText("Optional: private key file")
        pick = QPushButton("…")
        pick.clicked.connect(self.pick_key)
        keyrow = QWidget()
        kh = QHBoxLayout(keyrow)
        kh.setContentsMargins(0, 0, 0, 0)
        kh.addWidget(self.key, 1)
        kh.addWidget(pick)
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("Optional: e.g. -L 8080:localhost:80")
        self.form = QWidget()
        form = QFormLayout(self.form)
        form.setSpacing(10)
        form.addRow("Name", self.name)
        form.addRow("Host", self.host)
        form.addRow("Port", self.port)
        form.addRow("User", self.user)
        form.addRow("Key", keyrow)
        form.addRow("Options", self.extra)
        note = QLabel("Passwords are never saved: ssh asks for them when you connect.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", note)
        for w in (self.name, self.host, self.user, self.key, self.extra):
            w.textChanged.connect(self.store)
        self.port.valueChanged.connect(self.store)

        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)

        body = QHBoxLayout()
        body.addLayout(left)
        body.addSpacing(10)
        body.addWidget(self.form, 1)
        v = QVBoxLayout(self)
        v.addLayout(body, 1)
        v.addLayout(buttons)
        self.refresh(0)

    def refresh(self, select):
        if not self.profiles:
            # always something to fill in: an empty list starts with a blank server
            self.profiles.append(new_profile())
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.profiles:
            self.list.addItem(p["name"] or p["host"] or "(new server)")
        self.list.blockSignals(False)
        self.list.setCurrentRow(max(0, min(select, len(self.profiles) - 1)))
        self.show_profile(self.list.currentRow())

    def showEvent(self, e):
        super().showEvent(e)
        self.activateWindow()
        (self.host if self.name.text() else self.name).setFocus()

    def show_profile(self, i):
        if not (0 <= i < len(self.profiles)):
            return
        p = self.profiles[i]
        self._loading = True
        self.name.setText(p["name"])
        self.host.setText(p["host"])
        self.port.setValue(int(p.get("port") or 22))
        self.user.setText(p.get("user", ""))
        self.key.setText(p.get("key", ""))
        self.extra.setText(p.get("extra", ""))
        self._loading = False

    def store(self, *_):
        i = self.list.currentRow()
        if self._loading or not (0 <= i < len(self.profiles)):
            return
        p = self.profiles[i]
        p.update(name=self.name.text().strip(), host=self.host.text().strip(), port=self.port.value(),
                 user=self.user.text().strip(), key=self.key.text().strip(), extra=self.extra.text().strip())
        self.list.item(i).setText(p["name"] or p["host"] or "(new server)")

    def add(self):
        self.profiles.append(new_profile())
        self.refresh(len(self.profiles) - 1)
        self.name.setFocus()

    def remove(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.profiles):
            del self.profiles[i]
            self.refresh(i)

    def import_config(self):
        known = {(p["host"], p.get("user"), int(p.get("port") or 22)) for p in self.profiles}
        added = [p for p in read_ssh_config() if (p["host"], p["user"], p["port"]) not in known]
        self.profiles += added
        self.refresh(len(self.profiles) - 1)
        QMessageBox.information(self, "SSH", f"{len(added)} server(s) imported.")

    def pick_key(self):
        start = os.path.dirname(self.key.text()) or os.path.join(os.path.expanduser("~"), ".ssh")
        f, _ = QFileDialog.getOpenFileName(self, "Private key", start)
        if f:
            self.key.setText(os.path.normpath(f))

    def result_profiles(self):
        return [p for p in self.profiles if p["host"]]
