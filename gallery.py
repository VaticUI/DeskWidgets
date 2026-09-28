"""
Widget gallery, like "Edit Widgets" on macOS: pick a widget and a size, click to add it.
While it is open, the widgets on the desktop show a (−) to remove them.
"""

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton,
)

import core
from core import SIZES, SIZE_NAMES, MARGIN, font, paint_card
from kinds import KINDS

SCALE = 0.72


class PreviewCard(QWidget):
    def __init__(self, gallery, kind_cls, size):
        super().__init__()
        self.gallery = gallery
        self.kind_cls = kind_cls
        self.size_name = size
        self.kind = kind_cls(self, {}, preview=True)
        self.hover = False
        w, h = SIZES[size]
        self.setFixedSize(int((w + 2 * MARGIN) * SCALE), int((h + 2 * MARGIN) * SCALE) + 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Add \"{kind_cls.title}\" ({SIZE_NAMES[size].lower()})")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        p.save()
        p.scale(SCALE, SCALE)
        w, h = SIZES[self.size_name]
        card = QRectF(MARGIN, MARGIN, w, h)
        paint_card(p, card, self.kind, self.size_name, None)
        p.restore()
        # green (+) badge, like macOS
        c = QPointF(MARGIN * SCALE + 4, MARGIN * SCALE + 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(52, 199, 89) if self.hover else QColor(52, 199, 89, 210))
        p.drawEllipse(c, 11 if self.hover else 10, 11 if self.hover else 10)
        p.setBrush(QColor(255, 255, 255))
        p.drawRoundedRect(QRectF(c.x() - 5, c.y() - 1.2, 10, 2.4), 1.2, 1.2)
        p.drawRoundedRect(QRectF(c.x() - 1.2, c.y() - 5, 2.4, 10), 1.2, 1.2)
        p.setPen(core.theme.fg2)
        p.setFont(font(12, QFont.DemiBold))
        p.drawText(QRectF(0, self.height() - 22, self.width(), 18), Qt.AlignCenter, SIZE_NAMES[self.size_name])
        p.end()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.gallery.manager.add(self.kind_cls.id, self.size_name)


class Gallery(QWidget):
    W, H = 1000, 520

    def __init__(self, manager):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.manager = manager
        self.setFixedSize(self.W, self.H)

        self.frame = QFrame(self)
        self.frame.setObjectName("frame")
        self.frame.setGeometry(0, 0, self.W, self.H)
        root = QHBoxLayout(self.frame)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search widgets")
        self.search.textChanged.connect(self.fill_list)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedWidth(220)
        self.list.setIconSize(QSize(0, 0))
        self.list.currentRowChanged.connect(self.show_kind)
        left.addWidget(self.list, 1)
        root.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.desc = QLabel()
        self.desc.setObjectName("desc")
        self.desc.setWordWrap(True)
        right.addWidget(self.title)
        right.addWidget(self.desc)
        right.addSpacing(10)
        self.cards_row = QHBoxLayout()
        self.cards_row.setSpacing(18)
        self.cards_row.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        right.addLayout(self.cards_row)
        right.addStretch(1)
        bottom = QHBoxLayout()
        hint = QLabel("Click a preview to add it · drag widgets to move them · "
                      "right-click a widget for its size and settings")
        hint.setObjectName("desc")
        hint.setWordWrap(True)
        done = QPushButton("Done")
        done.setCursor(Qt.PointingHandCursor)
        done.clicked.connect(self.hide)
        bottom.addWidget(hint, 1)
        bottom.addWidget(done)
        right.addLayout(bottom)
        root.addLayout(right, 1)

        self.cards = []
        self.shown = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: [c.update() for c in self.cards])
        self.timer.start(1000)
        core.theme.changed.connect(self.restyle)
        self.restyle()
        self.fill_list()

    def restyle(self):
        d = core.theme.dark
        bg, fg, fg2, field, sel = (("rgba(32,32,36,245)", "#fff", "rgba(255,255,255,0.6)", "#3a3a3e", "#0a64d6")
                                   if d else
                                   ("rgba(246,246,248,248)", "#111", "rgba(0,0,0,0.55)", "#e2e2e6", "#0a64d6"))
        self.setStyleSheet(f"""
            #frame {{ background: {bg}; border-radius: 26px; border: 1px solid {'#3a3a3e' if d else '#d6d6da'}; }}
            QLineEdit {{ background: {field}; color: {fg}; border: none; border-radius: 8px; padding: 7px 10px;
                         font-size: 13px; }}
            QListWidget {{ background: transparent; border: none; outline: none; color: {fg}; font-size: 14px; }}
            QListWidget::item {{ padding: 7px 8px; border-radius: 8px; }}
            QListWidget::item:selected {{ background: {sel}; color: #fff; }}
            #title {{ color: {fg}; font-size: 22px; font-weight: 600; }}
            #desc {{ color: {fg2}; font-size: 13px; }}
            QPushButton {{ background: {sel}; color: #fff; border: none; border-radius: 8px; padding: 8px 22px;
                           font-size: 13px; font-weight: 600; }}
        """)
        for c in self.cards:
            c.update()

    def fill_list(self):
        q = self.search.text().strip().lower()
        self.shown = [k for k in KINDS if not q or q in k.title.lower() or q in k.desc.lower()]
        self.list.blockSignals(True)
        self.list.clear()
        for k in self.shown:
            QListWidgetItem(f"{k.icon}   {k.title}", self.list)
        self.list.blockSignals(False)
        if self.shown:
            self.list.setCurrentRow(0)
            self.show_kind(0)

    def show_kind(self, row):
        if not (0 <= row < len(self.shown)):
            return
        k = self.shown[row]
        self.title.setText(k.title)
        self.desc.setText(k.desc)
        for c in self.cards:
            self.cards_row.removeWidget(c)
            c.deleteLater()
        self.cards = [PreviewCard(self, k, s) for s in k.sizes]
        for c in self.cards:
            self.cards_row.addWidget(c, 0, Qt.AlignTop)

    def open(self):
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.move(g.x() + (g.width() - self.W) // 2, g.y() + g.height() - self.H - 40)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()
        self.manager.set_edit(True)

    def hideEvent(self, e):
        self.manager.set_edit(False)
        super().hideEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)
