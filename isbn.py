import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPlainTextEdit
from PyQt5.QtGui import QTextCursor
import re

class ISBNInputWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ISBN入力（978,979,977のみ許可）")
        self.resize(350, 250)

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.textChanged.connect(self.on_text_changed)
        self._updating = False  # 無限ループ防止

        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def on_text_changed(self):
        if self._updating:
            return

        original_text = self.text_edit.toPlainText()
        digits_only = re.sub(r'\D', '', original_text)  # 数字だけ抽出

        valid_chunks = []
        i = 0
        while i + 13 <= len(digits_only):
            chunk = digits_only[i:i+13]
            if chunk.startswith(('978', '979', '977')):
                valid_chunks.append(chunk)
            i += 13

        # 残りの未確定入力（13桁に満たない最後の部分）
        remainder = digits_only[i:]

        # 改行で区切って再構成（最後に未確定の数字が続く場合はそのまま）
        new_text = '\n'.join(valid_chunks)
        if remainder:
            new_text += '\n' + remainder

        if new_text != original_text:
            cursor = self.text_edit.textCursor()
            pos = cursor.position()
            self._updating = True
            self.text_edit.setPlainText(new_text)
            # カーソル再配置（末尾へ）
            cursor.setPosition(len(new_text))
            self.text_edit.setTextCursor(cursor)
            self._updating = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ISBNInputWidget()
    window.show()
    sys.exit(app.exec_())
