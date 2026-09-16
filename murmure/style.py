from string import Template

from PySide6.QtGui import QColor, QPalette

COLORS = {
    "light": dict(
        bg="#f5f6f2",
        panel="#ffffff",
        sidebar="#e9ede6",
        text="#24352b",
        muted="#536355",
        border="#c7d1c2",
        hero="#e2eadf",
        accent="#365d48",
        accent_text="#ffffff",
        hover="#e7efe1",
        selected="#d8e6ce",
        selected_text="#20351e",
        focus="#597d4d",
        disabled="#e5e9e1",
        disabled_text="#5b6657",
        danger="#973723",
        banner="#fff0dd",
        banner_text="#734511",
        bar="#a7b69e",
        tooltip="#293b30",
        tooltip_text="#ffffff",
    ),
    "dark": dict(
        bg="#171d1a",
        panel="#222c25",
        sidebar="#1c251f",
        text="#edf3e9",
        muted="#b3c1b0",
        border="#4d604f",
        hero="#2b3b2e",
        accent="#abd497",
        accent_text="#172911",
        hover="#344733",
        selected="#3e5737",
        selected_text="#f0ffe6",
        focus="#b1dc96",
        disabled="#303b31",
        disabled_text="#a1afa0",
        danger="#ffb09a",
        banner="#453923",
        banner_text="#ffe2ab",
        bar="#667c60",
        tooltip="#e3eedb",
        tooltip_text="#1c2b17",
    ),
}

SHEET = Template("""
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: $text; }
QMainWindow, QWidget#page { background: $bg; }
QWidget#sidebar { background: $sidebar; border-right: 1px solid $border; }
QLabel#brand { font-size: 26px; font-weight: 700; letter-spacing: -1px; }
QLabel#eyebrow { font-size: 11px; font-weight: 700; color: $muted; letter-spacing: 2px; }
QLabel#title { font-size: 30px; font-weight: 600; letter-spacing: -1px; }
QLabel#subtitle { color: $muted; font-size: 13px; }
QLabel#section { font-size: 17px; font-weight: 600; }
QFrame#card { background: $panel; border: 1px solid $border; border-radius: 16px; }
QFrame#hero { background: $hero; border: 1px solid $border; border-radius: 20px; }
QLabel#heroTitle { font-size: 25px; font-weight: 600; }
QLabel#status { font-weight: 600; color: $text; }
QLabel#banner { background: $banner; color: $banner_text; border-radius: 8px; padding: 12px; }
QPushButton { background: $panel; color: $text; border: 1px solid $border; border-radius: 8px;
 padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: $hover; border-color: $focus; }
QPushButton:pressed { background: $selected; }
QPushButton:disabled { color: $disabled_text; background: $disabled; border-color: $border; }
QPushButton#primary { background: $accent; color: $accent_text; border-color: $accent; }
QPushButton#primary:hover { background: $accent; border-color: $focus; }
QPushButton#primary:disabled { background: $disabled; color: $disabled_text; border-color: $border; }
QPushButton#danger { color: $danger; }
QPushButton#danger:disabled { color: $disabled_text; }
QPushButton#nav { background: transparent; text-align: left; border: none; padding: 12px 18px; }
QPushButton#nav:checked { background: $selected; color: $selected_text; }
QPushButton#nav:hover { background: $hover; }
QLineEdit, QComboBox, QPlainTextEdit { background: $panel; color: $text; border: 1px solid $border;
 border-radius: 7px; padding: 8px; selection-background-color: $selected; selection-color: $selected_text; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: $focus; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: $panel; color: $text;
 selection-background-color: $selected; selection-color: $selected_text; }
QListWidget { background: transparent; border: none; outline: none;
 selection-background-color: $selected; selection-color: $selected_text; }
QListWidget::item { background: $panel; color: $text; border: 1px solid $border; border-radius: 10px;
 padding: 13px; margin-bottom: 8px; }
QListWidget::item:selected, QListWidget::item:selected:!active {
 background: $selected; color: $selected_text; border-color: $focus; }
QListWidget::item:hover { border-color: $focus; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: $bar; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QCheckBox { spacing: 10px; padding: 5px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { border: 1px solid $border; background: $panel; border-radius: 3px; }
QProgressBar { border: none; border-radius: 3px; background: $border; max-height: 5px; }
QProgressBar::chunk { background: $accent; }
QMenu, QMessageBox { background: $panel; color: $text; }
QMenu { border: 1px solid $border; padding: 5px; }
QMenu::item { padding: 9px 26px; border-radius: 5px; }
QMenu::item:selected { background: $selected; color: $selected_text; }
QToolTip { background: $tooltip; color: $tooltip_text; border: none; padding: 7px; }
""")


def apply_theme(app, theme: str):
    colors = COLORS.get(theme, COLORS["light"])
    palette = QPalette()
    for role, name in (
        (QPalette.ColorRole.Window, "bg"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "panel"),
        (QPalette.ColorRole.AlternateBase, "hero"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.Button, "panel"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.Highlight, "selected"),
        (QPalette.ColorRole.HighlightedText, "selected_text"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
        (QPalette.ColorRole.ToolTipBase, "tooltip"),
        (QPalette.ColorRole.ToolTipText, "tooltip_text"),
    ):
        palette.setColor(role, QColor(colors[name]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled_text"]))
    app.setPalette(palette)
    app.setStyleSheet(SHEET.substitute(colors))
