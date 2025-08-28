"""
RFS Dashboard System (RFS v4.1)

대시보드 및 위젯 시스템
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)


class WidgetType(Enum):
    """위젯 타입"""

    CHART = "chart"
    METRIC = "metric"
    TABLE = "table"
    TEXT = "text"
    IMAGE = "image"
    MAP = "map"
    GAUGE = "gauge"
    PROGRESS = "progress"


class DashboardLayout(Enum):
    """대시보드 레이아웃"""

    GRID = "grid"
    FLEX = "flex"
    FIXED = "fixed"
    RESPONSIVE = "responsive"


@dataclass
class WidgetPosition:
    """위젯 위치"""

    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class WidgetStyle:
    """위젯 스타일"""

    background_color = None
    border_color = None
    border_width = None
    border_radius = None
    padding = None
    margin = None
    font_size = None
    font_color = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v
            for k, v in {
                "backgroundColor": self.background_color,
                "borderColor": self.border_color,
                "borderWidth": self.border_width,
                "borderRadius": self.border_radius,
                "padding": self.padding,
                "margin": self.margin,
                "fontSize": self.font_size,
                "color": self.font_color,
            }.items()
            if v is not None
        }


class Widget(ABC):
    """위젯 기본 클래스"""

    def __init__(
        self,
        widget_id: str,
        title: str,
        widget_type: WidgetType,
        position: WidgetPosition,
        style=None,
    ):
        self.widget_id = widget_id
        self.title = title
        self.widget_type = widget_type
        self.position = position
        self.style = style or WidgetStyle()
        self.config = {}
        self.data_source = None
        self.refresh_interval = None
        self.last_updated = None

    @abstractmethod
    async def render(self) -> Result[Dict[str, Any], str]:
        """위젯 렌더링

        Returns:
            Result[Dict[str, Any], str]: 렌더링된 위젯 데이터 또는 오류
        """
        raise NotImplementedError("Subclasses must implement render method")

    async def update_data(self) -> Result[None, str]:
        """데이터 업데이트"""
        if self.data_source:
            try:
                data_result = await self.data_source.fetch_data()
                if data_result.is_success():
                    self.last_updated = datetime.now()
                    return Success(None)
                else:
                    return data_result
            except Exception as e:
                return Failure(f"데이터 업데이트 실패: {str(e)}")
        return Success(None)

    def set_refresh_interval(self, seconds: int) -> None:
        """자동 새로고침 간격 설정"""
        self.refresh_interval = seconds

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.widget_id,
            "title": self.title,
            "type": self.widget_type.value,
            "position": self.position.to_dict(),
            "style": self.style.to_dict(),
            "config": self.config,
            "refreshInterval": self.refresh_interval,
            "lastUpdated": self.last_updated.isoformat() if self.last_updated else None,
        }


class ChartWidget(Widget):
    """차트 위젯"""

    def __init__(
        self,
        widget_id: str,
        title: str,
        position: WidgetPosition,
        chart_type="line",
        **config,
    ):
        super().__init__(widget_id, title, WidgetType.CHART, position)
        self.chart_type = chart_type
        self.config = {**config, **config}

    async def render(self) -> Result[Dict[str, Any], str]:
        """차트 렌더링"""
        try:
            widget_data = self.to_dict()
            widget_data = {
                **widget_data,
                "config": {**widget_data["config"], "chartType": self.chart_type},
            }
            if self.data_source:
                data_result = await self.data_source.fetch_data()
                if data_result.is_success():
                    widget_data = {
                        **widget_data,
                        "data": {"data": data_result.unwrap()},
                    }
                else:
                    widget_data["data"] = {"data": []}
                    widget_data = {
                        **widget_data,
                        "error": {"error": data_result.unwrap_err()},
                    }
            else:
                widget_data["data"] = {"data": []}
            return Success(widget_data)
        except Exception as e:
            return Failure(f"차트 위젯 렌더링 실패: {str(e)}")


class MetricWidget(Widget):
    """메트릭 위젯"""

    def __init__(
        self,
        widget_id: str,
        title: str,
        position: WidgetPosition,
        metric_type="number",
        format_string="{value}",
        **config,
    ):
        super().__init__(widget_id, title, WidgetType.METRIC, position)
        self.metric_type = metric_type
        self.format_string = format_string
        self.config = {**config, **config}

    async def render(self) -> Result[Dict[str, Any], str]:
        """메트릭 렌더링"""
        try:
            widget_data = self.to_dict()
            widget_data = {
                **widget_data,
                "config": {**widget_data["config"], "metricType": self.metric_type},
            }
            widget_data = {
                **widget_data,
                "config": {**widget_data["config"], "format": self.format_string},
            }
            if self.data_source:
                data_result = await self.data_source.fetch_data()
                if data_result.is_success():
                    raw_data = data_result.unwrap()
                    if type(raw_data).__name__ == "list" and len(raw_data) > 0:
                        widget_data = {
                            **widget_data,
                            "value": {
                                "value": (
                                    raw_data[0].get("value", 0)
                                    if hasattr(raw_data[0], "__class__")
                                    and raw_data[0].__class__.__name__ == "dict"
                                    else raw_data[0]
                                )
                            },
                        }
                    elif type(raw_data).__name__ == "dict":
                        widget_data = {
                            **widget_data,
                            "value": {"value": raw_data.get("value", 0)},
                        }
                    else:
                        widget_data["value"] = raw_data
                else:
                    widget_data["value"] = 0
                    widget_data = {
                        **widget_data,
                        "error": {"error": data_result.unwrap_err()},
                    }
            else:
                widget_data["value"] = 0
            return Success(widget_data)
        except Exception as e:
            return Failure(f"메트릭 위젯 렌더링 실패: {str(e)}")


class TableWidget(Widget):
    """테이블 위젯"""

    def __init__(
        self,
        widget_id: str,
        title: str,
        position: WidgetPosition,
        columns=None,
        **config,
    ):
        super().__init__(widget_id, title, WidgetType.TABLE, position)
        self.columns = columns or []
        self.config = {**config, **config}

    async def render(self) -> Result[Dict[str, Any], str]:
        """테이블 렌더링"""
        try:
            widget_data = self.to_dict()
            widget_data = {
                **widget_data,
                "config": {**widget_data["config"], "columns": self.columns},
            }
            if self.data_source:
                data_result = await self.data_source.fetch_data()
                if data_result.is_success():
                    widget_data = {
                        **widget_data,
                        "rows": {"rows": data_result.unwrap()},
                    }
                else:
                    widget_data["rows"] = {"rows": []}
                    widget_data = {
                        **widget_data,
                        "error": {"error": data_result.unwrap_err()},
                    }
            else:
                widget_data["rows"] = {"rows": []}
            return Success(widget_data)
        except Exception as e:
            return Failure(f"테이블 위젯 렌더링 실패: {str(e)}")


class TextWidget(Widget):
    """텍스트 위젯"""

    def __init__(
        self,
        widget_id: str,
        title: str,
        position: WidgetPosition,
        content="",
        markdown=False,
        **config,
    ):
        super().__init__(widget_id, title, WidgetType.TEXT, position)
        self.content = content
        self.markdown = markdown
        self.config = {**config, **config}

    async def render(self) -> Result[Dict[str, Any], str]:
        """텍스트 렌더링"""
        try:
            widget_data = self.to_dict()
            widget_data = {
                **widget_data,
                "config": {**widget_data["config"], "markdown": self.markdown},
            }
            widget_data["content"] = self.content
            return Success(widget_data)
        except Exception as e:
            return Failure(f"텍스트 위젯 렌더링 실패: {str(e)}")


@dataclass
class DashboardConfig:
    """대시보드 설정"""

    layout: DashboardLayout = DashboardLayout.GRID
    grid_columns = 12
    grid_row_height = 100
    auto_refresh = False
    refresh_interval = 30
    theme = "default"
    background_color = "#ffffff"


class Dashboard:
    """대시보드"""

    def __init__(
        self,
        dashboard_id: str,
        title: str,
        description="",
        config=None,
    ):
        self.dashboard_id = dashboard_id
        self.title = title
        self.description = description
        self.config = config or DashboardConfig()
        self.widgets = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.tags = []
        self.is_public = False
        self._refresh_tasks = {}

    def add_widget(self, widget: Widget) -> "Dashboard":
        """위젯 추가"""
        self.widgets = {**self.widgets, widget.widget_id: widget}
        self.updated_at = datetime.now()
        if widget.refresh_interval:
            self._schedule_widget_refresh(widget)
        return self

    def remove_widget(self, widget_id: str) -> bool:
        """위젯 제거"""
        if widget_id in self.widgets:
            if widget_id in self._refresh_tasks:
                self._refresh_tasks[widget_id].cancel()
                del self._refresh_tasks[widget_id]
            del self.widgets[widget_id]
            self.updated_at = datetime.now()
            return True
        return False

    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """위젯 조회"""
        return self.widgets.get(widget_id)

    def set_tags(self, tags: List[str]) -> "Dashboard":
        """태그 설정"""
        self.tags = tags
        return self

    def set_public(self, is_public: bool) -> "Dashboard":
        """공개 여부 설정"""
        self.is_public = is_public
        return self

    def _schedule_widget_refresh(self, widget: Widget):
        """위젯 자동 새로고침 스케줄링"""

        async def refresh_widget():
            while True:
                try:
                    await asyncio.sleep(widget.refresh_interval)
                    await widget.update_data()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    await logger.log_error(
                        f"위젯 새로고침 실패 {widget.widget_id}: {str(e)}"
                    )

        task = asyncio.create_task(refresh_widget())
        self._refresh_tasks = {**self._refresh_tasks, widget.widget_id: task}

    async def render(self) -> Result[Dict[str, Any], str]:
        """대시보드 렌더링"""
        try:
            rendered_widgets = {}
            for widget_id, widget in self.widgets.items():
                widget_result = await widget.render()
                if widget_result.is_success():
                    rendered_widgets = {
                        **rendered_widgets,
                        widget_id: {widget_id: widget_result.unwrap()},
                    }
                else:
                    rendered_widgets = {
                        **rendered_widgets,
                        widget_id: {
                            widget_id: {
                                "id": widget_id,
                                "error": widget_result.unwrap_err(),
                            }
                        },
                    }
            dashboard_data = {
                "id": self.dashboard_id,
                "title": self.title,
                "description": self.description,
                "config": {
                    "layout": self.config.layout.value,
                    "gridColumns": self.config.grid_columns,
                    "gridRowHeight": self.config.grid_row_height,
                    "autoRefresh": self.config.auto_refresh,
                    "refreshInterval": self.config.refresh_interval,
                    "theme": self.config.theme,
                    "backgroundColor": self.config.background_color,
                },
                "widgets": rendered_widgets,
                "createdAt": self.created_at.isoformat(),
                "updatedAt": self.updated_at.isoformat(),
                "tags": self.tags,
                "isPublic": self.is_public,
            }
            return Success(dashboard_data)
        except Exception as e:
            return Failure(f"대시보드 렌더링 실패: {str(e)}")

    def cleanup(self) -> None:
        """대시보드 정리 (새로고침 태스크 취소)"""
        for task in self._refresh_tasks.values():
            task.cancel()
        self._refresh_tasks = {}


class DashboardBuilder:
    """대시보드 빌더"""

    def __init__(self, dashboard_id: str, title: str) -> None:
        self.dashboard = Dashboard(dashboard_id, title)

    def description(self, description: str) -> "DashboardBuilder":
        """설명 설정"""
        self.dashboard.description = description
        return self

    def layout(self, layout: DashboardLayout) -> "DashboardBuilder":
        """레이아웃 설정"""
        self.dashboard.config.layout = layout
        return self

    def grid_config(self, columns=12, row_height=100) -> "DashboardBuilder":
        """그리드 설정"""
        self.dashboard.config.grid_columns = columns
        self.dashboard.config.grid_row_height = row_height
        return self

    def auto_refresh(self, enabled=True, interval=30) -> "DashboardBuilder":
        """자동 새로고침 설정"""
        self.dashboard.config.auto_refresh = enabled
        self.dashboard.config.refresh_interval = interval
        return self

    def theme(self, theme: str, background_color="#ffffff") -> "DashboardBuilder":
        """테마 설정"""
        self.dashboard.config.theme = theme
        self.dashboard.config.background_color = background_color
        return self

    def add_chart(
        self,
        widget_id: str,
        title: str,
        x: int,
        y: int,
        width: int,
        height: int,
        chart_type="line",
        **config,
    ) -> "DashboardBuilder":
        """차트 위젯 추가"""
        position = WidgetPosition(x, y, width, height)
        widget = ChartWidget(widget_id, title, position, chart_type, **config)
        self.dashboard.add_widget(widget)
        return self

    def add_metric(
        self,
        widget_id: str,
        title: str,
        x: int,
        y: int,
        width: int,
        height: int,
        metric_type="number",
        format_string="{value}",
        **config,
    ) -> "DashboardBuilder":
        """메트릭 위젯 추가"""
        position = WidgetPosition(x, y, width, height)
        widget = MetricWidget(
            widget_id, title, position, metric_type, format_string, **config
        )
        self.dashboard.add_widget(widget)
        return self

    def add_table(
        self,
        widget_id: str,
        title: str,
        x: int,
        y: int,
        width: int,
        height: int,
        columns=None,
        **config,
    ) -> "DashboardBuilder":
        """테이블 위젯 추가"""
        position = WidgetPosition(x, y, width, height)
        widget = TableWidget(widget_id, title, position, columns, **config)
        self.dashboard.add_widget(widget)
        return self

    def add_text(
        self,
        widget_id: str,
        title: str,
        x: int,
        y: int,
        width: int,
        height: int,
        content="",
        markdown=False,
        **config,
    ) -> "DashboardBuilder":
        """텍스트 위젯 추가"""
        position = WidgetPosition(x, y, width, height)
        widget = TextWidget(widget_id, title, position, content, markdown, **config)
        self.dashboard.add_widget(widget)
        return self

    def tags(self, *tags: str) -> "DashboardBuilder":
        """태그 설정"""
        self.dashboard.set_tags(list(tags))
        return self

    def public(self, is_public=True) -> "DashboardBuilder":
        """공개 설정"""
        self.dashboard.set_public(is_public)
        return self

    def build(self) -> Dashboard:
        """대시보드 빌드"""
        return self.dashboard


class DashboardManager:
    """대시보드 관리자"""

    def __init__(self) -> None:
        self.dashboards = {}

    def create_dashboard(
        self,
        dashboard_id: str,
        title: str,
        description="",
        config=None,
    ) -> Dashboard:
        """대시보드 생성"""
        dashboard = Dashboard(dashboard_id, title, description, config)
        self.dashboards = {**self.dashboards, dashboard_id: dashboard}
        return dashboard

    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """대시보드 조회"""
        return self.dashboards.get(dashboard_id)

    def list_dashboards(self, tags=None, public_only=False) -> List[Dashboard]:
        """대시보드 목록"""
        dashboards = list(self.dashboards.values())
        if public_only:
            dashboards = [d for d in dashboards if d.is_public]
        if tags:
            dashboards = [d for d in dashboards if any((tag in d.tags for tag in tags))]
        return dashboards

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """대시보드 삭제"""
        if dashboard_id in self.dashboards:
            dashboard = self.dashboards[dashboard_id]
            dashboard.cleanup()
            del self.dashboards[dashboard_id]
            return True
        return False

    async def export_dashboard(self, dashboard_id: str) -> Result[Dict[str, Any], str]:
        """대시보드 내보내기"""
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return Failure(f"대시보드를 찾을 수 없음: {dashboard_id}")
        return await dashboard.render()


_dashboard_manager = None


def get_dashboard_manager() -> DashboardManager:
    """대시보드 관리자 가져오기"""
    if _dashboard_manager is None:
        _dashboard_manager = DashboardManager()
    return _dashboard_manager


def create_dashboard(dashboard_id: str, title: str) -> DashboardBuilder:
    """대시보드 빌더 생성"""
    return DashboardBuilder(dashboard_id, title)
