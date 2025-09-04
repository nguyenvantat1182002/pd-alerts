import qdarkstyle

from windows import MainWindow
from PyQt5.QtWidgets import QApplication


palette = qdarkstyle.DarkPalette()
palette.ID = 'dark'

app = QApplication([])
app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5', palette=palette))

window = MainWindow()
window.show()

app.exec_()
