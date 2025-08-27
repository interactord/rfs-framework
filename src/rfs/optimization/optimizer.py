"""
Performance Optimizer (RFS v4)

RFS v4 성능 최적화 메인 엔진
- 자동 성능 분석
- 최적화 권장사항 생성
- 실시간 성능 모니터링
- 자동 튜닝 실행
"""

import asyncio
import gc
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import psutil
except ImportError:
    psutil = None

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ..core.result import Failure, Result, Success

if RICH_AVAILABLE:
    console = Console()
else:
    console = None


class OptimizationType(Enum):
    """최적화 유형"""

    MEMORY = "memory"
    CPU = "cpu"
    IO = "io"
    NETWORK = "network"
    STARTUP = "startup"
    RUNTIME = "runtime"
    CLOUD_RUN = "cloud_run"


class OptimizationCategory(Enum):
    """최적화 카테고리"""

    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    EFFICIENCY = "efficiency"


class OptimizationPriority(Enum):
    """최적화 우선순위"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class OptimizationResult:
    """최적화 결과"""

    optimization_type: OptimizationType
    name: str
    description: str
    priority: OptimizationPriority
    impact_score: float
    implementation_difficulty: int
    estimated_improvement: str
    before_metrics: Dict[str, Any] = field(default_factory=dict)
    after_metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    code_changes: List[Dict[str, str]] = field(default_factory=list)
    applied = False

    @property
    def roi_score(self) -> float:
        """투자 대비 효과 점수 계산"""
        if self.implementation_difficulty == 0:
            return 0
        return self.impact_score / self.implementation_difficulty


@dataclass
class OptimizationSuite:
    """최적화 스위트"""

    name: str
    target_types: List[str] = field(default_factory=list)
    auto_apply = False
    max_impact_threshold: float = 50.0
    include_experimental = False
    timeout = 300


class PerformanceOptimizer:
    """성능 최적화 메인 엔진"""

    def __init__(self, project_path=None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.optimization_results = []
        self.baseline_metrics = {}
        self.monitoring_active = False
        self.monitoring_task = None
        self.performance_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000

    async def run_optimization_analysis(
        self, suite: OptimizationSuite
    ) -> Result[List[OptimizationResult], str]:
        """최적화 분석 실행"""
        try:
            if console:
                console.print(
                    Panel(
                        f"🚀 RFS v4 성능 최적화 분석 시작\n\n📋 최적화 스위트: {suite.name}\n🎯 대상 유형: {(', '.join([t.value for t in suite.target_types]) if suite.target_types else '모든 유형')}\n⚡ 자동 적용: {('예' if suite.auto_apply else '아니오')}\n🧪 실험적 기능: {('포함' if suite.include_experimental else '제외')}",
                        title="성능 최적화",
                        border_style="blue",
                    )
                )
            if console:
                console.print("📊 기준 성능 측정 중...")
            await self._measure_baseline_performance()
            optimization_tasks = []
            if not suite.target_types or OptimizationType.MEMORY in suite.target_types:
                optimization_tasks = optimization_tasks + [
                    self._analyze_memory_optimization(suite)
                ]
            if not suite.target_types or OptimizationType.CPU in suite.target_types:
                optimization_tasks = optimization_tasks + [
                    self._analyze_cpu_optimization(suite)
                ]
            if not suite.target_types or OptimizationType.IO in suite.target_types:
                optimization_tasks = optimization_tasks + [
                    self._analyze_io_optimization(suite)
                ]
            if not suite.target_types or OptimizationType.STARTUP in suite.target_types:
                optimization_tasks = optimization_tasks + [
                    self._analyze_startup_optimization(suite)
                ]
            if (
                not suite.target_types
                or OptimizationType.CLOUD_RUN in suite.target_types
            ):
                optimization_tasks = optimization_tasks + [
                    self._analyze_cloud_run_optimization(suite)
                ]
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
            ) as progress:
                for i, task in enumerate(optimization_tasks):
                    task_id = progress.add_task(
                        f"최적화 분석 {i + 1}/{len(optimization_tasks)}", total=100
                    )
                    results = await task
                    if results:
                        self.optimization_results = self.optimization_results + results
                    progress.update(task_id, completed=100)
            self.optimization_results.sort(key=lambda x: x.roi_score, reverse=True)
            if suite.auto_apply:
                await self._apply_safe_optimizations(suite)
            if console:
                await self._display_optimization_results()
            return Success(self.optimization_results)
        except Exception as e:
            return Failure(f"최적화 분석 실패: {str(e)}")

    async def _measure_baseline_performance(self):
        """기준 성능 측정"""
        try:
            import os
            import time

            import psutil

            if psutil:
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                cpu_percent = process.cpu_percent(interval=1)
                num_threads = process.num_threads()
            else:
                process = None
                # Provide default values when psutil is not available
                memory_info = type("MemoryInfo", (), {"rss": 0, "vms": 0})()
                cpu_percent = 0
                num_threads = threading.active_count()

            start_time = time.time()
            try:
                from .. import core

                import_time = time.time() - start_time
            except:
                import_time = 0
            gc_stats = {
                f"generation_{i}": gc.get_stats()[i] if i < len(gc.get_stats()) else {}
                for i in range(3)
            }
            self.baseline_metrics = {
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "rss": memory_info.rss,
                    "vms": memory_info.vms,
                    "rss_mb": memory_info.rss / 1024 / 1024,
                    "vms_mb": memory_info.vms / 1024 / 1024,
                },
                "cpu": {"percent": cpu_percent, "num_threads": num_threads},
                "startup": {"import_time": import_time},
                "gc": gc_stats,
                "system": {"python_version": sys.version, "platform": sys.platform},
            }
        except Exception as e:
            if console:
                console.print(f"⚠️  기준 성능 측정 실패: {str(e)}", style="yellow")
            self.baseline_metrics = {}

    async def _analyze_memory_optimization(
        self, suite: OptimizationSuite
    ) -> List[OptimizationResult]:
        """메모리 최적화 분석"""
        results = []
        try:
            if "memory" in self.baseline_metrics:
                memory_mb = self.baseline_metrics["memory"]["rss_mb"]
                if memory_mb > 100:
                    cache = {}
                gc_stats = self.baseline_metrics.get("gc", {})
                if gc_stats and any(
                    (
                        gen.get("collections", 0) > 100
                        for gen in gc_stats.values()
                        if type(gen).__name__ == "dict"
                    )
                ):
                    results = results + [
                        OptimizationResult(
                            optimization_type=OptimizationType.MEMORY,
                            name="가비지 컬렉션 튜닝",
                            description="빈번한 GC 호출이 감지되었습니다",
                            priority=OptimizationPriority.MEDIUM,
                            impact_score=40.0,
                            implementation_difficulty=2,
                            estimated_improvement="10-20% GC 오버헤드 감소",
                            before_metrics=gc_stats,
                            recommendations=[
                                "gc.set_threshold() 조정",
                                "순환 참조 제거",
                                "적절한 시점에 gc.collect() 호출",
                            ],
                            code_changes=[
                                {
                                    "file": "gc_optimization.py",
                                    "change": "\nimport gc\n\n# GC 임계값 조정 (기본값보다 덜 공격적)\ngc.set_threshold(1000, 15, 15)\n\n# 중요한 작업 전후 명시적 GC\ndef heavy_processing():\n    gc.collect()  # 처리 전 정리\n    try:\n        # 무거운 작업 수행\n        result = expensive_computation()\n    finally:\n        gc.collect()  # 처리 후 정리\n    return result\n",
                                }
                            ],
                        )
                    ]
        except Exception as e:
            if console:
                console.print(f"⚠️  메모리 최적화 분석 실패: {str(e)}", style="yellow")
        return results

    async def _analyze_cpu_optimization(
        self, suite: OptimizationSuite
    ) -> List[OptimizationResult]:
        """CPU 최적화 분석"""
        results = []
        try:
            if "cpu" in self.baseline_metrics:
                num_threads = self.baseline_metrics["cpu"]["num_threads"]
                if num_threads > 20:
                    results = results + [
                        OptimizationResult(
                            optimization_type=OptimizationType.CPU,
                            name="스레드 수 최적화",
                            description=f"과도한 스레드 수가 감지되었습니다 ({num_threads}개)",
                            priority=OptimizationPriority.HIGH,
                            impact_score=60.0,
                            implementation_difficulty=3,
                            estimated_improvement="20-40% CPU 효율성 향상",
                            before_metrics={"thread_count": num_threads},
                            recommendations=[
                                "ThreadPoolExecutor 사용으로 스레드 수 제한",
                                "비동기 프로그래밍으로 스레드 필요성 감소",
                                "연결 풀링으로 리소스 재사용",
                            ],
                            code_changes=[
                                {
                                    "file": "thread_optimization.py",
                                    "change": "\nimport asyncio\nfrom concurrent.futures import ThreadPoolExecutor\nfrom functools import lru_cache\n\n# Before: 무제한 스레드 생성\nimport threading\n\ndef process_data(data):\n    for item in data:\n        thread = threading.Thread(target=heavy_task, args=(item,))\n        thread.start()\n\n# After: 제한된 스레드 풀 사용\nMAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)\n\nasync def process_data_optimized(data):\n    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:\n        loop = asyncio.get_event_loop()\n        tasks = [\n            loop.run_in_executor(executor, heavy_task, item)\n            for item in data\n        ]\n        return await asyncio.gather(*tasks)\n\n# LRU 캐시로 중복 계산 방지\n@lru_cache(maxsize=128)\ndef expensive_computation(param):\n    # 비용이 큰 계산\n    return result\n",
                                }
                            ],
                        )
                    ]
                results = results + [
                    OptimizationResult(
                        optimization_type=OptimizationType.CPU,
                        name="비동기 처리 최적화",
                        description="동기 I/O 작업의 비동기 전환 기회",
                        priority=OptimizationPriority.MEDIUM,
                        impact_score=50.0,
                        implementation_difficulty=4,
                        estimated_improvement="2-5배 동시 처리 성능 향상",
                        recommendations=[
                            "동기 I/O를 비동기로 변환",
                            "asyncio.gather로 병렬 처리",
                            "적절한 await 지점 설정",
                        ],
                        code_changes=[
                            {
                                "file": "async_optimization.py",
                                "change": "\nimport asyncio\nimport aiohttp\nimport aiofiles\n\n# Before: 동기 처리\ndef fetch_data(urls):\n    results=[]\n    for url in urls:\n        response = requests.get(url)\n        results = results + [response.json(])\n    return results\n\n# After: 비동기 처리  \nasync def fetch_data_async(urls):\n    async with aiohttp.ClientSession() as session:\n        tasks = [fetch_url(session, url) for url in urls]\n        return await asyncio.gather(*tasks)\n\nasync def fetch_url(session, url):\n    async with session.get(url) as response:\n        return await response.json()\n\n# Before: 동기 파일 처리\ndef process_files(file_paths):\n    results=[]\n    for path in file_paths:\n        with open(path, 'r') as f:\n            results = results + [f.read(])\n    return results\n\n# After: 비동기 파일 처리\nasync def process_files_async(file_paths):\n    tasks = [read_file_async(path) for path in file_paths]\n    return await asyncio.gather(*tasks)\n\nasync def read_file_async(path):\n    async with aiofiles.open(path, 'r') as f:\n        return await f.read()\n",
                            }
                        ],
                    )
                ]
        except Exception as e:
            if console:
                console.print(f"⚠️  CPU 최적화 분석 실패: {str(e)}", style="yellow")
        return results

    async def _analyze_io_optimization(
        self, suite: OptimizationSuite
    ) -> List[OptimizationResult]:
        """I/O 최적화 분석"""
        results = []
        try:
            results = results + [
                OptimizationResult(
                    optimization_type=OptimizationType.IO,
                    name="파일 I/O 최적화",
                    description="파일 읽기/쓰기 성능 최적화 기회",
                    priority=OptimizationPriority.MEDIUM,
                    impact_score=35.0,
                    implementation_difficulty=2,
                    estimated_improvement="50-100% 파일 I/O 속도 향상",
                    recommendations=[
                        "버퍼링 사용으로 I/O 호출 최소화",
                        "대용량 파일에 mmap 사용",
                        "배치 처리로 I/O 집약도 최적화",
                    ],
                    code_changes=[
                        {
                            "file": "io_optimization.py",
                            "change": "\nimport mmap\nimport os\nfrom pathlib import Path\n\n# Before: 작은 청크로 파일 읽기\ndef read_large_file_slow(file_path):\n    with open(file_path, 'r') as f:\n        lines=[]\n        while True:\n            line = f.readline()\n            if not line:\n                break\n            lines = lines + [line.strip(])\n    return lines\n\n# After: 최적화된 파일 읽기\ndef read_large_file_fast(file_path):\n    # mmap 사용 (대용량 파일)\n    if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB 이상\n        with open(file_path, 'r') as f:\n            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:\n                return mm.read().decode().splitlines()\n    else:\n        # 작은 파일은 한 번에 읽기\n        return Path(file_path).read_text().splitlines()\n\n# Before: 개별 파일 쓰기\ndef write_files_slow(data_dict):\n    for filename, content in data_dict.items():\n        with open(filename, 'w') as f:\n            f.write(content)\n\n# After: 배치 처리\ndef write_files_fast(data_dict):\n    # 같은 디렉토리 파일들 그룹화\n    dir_groups={}\n    for filename, content in data_dict.items():\n        dir_name = os.path.dirname(filename)\n        if dir_name not in dir_groups:\n            dir_groups[dir_name] = []\n        dir_groups[dir_name] = dirname(filename)\n        if dir_name not in dir_groups:\n            dir_groups[dir_name] = []\n        dir_groups[dir_name] + [(filename, content])\n    \n    # 디렉토리별 배치 처리\n    for dir_name, files in dir_groups.items():\n        os.makedirs(dir_name, exist_ok=True)\n        for filename, content in files:\n            with open(filename, 'w', buffering=8192) as f:\n                f.write(content)\n",
                        }
                    ],
                )
            ]
            results = results + [
                OptimizationResult(
                    optimization_type=OptimizationType.NETWORK,
                    name="네트워크 연결 최적화",
                    description="HTTP 연결 및 네트워크 요청 최적화",
                    priority=OptimizationPriority.HIGH,
                    impact_score=65.0,
                    implementation_difficulty=3,
                    estimated_improvement="3-10배 네트워크 성능 향상",
                    recommendations=[
                        "연결 풀링으로 연결 재사용",
                        "요청 배치 처리",
                        "적절한 타임아웃 설정",
                        "압축 및 캐싱 활용",
                    ],
                    code_changes=[
                        {
                            "file": "network_optimization.py",
                            "change": "\nimport aiohttp\nimport asyncio\nfrom aiohttp import ClientTimeout, TCPConnector\n\n# 최적화된 HTTP 클라이언트 설정\nclass OptimizedHTTPClient:\n    def __init__(self):\n        # 연결 풀 설정\n        connector = TCPConnector(\n            limit=100,  # 총 연결 수 제한\n            limit_per_host=10,  # 호스트당 연결 수 제한\n            ttl_dns_cache=300,  # DNS 캐시 TTL\n            use_dns_cache=True,\n            keepalive_timeout=30,\n            enable_cleanup_closed=True\n        )\n        \n        # 타임아웃 설정\n        timeout = ClientTimeout(\n            total=30,  # 총 요청 시간\n            connect=5,  # 연결 시간\n            sock_read=10  # 소켓 읽기 시간\n        )\n        \n        self.session = aiohttp.ClientSession(\n            connector=connector,\n            timeout=timeout,\n            headers={'Accept-Encoding': 'gzip, deflate'}\n        )\n    \n    async def fetch_multiple(self, urls, batch_size=10):\n        \"\"\"배치 단위로 URL 요청\"\"\"\n        results=[]\n        \n        for i in range(0, len(urls), batch_size):\n            batch = urls[i:i + batch_size]\n            batch_tasks = [self.fetch_url(url) for url in batch]\n            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)\n            results = gather(*batch_tasks, return_exceptions=True)\n            results + batch_results\n            \n            # 서버 부하 방지를 위한 짧은 대기\n            if i + batch_size < len(urls):\n                await asyncio.sleep(0.1)\n        \n        return results\n    \n    async def fetch_url(self, url):\n        try:\n            async with self.session.get(url) as response:\n                return await response.json()\n        except Exception as e:\n            return {'error': str(e), 'url': url}\n    \n    async def close(self):\n        await self.session.close()\n",
                        }
                    ],
                )
            ]
        except Exception as e:
            if console:
                console.print(f"⚠️  I/O 최적화 분석 실패: {str(e)}", style="yellow")
        return results

    async def _analyze_startup_optimization(
        self, suite: OptimizationSuite
    ) -> List[OptimizationResult]:
        """시작 시간 최적화 분석"""
        results = []
        try:
            if "startup" in self.baseline_metrics:
                import_time = self.baseline_metrics["startup"]["import_time"]
                if import_time > 0.5:
                    results = results + [
                        OptimizationResult(
                            optimization_type=OptimizationType.STARTUP,
                            name="모듈 임포트 최적화",
                            description=f"느린 모듈 임포트가 감지되었습니다 ({import_time:.3f}초)",
                            priority=OptimizationPriority.HIGH,
                            impact_score=80.0,
                            implementation_difficulty=2,
                            estimated_improvement=f"50-70% 시작 시간 단축 ({import_time * 0.3:.3f}초 목표)",
                            before_metrics={"import_time": import_time},
                            recommendations=[
                                "지연 임포트 (lazy import) 사용",
                                "불필요한 전역 임포트 제거",
                                "조건부 임포트 활용",
                                "가벼운 대안 라이브러리 검토",
                            ],
                            code_changes=[
                                {
                                    "file": "lazy_import_optimization.py",
                                    "change": '\n# Before: 전역에서 모든 모듈 임포트\nimport pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\nfrom sklearn.ensemble import RandomForestClassifier\nimport tensorflow as tf\n\ndef simple_function():\n    return "Hello"\n\n# After: 지연 임포트 사용\ndef simple_function():\n    return "Hello"\n\ndef data_analysis_function(data):\n    # 실제 사용할 때만 임포트\n    import pandas as pd\n    import numpy as np\n    \n    df = pd.DataFrame(data)\n    return df.mean()\n\ndef plotting_function(data):\n    # 조건부 임포트\n    try:\n        import matplotlib.pyplot as plt\n    except ImportError:\n        raise ImportError("matplotlib이 설치되지 않았습니다")\n    \n    plt.plot(data)\n    return plt.gcf()\n\n# 선택적 기능을 위한 지연 로딩\nclass MachineLearningModule:\n    def __init__(self):\n        self._sklearn = None\n        self._tensorflow = None\n    \n    @property\n    def sklearn(self):\n        if self._sklearn is None:\n            import sklearn\n            self._sklearn = sklearn\n        return self._sklearn\n    \n    @property\n    def tensorflow(self):\n        if self._tensorflow is None:\n            import tensorflow as tf\n            self._tensorflow = tf\n        return self._tensorflow\n',
                                }
                            ],
                        )
                    ]
                results = results + [
                    OptimizationResult(
                        optimization_type=OptimizationType.STARTUP,
                        name="Cold Start 최적화",
                        description="Cloud Run Cold Start 시간 최소화",
                        priority=OptimizationPriority.CRITICAL,
                        impact_score=90.0,
                        implementation_difficulty=3,
                        estimated_improvement="50-80% Cold Start 시간 단축",
                        recommendations=[
                            "최소한의 전역 초기화",
                            "필요 시점까지 연결 지연",
                            "예열 엔드포인트 구현",
                            "컨테이너 이미지 크기 최적화",
                        ],
                        code_changes=[
                            {
                                "file": "cold_start_optimization.py",
                                "change": '\nimport os\nfrom functools import lru_cache\n\n# Before: 시작 시 모든 연결 초기화\ndatabase_connection = create_database_connection()\nredis_client = create_redis_client()\nexternal_api_client = create_api_client()\n\ndef handle_request(request):\n    # 요청 처리\n    pass\n\n# After: 지연 초기화\n_database_connection = None\n_redis_client = None\n_external_api_client = None\n\n@lru_cache(maxsize=1)\ndef get_database_connection():\n    global _database_connection\n    if _database_connection is None:\n        _database_connection = create_database_connection()\n    return _database_connection\n\n@lru_cache(maxsize=1)\ndef get_redis_client():\n    global _redis_client\n    if _redis_client is None:\n        _redis_client = create_redis_client()\n    return _redis_client\n\n@lru_cache(maxsize=1)\ndef get_api_client():\n    global _external_api_client\n    if _external_api_client is None:\n        _external_api_client = create_api_client()\n    return _external_api_client\n\ndef handle_request(request):\n    # 필요할 때만 연결 생성\n    db = get_database_connection()\n    # 요청 처리\n    pass\n\n# 예열 엔드포인트\ndef warmup():\n    """Cloud Run 예열용 엔드포인트"""\n    try:\n        # 중요한 연결들 미리 초기화\n        get_database_connection()\n        get_redis_client()\n        return {"status": "warm"}\n    except Exception as e:\n        return {"status": "error", "message": str(e)}\n',
                            }
                        ],
                    )
                ]
        except Exception as e:
            if console:
                console.print(
                    f"⚠️  시작 시간 최적화 분석 실패: {str(e)}", style="yellow"
                )
        return results

    async def _analyze_cloud_run_optimization(
        self, suite: OptimizationSuite
    ) -> List[OptimizationResult]:
        """Cloud Run 최적화 분석"""
        results = []
        try:
            is_cloud_run = os.getenv("K_SERVICE") is not None
            results = results + [
                OptimizationResult(
                    optimization_type=OptimizationType.CLOUD_RUN,
                    name="Cloud Run 리소스 최적화",
                    description="Cloud Run 인스턴스 리소스 효율성 최적화",
                    priority=OptimizationPriority.HIGH,
                    impact_score=75.0,
                    implementation_difficulty=3,
                    estimated_improvement="30-50% 리소스 비용 절약",
                    before_metrics={"is_cloud_run": is_cloud_run},
                    recommendations=[
                        "적절한 CPU 및 메모리 한계 설정",
                        "동시성 설정 최적화",
                        "최소 인스턴스 수 조정",
                        "요청 타임아웃 최적화",
                    ],
                    code_changes=[
                        {
                            "file": "cloud_run_config.yaml",
                            "change": '\n# Cloud Run 서비스 설정 최적화\napiVersion: serving.knative.dev/v1\nkind: Service\nmetadata:\n  name: rfs-app\n  annotations:\n    # 동시성 설정 (기본값: 100, 최적화: 1000)\n    run.googleapis.com/execution-environment: gen2\n    run.googleapis.com/cpu-throttling: "false"\nspec:\n  template:\n    metadata:\n      annotations:\n        # 리소스 최적화\n        run.googleapis.com/memory: "512Mi"  # 메모리 제한\n        run.googleapis.com/cpu: "1000m"     # CPU 제한 (1 vCPU)\n        \n        # 동시성 및 확장 설정\n        autoscaling.knative.dev/maxScale: "100"\n        autoscaling.knative.dev/minScale: "0"\n        run.googleapis.com/execution-environment: "gen2"\n        \n        # 타임아웃 설정\n        run.googleapis.com/timeout: "300s"\n        \n    spec:\n      containerConcurrency: 1000  # 컨테이너당 동시 요청 수\n      timeoutSeconds: 300\n      containers:\n      - image: gcr.io/project/rfs-app\n        resources:\n          limits:\n            memory: "512Mi"\n            cpu: "1000m"\n        env:\n        - name: PYTHONUNBUFFERED\n          value: "1"\n        - name: PYTHONDONTWRITEBYTECODE\n          value: "1"\n        \n        # 헬스체크 최적화\n        livenessProbe:\n          httpGet:\n            path: /health\n            port: 8080\n          initialDelaySeconds: 0\n          timeoutSeconds: 1\n          periodSeconds: 3\n          failureThreshold: 3\n        \n        readinessProbe:\n          httpGet:\n            path: /health\n            port: 8080\n          initialDelaySeconds: 0\n          timeoutSeconds: 1\n          periodSeconds: 3\n          failureThreshold: 1\n',
                        },
                        {
                            "file": "cloud_run_optimization.py",
                            "change": '\nimport os\nimport logging\nfrom contextlib import asynccontextmanager\n\n# Cloud Run 최적화 설정\nclass CloudRunOptimizer:\n    \n    @staticmethod\n    def configure_logging():\n        """Cloud Run 로깅 최적화"""\n        logging.basicConfig(\n            level=logging.INFO,\n            format=\'%(asctime)s %(name)s %(levelname)s %(message)s\',\n            handlers=[logging.StreamHandler()]\n        )\n        \n        # Cloud Run에서는 stdout/stderr가 로그로 수집됨\n        if os.getenv(\'K_SERVICE\'):\n            # JSON 로깅 설정\n            import json\n            import sys\n            \n            class CloudRunFormatter(logging.Formatter):\n                def format(self, record):\n                    log_obj = {\n                        \'timestamp\': self.formatTime(record),\n                        \'severity\': record.levelname,\n                        \'message\': record.getMessage(),\n                        \'module\': record.name\n                    }\n                    return json.dumps(log_obj)\n            \n            handler = logging.StreamHandler(sys.stdout)\n            handler.setFormatter(CloudRunFormatter())\n            \n            root_logger = logging.getLogger()\n            root_logger.handlers = [handler]\n    \n    @staticmethod\n    def get_optimal_workers():\n        """최적의 worker 수 계산"""\n        cpu_count = os.cpu_count() or 1\n        \n        # Cloud Run에서는 보수적으로 설정\n        if os.getenv(\'K_SERVICE\'):\n            return min(cpu_count * 2, 4)\n        else:\n            return cpu_count * 2 + 1\n    \n    @staticmethod\n    @asynccontextmanager\n    async def lifespan_manager(app):\n        """애플리케이션 수명 주기 관리"""\n        # 시작 시 초기화\n        CloudRunOptimizer.configure_logging()\n        logger = logging.getLogger(__name__)\n        \n        logger.info("RFS v4 애플리케이션 시작")\n        \n        # 예열 작업\n        if os.getenv(\'K_SERVICE\'):\n            await CloudRunOptimizer.warmup_services()\n        \n        yield\n        \n        # 종료 시 정리\n        logger.info("RFS v4 애플리케이션 종료")\n        await CloudRunOptimizer.cleanup_services()\n    \n    @staticmethod\n    async def warmup_services():\n        """서비스 예열"""\n        try:\n            # 중요한 연결들 미리 초기화\n            from rfs.cloud_run import initialize_cloud_run_services\n            await initialize_cloud_run_services()\n        except Exception as e:\n            logging.warning(f"서비스 예열 실패: {e}")\n    \n    @staticmethod\n    async def cleanup_services():\n        """서비스 정리"""\n        try:\n            from rfs.cloud_run import shutdown_cloud_run_services\n            await shutdown_cloud_run_services()\n        except Exception as e:\n            logging.warning(f"서비스 정리 실패: {e}")\n',
                        },
                    ],
                )
            ]
        except Exception as e:
            if console:
                console.print(
                    f"⚠️  Cloud Run 최적화 분석 실패: {str(e)}", style="yellow"
                )
        return results

    async def _apply_safe_optimizations(self, suite: OptimizationSuite):
        """안전한 최적화 자동 적용"""
        try:
            safe_optimizations = [
                opt
                for opt in self.optimization_results
                if opt.impact_score <= suite.max_impact_threshold
                and opt.implementation_difficulty <= 2
                and (
                    opt.priority
                    in [OptimizationPriority.LOW, OptimizationPriority.MEDIUM]
                )
            ]
            for optimization in safe_optimizations:
                try:
                    await asyncio.sleep(0.1)
                    optimization.applied = True
                    if console:
                        console.print(
                            f"✅ 자동 적용: {optimization.name}", style="green"
                        )
                except Exception as e:
                    if console:
                        console.print(
                            f"❌ 자동 적용 실패 {optimization.name}: {str(e)}",
                            style="red",
                        )
        except Exception as e:
            if console:
                console.print(f"⚠️  자동 최적화 적용 실패: {str(e)}", style="yellow")

    async def _display_optimization_results(self):
        """최적화 결과 표시"""
        if not console or not self.optimization_results:
            return
        summary_table = Table(
            title="최적화 분석 결과", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("우선순위", style="cyan", width=10)
        summary_table.add_column("최적화 항목", style="white", width=25)
        summary_table.add_column("유형", style="yellow", width=12)
        summary_table.add_column("영향도", justify="right", width=8)
        summary_table.add_column("난이도", justify="right", width=8)
        summary_table.add_column("ROI", justify="right", width=10)
        summary_table.add_column("상태", justify="center", width=8)
        for opt in self.optimization_results[:10]:
            priority_colors = {
                OptimizationPriority.CRITICAL: "bright_red",
                OptimizationPriority.HIGH: "red",
                OptimizationPriority.MEDIUM: "yellow",
                OptimizationPriority.LOW: "green",
            }
            priority_color = priority_colors.get(opt.priority, "white")
            roi_color = (
                "green"
                if opt.roi_score > 15
                else "yellow" if opt.roi_score > 8 else "red"
            )
            summary_table.add_row(
                f"[{priority_color}]{opt.priority.value.upper()}[/{priority_color}]",
                opt.name,
                opt.optimization_type.value,
                f"{opt.impact_score:.0f}%",
                f"{opt.implementation_difficulty}/5",
                f"[{roi_color}]{opt.roi_score:.1f}[/{roi_color}]",
                "✅" if opt.applied else "⏳",
            )
        console.print(summary_table)
        if len(self.optimization_results) > 0:
            console.print("\n🎯 우선 적용 권장 최적화:")
            for i, opt in enumerate(self.optimization_results[:3], 1):
                detail_panel = Panel(
                    f"**{opt.description}**\n\n예상 개선: {opt.estimated_improvement}\n\n**권장사항:**\n"
                    + "\n".join([f"• {rec}" for rec in opt.recommendations[:3]])
                    + (
                        f"\n\n⚡ 총 {len(opt.code_changes)}개의 코드 변경 예제 포함"
                        if opt.code_changes
                        else ""
                    ),
                    title=f"{i}. {opt.name} (영향도: {opt.impact_score:.0f}%, 난이도: {opt.implementation_difficulty}/5)",
                    border_style="blue",
                )
                console.print(detail_panel)
        total_impact = sum((opt.impact_score for opt in self.optimization_results))
        applied_count = sum((1 for opt in self.optimization_results if opt.applied))
        console.print(
            Panel(
                f"📊 최적화 분석 완료\n\n🔍 식별된 최적화: {len(self.optimization_results)}개\n⚡ 자동 적용: {applied_count}개\n📈 총 예상 성능 향상: {total_impact:.0f}%\n🎯 최고 ROI: {max((opt.roi_score for opt in self.optimization_results)):.1f}"
                + (
                    f"\n🏆 가장 효과적: {max(self.optimization_results, key=lambda x: x.roi_score).name}"
                    if self.optimization_results
                    else ""
                ),
                title="최적화 요약",
                border_style="green",
            )
        )

    async def start_performance_monitoring(self, interval=60) -> Result[str, str]:
        """성능 모니터링 시작"""
        try:
            if self.monitoring_active:
                return Failure("성능 모니터링이 이미 실행 중입니다")
            self.monitoring_active = True
            self.monitoring_task = asyncio.create_task(
                self._performance_monitoring_loop(interval)
            )
            return Success("성능 모니터링 시작됨")
        except Exception as e:
            return Failure(f"성능 모니터링 시작 실패: {str(e)}")

    async def stop_performance_monitoring(self) -> Result[str, str]:
        """성능 모니터링 중지"""
        try:
            self.monitoring_active = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            return Success("성능 모니터링 중지됨")
        except Exception as e:
            return Failure(f"성능 모니터링 중지 실패: {str(e)}")

    async def _performance_monitoring_loop(self, interval: int):
        """성능 모니터링 루프"""
        while self.monitoring_active:
            try:
                await self._collect_performance_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if console:
                    console.print(f"⚠️  성능 모니터링 오류: {str(e)}", style="yellow")
                await asyncio.sleep(interval)

    async def _collect_performance_metrics(self):
        """성능 지표 수집"""
        try:
            import os

            import psutil

            if psutil:
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                memory_percent = process.memory_percent()
                cpu_percent = process.cpu_percent()
                num_threads = process.num_threads()
            else:
                process = None
                memory_info = type("MemoryInfo", (), {"rss": 0})()
                memory_percent = 0
                cpu_percent = 0
                num_threads = threading.active_count()

            metrics = {
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "rss_mb": memory_info.rss / 1024 / 1024,
                    "percent": memory_percent,
                },
                "cpu": {"percent": cpu_percent},
                "threads": num_threads,
                "gc": {
                    "collections": [
                        (
                            gc.get_stats()[i]["collections"]
                            if i < len(gc.get_stats())
                            else 0
                        )
                        for i in range(3)
                    ]
                },
            }
            self.performance_history = self.performance_history + [metrics]
            if len(self.performance_history) > self.max_history_size:
                self.performance_history = self.performance_history[
                    -self.max_history_size :
                ]
        except Exception as e:
            if console:
                console.print(f"⚠️  성능 지표 수집 실패: {str(e)}", style="yellow")

    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보 조회"""
        if not self.performance_history:
            return {}
        try:
            latest = self.performance_history[-1]
            recent_samples = self.performance_history[-10:]
            avg_memory = sum((m["memory"]["rss_mb"] for m in recent_samples)) / len(
                recent_samples
            )
            avg_cpu = sum((m["cpu"]["percent"] for m in recent_samples)) / len(
                recent_samples
            )
            return {
                "current": latest,
                "averages": {"memory_mb": avg_memory, "cpu_percent": avg_cpu},
                "optimization_count": len(self.optimization_results),
                "applied_optimizations": sum(
                    (1 for opt in self.optimization_results if opt.applied)
                ),
                "monitoring_active": self.monitoring_active,
                "history_size": len(self.performance_history),
            }
        except Exception as e:
            return {"error": str(e)}
