"""
RFS Advanced Analytics (RFS v4.1)

고급 분석 및 대시보드 시스템
"""

from .dashboard import (
    # 대시보드 시스템
    Dashboard,
    DashboardLayout,
    Widget,
    WidgetType,
    
    # 위젯 구현체
    ChartWidget,
    MetricWidget,
    TableWidget,
    TextWidget,
    
    # 대시보드 빌더
    DashboardBuilder,
    create_dashboard,
    
    # 대시보드 관리
    DashboardManager,
    get_dashboard_manager
)

from .charts import (
    # 차트 시스템
    Chart,
    ChartType,
    ChartData,
    ChartOptions,
    
    # 차트 구현체
    LineChart,
    BarChart,
    PieChart,
    ScatterChart,
    HistogramChart,
    HeatmapChart,
    
    # 차트 빌더
    ChartBuilder,
    create_chart
)

from .data_source import (
    # 데이터 소스
    DataSource,
    DataSourceType,
    DataQuery,
    
    # 데이터 소스 구현체
    DatabaseDataSource,
    FileDataSource,
    APIDataSource,
    MetricsDataSource,
    
    # 데이터 소스 관리
    DataSourceManager,
    register_data_source
)

from .visualization import (
    # 시각화 엔진
    VisualizationEngine,
    PlotConfig,
    ColorScheme,
    
    # 시각화 유틸리티
    generate_plot,
    export_chart,
    create_interactive_plot,
    
    # 테마 관리
    Theme,
    DefaultTheme,
    DarkTheme,
    apply_theme
)

from .reports import (
    # 리포트 시스템
    Report,
    ReportBuilder,
    ReportSection,
    
    # 리포트 타입
    PDFReport,
    HTMLReport,
    ExcelReport,
    
    # 리포트 생성
    generate_report,
    schedule_report,
    
    # 리포트 템플릿
    ReportTemplate,
    create_report_template
)

from .kpi import (
    # KPI 관리
    KPI,
    KPICalculator,
    KPIThreshold,
    
    # KPI 타입
    CountKPI,
    AverageKPI,
    PercentageKPI,
    TrendKPI,
    
    # KPI 대시보드
    KPIDashboard,
    create_kpi_dashboard
)

__all__ = [
    # Dashboard
    "Dashboard",
    "DashboardLayout",
    "Widget",
    "WidgetType",
    "ChartWidget",
    "MetricWidget", 
    "TableWidget",
    "TextWidget",
    "DashboardBuilder",
    "create_dashboard",
    "DashboardManager",
    "get_dashboard_manager",
    
    # Charts
    "Chart",
    "ChartType",
    "ChartData",
    "ChartOptions",
    "LineChart",
    "BarChart",
    "PieChart",
    "ScatterChart",
    "HistogramChart",
    "HeatmapChart",
    "ChartBuilder",
    "create_chart",
    
    # Data Source
    "DataSource",
    "DataSourceType",
    "DataQuery",
    "DatabaseDataSource",
    "FileDataSource",
    "APIDataSource",
    "MetricsDataSource",
    "DataSourceManager",
    "register_data_source",
    
    # Visualization
    "VisualizationEngine",
    "PlotConfig",
    "ColorScheme",
    "generate_plot",
    "export_chart",
    "create_interactive_plot",
    "Theme",
    "DefaultTheme",
    "DarkTheme",
    "apply_theme",
    
    # Reports
    "Report",
    "ReportBuilder",
    "ReportSection",
    "PDFReport",
    "HTMLReport",
    "ExcelReport",
    "generate_report",
    "schedule_report",
    "ReportTemplate",
    "create_report_template",
    
    # KPI
    "KPI",
    "KPICalculator",
    "KPIThreshold",
    "CountKPI",
    "AverageKPI",
    "PercentageKPI",
    "TrendKPI",
    "KPIDashboard",
    "create_kpi_dashboard"
]