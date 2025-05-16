import sys
import os
import json
import subprocess
import threading
import zipfile
import shutil
import requests
from PyQt5.QtCore import Qt, QUrl, QTimer, QObject, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QGroupBox, QMessageBox,
    QComboBox, QMenuBar, QMenu, QAction, QSplashScreen, QProgressBar
)
from PyQt5.QtGui import QPixmap, QIcon
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
        self.resize(1000, 800)
        view = QWebEngineView()
        view.load(QUrl(url))
        self.setCentralWidget(view)
        self.setWindowIcon(QIcon(LOGO_PATH))

class DownloadWindow(QWidget):
    def __init__(self, url, folder_name, parent=None):
        super().__init__()
        self.url = url
        self.folder_name = folder_name
        self.parent = parent
        self.zip_name = folder_name + ".zip"
        self.setWindowTitle(f"ダウンロード: {folder_name}")
        self.resize(400, 120)
        layout = QVBoxLayout(self)
        self.label = QLabel("準備中...", self)
        self.progress = QProgressBar(self)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        self.show()
        threading.Thread(target=self.download_and_extract, daemon=True).start()

    def download_and_extract(self):
        self.label.setText("ダウンロード中...")
        resp = requests.get(self.url, stream=True)
        total = int(resp.headers.get('content-length', 0))
        with open(self.zip_name, 'wb') as f:
            dl = 0
            for chunk in resp.iter_content(8192):
                if not chunk: continue
                f.write(chunk)
                dl += len(chunk)
                self.progress.setValue(int(dl * 100 / total))
        if zipfile.is_zipfile(self.zip_name):
            self.label.setText("Zipを解凍中...")
            root = self.folder_name
            with zipfile.ZipFile(self.zip_name, 'r') as z:
                z.extractall(root)
            sub = os.path.join(root, os.path.basename(root))
            if os.path.isdir(sub):
                for item in os.listdir(sub): shutil.move(os.path.join(sub, item), root)
                shutil.rmtree(sub)
            os.remove(self.zip_name)
        self.label.setText("完了しました！")
        self.progress.setValue(100)
        if self.parent:
            QTimer.singleShot(0, self.parent.reload_apps)

class AppDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION}")
        self._init_size = QSize(900, 700)
        self.resize(self._init_size)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル")
        file_menu.addAction("終了", self.close)
        ver_menu = menubar.addMenu("バージョン")
        ver_menu.addAction("バージョン情報", lambda: QMessageBox.information(self, "バージョン", f"{APP_TITLE} {APP_VERSION}"))
        other = menubar.addMenu("その他")
        pages = [("ホームページ", HOMEPAGE_URL), ("個人情報", PAGE_BASE+"personal_info.php"),
                 ("プライバシー", PAGE_BASE+"privacy-policy.php"), ("規約", PAGE_BASE+"terms-of-service.php")]
        for name, url in pages:
            other.addAction(name, lambda chk, u=url, n=name: self.open_web(n, u))
        menubar.addAction("リロード", self.reload_apps)

        header = QWidget(); hbox = QHBoxLayout(header)
        lbl_logo = QLabel()
        if os.path.exists(LOGO_PATH):
            lbl_logo.setPixmap(QPixmap(LOGO_PATH).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hbox.addWidget(lbl_logo); hbox.addStretch()
        for txt, link in [("ステータス","https://status.hijikinoheya.com/page/index.php"),
                          ("ニュース","https://home.hijikinoheya.com/news/page/index.php"),
                          ("ライセンス", LICENSE_URL)]:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, u=link, t=txt: self.open_web(t, u))
            hbox.addWidget(btn)
        self.combo_os = QComboBox(); self.combo_os.addItem("すべてのOS"); self.combo_os.currentTextChanged.connect(self.filter_items)
        self.combo_cat = QComboBox(); self.combo_cat.addItem("すべてのカテゴリ"); self.combo_cat.currentTextChanged.connect(self.filter_items)
        hbox.addWidget(QLabel("OS:")); hbox.addWidget(self.combo_os)
        hbox.addWidget(QLabel("カテゴリ:")); hbox.addWidget(self.combo_cat)

        self.container = QWidget(); self.vbox = QVBoxLayout(self.container); self.vbox.setAlignment(Qt.AlignTop)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.container)
        main_layout = QVBoxLayout(); main_layout.addWidget(header); main_layout.addWidget(scroll)
        central = QWidget(); central.setLayout(main_layout); self.setCentralWidget(central)

        self.manager = QNetworkAccessManager(); self.manager.finished.connect(self.on_data)
        self.apps = []; self.groups = {}
        QTimer.singleShot(0, self.load_data)

    def open_web(self, title, url):
        win = WebWindow(title, url); win.show(); setattr(self, f"_win_{title}", win)

    def reload_apps(self):
        self.resize(self._init_size)
        self.load_data()

    def load_data(self):
        self.manager.get(QNetworkRequest(QUrl(API_URL)))

    def on_data(self, reply):
        if reply.error():
            QMessageBox.critical(self, "Error", "データ取得失敗")
            return
        self.apps = json.loads(bytes(reply.readAll()).decode('utf-8'))
        self.combo_os.clear(); self.combo_os.addItem("すべてのOS")
        self.combo_cat.clear(); self.combo_cat.addItem("すべてのカテゴリ")
        oss, cats = set(), set()
        for app in self.apps:
            oss.add(app.get('os','全OS')); cats.add(app.get('category','未分類'))
        for o in sorted(oss): self.combo_os.addItem(o)
        for c in sorted(cats): self.combo_cat.addItem(c)
        self.populate()

    def populate(self):
        for i in reversed(range(self.vbox.count())):
            w = self.vbox.itemAt(i).widget()
            if w: w.setParent(None)
        self.groups.clear()
        for app in self.apps:
            cat = app.get('category','未分類')
            if cat not in self.groups:
                box = QGroupBox(cat); box.setLayout(QVBoxLayout()); self.groups[cat] = box; self.vbox.addWidget(box)
            self.add_entry(self.groups[cat].layout(), app)

    def add_entry(self, layout, app):
        title, desc, url = app['title'], app['description'], app['link']
        kind, osn = app.get('type','app'), app.get('os','全OS')
        folder, exe = app.get('folder', title), app.get('exe', f"{title}.exe")
        w = QWidget(); hl = QHBoxLayout(w)
        lbl = QLabel(f"<b>{title}</b><br>{desc}<br><i>対応OS: {osn}</i>")
        hl.addWidget(lbl)
        if kind == 'app':
            exists = os.path.isdir(folder)
            # Download
            dl = QPushButton("Download"); dl.setEnabled(not exists)
            dl.clicked.connect(lambda _, u=url, f=folder: DownloadWindow(u, f, parent=self))
            hl.addWidget(dl)
            # Run or Open
            run = QPushButton("実行")
            run.setEnabled(exists)
            def do_run(f, e):
                path = os.path.join(f, e)
                if sys.platform.startswith('darwin') and e.lower().endswith('.app'):
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen([path], shell=e.lower().endswith('.bat'))
            run.clicked.connect(lambda _, f=folder, e=exe: do_run(f, e))
            hl.addWidget(run)
            # ReadMe
            rd = QPushButton("ReadMe"); rd.setEnabled(False)
            rd_path = os.path.join(folder, 'README.txt')
            if exists and os.path.isfile(rd_path):
                rd.setEnabled(True)
                rd.clicked.connect(lambda _, p=rd_path: subprocess.Popen(['notepad', p] if sys.platform.startswith('win') else ['open', p]))
            hl.addWidget(rd)
            # Delete
            dlt = QPushButton("削除"); dlt.setEnabled(exists)
            dlt.clicked.connect(lambda _, f=folder: self.confirm_delete(f))
            hl.addWidget(dlt)
        else:
            btn = QPushButton("開く")
            btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
            hl.addWidget(btn)
        layout.addWidget(w)

    def confirm_delete(self, folder):
        res = QMessageBox.question(self, "削除確認", f"'{folder}'フォルダを削除しますか？", QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            shutil.rmtree(folder)
            self.reload_apps()

    def filter_items(self, _):
        so, sc = self.combo_os.currentText(), self.combo_cat.currentText()
        for app in self.apps:
            cat, osn = app.get('category',''), app.get('os','')
            box = self.groups.get(cat)
            if box:
                box.setVisible((sc == 'すべてのカテゴリ' or sc == cat) and (so == 'すべてのOS' or so == osn))

class SplashManager(QObject):
    finished = pyqtSignal()
    def __init__(self, splash):
        super().__init__(); self.splash = splash
        self.steps = [
            ("ネットワーク接続確認中", self.check_ping),
            ("サーバーの確認中", self.check_ping),
            ("情報を取得中", self.wait1),
            ("ロード中", self.wait2)
        ]
        self.cur = 0; self.dots = 0
    def start(self): self.run_step()
    def run_step(self):
        if self.cur >= len(self.steps):
            self.splash.showMessage(f"{APP_TITLE} {APP_VERSION}", Qt.AlignHCenter | Qt.AlignBottom, Qt.white)
            QTimer.singleShot(500, self.finished.emit)
            return
        txt, fn = self.steps[self.cur]
        self.anim = QTimer(self)
        self.anim.timeout.connect(lambda: self.update_dots(txt))
        self.anim.start(500)
        fn()
    def update_dots(self, base):
        self.dots = (self.dots + 1) % 4
        self.splash.showMessage(f"{base}{'.' * self.dots}", Qt.AlignHCenter | Qt.AlignBottom, Qt.white)
    def check_ping(self):
        host = HOMEPAGE_URL.replace('https://','').replace('http://','')
        flag = '-n' if sys.platform.startswith('win') else '-c'
        subprocess.Popen(['ping', flag, '5', host], stdout=subprocess.DEVNULL).wait()
        QTimer.singleShot(300, self.done)
    def wait1(self): QTimer.singleShot(1000, self.done)
    def wait2(self): QTimer.singleShot(2000, self.done)
    def done(self):
        self.anim.stop()
        self.cur += 1
        self.run_step()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(LOGO_PATH))
    pix = QPixmap(LOGO_PATH) if os.path.exists(LOGO_PATH) else QPixmap(300,300)
    splash = QSplashScreen(pix.scaled(800,600,Qt.KeepAspectRatio), Qt.WindowStaysOnTopHint)
    splash.show()
    mgr = SplashManager(splash)
    win = AppDownloader()
    mgr.finished.connect(lambda: (splash.finish(win), win.show()))
    mgr.start()
    sys.exit(app.exec_())
