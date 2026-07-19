"""NiceGUI 界面包。

启动方式：
    python gui_main.py

复用 SearchService 与 CLI 共享的 SQLite 数据库。
"""

from app.gui.state import gui_state

__all__ = ["gui_state"]
