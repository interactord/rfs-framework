"""
RFS Chart System (RFS v4.1)

차트 및 데이터 시각화 시스템
"""

import json
import math
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)


class ChartType(Enum):
    """차트 타입"""

    LINE = "line"
    BAR = "bar"
    COLUMN = "column"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    SCATTER = "scatter"
    AREA = "area"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    FUNNEL = "funnel"
    WATERFALL = "waterfall"


@dataclass
class ChartData:
    """차트 데이터"""

    labels: List[str] = field(default_factory=list)
    datasets: List[Dict[str, Any]] = field(default_factory=list)

    def add_dataset(
        self,
        label: str,
        data: List[Union[int, float]],
        color=None,
        **options,
    ) -> "ChartData":
        """데이터셋 추가"""
        dataset = {"label": label, "data": data, **options}
        if color:
            dataset["backgroundColor"] = {"backgroundColor": color}
            dataset["borderColor"] = {"borderColor": color}
        self.datasets = self.datasets + [dataset]
        return self

    def set_labels(self, labels: List[str]) -> "ChartData":
        """라벨 설정"""
        self.labels = labels
        return self

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {"labels": self.labels, "datasets": self.datasets}


@dataclass
class ChartOptions:
    """차트 옵션"""

    title = None
    width = 800
    height = 400
    responsive = True
    legend = True
    grid = True
    tooltip = True
    animation = True
    color_scheme: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        options = {
            "responsive": self.responsive,
            "plugins": {
                "legend": {"display": self.legend},
                "tooltip": {"enabled": self.tooltip},
            },
            "scales": {
                "x": {"grid": {"display": self.grid}},
                "y": {"grid": {"display": self.grid}},
            },
            "animation": {"duration": 1000 if self.animation else 0},
        }
        if self.title:
            options = {
                **options,
                "plugins": {
                    **options["plugins"],
                    "title": {"display": True, "text": self.title},
                },
            }
        return options


class Chart(ABC):
    """차트 기본 클래스"""

    def __init__(
        self,
        chart_id: str,
        chart_type: ChartType,
        title="",
        options=None,
    ):
        self.chart_id = chart_id
        self.chart_type = chart_type
        self.title = title
        self.options = options or ChartOptions(title=title)
        self.data = ChartData()

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """원시 데이터를 차트 데이터로 변환

        Args:
            raw_data: 원시 데이터 리스트

        Returns:
            Result[ChartData, str]: 변환된 차트 데이터 또는 오류
        """
        try:
            if not raw_data:
                return Success(ChartData(labels=[], datasets=[]))

            # 기본 데이터 변환 로직
            labels = []
            values = []

            for item in raw_data:
                if isinstance(item, dict):
                    # 딕셔너리 형태의 데이터
                    keys = list(item.keys())
                    if len(keys) >= 2:
                        # 첫 번째 키를 레이블로, 두 번째 키를 값으로 사용
                        labels.append(str(item[keys[0]]))
                        try:
                            values.append(float(item[keys[1]]))
                        except (ValueError, TypeError):
                            values.append(0)
                    elif len(keys) == 1:
                        # 하나의 키만 있는 경우
                        labels.append(str(keys[0]))
                        try:
                            values.append(float(item[keys[0]]))
                        except (ValueError, TypeError):
                            values.append(0)
                else:
                    # 비-딕셔너리 형태의 데이터
                    labels.append(str(len(labels)))
                    try:
                        values.append(float(item))
                    except (ValueError, TypeError):
                        values.append(0)

            # 기본 데이터셋 생성
            dataset = {
                "label": "Data",
                "data": values,
                "backgroundColor": self._get_default_colors()[: len(values)],
                "borderColor": self._get_default_colors()[: len(values)],
                "borderWidth": 1,
            }

            return Success(ChartData(labels=labels, datasets=[dataset]))
        except Exception as e:
            return Failure(f"Failed to prepare chart data: {str(e)}")

    def _get_default_colors(self) -> List[str]:
        """기본 색상 팔레트 반환"""
        return [
            "#007bff",
            "#28a745",
            "#dc3545",
            "#ffc107",
            "#6f42c1",
            "#20c997",
            "#fd7e14",
            "#e83e8c",
            "#6c757d",
            "#17a2b8",
        ]

    def set_data(self, raw_data: List[Dict[str, Any]]) -> Result["Chart", str]:
        """데이터 설정"""
        result = self.prepare_data(raw_data)
        if result.is_success():
            self.data = result.unwrap()
            return Success(self)
        return result

    def set_options(self, **options) -> "Chart":
        """옵션 설정"""
        for key, value in options.items():
            if hasattr(self.options, key):
                setattr(self.options, key, value)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.chart_id,
            "type": self.chart_type.value,
            "data": self.data.to_dict(),
            "options": self.options.to_dict(),
        }

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class LineChart(Chart):
    """라인 차트"""

    def __init__(self, chart_id: str, title: str = "", options: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(chart_id, ChartType.LINE, title, options)

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """라인 차트 데이터 준비"""
        try:
            if not raw_data:
                return Success(ChartData())
            x_key = "x"
            y_key = "y"
            first_item = raw_data[0]
            possible_x_keys = ["date", "time", "timestamp", "x", "label", "name"]
            possible_y_keys = ["value", "count", "amount", "y", "data"]
            for key in possible_x_keys:
                if key in first_item:
                    x_key = key
                    break
            for key in possible_y_keys:
                if key in first_item:
                    y_key = key
                    break
            series_data = {}
            labels: Set[Any] = set()
            for item in raw_data:
                x_val = str(item.get(x_key, ""))
                y_val = item.get(y_key, 0)
                series = item.get("series", "데이터")
                if series not in series_data:
                    series_data[series] = {series: {}}
                series_data = {
                    **series_data,
                    series: {**series_data[series], x_val: y_val},
                }
                labels.add(x_val)
            sorted_labels = sorted(list(labels))
            chart_data = ChartData(labels=sorted_labels)
            for series_name, data_points in series_data.items():
                values = [data_points.get(label, 0) for label in sorted_labels]
                chart_data.add_dataset(series_name, values)
            return Success(chart_data)
        except Exception as e:
            return Failure(f"라인 차트 데이터 준비 실패: {str(e)}")


class BarChart(Chart):
    """바 차트"""

    def __init__(
        self,
        chart_id: str,
        title="",
        horizontal=False,
        options=None,
    ):
        chart_type = ChartType.BAR if horizontal else ChartType.COLUMN
        super().__init__(chart_id, chart_type, title, options)
        self.horizontal = horizontal

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """바 차트 데이터 준비"""
        try:
            if not raw_data:
                return Success(ChartData())
            categories = []
            values = []
            for item in raw_data:
                category = None
                for key in ["category", "name", "label", "x"]:
                    if key in item:
                        category = str(item[key])
                        break
                value = 0
                for key in ["value", "count", "amount", "y"]:
                    if key in item:
                        value = item[key]
                        break
                if category:
                    categories = categories + [category]
                    values = values + [value]
            chart_data = ChartData(labels=categories)
            chart_data.add_dataset("데이터", values)
            return Success(chart_data)
        except Exception as e:
            return Failure(f"바 차트 데이터 준비 실패: {str(e)}")


class PieChart(Chart):
    """파이 차트"""

    def __init__(
        self,
        chart_id: str,
        title="",
        doughnut=False,
        options=None,
    ):
        chart_type = ChartType.DOUGHNUT if doughnut else ChartType.PIE
        super().__init__(chart_id, chart_type, title, options)
        self.doughnut = doughnut

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """파이 차트 데이터 준비"""
        try:
            if not raw_data:
                return Success(ChartData())
            labels = []
            values = []
            colors = []
            for i, item in enumerate(raw_data):
                label = None
                for key in ["label", "name", "category", "x"]:
                    if key in item:
                        label = str(item[key])
                        break
                value = 0
                for key in ["value", "count", "amount", "y"]:
                    if key in item:
                        value = item[key]
                        break
                if label:
                    labels = labels + [label]
                    values = values + [value]
                    color_idx = i % len(self.options.color_scheme)
                    colors = colors + [self.options.color_scheme[color_idx]]
            chart_data = ChartData(labels=labels)
            chart_data.add_dataset("데이터", values, backgroundColor=colors)
            return Success(chart_data)
        except Exception as e:
            return Failure(f"파이 차트 데이터 준비 실패: {str(e)}")


class ScatterChart(Chart):
    """산점도 차트"""

    def __init__(self, chart_id: str, title: str = "", options: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(chart_id, ChartType.SCATTER, title, options)

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """산점도 데이터 준비"""
        try:
            if not raw_data:
                return Success(ChartData())
            scatter_data = []
            for item in raw_data:
                x_val = item.get("x", 0)
                y_val = item.get("y", 0)
                scatter_data = scatter_data + [{"x": x_val, "y": y_val}]
            chart_data = ChartData()
            chart_data.add_dataset("산점도", scatter_data)
            return Success(chart_data)
        except Exception as e:
            return Failure(f"산점도 데이터 준비 실패: {str(e)}")


class HistogramChart(Chart):
    """히스토그램 차트"""

    def __init__(
        self,
        chart_id: str,
        title="",
        bins=10,
        options=None,
    ):
        super().__init__(chart_id, ChartType.HISTOGRAM, title, options)
        self.bins = bins

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """히스토그램 데이터 준비"""
        try:
            if not raw_data:
                return Success(ChartData())
            values = []
            for item in raw_data:
                for key in ["value", "data", "amount", "count"]:
                    if key in item:
                        values = values + [item[key]]
                        break
            if not values:
                return Success(ChartData())
            min_val = min(values)
            max_val = max(values)
            bin_width = (max_val - min_val) / self.bins
            bins = []
            counts = []
            for i in range(self.bins):
                bin_start = min_val + i * bin_width
                bin_end = min_val + (i + 1) * bin_width
                if i == self.bins - 1:
                    count = sum((1 for v in values if bin_start <= v <= bin_end))
                else:
                    count = sum((1 for v in values if bin_start <= v < bin_end))
                bins = bins + [f"{bin_start:.2f}-{bin_end:.2f}"]
                counts = counts + [count]
            chart_data = ChartData(labels=bins)
            chart_data.add_dataset("빈도", counts)
            return Success(chart_data)
        except Exception as e:
            return Failure(f"히스토그램 데이터 준비 실패: {str(e)}")


class HeatmapChart(Chart):
    """히트맵 차트"""

    def __init__(self, chart_id: str, title: str = "", options: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(chart_id, ChartType.HEATMAP, title, options)

    def prepare_data(self, raw_data: List[Dict[str, Any]]) -> Result[ChartData, str]:
        """히트맵 데이터 준비"""
        try:
            if not raw_data:
                return Success(ChartData())
            heatmap_data = []
            x_labels: Set[Any] = set()
            y_labels: Set[Any] = set()
            for item in raw_data:
                x = str(item.get("x", ""))
                y = str(item.get("y", ""))
                value = item.get("value", 0)
                heatmap_data = heatmap_data + [{"x": x, "y": y, "v": value}]
                x_labels.add(x)
                y_labels.add(y)
            chart_data = ChartData()
            chart_data.datasets = [
                {
                    "label": "히트맵",
                    "data": heatmap_data,
                    "backgroundColor": "rgba(75,192,192,0.4)",
                    "borderColor": "rgba(75,192,192,1)",
                }
            ]
            return Success(chart_data)
        except Exception as e:
            return Failure(f"히트맵 데이터 준비 실패: {str(e)}")


class ChartBuilder:
    """차트 빌더"""

    def __init__(self, chart_id: str, chart_type: ChartType) -> None:
        self.chart_id = chart_id
        self.chart_type = chart_type
        self.title = ""
        self.options = ChartOptions()
        self._chart_class = {
            ChartType.LINE: LineChart,
            ChartType.BAR: BarChart,
            ChartType.COLUMN: BarChart,
            ChartType.PIE: PieChart,
            ChartType.DOUGHNUT: PieChart,
            ChartType.SCATTER: ScatterChart,
            ChartType.HISTOGRAM: HistogramChart,
            ChartType.HEATMAP: HeatmapChart,
        }

    def title(self, title: str) -> "ChartBuilder":
        """제목 설정"""
        self.title = title
        self.options.title = title
        return self

    def size(self, width: int, height: int) -> "ChartBuilder":
        """크기 설정"""
        self.options.width = width
        self.options.height = height
        return self

    def colors(self, *colors: str) -> "ChartBuilder":
        """색상 스키마 설정"""
        self.options.color_scheme = list(colors)
        return self

    def legend(self, show=True) -> "ChartBuilder":
        """범례 설정"""
        self.options.legend = show
        return self

    def grid(self, show=True) -> "ChartBuilder":
        """그리드 설정"""
        self.options.grid = show
        return self

    def animation(self, enabled=True) -> "ChartBuilder":
        """애니메이션 설정"""
        self.options.animation = enabled
        return self

    def responsive(self, enabled=True) -> "ChartBuilder":
        """반응형 설정"""
        self.options.responsive = enabled
        return self

    def build(self) -> Chart:
        """차트 빌드"""
        chart_class = self._chart_class.get(self.chart_type)
        if not chart_class:
            raise ValueError(f"지원하지 않는 차트 타입: {self.chart_type}")
        if self.chart_type in [ChartType.PIE, ChartType.DOUGHNUT]:
            return chart_class(
                self.chart_id,
                self.title,
                self.chart_type == ChartType.DOUGHNUT,
                self.options,
            )
        elif self.chart_type == ChartType.HISTOGRAM:
            return chart_class(self.chart_id, self.title, 10, self.options)
        else:
            return chart_class(self.chart_id, self.title, self.options)


def create_chart(chart_id: str, chart_type: ChartType) -> ChartBuilder:
    """차트 빌더 생성"""
    return ChartBuilder(chart_id, chart_type)
