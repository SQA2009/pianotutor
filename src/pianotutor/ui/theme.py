"""UI color tokens and base stylesheet."""

BACKGROUND = "#16171D"
SURFACE = "#1F2230"
SURFACE_ALT = "#2A2E3F"
BORDER = "#3A3F54"
EBONY = "#11131A"
IVORY = "#F7F4EA"
IVORY_MUTED = "#B3BACE"
BRASS = "#D4AF37"
BRASS_DARK = "#B38F1B"
CORRECT_GREEN = "#39B36D"
LATE_AMBER = "#E3A53F"
EARLY_BLUE = "#4DA3FF"
MISS_RED = "#D85B68"
UNCERTAIN_GREY = "#8F95A3"

APP_STYLESHEET = f"""
QWidget {{
  background: {BACKGROUND};
  color: {IVORY};
  font-size: 13px;
}}
QMainWindow {{
  background: {BACKGROUND};
}}
QLabel[role="heading"] {{
  font-size: 24px;
  font-weight: 700;
  color: #FFFFFF;
}}
QLabel[role="subheading"] {{
  color: {IVORY_MUTED};
}}
QLabel[role="hint"] {{
  color: {IVORY_MUTED};
  font-size: 12px;
}}
QPushButton {{
  background: {SURFACE_ALT};
  border: 1px solid {BORDER};
  border-radius: 8px;
  padding: 7px 12px;
}}
QPushButton:hover {{
  background: #353B50;
}}
QPushButton:pressed {{
  background: #2B3044;
}}
QPushButton:disabled {{
  color: #7A8092;
  border-color: #2C3142;
  background: #232634;
}}
QPushButton[role="primary"] {{
  background: {BRASS};
  color: {EBONY};
  font-weight: 700;
  border: 1px solid {BRASS_DARK};
}}
QPushButton[role="primary"]:hover {{
  background: #E1C15B;
}}
QPushButton[role="primary"]:pressed {{
  background: #C9A22D;
}}
QComboBox, QListWidget, QTableWidget {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 8px;
  padding: 6px;
}}
QComboBox::drop-down {{
  border: none;
  width: 20px;
}}
QTabWidget::pane {{
  border: 1px solid {BORDER};
  border-radius: 8px;
  top: -1px;
}}
QTabBar::tab {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  padding: 8px 14px;
  margin-right: 4px;
}}
QTabBar::tab:selected {{
  background: {SURFACE_ALT};
  color: #FFFFFF;
}}
QProgressBar {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 6px;
  text-align: center;
  min-height: 16px;
}}
QProgressBar::chunk {{
  background-color: {BRASS};
  border-radius: 5px;
}}
QHeaderView::section {{
  background: {SURFACE_ALT};
  color: {IVORY};
  border: 0;
  border-right: 1px solid {BORDER};
  border-bottom: 1px solid {BORDER};
  padding: 6px;
}}
"""
