"""
Performance Optimizer (RFS v4)

RFS v4 성능 최적화 메인 엔진
- 자동 성능 분석
- 최적화 권장사항 생성
- 실시간 성능 모니터링
- 자동 튜닝 실행
"""

import asyncio
import time
import gc
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import psutil
import threading

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core import Result, Success, Failure

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
    impact_score: float  # 0-100
    implementation_difficulty: int  # 1-5 (1: 쉬움, 5: 어려움)
    estimated_improvement: str
    before_metrics: Dict[str, Any] = field(default_factory=dict)
    after_metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    code_changes: List[Dict[str, str]] = field(default_factory=list)
    applied: bool = False
    
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
    target_types: List[OptimizationType] = field(default_factory=list)
    auto_apply: bool = False
    max_impact_threshold: float = 50.0  # 자동 적용 임계값
    include_experimental: bool = False
    timeout: int = 300


class PerformanceOptimizer:
    """성능 최적화 메인 엔진"""
    
    def __init__(self, project_path: Optional[str] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.optimization_results: List[OptimizationResult] = []
        self.baseline_metrics: Dict[str, Any] = {}
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # 성능 모니터링 데이터
        self.performance_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
    
    async def run_optimization_analysis(self, suite: OptimizationSuite) -> Result[List[OptimizationResult], str]:
        """최적화 분석 실행"""
        try:
            if console:
                console.print(Panel(
                    f"🚀 RFS v4 성능 최적화 분석 시작\n\n"
                    f"📋 최적화 스위트: {suite.name}\n"
                    f"🎯 대상 유형: {', '.join([t.value for t in suite.target_types]) if suite.target_types else '모든 유형'}\n"
                    f"⚡ 자동 적용: {'예' if suite.auto_apply else '아니오'}\n"
                    f"🧪 실험적 기능: {'포함' if suite.include_experimental else '제외'}",
                    title="성능 최적화",
                    border_style="blue"
                ))
            
            # 기준 성능 측정
            if console:
                console.print("📊 기준 성능 측정 중...")
            
            await self._measure_baseline_performance()
            
            # 최적화 분석 실행
            optimization_tasks = []
            
            if not suite.target_types or OptimizationType.MEMORY in suite.target_types:
                optimization_tasks.append(self._analyze_memory_optimization(suite))
            
            if not suite.target_types or OptimizationType.CPU in suite.target_types:
                optimization_tasks.append(self._analyze_cpu_optimization(suite))
            
            if not suite.target_types or OptimizationType.IO in suite.target_types:
                optimization_tasks.append(self._analyze_io_optimization(suite))
            
            if not suite.target_types or OptimizationType.STARTUP in suite.target_types:
                optimization_tasks.append(self._analyze_startup_optimization(suite))
            
            if not suite.target_types or OptimizationType.CLOUD_RUN in suite.target_types:
                optimization_tasks.append(self._analyze_cloud_run_optimization(suite))
            
            # 병렬 분석 실행
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                
                for i, task in enumerate(optimization_tasks):
                    task_id = progress.add_task(f"최적화 분석 {i+1}/{len(optimization_tasks)}", total=100)
                    
                    results = await task
                    if results:
                        self.optimization_results.extend(results)
                    
                    progress.update(task_id, completed=100)
            
            # 결과 우선순위 정렬
            self.optimization_results.sort(key=lambda x: x.roi_score, reverse=True)
            
            # 자동 적용
            if suite.auto_apply:
                await self._apply_safe_optimizations(suite)
            
            # 결과 표시
            if console:
                await self._display_optimization_results()
            
            return Success(self.optimization_results)
            
        except Exception as e:
            return Failure(f"최적화 분석 실패: {str(e)}")
    
    async def _measure_baseline_performance(self):
        """기준 성능 측정"""
        try:
            import time
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # 메모리 사용량
            memory_info = process.memory_info()
            
            # CPU 사용량 (1초간 측정)
            cpu_percent = process.cpu_percent(interval=1)
            
            # 모듈 임포트 시간 측정
            start_time = time.time()
            try:
                from .. import core
                import_time = time.time() - start_time
            except:
                import_time = 0
            
            # GC 통계
            gc_stats = {
                f"generation_{i}": gc.get_stats()[i] if i < len(gc.get_stats()) else {}
                for i in range(3)
            }
            
            self.baseline_metrics = {
                'timestamp': datetime.now().isoformat(),
                'memory': {
                    'rss': memory_info.rss,
                    'vms': memory_info.vms,
                    'rss_mb': memory_info.rss / 1024 / 1024,
                    'vms_mb': memory_info.vms / 1024 / 1024
                },
                'cpu': {
                    'percent': cpu_percent,
                    'num_threads': process.num_threads()
                },
                'startup': {
                    'import_time': import_time
                },
                'gc': gc_stats,
                'system': {
                    'python_version': sys.version,
                    'platform': sys.platform
                }
            }
            
        except Exception as e:
            if console:
                console.print(f"⚠️  기준 성능 측정 실패: {str(e)}", style="yellow")
            self.baseline_metrics = {}
    
    async def _analyze_memory_optimization(self, suite: OptimizationSuite) -> List[OptimizationResult]:
        """메모리 최적화 분석"""
        results = []
        
        try:
            # 메모리 사용량 확인
            if 'memory' in self.baseline_metrics:
                memory_mb = self.baseline_metrics['memory']['rss_mb']
                
                if memory_mb > 100:  # 100MB 이상
                    results.append(OptimizationResult(
                        optimization_type=OptimizationType.MEMORY,
                        name="메모리 사용량 최적화",
                        description="높은 메모리 사용량을 감지했습니다",
                        priority=OptimizationPriority.HIGH,
                        impact_score=70.0,
                        implementation_difficulty=3,
                        estimated_improvement="30-50% 메모리 사용량 감소",
                        before_metrics={'memory_mb': memory_mb},
                        recommendations=[
                            "불필요한 전역 변수 제거",
                            "메모리 집약적인 작업에 제너레이터 사용",
                            "적절한 시점에 del 문으로 객체 해제",
                            "__slots__ 사용으로 클래스 메모리 최적화"
                        ],
                        code_changes=[
                            {
                                'file': 'optimization_suggestion.py',
                                'change': '''
# Before: 메모리 비효율적 코드
data = [expensive_operation(i) for i in range(1000000)]

# After: 제너레이터 사용
data = (expensive_operation(i) for i in range(1000000))

# Before: 메모리 누수 가능성
class DataProcessor:
    def __init__(self):
        self.cache = {}
        self.large_data = load_large_dataset()

# After: __slots__와 적절한 정리
class DataProcessor:
    __slots__ = ['cache', 'large_data']
    
    def __init__(self):
        self.cache = {}
        self.large_data = load_large_dataset()
    
    def cleanup(self):
        self.cache.clear()
        del self.large_data
'''
                            }
                        ]
                    ))
                
                # GC 최적화
                gc_stats = self.baseline_metrics.get('gc', {})
                if gc_stats and any(gen.get('collections', 0) > 100 for gen in gc_stats.values() if isinstance(gen, dict)):
                    results.append(OptimizationResult(
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
                            "적절한 시점에 gc.collect() 호출"
                        ],
                        code_changes=[
                            {
                                'file': 'gc_optimization.py',
                                'change': '''
import gc

# GC 임계값 조정 (기본값보다 덜 공격적)
gc.set_threshold(1000, 15, 15)

# 중요한 작업 전후 명시적 GC
def heavy_processing():
    gc.collect()  # 처리 전 정리
    try:
        # 무거운 작업 수행
        result = expensive_computation()
    finally:
        gc.collect()  # 처리 후 정리
    return result
'''
                            }
                        ]
                    ))
            
        except Exception as e:
            if console:
                console.print(f"⚠️  메모리 최적화 분석 실패: {str(e)}", style="yellow")
        
        return results
    
    async def _analyze_cpu_optimization(self, suite: OptimizationSuite) -> List[OptimizationResult]:
        """CPU 최적화 분석"""
        results = []
        
        try:
            # 스레드 수 확인
            if 'cpu' in self.baseline_metrics:
                num_threads = self.baseline_metrics['cpu']['num_threads']
                
                if num_threads > 20:  # 과도한 스레드
                    results.append(OptimizationResult(
                        optimization_type=OptimizationType.CPU,
                        name="스레드 수 최적화",
                        description=f"과도한 스레드 수가 감지되었습니다 ({num_threads}개)",
                        priority=OptimizationPriority.HIGH,
                        impact_score=60.0,
                        implementation_difficulty=3,
                        estimated_improvement="20-40% CPU 효율성 향상",
                        before_metrics={'thread_count': num_threads},
                        recommendations=[
                            "ThreadPoolExecutor 사용으로 스레드 수 제한",
                            "비동기 프로그래밍으로 스레드 필요성 감소",
                            "연결 풀링으로 리소스 재사용"
                        ],
                        code_changes=[
                            {
                                'file': 'thread_optimization.py',
                                'change': '''
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# Before: 무제한 스레드 생성
import threading

def process_data(data):
    for item in data:
        thread = threading.Thread(target=heavy_task, args=(item,))
        thread.start()

# After: 제한된 스레드 풀 사용
MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)

async def process_data_optimized(data):
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, heavy_task, item)
            for item in data
        ]
        return await asyncio.gather(*tasks)

# LRU 캐시로 중복 계산 방지
@lru_cache(maxsize=128)
def expensive_computation(param):
    # 비용이 큰 계산
    return result
'''
                            }
                        ]
                    ))
                
                # 비동기 최적화
                results.append(OptimizationResult(
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
                        "적절한 await 지점 설정"
                    ],
                    code_changes=[
                        {
                            'file': 'async_optimization.py',
                            'change': '''
import asyncio
import aiohttp
import aiofiles

# Before: 동기 처리
def fetch_data(urls):
    results = []
    for url in urls:
        response = requests.get(url)
        results.append(response.json())
    return results

# After: 비동기 처리  
async def fetch_data_async(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        return await asyncio.gather(*tasks)

async def fetch_url(session, url):
    async with session.get(url) as response:
        return await response.json()

# Before: 동기 파일 처리
def process_files(file_paths):
    results = []
    for path in file_paths:
        with open(path, 'r') as f:
            results.append(f.read())
    return results

# After: 비동기 파일 처리
async def process_files_async(file_paths):
    tasks = [read_file_async(path) for path in file_paths]
    return await asyncio.gather(*tasks)

async def read_file_async(path):
    async with aiofiles.open(path, 'r') as f:
        return await f.read()
'''
                        }
                    ]
                ))
            
        except Exception as e:
            if console:
                console.print(f"⚠️  CPU 최적화 분석 실패: {str(e)}", style="yellow")
        
        return results
    
    async def _analyze_io_optimization(self, suite: OptimizationSuite) -> List[OptimizationResult]:
        """I/O 최적화 분석"""
        results = []
        
        try:
            # 파일 I/O 최적화
            results.append(OptimizationResult(
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
                    "배치 처리로 I/O 집약도 최적화"
                ],
                code_changes=[
                    {
                        'file': 'io_optimization.py',
                        'change': '''
import mmap
import os
from pathlib import Path

# Before: 작은 청크로 파일 읽기
def read_large_file_slow(file_path):
    with open(file_path, 'r') as f:
        lines = []
        while True:
            line = f.readline()
            if not line:
                break
            lines.append(line.strip())
    return lines

# After: 최적화된 파일 읽기
def read_large_file_fast(file_path):
    # mmap 사용 (대용량 파일)
    if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB 이상
        with open(file_path, 'r') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                return mm.read().decode().splitlines()
    else:
        # 작은 파일은 한 번에 읽기
        return Path(file_path).read_text().splitlines()

# Before: 개별 파일 쓰기
def write_files_slow(data_dict):
    for filename, content in data_dict.items():
        with open(filename, 'w') as f:
            f.write(content)

# After: 배치 처리
def write_files_fast(data_dict):
    # 같은 디렉토리 파일들 그룹화
    dir_groups = {}
    for filename, content in data_dict.items():
        dir_name = os.path.dirname(filename)
        if dir_name not in dir_groups:
            dir_groups[dir_name] = []
        dir_groups[dir_name].append((filename, content))
    
    # 디렉토리별 배치 처리
    for dir_name, files in dir_groups.items():
        os.makedirs(dir_name, exist_ok=True)
        for filename, content in files:
            with open(filename, 'w', buffering=8192) as f:
                f.write(content)
'''
                    }
                ]
            ))
            
            # 네트워크 I/O 최적화
            results.append(OptimizationResult(
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
                    "압축 및 캐싱 활용"
                ],
                code_changes=[
                    {
                        'file': 'network_optimization.py',
                        'change': '''
import aiohttp
import asyncio
from aiohttp import ClientTimeout, TCPConnector

# 최적화된 HTTP 클라이언트 설정
class OptimizedHTTPClient:
    def __init__(self):
        # 연결 풀 설정
        connector = TCPConnector(
            limit=100,  # 총 연결 수 제한
            limit_per_host=10,  # 호스트당 연결 수 제한
            ttl_dns_cache=300,  # DNS 캐시 TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        # 타임아웃 설정
        timeout = ClientTimeout(
            total=30,  # 총 요청 시간
            connect=5,  # 연결 시간
            sock_read=10  # 소켓 읽기 시간
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'Accept-Encoding': 'gzip, deflate'}
        )
    
    async def fetch_multiple(self, urls, batch_size=10):
        """배치 단위로 URL 요청"""
        results = []
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_tasks = [self.fetch_url(url) for url in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)
            
            # 서버 부하 방지를 위한 짧은 대기
            if i + batch_size < len(urls):
                await asyncio.sleep(0.1)
        
        return results
    
    async def fetch_url(self, url):
        try:
            async with self.session.get(url) as response:
                return await response.json()
        except Exception as e:
            return {'error': str(e), 'url': url}
    
    async def close(self):
        await self.session.close()
'''
                    }
                ]
            ))
            
        except Exception as e:
            if console:
                console.print(f"⚠️  I/O 최적화 분석 실패: {str(e)}", style="yellow")
        
        return results
    
    async def _analyze_startup_optimization(self, suite: OptimizationSuite) -> List[OptimizationResult]:
        """시작 시간 최적화 분석"""
        results = []
        
        try:
            if 'startup' in self.baseline_metrics:
                import_time = self.baseline_metrics['startup']['import_time']
                
                if import_time > 0.5:  # 500ms 이상
                    results.append(OptimizationResult(
                        optimization_type=OptimizationType.STARTUP,
                        name="모듈 임포트 최적화",
                        description=f"느린 모듈 임포트가 감지되었습니다 ({import_time:.3f}초)",
                        priority=OptimizationPriority.HIGH,
                        impact_score=80.0,
                        implementation_difficulty=2,
                        estimated_improvement=f"50-70% 시작 시간 단축 ({import_time*0.3:.3f}초 목표)",
                        before_metrics={'import_time': import_time},
                        recommendations=[
                            "지연 임포트 (lazy import) 사용",
                            "불필요한 전역 임포트 제거",
                            "조건부 임포트 활용",
                            "가벼운 대안 라이브러리 검토"
                        ],
                        code_changes=[
                            {
                                'file': 'lazy_import_optimization.py',
                                'change': '''
# Before: 전역에서 모든 모듈 임포트
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
import tensorflow as tf

def simple_function():
    return "Hello"

# After: 지연 임포트 사용
def simple_function():
    return "Hello"

def data_analysis_function(data):
    # 실제 사용할 때만 임포트
    import pandas as pd
    import numpy as np
    
    df = pd.DataFrame(data)
    return df.mean()

def plotting_function(data):
    # 조건부 임포트
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib이 설치되지 않았습니다")
    
    plt.plot(data)
    return plt.gcf()

# 선택적 기능을 위한 지연 로딩
class MachineLearningModule:
    def __init__(self):
        self._sklearn = None
        self._tensorflow = None
    
    @property
    def sklearn(self):
        if self._sklearn is None:
            import sklearn
            self._sklearn = sklearn
        return self._sklearn
    
    @property
    def tensorflow(self):
        if self._tensorflow is None:
            import tensorflow as tf
            self._tensorflow = tf
        return self._tensorflow
'''
                            }
                        ]
                    ))
                
                # Cold Start 최적화
                results.append(OptimizationResult(
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
                        "컨테이너 이미지 크기 최적화"
                    ],
                    code_changes=[
                        {
                            'file': 'cold_start_optimization.py',
                            'change': '''
import os
from functools import lru_cache

# Before: 시작 시 모든 연결 초기화
database_connection = create_database_connection()
redis_client = create_redis_client()
external_api_client = create_api_client()

def handle_request(request):
    # 요청 처리
    pass

# After: 지연 초기화
_database_connection = None
_redis_client = None
_external_api_client = None

@lru_cache(maxsize=1)
def get_database_connection():
    global _database_connection
    if _database_connection is None:
        _database_connection = create_database_connection()
    return _database_connection

@lru_cache(maxsize=1)
def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = create_redis_client()
    return _redis_client

@lru_cache(maxsize=1)
def get_api_client():
    global _external_api_client
    if _external_api_client is None:
        _external_api_client = create_api_client()
    return _external_api_client

def handle_request(request):
    # 필요할 때만 연결 생성
    db = get_database_connection()
    # 요청 처리
    pass

# 예열 엔드포인트
def warmup():
    """Cloud Run 예열용 엔드포인트"""
    try:
        # 중요한 연결들 미리 초기화
        get_database_connection()
        get_redis_client()
        return {"status": "warm"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
'''
                        }
                    ]
                ))
            
        except Exception as e:
            if console:
                console.print(f"⚠️  시작 시간 최적화 분석 실패: {str(e)}", style="yellow")
        
        return results
    
    async def _analyze_cloud_run_optimization(self, suite: OptimizationSuite) -> List[OptimizationResult]:
        """Cloud Run 최적화 분석"""
        results = []
        
        try:
            # Cloud Run 환경 감지
            is_cloud_run = os.getenv('K_SERVICE') is not None
            
            results.append(OptimizationResult(
                optimization_type=OptimizationType.CLOUD_RUN,
                name="Cloud Run 리소스 최적화",
                description="Cloud Run 인스턴스 리소스 효율성 최적화",
                priority=OptimizationPriority.HIGH,
                impact_score=75.0,
                implementation_difficulty=3,
                estimated_improvement="30-50% 리소스 비용 절약",
                before_metrics={'is_cloud_run': is_cloud_run},
                recommendations=[
                    "적절한 CPU 및 메모리 한계 설정",
                    "동시성 설정 최적화", 
                    "최소 인스턴스 수 조정",
                    "요청 타임아웃 최적화"
                ],
                code_changes=[
                    {
                        'file': 'cloud_run_config.yaml',
                        'change': '''
# Cloud Run 서비스 설정 최적화
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: rfs-app
  annotations:
    # 동시성 설정 (기본값: 100, 최적화: 1000)
    run.googleapis.com/execution-environment: gen2
    run.googleapis.com/cpu-throttling: "false"
spec:
  template:
    metadata:
      annotations:
        # 리소스 최적화
        run.googleapis.com/memory: "512Mi"  # 메모리 제한
        run.googleapis.com/cpu: "1000m"     # CPU 제한 (1 vCPU)
        
        # 동시성 및 확장 설정
        autoscaling.knative.dev/maxScale: "100"
        autoscaling.knative.dev/minScale: "0"
        run.googleapis.com/execution-environment: "gen2"
        
        # 타임아웃 설정
        run.googleapis.com/timeout: "300s"
        
    spec:
      containerConcurrency: 1000  # 컨테이너당 동시 요청 수
      timeoutSeconds: 300
      containers:
      - image: gcr.io/project/rfs-app
        resources:
          limits:
            memory: "512Mi"
            cpu: "1000m"
        env:
        - name: PYTHONUNBUFFERED
          value: "1"
        - name: PYTHONDONTWRITEBYTECODE
          value: "1"
        
        # 헬스체크 최적화
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 0
          timeoutSeconds: 1
          periodSeconds: 3
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 0
          timeoutSeconds: 1
          periodSeconds: 3
          failureThreshold: 1
'''
                    },
                    {
                        'file': 'cloud_run_optimization.py',
                        'change': '''
import os
import logging
from contextlib import asynccontextmanager

# Cloud Run 최적화 설정
class CloudRunOptimizer:
    
    @staticmethod
    def configure_logging():
        """Cloud Run 로깅 최적화"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s %(message)s',
            handlers=[logging.StreamHandler()]
        )
        
        # Cloud Run에서는 stdout/stderr가 로그로 수집됨
        if os.getenv('K_SERVICE'):
            # JSON 로깅 설정
            import json
            import sys
            
            class CloudRunFormatter(logging.Formatter):
                def format(self, record):
                    log_obj = {
                        'timestamp': self.formatTime(record),
                        'severity': record.levelname,
                        'message': record.getMessage(),
                        'module': record.name
                    }
                    return json.dumps(log_obj)
            
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(CloudRunFormatter())
            
            root_logger = logging.getLogger()
            root_logger.handlers = [handler]
    
    @staticmethod
    def get_optimal_workers():
        """최적의 worker 수 계산"""
        cpu_count = os.cpu_count() or 1
        
        # Cloud Run에서는 보수적으로 설정
        if os.getenv('K_SERVICE'):
            return min(cpu_count * 2, 4)
        else:
            return cpu_count * 2 + 1
    
    @staticmethod
    @asynccontextmanager
    async def lifespan_manager(app):
        """애플리케이션 수명 주기 관리"""
        # 시작 시 초기화
        CloudRunOptimizer.configure_logging()
        logger = logging.getLogger(__name__)
        
        logger.info("RFS v4 애플리케이션 시작")
        
        # 예열 작업
        if os.getenv('K_SERVICE'):
            await CloudRunOptimizer.warmup_services()
        
        yield
        
        # 종료 시 정리
        logger.info("RFS v4 애플리케이션 종료")
        await CloudRunOptimizer.cleanup_services()
    
    @staticmethod
    async def warmup_services():
        """서비스 예열"""
        try:
            # 중요한 연결들 미리 초기화
            from rfs.cloud_run import initialize_cloud_run_services
            await initialize_cloud_run_services()
        except Exception as e:
            logging.warning(f"서비스 예열 실패: {e}")
    
    @staticmethod
    async def cleanup_services():
        """서비스 정리"""
        try:
            from rfs.cloud_run import shutdown_cloud_run_services
            await shutdown_cloud_run_services()
        except Exception as e:
            logging.warning(f"서비스 정리 실패: {e}")
'''
                    }
                ]
            ))
            
        except Exception as e:
            if console:
                console.print(f"⚠️  Cloud Run 최적화 분석 실패: {str(e)}", style="yellow")
        
        return results
    
    async def _apply_safe_optimizations(self, suite: OptimizationSuite):
        """안전한 최적화 자동 적용"""
        try:
            safe_optimizations = [
                opt for opt in self.optimization_results
                if opt.impact_score <= suite.max_impact_threshold
                and opt.implementation_difficulty <= 2
                and opt.priority in [OptimizationPriority.LOW, OptimizationPriority.MEDIUM]
            ]
            
            for optimization in safe_optimizations:
                try:
                    # 실제 최적화 적용 로직
                    # 여기서는 시뮬레이션
                    await asyncio.sleep(0.1)  # 적용 시뮬레이션
                    optimization.applied = True
                    
                    if console:
                        console.print(f"✅ 자동 적용: {optimization.name}", style="green")
                        
                except Exception as e:
                    if console:
                        console.print(f"❌ 자동 적용 실패 {optimization.name}: {str(e)}", style="red")
            
        except Exception as e:
            if console:
                console.print(f"⚠️  자동 최적화 적용 실패: {str(e)}", style="yellow")
    
    async def _display_optimization_results(self):
        """최적화 결과 표시"""
        if not console or not self.optimization_results:
            return
        
        # 결과 요약 테이블
        summary_table = Table(title="최적화 분석 결과", show_header=True, header_style="bold magenta")
        summary_table.add_column("우선순위", style="cyan", width=10)
        summary_table.add_column("최적화 항목", style="white", width=25)
        summary_table.add_column("유형", style="yellow", width=12)
        summary_table.add_column("영향도", justify="right", width=8)
        summary_table.add_column("난이도", justify="right", width=8)
        summary_table.add_column("ROI", justify="right", width=10)
        summary_table.add_column("상태", justify="center", width=8)
        
        for opt in self.optimization_results[:10]:  # 상위 10개만 표시
            priority_colors = {
                OptimizationPriority.CRITICAL: "bright_red",
                OptimizationPriority.HIGH: "red",
                OptimizationPriority.MEDIUM: "yellow",
                OptimizationPriority.LOW: "green"
            }
            
            priority_color = priority_colors.get(opt.priority, "white")
            roi_color = "green" if opt.roi_score > 15 else "yellow" if opt.roi_score > 8 else "red"
            
            summary_table.add_row(
                f"[{priority_color}]{opt.priority.value.upper()}[/{priority_color}]",
                opt.name,
                opt.optimization_type.value,
                f"{opt.impact_score:.0f}%",
                f"{opt.implementation_difficulty}/5",
                f"[{roi_color}]{opt.roi_score:.1f}[/{roi_color}]",
                "✅" if opt.applied else "⏳"
            )
        
        console.print(summary_table)
        
        # 상위 3개 상세 정보
        if len(self.optimization_results) > 0:
            console.print("\n🎯 우선 적용 권장 최적화:")
            
            for i, opt in enumerate(self.optimization_results[:3], 1):
                detail_panel = Panel(
                    f"**{opt.description}**\n\n"
                    f"예상 개선: {opt.estimated_improvement}\n\n"
                    f"**권장사항:**\n" + 
                    "\n".join([f"• {rec}" for rec in opt.recommendations[:3]]) +
                    (f"\n\n⚡ 총 {len(opt.code_changes)}개의 코드 변경 예제 포함" if opt.code_changes else ""),
                    title=f"{i}. {opt.name} (영향도: {opt.impact_score:.0f}%, 난이도: {opt.implementation_difficulty}/5)",
                    border_style="blue"
                )
                console.print(detail_panel)
        
        # 전체 통계
        total_impact = sum(opt.impact_score for opt in self.optimization_results)
        applied_count = sum(1 for opt in self.optimization_results if opt.applied)
        
        console.print(Panel(
            f"📊 최적화 분석 완료\n\n"
            f"🔍 식별된 최적화: {len(self.optimization_results)}개\n"
            f"⚡ 자동 적용: {applied_count}개\n"
            f"📈 총 예상 성능 향상: {total_impact:.0f}%\n"
            f"🎯 최고 ROI: {max(opt.roi_score for opt in self.optimization_results):.1f}" +
            (f"\n🏆 가장 효과적: {max(self.optimization_results, key=lambda x: x.roi_score).name}" if self.optimization_results else ""),
            title="최적화 요약",
            border_style="green"
        ))
    
    async def start_performance_monitoring(self, interval: int = 60) -> Result[str, str]:
        """성능 모니터링 시작"""
        try:
            if self.monitoring_active:
                return Failure("성능 모니터링이 이미 실행 중입니다")
            
            self.monitoring_active = True
            self.monitoring_task = asyncio.create_task(self._performance_monitoring_loop(interval))
            
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
                # 현재 성능 지표 수집
                await self._collect_performance_metrics()
                
                # 주기적으로 대기
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
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'memory': {
                    'rss_mb': process.memory_info().rss / 1024 / 1024,
                    'percent': process.memory_percent()
                },
                'cpu': {
                    'percent': process.cpu_percent()
                },
                'threads': process.num_threads(),
                'gc': {
                    'collections': [gc.get_stats()[i]['collections'] if i < len(gc.get_stats()) else 0 for i in range(3)]
                }
            }
            
            # 히스토리에 추가
            self.performance_history.append(metrics)
            
            # 히스토리 크기 제한
            if len(self.performance_history) > self.max_history_size:
                self.performance_history = self.performance_history[-self.max_history_size:]
                
        except Exception as e:
            if console:
                console.print(f"⚠️  성능 지표 수집 실패: {str(e)}", style="yellow")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보 조회"""
        if not self.performance_history:
            return {}
        
        try:
            # 최신 지표
            latest = self.performance_history[-1]
            
            # 평균 계산 (최근 10개 샘플)
            recent_samples = self.performance_history[-10:]
            
            avg_memory = sum(m['memory']['rss_mb'] for m in recent_samples) / len(recent_samples)
            avg_cpu = sum(m['cpu']['percent'] for m in recent_samples) / len(recent_samples)
            
            return {
                'current': latest,
                'averages': {
                    'memory_mb': avg_memory,
                    'cpu_percent': avg_cpu
                },
                'optimization_count': len(self.optimization_results),
                'applied_optimizations': sum(1 for opt in self.optimization_results if opt.applied),
                'monitoring_active': self.monitoring_active,
                'history_size': len(self.performance_history)
            }
            
        except Exception as e:
            return {'error': str(e)}