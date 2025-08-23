"""
I/O Optimization Engine for RFS Framework

I/O 성능 최적화, 버퍼링 전략, 압축 최적화
- 디스크 I/O 최적화
- 네트워크 I/O 최적화  
- 버퍼링 및 캐싱 전략
- 압축 및 직렬화 최적화
"""

import asyncio
import aiofiles
import aiohttp
import time
import os
import gzip
import zlib
import pickle
import json
from typing import Dict, List, Optional, Any, Union, BinaryIO, TextIO, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import threading
from pathlib import Path
import hashlib

from rfs.core.result import Result, Success, Failure
from rfs.core.config import get_config
from rfs.reactive.mono import Mono
from rfs.events.event import Event

class IOOptimizationStrategy(Enum):
    """I/O 최적화 전략"""
    THROUGHPUT = "throughput"      # 처리량 최적화
    LATENCY = "latency"           # 지연시간 최적화
    BALANCED = "balanced"         # 균형 최적화
    MEMORY_EFFICIENT = "memory"   # 메모리 효율적

class BufferingStrategy(Enum):
    """버퍼링 전략"""
    NO_BUFFER = "no_buffer"       # 버퍼링 없음
    SMALL_BUFFER = "small"        # 작은 버퍼 (4KB)
    MEDIUM_BUFFER = "medium"      # 중간 버퍼 (64KB)
    LARGE_BUFFER = "large"        # 큰 버퍼 (1MB)
    ADAPTIVE = "adaptive"         # 적응형 버퍼링

class CompressionStrategy(Enum):
    """압축 전략"""
    NONE = "none"                 # 압축 없음
    GZIP = "gzip"                # GZIP 압축
    ZLIB = "zlib"                # ZLIB 압축
    ADAPTIVE = "adaptive"         # 적응형 압축

@dataclass
class IOThresholds:
    """I/O 임계값 설정"""
    disk_read_mb_per_sec: float = 100.0      # 디스크 읽기 속도 임계값
    disk_write_mb_per_sec: float = 80.0      # 디스크 쓰기 속도 임계값
    network_timeout_sec: float = 30.0        # 네트워크 타임아웃
    buffer_size_kb: int = 64                 # 기본 버퍼 크기
    max_concurrent_operations: int = 50       # 최대 동시 작업 수
    cache_size_mb: int = 100                 # 캐시 크기

@dataclass
class IOStats:
    """I/O 통계"""
    disk_reads: int
    disk_writes: int
    network_requests: int
    bytes_read: int
    bytes_written: int
    avg_read_time: float
    avg_write_time: float
    avg_network_time: float
    cache_hit_rate: float
    compression_ratio: float
    optimization_score: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class IOOptimizationConfig:
    """I/O 최적화 설정"""
    strategy: IOOptimizationStrategy = IOOptimizationStrategy.BALANCED
    buffering_strategy: BufferingStrategy = BufferingStrategy.ADAPTIVE
    compression_strategy: CompressionStrategy = CompressionStrategy.ADAPTIVE
    thresholds: IOThresholds = field(default_factory=IOThresholds)
    enable_caching: bool = True
    enable_compression: bool = True
    enable_monitoring: bool = True
    monitoring_interval_seconds: float = 30.0

class IOCache:
    """I/O 캐시 시스템"""
    
    def __init__(self, max_size_mb: int = 100):
        self.max_size = max_size_mb * 1024 * 1024  # bytes
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.sizes: Dict[str, int] = {}
        self.current_size = 0
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()
    
    def _generate_key(self, path: str, params: Dict[str, Any] = None) -> str:
        """캐시 키 생성"""
        key_data = f"{path}:{str(params) if params else ''}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, path: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        key = self._generate_key(path, params)
        
        with self.lock:
            if key in self.cache:
                self.access_times[key] = datetime.now()
                self.hits += 1
                return self.cache[key]['data']
            else:
                self.misses += 1
                return None
    
    def put(self, path: str, data: Any, params: Dict[str, Any] = None) -> bool:
        """캐시에 데이터 저장"""
        key = self._generate_key(path, params)
        
        # 데이터 크기 추정
        try:
            if isinstance(data, (str, bytes)):
                size = len(data)
            else:
                size = len(pickle.dumps(data))
        except:
            size = 1024  # 기본값
        
        with self.lock:
            # 캐시 크기 체크
            if self.current_size + size > self.max_size:
                self._evict_lru(size)
            
            # 데이터 저장
            self.cache[key] = {
                'data': data,
                'created_at': datetime.now()
            }
            self.access_times[key] = datetime.now()
            self.sizes[key] = size
            self.current_size += size
            
            return True
    
    def _evict_lru(self, needed_space: int) -> None:
        """LRU 방식으로 캐시 제거"""
        # 오래된 순으로 정렬
        sorted_items = sorted(self.access_times.items(), key=lambda x: x[1])
        
        for key, _ in sorted_items:
            if self.current_size + needed_space <= self.max_size:
                break
            
            # 항목 제거
            if key in self.cache:
                del self.cache[key]
            if key in self.access_times:
                del self.access_times[key]
            if key in self.sizes:
                self.current_size -= self.sizes[key]
                del self.sizes[key]
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.sizes.clear()
            self.current_size = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / max(1, total_requests)
        
        return {
            'entries': len(self.cache),
            'size_mb': self.current_size / 1024 / 1024,
            'max_size_mb': self.max_size / 1024 / 1024,
            'hit_rate': hit_rate,
            'hits': self.hits,
            'misses': self.misses
        }

class CompressionManager:
    """압축 관리자"""
    
    def __init__(self, strategy: CompressionStrategy = CompressionStrategy.ADAPTIVE):
        self.strategy = strategy
        self.compression_stats = defaultdict(list)
    
    async def compress(self, data: bytes, method: str = None) -> Result[bytes, str]:
        """데이터 압축"""
        try:
            if method is None:
                method = self._select_compression_method(data)
            
            start_time = time.time()
            
            if method == CompressionStrategy.GZIP.value:
                compressed = gzip.compress(data)
            elif method == CompressionStrategy.ZLIB.value:
                compressed = zlib.compress(data)
            else:
                compressed = data  # 압축하지 않음
            
            duration = time.time() - start_time
            ratio = len(compressed) / max(1, len(data))
            
            # 통계 기록
            self.compression_stats[method].append({
                'original_size': len(data),
                'compressed_size': len(compressed),
                'ratio': ratio,
                'duration': duration
            })
            
            return Success(compressed)
            
        except Exception as e:
            return Failure(f"Compression failed: {e}")
    
    async def decompress(self, data: bytes, method: str) -> Result[bytes, str]:
        """데이터 압축 해제"""
        try:
            if method == CompressionStrategy.GZIP.value:
                decompressed = gzip.decompress(data)
            elif method == CompressionStrategy.ZLIB.value:
                decompressed = zlib.decompress(data)
            else:
                decompressed = data  # 압축되지 않음
            
            return Success(decompressed)
            
        except Exception as e:
            return Failure(f"Decompression failed: {e}")
    
    def _select_compression_method(self, data: bytes) -> str:
        """압축 방법 선택"""
        if self.strategy == CompressionStrategy.NONE:
            return CompressionStrategy.NONE.value
        elif self.strategy == CompressionStrategy.GZIP:
            return CompressionStrategy.GZIP.value
        elif self.strategy == CompressionStrategy.ZLIB:
            return CompressionStrategy.ZLIB.value
        elif self.strategy == CompressionStrategy.ADAPTIVE:
            # 데이터 크기와 유형에 따라 적응적 선택
            if len(data) < 1024:  # 작은 데이터는 압축하지 않음
                return CompressionStrategy.NONE.value
            elif len(data) < 100 * 1024:  # 100KB 미만은 ZLIB
                return CompressionStrategy.ZLIB.value
            else:  # 큰 데이터는 GZIP
                return CompressionStrategy.GZIP.value
        
        return CompressionStrategy.NONE.value
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """압축 통계"""
        stats = {}
        
        for method, records in self.compression_stats.items():
            if records:
                avg_ratio = sum(r['ratio'] for r in records) / len(records)
                avg_duration = sum(r['duration'] for r in records) / len(records)
                total_saved = sum(r['original_size'] - r['compressed_size'] for r in records)
                
                stats[method] = {
                    'operations': len(records),
                    'avg_compression_ratio': avg_ratio,
                    'avg_duration': avg_duration,
                    'total_bytes_saved': total_saved
                }
        
        return stats

class DiskIOOptimizer:
    """디스크 I/O 최적화"""
    
    def __init__(self, config: IOOptimizationConfig):
        self.config = config
        self.cache = IOCache(config.thresholds.cache_size_mb) if config.enable_caching else None
        self.compression_manager = CompressionManager(config.compression_strategy)
        self.operation_stats = defaultdict(list)
        self.semaphore = asyncio.Semaphore(config.thresholds.max_concurrent_operations)
    
    def _get_buffer_size(self, file_size: int = None) -> int:
        """최적 버퍼 크기 결정"""
        if self.config.buffering_strategy == BufferingStrategy.NO_BUFFER:
            return 0
        elif self.config.buffering_strategy == BufferingStrategy.SMALL_BUFFER:
            return 4 * 1024
        elif self.config.buffering_strategy == BufferingStrategy.MEDIUM_BUFFER:
            return 64 * 1024
        elif self.config.buffering_strategy == BufferingStrategy.LARGE_BUFFER:
            return 1024 * 1024
        elif self.config.buffering_strategy == BufferingStrategy.ADAPTIVE:
            if file_size and file_size < 64 * 1024:
                return 4 * 1024
            elif file_size and file_size < 1024 * 1024:
                return 64 * 1024
            else:
                return 256 * 1024
        
        return 64 * 1024  # 기본값
    
    async def read_file(self, file_path: str, use_cache: bool = True) -> Result[bytes, str]:
        """파일 읽기 최적화"""
        async with self.semaphore:
            try:
                # 캐시 확인
                if use_cache and self.cache:
                    cached_data = self.cache.get(file_path)
                    if cached_data is not None:
                        return Success(cached_data)
                
                start_time = time.time()
                
                # 파일 정보 확인
                path_obj = Path(file_path)
                if not path_obj.exists():
                    return Failure(f"File not found: {file_path}")
                
                file_size = path_obj.stat().st_size
                buffer_size = self._get_buffer_size(file_size)
                
                # 파일 읽기
                async with aiofiles.open(file_path, 'rb', buffering=buffer_size) as f:
                    data = await f.read()
                
                # 압축 해제 (필요시)
                if file_path.endswith('.gz'):
                    decomp_result = await self.compression_manager.decompress(data, 'gzip')
                    if decomp_result.is_success():
                        data = decomp_result.unwrap()
                
                duration = time.time() - start_time
                
                # 통계 기록
                self.operation_stats['read'].append({
                    'file_path': file_path,
                    'size': len(data),
                    'duration': duration,
                    'speed_mb_per_sec': (len(data) / 1024 / 1024) / max(0.001, duration)
                })
                
                # 캐시 저장
                if use_cache and self.cache:
                    self.cache.put(file_path, data)
                
                return Success(data)
                
            except Exception as e:
                return Failure(f"File read failed: {e}")
    
    async def write_file(self, file_path: str, data: bytes, use_compression: bool = None) -> Result[bool, str]:
        """파일 쓰기 최적화"""
        async with self.semaphore:
            try:
                start_time = time.time()
                
                # 압축 여부 결정
                if use_compression is None:
                    use_compression = self.config.enable_compression and len(data) > 1024
                
                # 데이터 압축
                compressed_data = data
                compression_method = 'none'
                
                if use_compression:
                    comp_result = await self.compression_manager.compress(data)
                    if comp_result.is_success():
                        compressed_data = comp_result.unwrap()
                        compression_method = 'adaptive'
                        
                        # 압축 효율이 낮으면 원본 사용
                        if len(compressed_data) >= len(data) * 0.9:
                            compressed_data = data
                            compression_method = 'none'
                
                # 파일 쓰기
                buffer_size = self._get_buffer_size(len(compressed_data))
                
                # 디렉토리 생성
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(file_path, 'wb', buffering=buffer_size) as f:
                    await f.write(compressed_data)
                    await f.fsync()  # 강제 동기화
                
                duration = time.time() - start_time
                
                # 통계 기록
                self.operation_stats['write'].append({
                    'file_path': file_path,
                    'original_size': len(data),
                    'written_size': len(compressed_data),
                    'compression_method': compression_method,
                    'duration': duration,
                    'speed_mb_per_sec': (len(compressed_data) / 1024 / 1024) / max(0.001, duration)
                })
                
                # 캐시 업데이트
                if self.cache:
                    self.cache.put(file_path, data)
                
                return Success(True)
                
            except Exception as e:
                return Failure(f"File write failed: {e}")
    
    async def read_file_streaming(self, file_path: str, chunk_size: int = None) -> AsyncGenerator[bytes, None]:
        """스트리밍 파일 읽기"""
        try:
            chunk_size = chunk_size or self._get_buffer_size()
            
            async with aiofiles.open(file_path, 'rb') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
        except Exception as e:
            raise Exception(f"Streaming read failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """디스크 I/O 통계"""
        stats = {'cache_stats': self.cache.get_stats() if self.cache else {}}
        
        for operation, records in self.operation_stats.items():
            if records:
                total_operations = len(records)
                total_size = sum(r.get('size', r.get('original_size', 0)) for r in records)
                avg_duration = sum(r['duration'] for r in records) / total_operations
                avg_speed = sum(r['speed_mb_per_sec'] for r in records) / total_operations
                
                stats[f'{operation}_stats'] = {
                    'total_operations': total_operations,
                    'total_mb': total_size / 1024 / 1024,
                    'avg_duration': avg_duration,
                    'avg_speed_mb_per_sec': avg_speed
                }
        
        return stats

class NetworkIOOptimizer:
    """네트워크 I/O 최적화"""
    
    def __init__(self, config: IOOptimizationConfig):
        self.config = config
        self.cache = IOCache(config.thresholds.cache_size_mb // 2) if config.enable_caching else None
        self.session_cache = {}
        self.operation_stats = defaultdict(list)
        self.semaphore = asyncio.Semaphore(config.thresholds.max_concurrent_operations)
    
    async def _get_session(self, base_url: str = None) -> aiohttp.ClientSession:
        """HTTP 세션 획득 (재사용)"""
        session_key = base_url or 'default'
        
        if session_key not in self.session_cache:
            timeout = aiohttp.ClientTimeout(total=self.config.thresholds.network_timeout_sec)
            connector = aiohttp.TCPConnector(
                limit=self.config.thresholds.max_concurrent_operations,
                limit_per_host=10,
                keepalive_timeout=60,
                enable_cleanup_closed=True
            )
            
            self.session_cache[session_key] = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        
        return self.session_cache[session_key]
    
    async def http_get(self, url: str, headers: Dict[str, str] = None, use_cache: bool = True) -> Result[bytes, str]:
        """HTTP GET 최적화"""
        async with self.semaphore:
            try:
                # 캐시 확인
                cache_params = {'headers': headers} if headers else None
                if use_cache and self.cache:
                    cached_data = self.cache.get(url, cache_params)
                    if cached_data is not None:
                        return Success(cached_data)
                
                start_time = time.time()
                session = await self._get_session()
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.read()
                        duration = time.time() - start_time
                        
                        # 통계 기록
                        self.operation_stats['http_get'].append({
                            'url': url,
                            'size': len(data),
                            'duration': duration,
                            'speed_mb_per_sec': (len(data) / 1024 / 1024) / max(0.001, duration)
                        })
                        
                        # 캐시 저장 (GET 요청만)
                        if use_cache and self.cache:
                            self.cache.put(url, data, cache_params)
                        
                        return Success(data)
                    else:
                        return Failure(f"HTTP GET failed: {response.status}")
                
            except Exception as e:
                return Failure(f"HTTP GET failed: {e}")
    
    async def http_post(self, url: str, data: bytes, headers: Dict[str, str] = None) -> Result[bytes, str]:
        """HTTP POST 최적화"""
        async with self.semaphore:
            try:
                start_time = time.time()
                session = await self._get_session()
                
                async with session.post(url, data=data, headers=headers) as response:
                    response_data = await response.read()
                    duration = time.time() - start_time
                    
                    # 통계 기록
                    self.operation_stats['http_post'].append({
                        'url': url,
                        'request_size': len(data),
                        'response_size': len(response_data),
                        'duration': duration,
                        'speed_mb_per_sec': ((len(data) + len(response_data)) / 1024 / 1024) / max(0.001, duration)
                    })
                    
                    if response.status in [200, 201]:
                        return Success(response_data)
                    else:
                        return Failure(f"HTTP POST failed: {response.status}")
                
            except Exception as e:
                return Failure(f"HTTP POST failed: {e}")
    
    async def batch_http_get(self, urls: List[str], max_concurrent: int = 10) -> List[Result[bytes, str]]:
        """배치 HTTP GET"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_one(url: str) -> Result[bytes, str]:
            async with semaphore:
                return await self.http_get(url, use_cache=True)
        
        tasks = [fetch_one(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외를 Result로 변환
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(Failure(str(result)))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def cleanup_sessions(self) -> None:
        """세션 정리"""
        for session in self.session_cache.values():
            if not session.closed:
                await session.close()
        self.session_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """네트워크 I/O 통계"""
        stats = {'cache_stats': self.cache.get_stats() if self.cache else {}}
        
        for operation, records in self.operation_stats.items():
            if records:
                total_operations = len(records)
                
                if operation == 'http_get':
                    total_size = sum(r['size'] for r in records)
                elif operation == 'http_post':
                    total_size = sum(r['request_size'] + r['response_size'] for r in records)
                else:
                    total_size = 0
                
                avg_duration = sum(r['duration'] for r in records) / total_operations
                avg_speed = sum(r['speed_mb_per_sec'] for r in records) / total_operations
                
                stats[f'{operation}_stats'] = {
                    'total_operations': total_operations,
                    'total_mb': total_size / 1024 / 1024,
                    'avg_duration': avg_duration,
                    'avg_speed_mb_per_sec': avg_speed
                }
        
        return stats

class IOOptimizer:
    """I/O 최적화 엔진"""
    
    def __init__(self, config: Optional[IOOptimizationConfig] = None):
        self.config = config or IOOptimizationConfig()
        self.disk_optimizer = DiskIOOptimizer(self.config)
        self.network_optimizer = NetworkIOOptimizer(self.config)
        
        self.monitoring_task: Optional[asyncio.Task] = None
        self.stats_history: deque = deque(maxlen=100)
        self.is_running = False
    
    async def initialize(self) -> Result[bool, str]:
        """I/O 최적화 엔진 초기화"""
        try:
            if self.config.enable_monitoring:
                await self.start_monitoring()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"IO optimizer initialization failed: {e}")
    
    async def start_monitoring(self) -> Result[bool, str]:
        """I/O 모니터링 시작"""
        if self.is_running:
            return Success(True)
            
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to start IO monitoring: {e}")
    
    async def stop_monitoring(self) -> Result[bool, str]:
        """I/O 모니터링 중지"""
        try:
            self.is_running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to stop IO monitoring: {e}")
    
    async def _monitoring_loop(self) -> None:
        """I/O 모니터링 루프"""
        while self.is_running:
            try:
                stats = await self._collect_io_stats()
                if stats.is_success():
                    io_stats = stats.unwrap()
                    self.stats_history.append(io_stats)
                
                await asyncio.sleep(self.config.monitoring_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"IO monitoring error: {e}")
                await asyncio.sleep(self.config.monitoring_interval_seconds)
    
    async def _collect_io_stats(self) -> Result[IOStats, str]:
        """I/O 통계 수집"""
        try:
            disk_stats = self.disk_optimizer.get_stats()
            network_stats = self.network_optimizer.get_stats()
            
            # 디스크 통계
            disk_reads = disk_stats.get('read_stats', {}).get('total_operations', 0)
            disk_writes = disk_stats.get('write_stats', {}).get('total_operations', 0)
            avg_read_time = disk_stats.get('read_stats', {}).get('avg_duration', 0)
            avg_write_time = disk_stats.get('write_stats', {}).get('avg_duration', 0)
            
            # 네트워크 통계  
            network_requests = (network_stats.get('http_get_stats', {}).get('total_operations', 0) +
                              network_stats.get('http_post_stats', {}).get('total_operations', 0))
            avg_network_time = ((network_stats.get('http_get_stats', {}).get('avg_duration', 0) +
                               network_stats.get('http_post_stats', {}).get('avg_duration', 0)) / 2)
            
            # 바이트 통계
            bytes_read = int(disk_stats.get('read_stats', {}).get('total_mb', 0) * 1024 * 1024)
            bytes_written = int(disk_stats.get('write_stats', {}).get('total_mb', 0) * 1024 * 1024)
            
            # 캐시 적중률
            disk_cache_stats = disk_stats.get('cache_stats', {})
            network_cache_stats = network_stats.get('cache_stats', {})
            
            cache_hit_rate = 0.0
            if disk_cache_stats or network_cache_stats:
                total_hits = disk_cache_stats.get('hits', 0) + network_cache_stats.get('hits', 0)
                total_requests = (disk_cache_stats.get('hits', 0) + disk_cache_stats.get('misses', 0) +
                                network_cache_stats.get('hits', 0) + network_cache_stats.get('misses', 0))
                cache_hit_rate = total_hits / max(1, total_requests)
            
            # 압축 비율
            compression_stats = self.disk_optimizer.compression_manager.get_compression_stats()
            compression_ratio = 0.0
            if compression_stats:
                ratios = [stats['avg_compression_ratio'] for stats in compression_stats.values()]
                compression_ratio = sum(ratios) / len(ratios) if ratios else 0.0
            
            # 최적화 점수 계산
            optimization_score = self._calculate_optimization_score(
                avg_read_time, avg_write_time, avg_network_time, cache_hit_rate
            )
            
            stats = IOStats(
                disk_reads=disk_reads,
                disk_writes=disk_writes,
                network_requests=network_requests,
                bytes_read=bytes_read,
                bytes_written=bytes_written,
                avg_read_time=avg_read_time,
                avg_write_time=avg_write_time,
                avg_network_time=avg_network_time,
                cache_hit_rate=cache_hit_rate,
                compression_ratio=compression_ratio,
                optimization_score=optimization_score
            )
            
            return Success(stats)
            
        except Exception as e:
            return Failure(f"Failed to collect IO stats: {e}")
    
    def _calculate_optimization_score(self, avg_read_time: float, avg_write_time: float,
                                     avg_network_time: float, cache_hit_rate: float) -> float:
        """최적화 점수 계산 (0-100)"""
        score = 100.0
        
        # 읽기 시간 평가
        if avg_read_time > 1.0:  # 1초 이상
            score -= 20
        elif avg_read_time > 0.5:  # 0.5초 이상
            score -= 10
        
        # 쓰기 시간 평가
        if avg_write_time > 2.0:  # 2초 이상
            score -= 20
        elif avg_write_time > 1.0:  # 1초 이상
            score -= 10
        
        # 네트워크 시간 평가
        if avg_network_time > 5.0:  # 5초 이상
            score -= 30
        elif avg_network_time > 2.0:  # 2초 이상
            score -= 15
        
        # 캐시 적중률 평가
        score += (cache_hit_rate - 0.5) * 40  # 50% 이상이면 보너스
        
        return max(0.0, min(100.0, score))
    
    # Disk I/O 메소드들
    async def read_file(self, file_path: str, use_cache: bool = True) -> Result[bytes, str]:
        """파일 읽기"""
        return await self.disk_optimizer.read_file(file_path, use_cache)
    
    async def write_file(self, file_path: str, data: bytes, use_compression: bool = None) -> Result[bool, str]:
        """파일 쓰기"""
        return await self.disk_optimizer.write_file(file_path, data, use_compression)
    
    async def read_file_streaming(self, file_path: str, chunk_size: int = None) -> AsyncGenerator[bytes, None]:
        """스트리밍 파일 읽기"""
        async for chunk in self.disk_optimizer.read_file_streaming(file_path, chunk_size):
            yield chunk
    
    # Network I/O 메소드들
    async def http_get(self, url: str, headers: Dict[str, str] = None, use_cache: bool = True) -> Result[bytes, str]:
        """HTTP GET"""
        return await self.network_optimizer.http_get(url, headers, use_cache)
    
    async def http_post(self, url: str, data: bytes, headers: Dict[str, str] = None) -> Result[bytes, str]:
        """HTTP POST"""
        return await self.network_optimizer.http_post(url, data, headers)
    
    async def batch_http_get(self, urls: List[str], max_concurrent: int = 10) -> List[Result[bytes, str]]:
        """배치 HTTP GET"""
        return await self.network_optimizer.batch_http_get(urls, max_concurrent)
    
    async def optimize(self) -> Result[Dict[str, Any], str]:
        """I/O 최적화 실행"""
        try:
            # 현재 통계 수집
            stats_result = await self._collect_io_stats()
            if not stats_result.is_success():
                return stats_result
            
            current_stats = stats_result.unwrap()
            
            # 개별 최적화 통계
            disk_stats = self.disk_optimizer.get_stats()
            network_stats = self.network_optimizer.get_stats()
            compression_stats = self.disk_optimizer.compression_manager.get_compression_stats()
            
            # 최적화 추천사항 생성
            recommendations = self._generate_recommendations(current_stats)
            
            results = {
                'current_stats': current_stats,
                'disk_stats': disk_stats,
                'network_stats': network_stats,
                'compression_stats': compression_stats,
                'recommendations': recommendations
            }
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"IO optimization failed: {e}")
    
    def _generate_recommendations(self, stats: IOStats) -> List[str]:
        """최적화 추천사항 생성"""
        recommendations = []
        
        # 읽기 성능 추천
        if stats.avg_read_time > 1.0:
            recommendations.append("Consider using larger buffer sizes for file reading")
            recommendations.append("Enable caching for frequently accessed files")
        
        # 쓰기 성능 추천
        if stats.avg_write_time > 2.0:
            recommendations.append("Consider batch writing for multiple small files")
            recommendations.append("Use asynchronous writing for better performance")
        
        # 네트워크 성능 추천
        if stats.avg_network_time > 5.0:
            recommendations.append("Consider connection pooling for HTTP requests")
            recommendations.append("Enable compression for large data transfers")
        
        # 캐시 성능 추천
        if stats.cache_hit_rate < 0.5:
            recommendations.append("Increase cache size or improve cache strategy")
        
        # 압축 추천
        if stats.compression_ratio > 0.8:  # 압축 효율이 낮음
            recommendations.append("Consider disabling compression for this data type")
        elif stats.compression_ratio == 0.0 and stats.bytes_written > 1024 * 1024:
            recommendations.append("Consider enabling compression for large files")
        
        return recommendations
    
    def get_current_stats(self) -> Result[IOStats, str]:
        """현재 I/O 통계"""
        if not self.stats_history:
            return Failure("No statistics available")
        
        return Success(self.stats_history[-1])
    
    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            
            # 네트워크 세션 정리
            await self.network_optimizer.cleanup_sessions()
            
            # 캐시 정리
            if self.disk_optimizer.cache:
                self.disk_optimizer.cache.clear()
            if self.network_optimizer.cache:
                self.network_optimizer.cache.clear()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")

# 전역 optimizer 인스턴스
_io_optimizer: Optional[IOOptimizer] = None

def get_io_optimizer(config: Optional[IOOptimizationConfig] = None) -> IOOptimizer:
    """I/O optimizer 싱글톤 인스턴스 반환"""
    global _io_optimizer
    if _io_optimizer is None:
        _io_optimizer = IOOptimizer(config)
    return _io_optimizer

async def optimize_io_performance(strategy: IOOptimizationStrategy = IOOptimizationStrategy.BALANCED) -> Result[Dict[str, Any], str]:
    """I/O 성능 최적화 실행"""
    config = IOOptimizationConfig(strategy=strategy)
    optimizer = get_io_optimizer(config)
    
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    
    return await optimizer.optimize()