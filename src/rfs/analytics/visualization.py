"""
RFS Advanced Analytics - Visualization Engine (RFS v4.1)

시각화 엔진 및 플롯 생성 시스템
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import base64
import io
from pathlib import Path

from ..core.types import Result, Success, Failure


class PlotType(Enum):
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    PIE = "pie"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    BOX = "box"
    VIOLIN = "violin"
    AREA = "area"
    CANDLESTICK = "candlestick"


class ColorScheme(Enum):
    DEFAULT = "default"
    VIRIDIS = "viridis"
    PLASMA = "plasma"
    INFERNO = "inferno"
    MAGMA = "magma"
    BLUES = "blues"
    GREENS = "greens"
    REDS = "reds"
    PURPLE = "purple"
    ORANGE = "orange"
    CATEGORICAL = "categorical"


@dataclass
class PlotConfig:
    """플롯 설정"""
    title: str = ""
    subtitle: str = ""
    width: int = 800
    height: int = 600
    background_color: str = "white"
    grid: bool = True
    legend: bool = True
    responsive: bool = True
    animation: bool = True
    interactive: bool = True
    
    # 축 설정
    x_label: str = ""
    y_label: str = ""
    x_axis_type: str = "linear"  # linear, log, datetime, category
    y_axis_type: str = "linear"
    
    # 스타일링
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    font_family: str = "Arial, sans-serif"
    font_size: int = 12
    
    # 마진 설정
    margin_top: int = 50
    margin_right: int = 50
    margin_bottom: int = 80
    margin_left: int = 80


@dataclass
class PlotData:
    """플롯 데이터"""
    x_data: List[Any]
    y_data: List[Any]
    labels: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    sizes: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Theme(ABC):
    """테마 추상 클래스"""
    
    @abstractmethod
    def get_colors(self) -> List[str]:
        """색상 팔레트 반환"""
        pass
    
    @abstractmethod
    def get_config_overrides(self) -> Dict[str, Any]:
        """설정 오버라이드 반환"""
        pass


class DefaultTheme(Theme):
    """기본 테마"""
    
    def get_colors(self) -> List[str]:
        return [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
        ]
    
    def get_config_overrides(self) -> Dict[str, Any]:
        return {
            "background_color": "white",
            "font_family": "Arial, sans-serif",
            "grid": True
        }


class DarkTheme(Theme):
    """다크 테마"""
    
    def get_colors(self) -> List[str]:
        return [
            "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
            "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd"
        ]
    
    def get_config_overrides(self) -> Dict[str, Any]:
        return {
            "background_color": "#2e2e2e",
            "font_family": "Arial, sans-serif",
            "grid": True,
            "font_color": "white"
        }


class BusinessTheme(Theme):
    """비즈니스 테마"""
    
    def get_colors(self) -> List[str]:
        return [
            "#003f5c", "#2f4b7c", "#665191", "#a05195", "#d45087",
            "#f95d6a", "#ff7c43", "#ffa600", "#488f31", "#de425b"
        ]
    
    def get_config_overrides(self) -> Dict[str, Any]:
        return {
            "background_color": "#f8f9fa",
            "font_family": "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
            "grid": True,
            "font_size": 11
        }


class VisualizationEngine:
    """시각화 엔진"""
    
    def __init__(self, backend: str = "plotly"):
        self.backend = backend
        self.current_theme: Theme = DefaultTheme()
        self._backend_module = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """백엔드 초기화"""
        try:
            if self.backend == "plotly":
                import plotly.graph_objects as go
                import plotly.express as px
                self._backend_module = {"go": go, "px": px}
            elif self.backend == "matplotlib":
                import matplotlib.pyplot as plt
                import seaborn as sns
                self._backend_module = {"plt": plt, "sns": sns}
            elif self.backend == "bokeh":
                from bokeh.plotting import figure, show
                from bokeh.models import HoverTool
                self._backend_module = {"figure": figure, "show": show, "HoverTool": HoverTool}
        except ImportError as e:
            print(f"Backend {self.backend} not available: {e}")
    
    def set_theme(self, theme: Theme) -> Result[bool, str]:
        """테마 설정"""
        try:
            self.current_theme = theme
            return Success(True)
        except Exception as e:
            return Failure(f"Theme setting failed: {str(e)}")
    
    async def generate_plot(
        self,
        plot_type: PlotType,
        data: PlotData,
        config: Optional[PlotConfig] = None
    ) -> Result[Dict[str, Any], str]:
        """플롯 생성"""
        if not self._backend_module:
            return Failure(f"Backend {self.backend} not initialized")
        
        config = config or PlotConfig()
        
        # 테마 적용
        theme_overrides = self.current_theme.get_config_overrides()
        for key, value in theme_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        try:
            if self.backend == "plotly":
                return await self._generate_plotly_plot(plot_type, data, config)
            elif self.backend == "matplotlib":
                return await self._generate_matplotlib_plot(plot_type, data, config)
            elif self.backend == "bokeh":
                return await self._generate_bokeh_plot(plot_type, data, config)
            else:
                return Failure(f"Unsupported backend: {self.backend}")
        
        except Exception as e:
            return Failure(f"Plot generation failed: {str(e)}")
    
    async def _generate_plotly_plot(
        self,
        plot_type: PlotType,
        data: PlotData,
        config: PlotConfig
    ) -> Result[Dict[str, Any], str]:
        """Plotly 플롯 생성"""
        go = self._backend_module["go"]
        px = self._backend_module["px"]
        
        colors = self.current_theme.get_colors()
        
        if plot_type == PlotType.LINE:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data.x_data,
                y=data.y_data,
                mode='lines+markers',
                name=config.title,
                line=dict(color=colors[0])
            ))
        
        elif plot_type == PlotType.BAR:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=data.x_data,
                y=data.y_data,
                name=config.title,
                marker_color=colors[0]
            ))
        
        elif plot_type == PlotType.SCATTER:
            fig = go.Figure()
            sizes = data.sizes or [10] * len(data.x_data)
            fig.add_trace(go.Scatter(
                x=data.x_data,
                y=data.y_data,
                mode='markers',
                name=config.title,
                marker=dict(
                    size=sizes,
                    color=colors[0],
                    opacity=0.7
                )
            ))
        
        elif plot_type == PlotType.PIE:
            fig = go.Figure()
            fig.add_trace(go.Pie(
                labels=data.labels or data.x_data,
                values=data.y_data,
                marker_colors=colors[:len(data.y_data)]
            ))
        
        elif plot_type == PlotType.HISTOGRAM:
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=data.x_data,
                nbinsx=20,
                name=config.title,
                marker_color=colors[0]
            ))
        
        elif plot_type == PlotType.HEATMAP:
            # x_data와 y_data를 2D 배열로 변환
            if len(data.x_data) != len(data.y_data):
                return Failure("Heatmap requires equal length x and y data")
            
            # 임시로 간단한 히트맵 생성
            z_data = [[data.y_data[i] for i in range(len(data.y_data))]]
            
            fig = go.Figure()
            fig.add_trace(go.Heatmap(
                z=z_data,
                x=data.x_data,
                colorscale='Viridis'
            ))
        
        else:
            return Failure(f"Unsupported plot type: {plot_type}")
        
        # 레이아웃 설정
        fig.update_layout(
            title=config.title,
            xaxis_title=config.x_label,
            yaxis_title=config.y_label,
            width=config.width,
            height=config.height,
            paper_bgcolor=config.background_color,
            plot_bgcolor=config.background_color,
            font=dict(
                family=config.font_family,
                size=config.font_size
            ),
            showlegend=config.legend,
            margin=dict(
                t=config.margin_top,
                r=config.margin_right,
                b=config.margin_bottom,
                l=config.margin_left
            )
        )
        
        # Grid 설정
        if config.grid:
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        
        # JSON으로 변환
        plot_json = fig.to_json()
        plot_html = fig.to_html(include_plotlyjs='cdn')
        
        return Success({
            "type": "plotly",
            "json": plot_json,
            "html": plot_html,
            "config": config.__dict__
        })
    
    async def _generate_matplotlib_plot(
        self,
        plot_type: PlotType,
        data: PlotData,
        config: PlotConfig
    ) -> Result[Dict[str, Any], str]:
        """Matplotlib 플롯 생성"""
        plt = self._backend_module["plt"]
        colors = self.current_theme.get_colors()
        
        # 새로운 figure 생성
        fig, ax = plt.subplots(figsize=(config.width/100, config.height/100))
        
        if plot_type == PlotType.LINE:
            ax.plot(data.x_data, data.y_data, color=colors[0], marker='o', linewidth=2)
        
        elif plot_type == PlotType.BAR:
            ax.bar(data.x_data, data.y_data, color=colors[0])
        
        elif plot_type == PlotType.SCATTER:
            sizes = data.sizes or [50] * len(data.x_data)
            ax.scatter(data.x_data, data.y_data, s=sizes, c=colors[0], alpha=0.7)
        
        elif plot_type == PlotType.PIE:
            labels = data.labels or data.x_data
            ax.pie(data.y_data, labels=labels, colors=colors[:len(data.y_data)], autopct='%1.1f%%')
        
        elif plot_type == PlotType.HISTOGRAM:
            ax.hist(data.x_data, bins=20, color=colors[0], alpha=0.7)
        
        else:
            return Failure(f"Unsupported plot type for matplotlib: {plot_type}")
        
        # 스타일 설정
        ax.set_title(config.title, fontsize=config.font_size + 2)
        ax.set_xlabel(config.x_label, fontsize=config.font_size)
        ax.set_ylabel(config.y_label, fontsize=config.font_size)
        
        if config.grid:
            ax.grid(True, alpha=0.3)
        
        # 배경색 설정
        fig.patch.set_facecolor(config.background_color)
        ax.set_facecolor(config.background_color)
        
        # 이미지를 base64로 변환
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)  # 메모리 정리
        
        return Success({
            "type": "matplotlib",
            "image_base64": image_base64,
            "format": "png",
            "config": config.__dict__
        })
    
    async def _generate_bokeh_plot(
        self,
        plot_type: PlotType,
        data: PlotData,
        config: PlotConfig
    ) -> Result[Dict[str, Any], str]:
        """Bokeh 플롯 생성"""
        figure_func = self._backend_module["figure"]
        colors = self.current_theme.get_colors()
        
        p = figure_func(
            title=config.title,
            x_axis_label=config.x_label,
            y_axis_label=config.y_label,
            width=config.width,
            height=config.height,
            background_fill_color=config.background_color
        )
        
        if plot_type == PlotType.LINE:
            p.line(data.x_data, data.y_data, line_color=colors[0], line_width=2)
            p.circle(data.x_data, data.y_data, color=colors[0], size=6)
        
        elif plot_type == PlotType.BAR:
            p.vbar(x=data.x_data, top=data.y_data, width=0.8, color=colors[0])
        
        elif plot_type == PlotType.SCATTER:
            sizes = data.sizes or [10] * len(data.x_data)
            p.circle(data.x_data, data.y_data, size=sizes, color=colors[0], alpha=0.7)
        
        else:
            return Failure(f"Unsupported plot type for bokeh: {plot_type}")
        
        # 그리드 설정
        p.grid.visible = config.grid
        
        # HTML 생성
        from bokeh.embed import file_html
        from bokeh.resources import CDN
        
        html = file_html(p, CDN, config.title)
        
        return Success({
            "type": "bokeh",
            "html": html,
            "config": config.__dict__
        })


async def generate_plot(
    plot_type: PlotType,
    x_data: List[Any],
    y_data: List[Any],
    config: Optional[PlotConfig] = None,
    backend: str = "plotly",
    theme: Optional[Theme] = None
) -> Result[Dict[str, Any], str]:
    """플롯 생성 헬퍼 함수"""
    engine = VisualizationEngine(backend)
    
    if theme:
        theme_result = engine.set_theme(theme)
        if theme_result.is_failure():
            return theme_result
    
    plot_data = PlotData(x_data=x_data, y_data=y_data)
    
    return await engine.generate_plot(plot_type, plot_data, config)


async def export_chart(
    plot_result: Dict[str, Any],
    file_path: str,
    format: str = "html"
) -> Result[bool, str]:
    """차트 내보내기"""
    try:
        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "html" and "html" in plot_result:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(plot_result["html"])
        
        elif format == "json" and "json" in plot_result:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(plot_result["json"])
        
        elif format == "png" and "image_base64" in plot_result:
            image_data = base64.b64decode(plot_result["image_base64"])
            with open(output_path, 'wb') as f:
                f.write(image_data)
        
        else:
            return Failure(f"Unsupported export format: {format}")
        
        return Success(True)
        
    except Exception as e:
        return Failure(f"Export failed: {str(e)}")


async def create_interactive_plot(
    plot_type: PlotType,
    x_data: List[Any],
    y_data: List[Any],
    config: Optional[PlotConfig] = None,
    callbacks: Optional[Dict[str, Callable]] = None
) -> Result[Dict[str, Any], str]:
    """인터랙티브 플롯 생성"""
    if config is None:
        config = PlotConfig()
    
    # 인터랙티브 기능 활성화
    config.interactive = True
    config.animation = True
    
    # Plotly 백엔드 사용 (인터랙티브 기능 최고)
    result = await generate_plot(plot_type, x_data, y_data, config, "plotly")
    
    if result.is_failure():
        return result
    
    plot_data = result.unwrap()
    
    # 콜백 추가 (실제 구현에서는 JavaScript 콜백 추가)
    if callbacks:
        plot_data["callbacks"] = callbacks
    
    return Success(plot_data)


def apply_theme(config: PlotConfig, theme: Theme) -> PlotConfig:
    """테마를 설정에 적용"""
    theme_overrides = theme.get_config_overrides()
    
    for key, value in theme_overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config


class PlotBuilder:
    """플롯 빌더 (Fluent API)"""
    
    def __init__(self):
        self._plot_type: Optional[PlotType] = None
        self._x_data: List[Any] = []
        self._y_data: List[Any] = []
        self._config = PlotConfig()
        self._theme: Optional[Theme] = None
        self._backend = "plotly"
    
    def plot_type(self, plot_type: PlotType) -> 'PlotBuilder':
        """플롯 타입 설정"""
        self._plot_type = plot_type
        return self
    
    def data(self, x_data: List[Any], y_data: List[Any]) -> 'PlotBuilder':
        """데이터 설정"""
        self._x_data = x_data
        self._y_data = y_data
        return self
    
    def title(self, title: str) -> 'PlotBuilder':
        """제목 설정"""
        self._config.title = title
        return self
    
    def size(self, width: int, height: int) -> 'PlotBuilder':
        """크기 설정"""
        self._config.width = width
        self._config.height = height
        return self
    
    def labels(self, x_label: str, y_label: str) -> 'PlotBuilder':
        """축 레이블 설정"""
        self._config.x_label = x_label
        self._config.y_label = y_label
        return self
    
    def theme(self, theme: Theme) -> 'PlotBuilder':
        """테마 설정"""
        self._theme = theme
        return self
    
    def backend(self, backend: str) -> 'PlotBuilder':
        """백엔드 설정"""
        self._backend = backend
        return self
    
    def color_scheme(self, color_scheme: ColorScheme) -> 'PlotBuilder':
        """색상 스킴 설정"""
        self._config.color_scheme = color_scheme
        return self
    
    def interactive(self, interactive: bool = True) -> 'PlotBuilder':
        """인터랙티브 모드 설정"""
        self._config.interactive = interactive
        return self
    
    def grid(self, show_grid: bool = True) -> 'PlotBuilder':
        """그리드 표시 설정"""
        self._config.grid = show_grid
        return self
    
    async def build(self) -> Result[Dict[str, Any], str]:
        """플롯 생성"""
        if not self._plot_type:
            return Failure("Plot type not specified")
        
        if not self._x_data or not self._y_data:
            return Failure("Plot data not specified")
        
        return await generate_plot(
            self._plot_type,
            self._x_data,
            self._y_data,
            self._config,
            self._backend,
            self._theme
        )


def create_plot() -> PlotBuilder:
    """플롯 빌더 생성"""
    return PlotBuilder()


# 샘플 데이터 생성 유틸리티
def generate_sample_data(data_type: str = "line", size: int = 50) -> Tuple[List[Any], List[Any]]:
    """샘플 데이터 생성"""
    import random
    import math
    
    if data_type == "line":
        x_data = list(range(size))
        y_data = [math.sin(x * 0.1) + random.random() * 0.1 for x in x_data]
    
    elif data_type == "bar":
        x_data = [f"Category {i+1}" for i in range(size)]
        y_data = [random.randint(1, 100) for _ in range(size)]
    
    elif data_type == "scatter":
        x_data = [random.uniform(0, 100) for _ in range(size)]
        y_data = [random.uniform(0, 100) for _ in range(size)]
    
    elif data_type == "pie":
        x_data = [f"Slice {i+1}" for i in range(min(size, 10))]
        y_data = [random.randint(1, 100) for _ in range(len(x_data))]
    
    else:
        x_data = list(range(size))
        y_data = [random.random() * 100 for _ in range(size)]
    
    return x_data, y_data


# 전역 시각화 엔진
_global_visualization_engine = None


def get_visualization_engine(backend: str = "plotly") -> VisualizationEngine:
    """전역 시각화 엔진 가져오기"""
    global _global_visualization_engine
    if _global_visualization_engine is None:
        _global_visualization_engine = VisualizationEngine(backend)
    return _global_visualization_engine