from PyQt5 import QtWidgets, QtCore, QtGui
from EventBus import EventBus
from Wolke import Wolke
import os.path
from roll20export import roll20Exporter
import logging
import traceback
import Version

def doRoll20Export():
    result = -1

    if os.path.isdir(Wolke.Settings['Pfad-Chars']):
        startDir = Wolke.Settings['Pfad-Chars']
    else:
        startDir = ""
        
    # Let the user choose a saving location and name
    saveFileDialog = QtWidgets.QFileDialog(None, "Roll20-Charakterbogen aktualisieren...", startDir, "JSON-Datei (*.json)")
    spath = ""
    if saveFileDialog.exec_():
        spath = saveFileDialog.selectedFiles()[0]
    if spath == "":
        return
        
    try:
        exporter = roll20Exporter.roll20Exporter()
        infoBox = QtWidgets.QMessageBox()
        infoBox.setIcon(QtWidgets.QMessageBox.Information)
        infoBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        infoBox.setEscapeButton(QtWidgets.QMessageBox.Close)  
        if exporter.exportCharacter(spath):
            infoBox.setText("JSON-Aktualisierung erfolgreich!")
        else:
            infoBox.setText("JSON-File ungültig!")
        infoBox.exec_()
    except Exception as e:
        logging.error("Sephrasto Fehlercode " + str(Wolke.Fehlercode) + ". Exception: " + str(e))
        infoBox = QtWidgets.QMessageBox()
        infoBox.setIcon(QtWidgets.QMessageBox.Information)
        infoBox.setText("JSON-Aktualisierung fehlgeschlagen!")
        infoBox.setInformativeText("Beim Aktualisieren des Charakterbogens ist ein Fehler aufgetreten.\n\
Fehlercode: " + str(Wolke.Fehlercode) + "\n\
Fehlermeldung: " + Wolke.ErrorCode[Wolke.Fehlercode] + "\n\
Exception: " + traceback.format_exc())
        infoBox.setWindowTitle("JSON-Aktualisierung fehlgeschlagen.")
        infoBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        infoBox.setEscapeButton(QtWidgets.QMessageBox.Close)  
        infoBox.exec_()


class Plugin:
    def __init__(self):
        if Version._sephrasto_version_major < 2 and Version._sephrasto_version_minor < 4:
            EventBus.addFilter("class_beschreibung_wrapper", self.provideBeschrWrapper)

    def createCharakterButtons(self):
        self.roll20ExportButton = QtWidgets.QPushButton()
        self.roll20ExportButton.setObjectName("roll20ExportButton")
        self.roll20ExportButton.setText("Roll20 Export")
        self.roll20ExportButton.clicked.connect(doRoll20Export)
        return [self.roll20ExportButton]


    def provideBeschrWrapper(self, base, params):
        class Roll20ExportBeschrWrapper(base):
            def __init__(self):
                super().__init__()
                self.roll20ExportButton = QtWidgets.QPushButton(self.formBeschr)
                self.roll20ExportButton.setMinimumSize(QtCore.QSize(100, 0))
                self.roll20ExportButton.setMaximumSize(QtCore.QSize(16777214, 16777215))
                self.roll20ExportButton.setObjectName("roll20ExportButton")
                self.roll20ExportButton.setText("Roll20 Export")
                self.roll20ExportButton.clicked.connect(doRoll20Export)
                self.uiBeschr.gridLayout.addWidget(self.roll20ExportButton)

        return Roll20ExportBeschrWrapper
   
