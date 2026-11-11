import sys
import math
import threading
import urllib.request
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy, QStackedWidget,
    QScrollArea, QLineEdit, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, QPoint, pyqtSignal
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QLinearGradient, QRadialGradient, QPen, QBrush, QPixmap
)
from games import Game, scan_all, get_steam_cover_url, fetch_steam_details
from friends import fetch_steam_friends, get_dummy_friends

USER_PROFILE = {"name": "Tima", "avatar_color": "#555555"}
FONT_MAIN = "Segoe UI"
FONT_LIGHT = "Segoe UI Light"

BG        = "#050505"                    
PANEL     = "rgba(45, 45, 45, 0.85)"     
BORDER    = "rgba(255, 255, 255, 0.15)"  
TEXT      = "#FFFFFF"                    
TEXT_DIM  = "rgba(255, 255, 255, 0.45)"  

def get_color_for_game(name):
    colors = ["#3d6cff", "#ff5722", "#00a8a8", "#8c3cc8", "#c0392b", "#d4af37", "#aa0000", "#ff007f"]
    return colors[hash(name) % len(colors)]

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 400)
        
        screen_geo = self.screen().geometry()
        self.move(screen_geo.center().x() - self.width() // 2, screen_geo.center().y() - self.height() // 2)

        self.anim_move = QPropertyAnimation(self, b"pos")
        self.anim_move.setDuration(1000)
        self.anim_move.setEasingCurve(QEasingCurve.Type.OutExpo)
        
        self.anim_fade = QPropertyAnimation(self, b"windowOpacity")
        self.anim_fade.setDuration(800)
        self.anim_fade.setEasingCurve(QEasingCurve.Type.InOutCubic)

        QTimer.singleShot(1500, self.start_disappear)

    def start_disappear(self):
        self.anim_move.setStartValue(self.pos())
        self.anim_move.setEndValue(self.pos() - QPoint(0, 150))
        self.anim_fade.setStartValue(1.0)
        self.anim_fade.setEndValue(0.0)
        
        self.anim_move.start()
        self.anim_fade.start()
        self.anim_fade.finished.connect(self.finish)

    def finish(self):
        self.main_window = MainWindow()
        self.main_window.show()
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 100, 0, 250)
        grad.setColorAt(0, QColor("#FFFFFF"))
        grad.setColorAt(1, QColor("#666666"))
        painter.setFont(QFont(FONT_MAIN, 72, QFont.Weight.Black))
        pen = QPen()
        pen.setBrush(QBrush(grad))
        painter.setPen(pen)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "COOP")

class GameListItem(QFrame):
    clicked = pyqtSignal(object)
    def __init__(self, game: Game):
        super().__init__()
        self.game = game
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        
        self.setStyleSheet(f"""
            QFrame {{ border-radius: 12px; border: 1px solid transparent; background: transparent; }}
            QFrame:hover {{ background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.1); }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(15)
        
        self.icon = QLabel()
        self.icon.setFixedSize(40, 40)
        self.icon.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {get_color_for_game(game.name)}, stop:1 #000000); border-radius: 8px;")
        layout.addWidget(self.icon)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name = QLabel(game.name)
        name.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 600; font-family: '{FONT_MAIN}';")
        
        meta = QLabel(game.source.capitalize())
        meta.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        
        text_layout.addWidget(name)
        text_layout.addWidget(meta)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_cover(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.icon.setPixmap(pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            self.icon.setStyleSheet("border-radius: 8px;")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.game)

class FriendListItem(QFrame):
    def __init__(self, friend):
        super().__init__()
        self.setFixedHeight(64)
        self.setStyleSheet(f"QFrame {{ border-radius: 12px; background: transparent; }} QFrame:hover {{ background: rgba(255, 255, 255, 0.08); }}")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(15)
        
        self.av = QLabel()
        self.av.setFixedSize(40, 40)
        color = "#FFFFFF" if friend.get('online') else "#444444"
        self.av.setStyleSheet(f"background: {color}; border-radius: 20px;")
        layout.addWidget(self.av)
        
        col = QVBoxLayout()
        col.setSpacing(2)
        
        name = QLabel(friend.get('name', 'Unknown'))
        name.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 600; font-family: '{FONT_MAIN}';")
        
        status_color = TEXT if friend.get('game') else TEXT_DIM
        status_text = friend.get('game') if friend.get('game') else friend.get('status', '')
        status = QLabel(f"{friend.get('launcher', '')} • {status_text}")
        status.setStyleSheet(f"color: {status_color}; font-size: 11px; font-weight: 600;")
        
        col.addWidget(name)
        col.addWidget(status)
        layout.addLayout(col)
        layout.addStretch()

    def set_avatar(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.av.setPixmap(pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            self.av.setStyleSheet("border-radius: 20px;")

class DropdownPanel(QFrame):
    def __init__(self, parent, on_state_change):
        super().__init__(parent)
        self.parent = parent
        self.on_state_change = on_state_change
        self.is_pinned = False
        self.is_open = False
        
        self.setStyleSheet(f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 16px; }}")
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 20)
        self.setGraphicsEffect(shadow)
        
        self.anim_max = QPropertyAnimation(self, b"maximumHeight")
        self.anim_max.setDuration(250)
        self.anim_max.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.anim_min = QPropertyAnimation(self, b"minimumHeight")
        self.anim_min.setDuration(250)
        self.anim_min.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.check_hide)
        
        self.setFixedWidth(340)
        self.setFixedHeight(0)
        
    def set_content(self, content_widget):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(content_widget)
        
    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned: self.hide_timer.stop()
        else:
            if not self.underMouse(): self.close_dropdown()
        self.on_state_change()
                
    def open_dropdown(self, x, y):
        self.hide_timer.stop()
        self.move(x, y)
        self.show()
        self.raise_()
        self.is_open = True
        
        self.anim_max.stop()
        self.anim_min.stop()
        self.anim_max.setStartValue(self.maximumHeight())
        self.anim_max.setEndValue(500)
        self.anim_min.setStartValue(self.minimumHeight())
        self.anim_min.setEndValue(500)
        self.anim_max.start()
        self.anim_min.start()
        self.on_state_change()
            
    def close_dropdown(self):
        if not self.is_pinned and self.is_open:
            self.is_open = False
            self.anim_max.stop()
            self.anim_min.stop()
            self.anim_max.setStartValue(self.maximumHeight())
            self.anim_max.setEndValue(0)
            self.anim_min.setStartValue(self.minimumHeight())
            self.anim_min.setEndValue(0)
            self.anim_max.start()
            self.anim_min.start()
            self.on_state_change()
            
    def enterEvent(self, event):
        self.hide_timer.stop()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if not self.is_pinned: self.hide_timer.start(200)
        super().leaveEvent(event)
        
    def check_hide(self):
        if not self.is_pinned: self.close_dropdown()

class MainWindow(QMainWindow):
    games_loaded = pyqtSignal(list)
    cover_loaded = pyqtSignal(str, bytes)
    desc_loaded = pyqtSignal(str)
    friends_loaded = pyqtSignal(list)
    avatar_loaded = pyqtSignal(str, bytes)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coop Launcher")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(f"background-color: {BG};")

        self.selected_game = None
        self.anim_t = 0
        self.games = []
        self.game_items = {}
        
        self.init_ui()
        
        self.bg_timer = QTimer(self)
        self.bg_timer.timeout.connect(self.animate_bg)
        self.bg_timer.start(30)

        self.games_loaded.connect(self.on_games_loaded)
        self.cover_loaded.connect(self.on_cover_loaded)
        self.desc_loaded.connect(self.on_desc_loaded)
        self.friends_loaded.connect(self.on_friends_loaded)
        self.avatar_loaded.connect(self.on_avatar_loaded)

        threading.Thread(target=self.scan_worker, daemon=True).start()
        threading.Thread(target=self.load_friends_worker, daemon=True).start()

    def scan_worker(self):
        try:
            games = scan_all()
            self.games_loaded.emit(games)
        except Exception as e:
            print(f"Ошибка сканирования: {e}")

    def on_games_loaded(self, games):
        self.games = games
        for i in reversed(range(self.games_layout.count())): 
            widget = self.games_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
        
        for g in self.games:
            item = GameListItem(g)
            item.clicked.connect(self.select_game)
            self.games_layout.addWidget(item)
            self.game_items[g.key] = item
        self.games_layout.addStretch()
        
        threading.Thread(target=self.load_covers_worker, daemon=True).start()

    def load_covers_worker(self):
        for g in self.games:
            if g.source == "steam":
                url = get_steam_cover_url(g.app_id)
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        data = r.read()
                    self.cover_loaded.emit(g.key, data)
                except Exception:
                    pass

    def on_cover_loaded(self, key, data):
        item = self.game_items.get(key)
        if item:
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                item.set_cover(pixmap)

    def load_friends_worker(self):
        friends = fetch_steam_friends()
        if not friends:
            friends = get_dummy_friends()
        self.friends_loaded.emit(friends)

    def on_friends_loaded(self, friends):
        while self.friends_container.count():
            item = self.friends_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        self.friend_items = []
        for f in friends:
            item = FriendListItem(f)
            self.friends_container.addWidget(item)
            self.friend_items.append((f, item))
        self.friends_container.addStretch()
        
        threading.Thread(target=self.load_avatars_worker, args=(friends,), daemon=True).start()

    def load_avatars_worker(self, friends):
        for f in friends:
            url = f.get("avatar", "")
            if url:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        data = r.read()
                    self.avatar_loaded.emit(f["steam_id"], data)
                except Exception:
                    pass

    def on_avatar_loaded(self, steam_id, data):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            for f, item in getattr(self, 'friend_items', []):
                if f.get("steam_id") == steam_id:
                    item.set_avatar(pixmap)
                    break

    def animate_bg(self):
        self.anim_t += 0.01
        self.update()

    def open_dropdown(self, dropdown, btn):
        if dropdown == self.dropdown_lib and not self.dropdown_friends.is_pinned: self.dropdown_friends.close_dropdown()
        elif dropdown == self.dropdown_friends and not self.dropdown_lib.is_pinned: self.dropdown_lib.close_dropdown()
        pos = btn.mapTo(self, QPoint(0, 0))
        x = pos.x() + btn.width() // 2 - 170
        y = btn.mapTo(self, QPoint(0, btn.height())).y() + 5
        dropdown.open_dropdown(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'dropdown_lib') and self.dropdown_lib.is_open:
            pos = self.btn_lib.mapTo(self, QPoint(0, 0))
            self.dropdown_lib.move(pos.x() + self.btn_lib.width() // 2 - 170, self.btn_lib.mapTo(self, QPoint(0, self.btn_lib.height())).y() + 5)
        if hasattr(self, 'dropdown_friends') and self.dropdown_friends.is_open:
            pos = self.btn_friends.mapTo(self, QPoint(0, 0))
            self.dropdown_friends.move(pos.x() + self.btn_friends.width() // 2 - 170, self.btn_friends.mapTo(self, QPoint(0, self.btn_friends.height())).y() + 5)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_l = QVBoxLayout(central)
        main_l.setContentsMargins(0, 0, 0, 0)
        main_l.setSpacing(0)

        top = QWidget()
        top.setFixedHeight(70)
        top.setStyleSheet(f"background: {PANEL}; border-bottom: 1px solid {BORDER};")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(30, 0, 30, 0)
        tl.setSpacing(40)
        
        logo = QLabel("COOP")
        logo.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 900; letter-spacing: 4px;")
        tl.addWidget(logo)
        
        self.btn_lib = QPushButton("БИБЛИОТЕКА")
        self.btn_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lib.enterEvent = lambda e: self.open_dropdown(self.dropdown_lib, self.btn_lib)
        self.btn_lib.leaveEvent = lambda e: self.dropdown_lib.leaveEvent(e) if not self.dropdown_lib.is_pinned else None
        self.btn_lib.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        self.btn_friends = QPushButton("ДРУЗЬЯ")
        self.btn_friends.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_friends.enterEvent = lambda e: self.open_dropdown(self.dropdown_friends, self.btn_friends)
        self.btn_friends.leaveEvent = lambda e: self.dropdown_friends.leaveEvent(e) if not self.dropdown_friends.is_pinned else None

        tl.addWidget(self.btn_lib)
        tl.addWidget(self.btn_friends)
        tl.addStretch()
        
        name = QLabel(USER_PROFILE['name'].upper())
        name.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700; letter-spacing: 1px; margin-right: 15px;")
        av = QLabel()
        av.setFixedSize(36, 36)
        av.setStyleSheet(f"background: {USER_PROFILE['avatar_color']}; border-radius: 18px; border: 1px solid {TEXT};")
        
        tl.addWidget(name)
        tl.addWidget(av)
        main_l.addWidget(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        lib_w = QWidget()
        lib_w.setStyleSheet("background: transparent;")
        lib_l = QVBoxLayout(lib_w)
        lib_l.setContentsMargins(0, 0, 0, 0)
        lib_l.setSpacing(10)
        
        search_layout = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Поиск игры...")
        search.setStyleSheet(f"QLineEdit {{ background: rgba(0, 0, 0, 0.3); color: {TEXT}; border: 1px solid {BORDER}; border-radius: 12px; padding: 10px 14px; font-size: 14px; }} QLineEdit:focus {{ border: 1px solid {TEXT}; }}")
        search_layout.addWidget(search)
        
        btn_pin_lib = QPushButton("📌")
        btn_pin_lib.setFixedSize(36, 36)
        btn_pin_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pin_lib.setStyleSheet(f"QPushButton {{ background: rgba(0, 0, 0, 0.3); color: {TEXT_DIM}; font-size: 14px; border: 1px solid {BORDER}; border-radius: 12px; }} QPushButton:hover {{ color: {TEXT}; }}")
        search_layout.addWidget(btn_pin_lib)
        lib_l.addLayout(search_layout)
        
        scroll_games = QScrollArea()
        scroll_games.setWidgetResizable(True)
        scroll_games.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar { width: 0; }")
        sg_w = QWidget()
        sg_w.setStyleSheet("background: transparent;")
        self.games_layout = QVBoxLayout(sg_w)
        self.games_layout.setContentsMargins(0, 0, 0, 0)
        self.games_layout.setSpacing(5)
        scroll_games.setWidget(sg_w)
        lib_l.addWidget(scroll_games)
        
        self.dropdown_lib = DropdownPanel(self, self.update_tabs)
        self.dropdown_lib.set_content(lib_w)
        btn_pin_lib.clicked.connect(self.dropdown_lib.toggle_pin)

        fr_w = QWidget()
        fr_w.setStyleSheet("background: transparent;")
        fr_l = QVBoxLayout(fr_w)
        fr_l.setContentsMargins(0, 0, 0, 0)
        
        search_fr_layout = QHBoxLayout()
        btn_pin_fr = QPushButton("📌")
        btn_pin_fr.setFixedSize(36, 36)
        btn_pin_fr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pin_fr.setStyleSheet(f"QPushButton {{ background: rgba(0, 0, 0, 0.3); color: {TEXT_DIM}; font-size: 14px; border: 1px solid {BORDER}; border-radius: 12px; }} QPushButton:hover {{ color: {TEXT}; }}")
        search_fr_layout.addStretch()
        search_fr_layout.addWidget(btn_pin_fr)
        fr_l.addLayout(search_fr_layout)
        
        scroll_fr = QScrollArea()
        scroll_fr.setWidgetResizable(True)
        scroll_fr.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar { width: 0; }")
        sf_w = QWidget()
        sf_w.setStyleSheet("background: transparent;")
        self.friends_container = QVBoxLayout(sf_w)
        self.friends_container.setContentsMargins(0, 0, 0, 0)
        self.friends_container.setSpacing(5)
        scroll_fr.setWidget(sf_w)
        fr_l.addWidget(scroll_fr)
        
        self.dropdown_friends = DropdownPanel(self, self.update_tabs)
        self.dropdown_friends.set_content(fr_w)
        btn_pin_fr.clicked.connect(self.dropdown_friends.toggle_pin)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        welcome_page = QWidget()
        wl = QVBoxLayout(welcome_page)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w_title = QLabel("Добро пожаловать")
        w_title.setStyleSheet(f"color: {TEXT}; font-size: 64px; font-weight: 300; font-family: '{FONT_LIGHT}';")
        w_sub = QLabel("Сканирую библиотеки Steam и Epic...")
        w_sub.setStyleSheet(f"color: {TEXT_DIM}; font-size: 16px; margin-top: 15px; font-weight: 500;")
        wl.addWidget(w_title, alignment=Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(w_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(welcome_page)

        self.game_page = QWidget()
        self.game_page.setStyleSheet("background: transparent;")
        gl = QVBoxLayout(self.game_page)
        gl.setContentsMargins(0, 0, 0, 0)

        self.art_frame = QWidget()
        self.art_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        art_l = QVBoxLayout(self.art_frame)
        art_l.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        art_l.setContentsMargins(80, 80, 80, 80)

        self.g_title = QLabel("")
        self.g_title.setStyleSheet(f"color: {TEXT}; font-size: 72px; font-weight: 800; font-family: '{FONT_MAIN}'; letter-spacing: -1px;")
        self.g_meta = QLabel("")
        self.g_meta.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px; font-weight: 700; letter-spacing: 2px;")
        self.g_desc = QLabel("")
        self.g_desc.setStyleSheet(f"color: rgba(255,255,255,0.6); font-size: 16px; line-height: 1.5;")
        self.g_desc.setWordWrap(True)
        self.g_desc.setMaximumWidth(700)
        
        self.btn_action = QPushButton("ИГРАТЬ")
        self.btn_action.setFixedSize(260, 60)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.hide()
        self.btn_action.clicked.connect(self.on_action_clicked)

        art_l.addWidget(self.g_title)
        art_l.addSpacing(10)
        art_l.addWidget(self.g_meta)
        art_l.addSpacing(20)
        art_l.addWidget(self.g_desc)
        art_l.addSpacing(40)
        art_l.addWidget(self.btn_action)

        gl.addWidget(self.art_frame)
        self.stack.addWidget(self.game_page)

        body.addWidget(self.stack, stretch=1)
        main_l.addLayout(body)
        self.update_tabs()

    def update_tabs(self):
        active = f"color: {TEXT}; border-bottom: 2px solid {TEXT};"
        inactive = f"color: {TEXT_DIM}; border-bottom: 2px solid transparent;"
        self.btn_lib.setStyleSheet(f"QPushButton {{ background: transparent; {active if self.dropdown_lib.is_open else inactive} font-size: 12px; font-weight: 800; letter-spacing: 2px; padding: 0 5px; padding-bottom: 5px; }} QPushButton:hover {{ color: {TEXT}; }}")
        self.btn_friends.setStyleSheet(f"QPushButton {{ background: transparent; {active if self.dropdown_friends.is_open else inactive} font-size: 12px; font-weight: 800; letter-spacing: 2px; padding: 0 5px; padding-bottom: 5px; }} QPushButton:hover {{ color: {TEXT}; }}")

    def select_game(self, game: Game):
        self.selected_game = game
        self.stack.setCurrentIndex(1)
        
        self.g_title.setText(game.name)
        self.g_meta.setText(f"{game.source.upper()}")
        self.g_desc.setText("Загрузка описания...")
        
        c = get_color_for_game(game.name)
        self.art_frame.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(5, 5, 5, 0.95), stop:0.5 rgba(5, 5, 5, 0.5)),
                qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c}, stop:1 {BG});
            border-radius: 24px;
            border: 1px solid rgba(255,255,255,0.05);
        """)
        
        self.btn_action.show()
        self.btn_action.setText("ИГРАТЬ")
        self.btn_action.setEnabled(True)
        self.btn_action.setStyleSheet(f"QPushButton {{ background: {TEXT}; color: {BG}; border: none; border-radius: 30px; font-weight: 800; letter-spacing: 2px; font-size: 16px; }} QPushButton:hover {{ background: #CCCCCC; }}")

        if game.source == "steam":
            threading.Thread(target=self.load_desc_worker, args=(game,), daemon=True).start()
        else:
            self.g_desc.setText(f"Игра из библиотеки {game.source.capitalize()}.")

    def load_desc_worker(self, game):
        details = fetch_steam_details(game.app_id)
        desc = details.get("description", "")
        genres = ", ".join(details.get("genres", []))
        full = desc + (f"\n\nЖанры: {genres}" if genres else "")
        if full.strip():
            self.desc_loaded.emit(full)
        else:
            self.desc_loaded.emit("Описание недоступно.")

    def on_desc_loaded(self, text):
        self.g_desc.setText(text)

    def on_action_clicked(self):
        if not self.selected_game: return
        import os
        os.startfile(self.selected_game.launch_uri)
        self.btn_action.setText("ЗАПУЩЕНО")
        self.btn_action.setEnabled(False)
        self.btn_action.setStyleSheet(f"QPushButton {{ background: transparent; color: {TEXT_DIM}; border: 1px solid {BORDER}; border-radius: 30px; font-weight: 800; letter-spacing: 2px; font-size: 16px; }}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG))
        w, h = self.width(), self.height()
        c1 = QColor(30, 30, 30, 60) 
        g1 = QRadialGradient(w*(0.3 + 0.1*math.sin(self.anim_t)), h*(0.4 + 0.1*math.cos(self.anim_t)), w*0.7)
        g1.setColorAt(0, c1); g1.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(self.rect(), g1)
        c2 = QColor(20, 20, 20, 60) 
        g2 = QRadialGradient(w*(0.7 + 0.1*math.cos(self.anim_t + 1)), h*(0.6 + 0.1*math.sin(self.anim_t + 1)), w*0.6)
        g2.setColorAt(0, c2); g2.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(self.rect(), g2)
