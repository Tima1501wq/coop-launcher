from __future__ import annotations
import math, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import (
    Qt, QRectF, QUrl, QTimer, QVariantAnimation,
    pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QIcon,
)
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QScrollArea, QVBoxLayout, QWidget,
)

from games import Game, scan_all
from coop import (
    fetch_coop_info, load_cache, load_favorites,
    save_cache, save_favorites,
)


class AnimatedBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(24000)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_value)
        self._anim.start()

    def _on_value(self, v):
        self._t = v
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = max(self.width(), 1), max(self.height(), 1)
        p.fillRect(self.rect(), QColor("#0a1119"))
        t = self._t
        w2 = math.tau
        cx1 = w * (0.28 + 0.18 * math.sin(t * w2))
        cy1 = h * (0.35 + 0.18 * math.cos(t * w2))
        g1 = QRadialGradient(cx1, cy1, max(w, h) * 0.7)
        g1.setColorAt(0.0, QColor(50, 90, 220, 70))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g1)
        cx2 = w * (0.72 + 0.18 * math.cos(t * w2 + 1.2))
        cy2 = h * (0.62 + 0.18 * math.sin(t * w2 + 1.2))
        g2 = QRadialGradient(cx2, cy2, max(w, h) * 0.65)
        g2.setColorAt(0.0, QColor(140, 60, 200, 60))
        g2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g2)


class GameCard(QFrame):
    activated = pyqtSignal(object)
    context_requested = pyqtSignal(object, object)

    MARGIN = 12
    W, H = 240, 135
    RADIUS = 12

    def __init__(self, game: Game):
        super().__init__()
        self.game = game
        self._cover: QPixmap | None = None
        self._is_coop: bool | None = None
        self._is_fav = False
        self._hover = 0.0
        self._cover_progress = 0.0

        self.setFixedSize(self.W + self.MARGIN * 2, self.H + self.MARGIN * 2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._hover_anim = QPropertyAnimation(self, b"hover_progress", self)
        self._hover_anim.setDuration(200)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._opacity_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._opacity_anim.setDuration(360)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_hover(self): return self._hover
    def _set_hover(self, v):
        self._hover = v
        self.update()
    hover_progress = pyqtProperty(float, fget=_get_hover, fset=_set_hover)

    def _get_cover(self): return self._cover_progress
    def _set_cover(self, v):
        self._cover_progress = v
        self.update()
    cover_progress = pyqtProperty(float, fget=_get_cover, fset=_set_cover)

    def set_cover(self, pm: QPixmap):
        self._cover = pm
        self._cover_progress = 0.0
        anim = QPropertyAnimation(self, b"cover_progress", self)
        anim.setDuration(420)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def set_coop(self, v):
        self._is_coop = v
        self.update()

    def set_favorite(self, v):
        self._is_fav = v
        self.update()

    def reveal(self, delay_ms: int = 0):
        self._opacity_anim.stop()
        self._opacity.setOpacity(0.0)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        QTimer.singleShot(delay_ms, self._opacity_anim.start)

    def enterEvent(self, _e):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()

    def leaveEvent(self, _e):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.game)
        elif e.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(self.game, e.globalPosition().toPoint())

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        hv = self._hover
        cx, cy = self.width() / 2, self.height() / 2
        scale = 1.0 + 0.03 * hv
        p.translate(cx, cy)
        p.scale(scale, scale)
        p.translate(-cx, -cy)

        m = self.MARGIN
        rect = QRectF(m, m, self.W, self.H)
        r = self.RADIUS

        shadow_a = int(60 + 130 * hv)
        for i in range(10, 0, -1):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, shadow_a // (i + 1)))
            offset = 3 + i * 0.6
            grow = i * 0.5
            p.drawRoundedRect(
                rect.adjusted(-grow, -grow, grow, grow).translated(0, offset),
                r + grow, r + grow,
            )

        path = QPainterPath()
        path.addRoundedRect(rect, r, r)
        p.setClipPath(path)
        p.fillPath(path, QColor("#1a2535"))

        if self._cover:
            scaled = self._cover.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) / 2
            y = rect.y() + (rect.height() - scaled.height()) / 2
            p.setOpacity(self._cover_progress)
            p.drawPixmap(int(x), int(y), scaled)
            p.setOpacity(1.0)
            grad = QLinearGradient(
                rect.x(), rect.y() + rect.height() * 0.35,
                rect.x(), rect.bottom(),
            )
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(1.0, QColor(0, 0, 0, 235))
            p.fillRect(rect, grad)

        p.setClipping(False)
        f = QFont(); f.setPointSize(10); f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        text_rect = QRectF(
            rect.x() + 10, rect.y(),
            rect.width() - 20, rect.height() - 10,
        )
        p.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignBottom
                | Qt.TextFlag.TextWordWrap),
            self.game.name,
        )

        badge = self.game.source.upper()
        f2 = QFont(); f2.setPointSize(7); f2.setBold(True)
        p.setFont(f2)
        fm = p.fontMetrics()
        bw = fm.horizontalAdvance(badge) + 12
        bh = fm.height() + 4
        bx, by = rect.x() + 8, rect.y() + 8

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 175))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
        p.setPen(QColor("white"))
        p.drawText(QRectF(bx, by, bw, bh),
                   int(Qt.AlignmentFlag.AlignCenter), badge)

        if self._is_fav:
            f3 = QFont(); f3.setPointSize(13)
            p.setFont(f3)
            p.setPen(QColor("#ffd700"))
            p.drawText(
                QRectF(bx + bw + 4, by - 4, 22, 22),
                int(Qt.AlignmentFlag.AlignCenter), "★",
            )

        if self._is_coop:
            bw2 = 54
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(30, 170, 80, 230))
            p.drawRoundedRect(
                QRectF(rect.right() - 8 - bw2, by, bw2, bh), 4, 4,
            )
            p.setPen(QColor("white"))
            p.setFont(f2)
            p.drawText(
                QRectF(rect.right() - 8 - bw2, by, bw2, bh),
                int(Qt.AlignmentFlag.AlignCenter), "CO-OP",
            )

        if hv > 0.02:
            pen = QPen(QColor(90, 160, 255, int(190 * hv)))
            pen.setWidthF(1.6)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, r, r)


class LauncherWindow(QMainWindow):
    games_scanned = pyqtSignal(list)
    cover_loaded = pyqtSignal(str, bytes)
    coop_detected = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coop Launcher")
        self.resize(1320, 840)
        self.setMinimumSize(900, 560)

        self.games: list[Game] = []
        self.coop_status: dict[str, bool] = load_cache()
        self.favorites: set[str] = set(load_favorites())
        self.cards: dict[str, GameCard] = {}

        self.games_scanned.connect(self._on_games_scanned)
        self.cover_loaded.connect(self._on_cover_loaded)
        self.coop_detected.connect(self._on_coop_detected)

        self._build_ui()
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background: transparent;")

        self.bg = AnimatedBackground(central)
        self.bg.lower()

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(14)

        title = QLabel("Coop Launcher")
        title.setStyleSheet(
            "color:#eaf0f7;font-size:24px;font-weight:800;letter-spacing:0.5px;"
        )
        header.addWidget(title)
        header.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск игры...")
        self.search.setFixedWidth(300)
        self.search.setStyleSheet("""
            QLineEdit {
                background: rgba(24,38,52,0.85);
                color:#eaf0f7;
                border:1px solid #253a52;
                border-radius:10px;
                padding:8px 14px;
                font-size:13px;
            }
            QLineEdit:focus {
                border:1px solid #3d6cff;
                background: rgba(24,38,52,1.0);
            }
        """)
        self.search.textChanged.connect(self._apply_filter)
        header.addWidget(self.search)

        self.only_coop = QCheckBox("Только кооп")
        self.only_fav = QCheckBox("Избранное")
        for cb in (self.only_coop, self.only_fav):
            cb.setStyleSheet("""
                QCheckBox { color:#cfd8e3; font-size:13px; padding:4px; }
                QCheckBox::indicator {
                    width:16px; height:16px; border-radius:4px;
                    border:1px solid #35516f; background:#141e2b;
                }
                QCheckBox::indicator:checked {
                    background:#3d6cff; border:1px solid #5b84ff;
                }
            """)
            cb.stateChanged.connect(self._apply_filter)
            header.addWidget(cb)

        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.scroll.viewport().setStyleSheet("background:transparent;")

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background:transparent;")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

        self.status = QLabel("Сканирую библиотеки...")
        self.status.setStyleSheet("color:#7d8b9a;font-size:12px;padding:2px;")
        root.addWidget(self.status)

        self._apply_menu_style()

    def _apply_menu_style(self):
        self.setStyleSheet(self.styleSheet() + """
            QMenu {
                background:#131e2b; color:#eaf0f7;
                border:1px solid #253a52; border-radius:8px; padding:6px;
                font-size:13px;
            }
            QMenu::item { padding:7px 22px; border-radius:5px; }
            QMenu::item:selected { background:#243a52; }
            QMenu::separator { height:1px; background:#253a52; margin:5px 8px; }
            QScrollBar:vertical {
                background: transparent; width:10px; margin:0;
            }
            QScrollBar::handle:vertical {
                background: #2a3f57; border-radius:5px; min-height:30px;
            }
            QScrollBar::handle:vertical:hover { background:#3d6cff; }
            QScrollBar::add-line, QScrollBar::sub-line { height:0; }
        """)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.bg.setGeometry(0, 0, self.width(), self.height())
        if self.cards:
            self._relayout(reveal=False)

    def _scan_worker(self):
        try:
            games = scan_all()
        except Exception:
            games = []
        self.games_scanned.emit(games)

    def _on_games_scanned(self, games):
        self.games = games
        self._build_cards()
        self._relayout(reveal=True)
        self.status.setText(
            f"Найдено игр: {len(games)}. Загружаю обложки и кооп-статусы..."
        )
        self._start_cover_loading()
        self._start_coop_detection()

    def _build_cards(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self.cards.clear()
        for g in self.games:
            c = GameCard(g)
            c.set_coop(self.coop_status.get(g.key))
            c.set_favorite(g.key in self.favorites)
            c.activated.connect(self._launch)
            c.context_requested.connect(self._show_context)
            self.cards[g.key] = c

    def _start_cover_loading(self):
        urls = {g.key: g.cover_url for g in self.games if g.cover_url}
        if not urls:
            return
        threading.Thread(target=self._cover_worker, args=(urls,),
                         daemon=True).start()

    def _cover_worker(self, urls):
        def fetch(item):
            k, u = item
            try:
                req = urllib.request.Request(
                    u, headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    return k, r.read()
            except Exception:
                return k, None

        with ThreadPoolExecutor(max_workers=8) as ex:
            for k, data in ex.map(fetch, urls.items()):
                if data:
                    self.cover_loaded.emit(k, data)

    def _on_cover_loaded(self, key, data):
        card = self.cards.get(key)
        if not card:
            return
        pm = QPixmap()
        if pm.loadFromData(data):
            card.set_cover(pm)

    def _start_coop_detection(self):
        to_check = [
            g for g in self.games
            if g.source == "steam" and g.key not in self.coop_status
        ]
        if not to_check:
            self.status.setText(f"Готово. Игр: {len(self.games)}")
            return
        threading.Thread(target=self._coop_worker, args=(to_check,),
                         daemon=True).start()

    def _coop_worker(self, games):
        for g in games:
            res = fetch_coop_info(g.app_id)
            if res is not None:
                self.coop_status[g.key] = res
                save_cache(self.coop_status)
                self.coop_detected.emit(g.key, res)
            time.sleep(1.6)

    def _on_coop_detected(self, key, res):
        c = self.cards.get(key)
        if c:
            c.set_coop(res)
        if self.only_coop.isChecked():
            self._relayout(reveal=True)

    def _apply_filter(self, *_):
        self._relayout(reveal=True)

    def _visible_cards(self) -> list[GameCard]:
        q = self.search.text().strip().lower()
        coop_only = self.only_coop.isChecked()
        fav_only = self.only_fav.isChecked()
        out: list[GameCard] = []
        for g in self.games:
            if q and q not in g.name.lower():
                continue
            if coop_only and not self.coop_status.get(g.key):
                continue
            if fav_only and g.key not in self.favorites:
                continue
            out.append(self.cards[g.key])
        out.sort(key=lambda c: (
            c.game.key not in self.favorites,
            c.game.name.lower(),
        ))
        return out

    def _relayout(self, reveal: bool = True):
        while self.grid.count():
            self.grid.takeAt(0)
        visible = self._visible_cards()
        vis_keys = {c.game.key for c in visible}
        for k, c in self.cards.items():
            if k not in vis_keys:
                c.hide()
        cols = max(1, (self.scroll.viewport().width() - 10) // 264)
        for i, c in enumerate(visible):
            c.show()
            self.grid.addWidget(c, i // cols, i % cols)
            if reveal:
                c.reveal(delay_ms=min(i * 18, 600))

    def _launch(self, game: Game):
        QDesktopServices.openUrl(QUrl(game.launch_uri))
        self.status.setText(f"Запуск: {game.name}")

    def _show_context(self, game: Game, pos):
        menu = QMenu(self)
        is_fav = game.key in self.favorites
        is_coop = bool(self.coop_status.get(game.key))

        fav_act = menu.addAction(
            "Убрать из избранного" if is_fav else "⭐ В избранное"
        )
        coop_act = menu.addAction(
            "Снять метку «кооп»" if is_coop else "✅ Пометить как кооп"
        )
        menu.addSeparator()
        launch_act = menu.addAction("▶ Запустить")

        act = menu.exec(pos)
        if act == fav_act:
            if is_fav:
                self.favorites.remove(game.key)
            else:
                self.favorites.add(game.key)
            save_favorites(self.favorites)
            self.cards[game.key].set_favorite(game.key in self.favorites)
            self._relayout(reveal=True)
        elif act == coop_act:
            new = not is_coop
            self.coop_status[game.key] = new
            save_cache(self.coop_status)
            self.cards[game.key].set_coop(new)
            self._relayout(reveal=True)
        elif act == launch_act:
            self._launch(game)
