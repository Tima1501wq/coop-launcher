import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui import SplashScreen

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    splash = SplashScreen()
    splash.show()
    sys.exit(app.exec())
