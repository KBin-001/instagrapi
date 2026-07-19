"""应用服务层。

CLI 与未来的 GUI 共用同一套搜索、导出、任务管理逻辑。
所有耗时任务通过 SearchService 等服务类执行，展示层只接收结构化进度回调。
"""

from app.services.search_service import SearchService

__all__ = ["SearchService"]
