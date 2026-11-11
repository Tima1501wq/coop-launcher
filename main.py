import sys
from PyQt6.QtWidgets import QApplication
from ui import LauncherWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Coop Launcher")
    win = LauncherWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
