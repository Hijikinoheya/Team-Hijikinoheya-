import sys
import os
import json
import subprocess
from PyQt5.QtCore import Qt, QUrl, QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QGroupBox, QMessageBox,
    QComboBox, QMenuBar, QMenu, QAction, QSplashScreen
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt5.Qt import QDesktopServices

# 定数設定
API_URL = "https://home.hijikinoheya.com/app/app.json"
LICENSE_URL = "https://home.hijikinoheya.com/license_page.php"
HOMEPAGE_URL = "https://home.hijikinoheya.com"
PAGE_BASE = "https://home.hijikinoheya.com/page/"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")
APP_TITLE = "Team Hijikinoheya App Downloader"
APP_VERSION = "V1.0"

class WebWindow(QMainWindow):
    def __init__(self, title, url):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(800, 600)
        view = QWebEngineView()
        view.load(QUrl(url))
        self.setCentralWidget(view)

class AppDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION}")
        self.resize(900, 700)

        # メニューバー作成
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # ファイルメニュー
        file_menu = QMenu("ファイル", self)
        exit_act = QAction("終了", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)
        menubar.addMenu(file_menu)

        # バージョンメニュー
        ver_menu = QMenu("バージョン", self)
        ver_act = QAction("バージョン情報", self)
        ver_act.triggered.connect(lambda: QMessageBox.information(self, "バージョン", f"{APP_TITLE} {APP_VERSION}"))
        ver_menu.addAction(ver_act)
        menubar.addMenu(ver_menu)

        # その他メニュー
        other_menu = QMenu("その他", self)
        pages = [
            ("ホームページ", HOMEPAGE_URL),
            ("個人情報の取り扱いについて", PAGE_BASE + "personal_info.php"),
            ("プライバシーポリシー", PAGE_BASE + "privacy-policy.php"),
            ("利用規約", PAGE_BASE + "terms-of-service.php")
        ]
        for name, url in pages:
            act = QAction(name, self)
            act.triggered.connect(lambda chk, u=url, n=name: self.open_web(n, u))
            other_menu.addAction(act)
        menubar.addMenu(other_menu)

        # ロゴ表示（サイズ調整）
        logo = QLabel()
        if os.path.exists(LOGO_PATH):
            pix = QPixmap(LOGO_PATH).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        else:
            logo.setText("Logo not found")

        # 操作ボタン群
        btn_status = QPushButton("ステータスページ")
        btn_status.clicked.connect(lambda: self.open_web("Status", "https://status.hijikinoheya.com/page/index.php"))
        btn_news = QPushButton("ニュース一覧")
        btn_news.clicked.connect(lambda: self.open_web("News", "https://home.hijikinoheya.com/news/page/index.php"))
        btn_license = QPushButton("ライセンス情報")
        btn_license.clicked.connect(lambda: self.open_web("License", LICENSE_URL))

        # カテゴリフィルタ
        self.combo = QComboBox()
        self.combo.addItem("すべてのカテゴリ")
        self.combo.currentTextChanged.connect(self.filter_category)

        top_layout = QHBoxLayout()
        top_layout.addWidget(logo)
        top_layout.addStretch()
        top_layout.addWidget(btn_status)
        top_layout.addWidget(btn_news)
        top_layout.addWidget(btn_license)
        top_layout.addWidget(self.combo)

        # アプリ一覧表示用スクロールエリア
        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setAlignment(Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(scroll)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # ネットワークマネージャ
        self.manager = QNetworkAccessManager()
        self.manager.finished.connect(self.on_data)

        # 初期データ取得
        QTimer.singleShot(0, self.load_data)

        self.apps = []
        self.groups = {}

    def open_web(self, title, url):
        win = WebWindow(title, url)
        win.show()
        setattr(self, f"_win_{title}", win)

    def load_data(self):
        req = QNetworkRequest(QUrl(API_URL))
        self.manager.get(req)

    def on_data(self, reply):
        if reply.error():
            QMessageBox.critical(self, "Error", "データの取得に失敗しました。")
            return
        data = reply.readAll()
        try:
            arr = json.loads(str(data, 'utf-8'))
            self.apps = arr
            self.populate()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"JSON解析エラー: {e}")

    def populate(self):
        # 以前のカードをクリア
        for i in reversed(range(self.vbox.count())):
            w = self.vbox.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.groups.clear()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("すべてのカテゴリ")

        # カテゴリごとにグルーピング
        for app in self.apps:
            cat = app.get('category', '未分類')
            if cat not in self.groups:
                box = QGroupBox(cat)
                layout = QVBoxLayout(box)
                self.groups[cat] = layout
                self.vbox.addWidget(box)
                self.combo.addItem(cat)
            self.add_card(self.groups[cat], app)

        self.combo.blockSignals(False)

    def add_card(self, layout, app):
        title = app.get('title', 'No Title')
        desc = app.get('description', '')
        link = app.get('download', '')
        w = QWidget()
        hl = QHBoxLayout(w)
        lbl = QLabel(f"<b>{title}</b><br>{desc}")
        btn = QPushButton("Download")
        btn.clicked.connect(lambda _, url=link: QDesktopServices.openUrl(QUrl(url)))
        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(btn)
        layout.addWidget(w)

    def filter_category(self, text):
        for cat, lay in self.groups.items():
            box = lay.parent()
            box.setVisible(text == "すべてのカテゴリ" or text == cat)

class SplashManager(QObject):
    finished = pyqtSignal()

    def __init__(self, splash):
        super().__init__()
        self.splash = splash
        self.steps = [
            ("ネットワーク接続確認中", self.check_ping),
            ("サーバーの確認中", self.check_ping),
            ("情報を取得中", self.wait_one_sec),
            ("ロード中", self.wait_two_sec)
        ]
        self.current = 0
        self.dot_count = 0

    def start(self):
        self.run_step()

    def run_step(self):
        if self.current >= len(self.steps):
            self.splash.showMessage(f"{APP_TITLE} {APP_VERSION}", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
            QTimer.singleShot(500, self.finished.emit)
            return
        text, func = self.steps[self.current]
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(lambda: self.update_dots(text))
        self.anim_timer.start(500)
        func()

    def update_dots(self, base):
        self.dot_count = (self.dot_count + 1) % 4
        dots = '.' * self.dot_count
        self.splash.showMessage(f"{base}{dots}", Qt.AlignBottom | Qt.AlignCenter, Qt.white)

    def check_ping(self):
        # ping を5回実行し、成功を判定
        host = HOMEPAGE_URL.replace('https://','').replace('http://','')
        count_flag = '-n' if sys.platform.startswith('win') else '-c'
        cmd = ['ping', count_flag, '5', host]
        result = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
        # 成功または失敗にかかわらず次のステップへ
        QTimer.singleShot(300, self.step_done)

    def wait_one_sec(self):
        QTimer.singleShot(1000, self.step_done)

    def wait_two_sec(self):
        QTimer.singleShot(2000, self.step_done)

    def step_done(self):
        self.anim_timer.stop()
        self.current += 1
        self.run_step()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # スプラッシュ画面設定
    pix = QPixmap(LOGO_PATH) if os.path.exists(LOGO_PATH) else QPixmap(400,300)
    splash_pix = pix.scaled(400, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    manager = SplashManager(splash)
    downloader = AppDownloader()
    manager.finished.connect(lambda: (splash.finish(downloader), downloader.show()))
    manager.start()
    sys.exit(app.exec_())
