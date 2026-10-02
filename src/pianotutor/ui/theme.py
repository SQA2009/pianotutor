"""UI color tokens and base stylesheet."""

EBONY = "#1C1B1F"
IVORY = "#F7F4EA"
IVORY_MUTED = "#D7D2C3"
BRASS = "#C9A227"
CORRECT_GREEN = "#39B36D"
LATE_AMBER = "#E3A53F"
EARLY_BLUE = "#4DA3FF"
MISS_RED = "#D85B68"
UNCERTAIN_GREY = "#8F95A3"

APP_STYLESHEET = f"""
QWidget {{
  background: {EBONY};
  color: {IVORY};
  font-size: 13px;
}}
QLabel[role="heading"] {{
  font-size: 20px;
  font-weight: 700;
}}
QLabel[role="subheading"] {{
  color: {IVORY_MUTED};
}}
QPushButton[role="primary"] {{
  background: {BRASS};
  color: {EBONY};
  font-weight: 700;
  border-radius: 6px;
  padding: 6px 10px;
}}
QProgressBar {{
  border: 1px solid {IVORY_MUTED};
  border-radius: 4px;
  text-align: center;
}}
QProgressBar::chunk {{
  background-color: {BRASS};
}}
"""
