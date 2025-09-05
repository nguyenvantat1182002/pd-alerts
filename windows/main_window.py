import json
import os
import utils

from tradingview import TradingViewWs
from threads import TrackerThread
from PyQt5.QtCore import (QCoreApplication, QMetaObject, QSize, Qt, QFileSystemWatcher, QThread)
from PyQt5.QtGui import QCursor, QStandardItemModel, QStandardItem, QCloseEvent
from PyQt5.QtWidgets import *

from .widgets import CheckableComboBox


ASSETS_PATH = os.path.join(os.getcwd(), 'assets.json')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.symbols_model  = QStandardItemModel()

        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.addPath(ASSETS_PATH)
        self.file_watcher.fileChanged.connect(self.update_watched_files)

        self.ui.lineEdit.setCompleter(QCompleter(self.symbols_model, self))
        
        self.ui.pushButton.clicked.connect(self.pushButton_clicked)
        
        self.update_watched_files(ASSETS_PATH)

        self.sessions: dict[str, TradingViewWs] = {}
        self.tracker = TrackerThread()
        self.tracker.start()
        
    def is_valid_exchange_symbol(self, symbol: str) -> bool:
        exchange, symbol = symbol.split(":")
        if not exchange or not symbol:
            return False
        
        with open(ASSETS_PATH, encoding='utf-8') as file:
            assets: dict = json.load(file)

        if not symbol in assets:
            return False
        
        if not exchange in assets[symbol]:
            return False
        
        return True
    
    def get_exchange_symbol(self) -> str:
        text = self.ui.lineEdit.text().strip()
        parts = text.split(':')
        
        return f'{parts[-1]}:{parts[0]}'
    
    def update_watched_files(self, path: str):
        with open(path, encoding='utf-8') as file:
            assets: dict = json.load(file)

        self.symbols_model.clear()
        
        for k, v in assets.items():
            for exchange in v:
                self.symbols_model.appendRow(QStandardItem(f'{k}:{exchange}'))

    def remove_button_clicked(self):
        row = self.ui.tableWidget.currentRow()

        symbol = self.ui.tableWidget.item(row, 0).text()
        
        timeframes = self.ui.tableWidget.item(row, 1).text()
        timeframes = timeframes.split(',')
        
        for timeframe in timeframes:
            timeframe = timeframe.strip()
            identify = f'{symbol}_{timeframe}'

            session = self.sessions[identify]
            session.close()
            
            self.sessions.pop(identify)
            
        self.ui.tableWidget.removeRow(row)
        
    def closeEvent(self, _: QCloseEvent):
        for _, session in self.sessions.items():
            session.close()
            
    def pushButton_clicked(self):
        symbol = self.get_exchange_symbol()
        if not self.is_valid_exchange_symbol(symbol):
            return
        
        items: list[QTableWidgetItem] = self.ui.tableWidget.findItems(symbol, Qt.MatchExactly)
        if items:
            return
        
        timeframes = self.ui.comboBox.currentData()
        if not timeframes:
            return
        
        button = QPushButton('Remove')
        button.setStyleSheet('border-radius: none; margin: 1px;')
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.remove_button_clicked)
        
        row = self.ui.tableWidget.rowCount()
        self.ui.tableWidget.insertRow(row)
        self.ui.tableWidget.setItem(row, 0, QTableWidgetItem(symbol))
        self.ui.tableWidget.setItem(row, 1, QTableWidgetItem(self.ui.comboBox.currentText()))
        self.ui.tableWidget.setCellWidget(row, 2, button)
        
        for timeframe in timeframes:
            session = TradingViewWs(symbol, utils.TIMEFRAME_MAPPING[timeframe])
            
            self.sessions.update({f'{symbol}_{timeframe}': session})
            self.tracker.sessions.put_nowait(session)
            
            QThread.msleep(30)
            
class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(601, 459)
        MainWindow.setMinimumSize(QSize(601, 459))
        MainWindow.setStyleSheet(u"font: 10pt \"Segoe UI\";")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(9, 9, 9, 9)
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame)
        self.verticalLayout.setSpacing(10)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame_2 = QFrame(self.frame)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setMaximumSize(QSize(16777215, 40))
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_2.setSpacing(5)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.lineEdit = QLineEdit(self.frame_2)
        self.lineEdit.setObjectName(u"lineEdit")
        self.lineEdit.setMinimumSize(QSize(0, 31))
        self.lineEdit.setMaximumSize(QSize(16777215, 31))

        self.horizontalLayout_2.addWidget(self.lineEdit)

        self.comboBox = CheckableComboBox(self.frame_2)
        self.comboBox.setObjectName(u"comboBox")
        self.comboBox.setMinimumSize(QSize(150, 31))
        self.comboBox.setMaximumSize(QSize(150, 31))
        self.comboBox.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_2.addWidget(self.comboBox)

        self.pushButton = QPushButton(self.frame_2)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMinimumSize(QSize(100, 31))
        self.pushButton.setMaximumSize(QSize(100, 31))
        self.pushButton.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_2.addWidget(self.pushButton)


        self.verticalLayout.addWidget(self.frame_2)

        self.frame_3 = QFrame(self.frame)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.tableWidget = QTableWidget(self.frame_3)
        if (self.tableWidget.columnCount() < 3):
            self.tableWidget.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.tableWidget.setObjectName(u"tableWidget")
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableWidget.horizontalHeader().setDefaultSectionSize(130)
        self.tableWidget.horizontalHeader().setStretchLastSection(True)

        self.horizontalLayout_4.addWidget(self.tableWidget)


        self.verticalLayout.addWidget(self.frame_3)


        self.horizontalLayout.addWidget(self.frame)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"PD ALERTS", None))
        self.lineEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Symbol", None))
        
        self.comboBox.addItems(['15m', '30m', '1h', '4h'])
        self.comboBox.setCurrentText('15m')
        
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u"Add", None))
        ___qtablewidgetitem = self.tableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"Symbol", None));
        ___qtablewidgetitem1 = self.tableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Timeframes", None));
    # retranslateUi
