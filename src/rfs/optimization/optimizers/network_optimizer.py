"""
Network Optimization Engine for RFS Framework

네트워크 성능 최적화, 연결 최적화, 요청 최적화
- HTTP/HTTPS 연결 최적화
- 요청 배치 처리 및 캐싱
- 네트워크 지연시간 최소화
- 대역폭 사용량 최적화
"""

import asyncio
import aiohttp
import time
import socket
import ssl
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import threading
import urllib.parse
import gzip
import json
import weakref

from rfs.core.result import Result, Success, Failure
from rfs.core.config import get_config
from rfs.reactive.mono import Mono
from rfs.events.event import Event

class NetworkOptimizationStrategy(Enum):
    """네트워크 최적화 전략"""
    LATENCY_OPTIMIZED = "latency"          # 지연시간 최적화
    BANDWIDTH_OPTIMIZED = "bandwidth"      # 대역폭 최적화
    BALANCED = "balanced"                  # 균형 최적화
    HIGH_THROUGHPUT = "throughput"         # 처리량 최적화

class CompressionType(Enum):
    """압축 유형"""
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"
    BROTLI = "br"

class CacheStrategy(Enum):
    """캐시 전략"""
    NO_CACHE = "no_cache"
    MEMORY_ONLY = "memory_only"
    PERSISTENT = "persistent"
    DISTRIBUTED = "distributed"

@dataclass
class NetworkThresholds:
    """네트워크 임계값 설정"""
    connection_timeout_sec: float = 10.0      # 연결 타임아웃
    read_timeout_sec: float = 30.0            # 읽기 타임아웃
    max_connections_per_host: int = 10        # 호스트당 최대 연결 수
    max_total_connections: int = 100          # 총 최대 연결 수
    keepalive_timeout_sec: float = 60.0       # Keep-alive 타임아웃
    retry_attempts: int = 3                   # 재시도 횟수
    circuit_breaker_threshold: int = 5        # 서킷 브레이커 임계값
    cache_size_mb: int = 100                  # 캐시 크기
    compression_threshold_bytes: int = 1024   # 압축 임계값

@dataclass
class NetworkStats:
    """네트워크 통계"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    avg_connection_time: float
    avg_download_speed_mbps: float
    cache_hit_rate: float
    compression_ratio: float
    active_connections: int
    circuit_breaker_opens: int
    retry_count: int
    bytes_sent: int
    bytes_received: int
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class NetworkOptimizationConfig:
    """네트워크 최적화 설정"""
    strategy: NetworkOptimizationStrategy = NetworkOptimizationStrategy.BALANCED
    thresholds: NetworkThresholds = field(default_factory=NetworkThresholds)
    enable_compression: bool = True
    enable_caching: bool = True
    enable_connection_pooling: bool = True
    enable_circuit_breaker: bool = True
    enable_request_batching: bool = True
    monitoring_interval_seconds: float = 60.0
    user_agent: str = "RFS-Framework/4.2"

class ConnectionCache:
    """연결 캐시"""
    
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.lock = threading.Lock()
    
    def get_connection_info(self, host: str) -> Optional[Dict[str, Any]]:
        """연결 정보 조회"""
        with self.lock:
            if host in self.cache:
                self.access_times[host] = datetime.now()
                return self.cache[host]
            return None
    
    def cache_connection_info(self, host: str, info: Dict[str, Any]) -> None:
        """연결 정보 캐시"""
        with self.lock:
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            self.cache[host] = info
            self.access_times[host] = datetime.now()
    
    def _evict_lru(self) -> None:
        """LRU 방식으로 캐시 제거"""
        if not self.access_times:
            return
        
        oldest_host = min(self.access_times.items(), key=lambda x: x[1])[0]
        if oldest_host in self.cache:
            del self.cache[oldest_host]
        if oldest_host in self.access_times:
            del self.access_times[oldest_host]
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()

class CircuitBreaker:
    """서킷 브레이커"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self.lock = threading.Lock()
    
    def can_execute(self) -> bool:
        """실행 가능 여부 확인"""
        with self.lock:
            if self.state == "closed":
                return True
            elif self.state == "open":
                if (self.last_failure_time and 
                    time.time() - self.last_failure_time > self.recovery_timeout):
                    self.state = "half-open"
                    return True
                return False
            else:  # half-open
                return True
    
    def record_success(self) -> None:
        """성공 기록"""
        with self.lock:
            self.failure_count = 0
            self.state = "closed"
    
    def record_failure(self) -> None:
        """실패 기록"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
    
    def get_state(self) -> str:
        """현재 상태 반환"""
        return self.state

class RequestBatcher:
    """요청 배치 처리기"""
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_requests: List[Tuple[str, Dict, asyncio.Future]] = []
        self.last_batch_time = time.time()
        self.lock = asyncio.Lock()
    
    async def add_request(self, url: str, options: Dict[str, Any]) -> asyncio.Future:
        """요청 추가"""
        future = asyncio.Future()
        
        async with self.lock:
            self.pending_requests.append((url, options, future))
            
            # 배치 크기 도달 또는 타임아웃 시 실행
            if (len(self.pending_requests) >= self.batch_size or 
                time.time() - self.last_batch_time > self.batch_timeout):
                await self._execute_batch()
        
        return future
    
    async def _execute_batch(self) -> None:
        """배치 실행"""
        if not self.pending_requests:
            return
        
        batch = self.pending_requests.copy()
        self.pending_requests.clear()
        self.last_batch_time = time.time()
        
        # 실제 배치 실행은 구체적인 구현에 따라 다름
        # 여기서는 단순히 각 요청을 개별적으로 실행
        for url, options, future in batch:
            try:
                # 실제 HTTP 요청 실행 (예시)
                result = await self._execute_single_request(url, options)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
    
    async def _execute_single_request(self, url: str, options: Dict[str, Any]) -> Any:
        """단일 요청 실행 (플레이스홀더)"""
        # 실제 구현에서는 HTTP 클라이언트 사용
        await asyncio.sleep(0.1)  # 모의 네트워크 지연
        return {"url": url, "status": 200}

class ResponseCache:
    """응답 캐시"""
    
    def __init__(self, max_size_mb: int = 100):
        self.max_size = max_size_mb * 1024 * 1024
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.sizes: Dict[str, int] = {}
        self.access_times: Dict[str, datetime] = {}
        self.current_size = 0
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()
    
    def _generate_key(self, url: str, headers: Dict[str, Any] = None) -> str:
        """캐시 키 생성"""
        key_data = f"{url}:{str(sorted((headers or {}).items()))}"
        import hashlib
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, url: str, headers: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """캐시에서 응답 조회"""
        key = self._generate_key(url, headers)
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # TTL 체크
                if entry.get('expires_at') and datetime.now() > entry['expires_at']:
                    self._remove_entry(key)
                    self.misses += 1
                    return None
                
                self.access_times[key] = datetime.now()
                self.hits += 1
                return entry['data']
            else:
                self.misses += 1
                return None
    
    def put(self, url: str, data: Dict[str, Any], headers: Dict[str, Any] = None,
            ttl_seconds: int = 300) -> bool:
        """캐시에 응답 저장"""
        key = self._generate_key(url, headers)
        
        try:
            # 데이터 크기 추정
            data_size = len(json.dumps(data, default=str))
        except:
            data_size = 1024  # 기본값
        
        with self.lock:
            # 공간 확보
            while self.current_size + data_size > self.max_size and self.cache:
                self._evict_lru()
            
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
            
            self.cache[key] = {
                'data': data,
                'created_at': datetime.now(),
                'expires_at': expires_at
            }
            self.sizes[key] = data_size
            self.access_times[key] = datetime.now()
            self.current_size += data_size
            
            return True
    
    def _remove_entry(self, key: str) -> None:
        """엔트리 제거"""
        if key in self.cache:
            del self.cache[key]
        if key in self.sizes:
            self.current_size -= self.sizes[key]
            del self.sizes[key]
        if key in self.access_times:
            del self.access_times[key]
    
    def _evict_lru(self) -> None:
        """LRU 방식으로 캐시 제거"""
        if not self.access_times:
            return
        
        oldest_key = min(self.access_times.items(), key=lambda x: x[1])[0]
        self._remove_entry(oldest_key)
    
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
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self.lock:
            self.cache.clear()
            self.sizes.clear()
            self.access_times.clear()
            self.current_size = 0

class ConnectionOptimizer:
    """연결 최적화"""
    
    def __init__(self, config: NetworkOptimizationConfig):
        self.config = config
        self.connection_cache = ConnectionCache()
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.connection_stats = defaultdict(lambda: {
            'total_connections': 0,
            'successful_connections': 0,
            'connection_times': deque(maxlen=100),
            'last_used': None
        })
    
    async def get_optimized_session(self, base_url: str = None) -> aiohttp.ClientSession:
        """최적화된 세션 획득"""
        session_key = base_url or 'default'
        
        if session_key not in self.sessions:
            # 연결 최적화 설정
            connector = aiohttp.TCPConnector(
                limit=self.config.thresholds.max_total_connections,
                limit_per_host=self.config.thresholds.max_connections_per_host,
                keepalive_timeout=self.config.thresholds.keepalive_timeout_sec,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300,  # 5분
                family=socket.AF_INET,
                ssl=self._create_ssl_context()
            )
            
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=self.config.thresholds.connection_timeout_sec,
                sock_read=self.config.thresholds.read_timeout_sec
            )
            
            headers = {
                'User-Agent': self.config.user_agent
            }
            
            if self.config.enable_compression:
                headers['Accept-Encoding'] = 'gzip, deflate, br'
            
            self.sessions[session_key] = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
                auto_decompress=True
            )
        
        return self.sessions[session_key]
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """SSL 컨텍스트 생성"""
        context = ssl.create_default_context()
        
        # 성능 최적화 설정
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        return context
    
    def record_connection_attempt(self, host: str, duration: float, success: bool) -> None:
        """연결 시도 기록"""
        stats = self.connection_stats[host]
        stats['total_connections'] += 1
        stats['connection_times'].append(duration)
        stats['last_used'] = datetime.now()
        
        if success:
            stats['successful_connections'] += 1
        
        # 연결 정보 캐시 업데이트
        if success:
            connection_info = {
                'avg_connection_time': sum(stats['connection_times']) / len(stats['connection_times']),
                'success_rate': stats['successful_connections'] / stats['total_connections'],
                'last_successful_connection': datetime.now()
            }
            self.connection_cache.cache_connection_info(host, connection_info)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """연결 통계"""
        total_connections = sum(stats['total_connections'] for stats in self.connection_stats.values())
        successful_connections = sum(stats['successful_connections'] for stats in self.connection_stats.values())
        
        all_connection_times = []
        for stats in self.connection_stats.values():
            all_connection_times.extend(stats['connection_times'])
        
        avg_connection_time = sum(all_connection_times) / max(1, len(all_connection_times))
        
        return {
            'total_hosts': len(self.connection_stats),
            'total_connections': total_connections,
            'successful_connections': successful_connections,
            'success_rate': successful_connections / max(1, total_connections),
            'avg_connection_time': avg_connection_time,
            'active_sessions': len(self.sessions)
        }
    
    async def cleanup_sessions(self) -> None:
        """세션 정리"""
        for session in self.sessions.values():
            if not session.closed:
                await session.close()
        self.sessions.clear()

class RequestOptimizer:
    """요청 최적화"""
    
    def __init__(self, config: NetworkOptimizationConfig):
        self.config = config
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.request_batcher = RequestBatcher() if config.enable_request_batching else None
        self.request_stats = defaultdict(lambda: {
            'total_requests': 0,
            'successful_requests': 0,
            'response_times': deque(maxlen=100),
            'sizes': deque(maxlen=100),
            'last_request': None
        })
    
    def _get_circuit_breaker(self, host: str) -> CircuitBreaker:
        """서킷 브레이커 획득"""
        if host not in self.circuit_breakers:
            self.circuit_breakers[host] = CircuitBreaker(
                failure_threshold=self.config.thresholds.circuit_breaker_threshold
            )
        return self.circuit_breakers[host]
    
    async def execute_request(self, session: aiohttp.ClientSession, method: str, url: str,
                             **kwargs) -> Result[aiohttp.ClientResponse, str]:
        """최적화된 요청 실행"""
        parsed_url = urllib.parse.urlparse(url)
        host = parsed_url.netloc
        
        # 서킷 브레이커 체크
        if self.config.enable_circuit_breaker:
            circuit_breaker = self._get_circuit_breaker(host)
            if not circuit_breaker.can_execute():
                return Failure(f"Circuit breaker open for host: {host}")
        
        start_time = time.time()
        
        try:
            # 압축 설정
            if self.config.enable_compression and method.upper() in ['POST', 'PUT', 'PATCH']:
                data = kwargs.get('data') or kwargs.get('json')
                if data:
                    kwargs['compress'] = True
            
            # 재시도 로직
            last_error = None
            for attempt in range(self.config.thresholds.retry_attempts):
                try:
                    response = await session.request(method, url, **kwargs)
                    
                    # 성공 기록
                    duration = time.time() - start_time
                    self._record_request_success(host, duration, response)
                    
                    if self.config.enable_circuit_breaker:
                        circuit_breaker.record_success()
                    
                    return Success(response)
                    
                except asyncio.TimeoutError as e:
                    last_error = f"Timeout on attempt {attempt + 1}: {e}"
                    if attempt < self.config.thresholds.retry_attempts - 1:
                        await asyncio.sleep(2 ** attempt)  # 지수 백오프
                    continue
                except Exception as e:
                    last_error = f"Error on attempt {attempt + 1}: {e}"
                    if attempt < self.config.thresholds.retry_attempts - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
            
            # 모든 재시도 실패
            duration = time.time() - start_time
            self._record_request_failure(host, duration, last_error)
            
            if self.config.enable_circuit_breaker:
                circuit_breaker.record_failure()
            
            return Failure(f"Request failed after {self.config.thresholds.retry_attempts} attempts: {last_error}")
            
        except Exception as e:
            duration = time.time() - start_time
            self._record_request_failure(host, duration, str(e))
            
            if self.config.enable_circuit_breaker:
                circuit_breaker.record_failure()
            
            return Failure(f"Request execution failed: {e}")
    
    def _record_request_success(self, host: str, duration: float, response: aiohttp.ClientResponse) -> None:
        """요청 성공 기록"""
        stats = self.request_stats[host]
        stats['total_requests'] += 1
        stats['successful_requests'] += 1
        stats['response_times'].append(duration)
        stats['last_request'] = datetime.now()
        
        # 응답 크기 기록
        content_length = response.headers.get('Content-Length')
        if content_length:
            stats['sizes'].append(int(content_length))
    
    def _record_request_failure(self, host: str, duration: float, error: str) -> None:
        """요청 실패 기록"""
        stats = self.request_stats[host]
        stats['total_requests'] += 1
        stats['response_times'].append(duration)
        stats['last_request'] = datetime.now()
    
    def get_request_stats(self) -> Dict[str, Any]:
        """요청 통계"""
        total_requests = sum(stats['total_requests'] for stats in self.request_stats.values())
        successful_requests = sum(stats['successful_requests'] for stats in self.request_stats.values())
        
        all_response_times = []
        all_sizes = []
        
        for stats in self.request_stats.values():
            all_response_times.extend(stats['response_times'])
            all_sizes.extend(stats['sizes'])
        
        avg_response_time = sum(all_response_times) / max(1, len(all_response_times))
        avg_size = sum(all_sizes) / max(1, len(all_sizes))
        
        # 서킷 브레이커 상태
        circuit_breaker_states = {host: cb.get_state() 
                                for host, cb in self.circuit_breakers.items()}
        
        return {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'success_rate': successful_requests / max(1, total_requests),
            'avg_response_time': avg_response_time,
            'avg_response_size_bytes': avg_size,
            'circuit_breaker_states': circuit_breaker_states,
            'hosts_tracked': len(self.request_stats)
        }

class CachingOptimizer:
    """캐싱 최적화"""
    
    def __init__(self, config: NetworkOptimizationConfig):
        self.config = config
        self.response_cache = ResponseCache(config.thresholds.cache_size_mb)
        self.cache_strategy = CacheStrategy.MEMORY_ONLY  # 기본 전략
    
    def should_cache_response(self, response: aiohttp.ClientResponse) -> bool:
        """응답 캐시 여부 결정"""
        if not self.config.enable_caching:
            return False
        
        # 캐시 가능한 응답 코드
        if response.status not in [200, 201, 203, 204, 206, 300, 301, 410]:
            return False
        
        # Cache-Control 헤더 확인
        cache_control = response.headers.get('Cache-Control', '')
        if 'no-cache' in cache_control or 'no-store' in cache_control:
            return False
        
        # Content-Type 확인 (일부 유형만 캐시)
        content_type = response.headers.get('Content-Type', '')
        cacheable_types = [
            'application/json',
            'text/html',
            'text/plain',
            'application/xml',
            'text/xml'
        ]
        
        return any(ct in content_type for ct in cacheable_types)
    
    def get_cache_ttl(self, response: aiohttp.ClientResponse) -> int:
        """캐시 TTL 계산"""
        # Cache-Control max-age 확인
        cache_control = response.headers.get('Cache-Control', '')
        if 'max-age=' in cache_control:
            try:
                max_age = int(cache_control.split('max-age=')[1].split(',')[0])
                return max_age
            except:
                pass
        
        # Expires 헤더 확인
        expires = response.headers.get('Expires')
        if expires:
            try:
                from email.utils import parsedate_to_datetime
                expires_dt = parsedate_to_datetime(expires)
                ttl = int((expires_dt - datetime.now()).total_seconds())
                return max(0, ttl)
            except:
                pass
        
        # 기본 TTL (5분)
        return 300
    
    async def get_cached_response(self, url: str, headers: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """캐시된 응답 조회"""
        return self.response_cache.get(url, headers)
    
    async def cache_response(self, url: str, response_data: Dict[str, Any], 
                           response: aiohttp.ClientResponse, headers: Dict[str, Any] = None) -> None:
        """응답 캐시"""
        if self.should_cache_response(response):
            ttl = self.get_cache_ttl(response)
            self.response_cache.put(url, response_data, headers, ttl)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return self.response_cache.get_stats()
    
    def clear_cache(self) -> None:
        """캐시 삭제"""
        self.response_cache.clear()

class NetworkOptimizer:
    """네트워크 최적화 엔진"""
    
    def __init__(self, config: Optional[NetworkOptimizationConfig] = None):
        self.config = config or NetworkOptimizationConfig()
        
        self.connection_optimizer = ConnectionOptimizer(self.config)
        self.request_optimizer = RequestOptimizer(self.config)
        self.caching_optimizer = CachingOptimizer(self.config)
        
        self.monitoring_task: Optional[asyncio.Task] = None
        self.stats_history: deque = deque(maxlen=100)
        self.is_running = False
        
        # 전체 통계
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.start_time = time.time()
    
    async def initialize(self) -> Result[bool, str]:
        """네트워크 최적화 엔진 초기화"""
        try:
            if self.config.monitoring_interval_seconds > 0:
                await self.start_monitoring()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Network optimizer initialization failed: {e}")
    
    async def start_monitoring(self) -> Result[bool, str]:
        """네트워크 모니터링 시작"""
        if self.is_running:
            return Success(True)
            
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to start network monitoring: {e}")
    
    async def stop_monitoring(self) -> Result[bool, str]:
        """네트워크 모니터링 중지"""
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
            return Failure(f"Failed to stop network monitoring: {e}")
    
    async def _monitoring_loop(self) -> None:
        """네트워크 모니터링 루프"""
        while self.is_running:
            try:
                stats = await self._collect_network_stats()
                if stats.is_success():
                    network_stats = stats.unwrap()
                    self.stats_history.append(network_stats)
                
                await asyncio.sleep(self.config.monitoring_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Network monitoring error: {e}")
                await asyncio.sleep(self.config.monitoring_interval_seconds)
    
    async def _collect_network_stats(self) -> Result[NetworkStats, str]:
        """네트워크 통계 수집"""
        try:
            connection_stats = self.connection_optimizer.get_connection_stats()
            request_stats = self.request_optimizer.get_request_stats()
            cache_stats = self.caching_optimizer.get_cache_stats()
            
            # 평균 계산
            total_requests = request_stats['total_requests']
            successful_requests = request_stats['successful_requests']
            avg_response_time = request_stats['avg_response_time']
            avg_connection_time = connection_stats['avg_connection_time']
            
            # 다운로드 속도 계산 (MB/s)
            elapsed_time = time.time() - self.start_time
            avg_download_speed = 0.0
            if elapsed_time > 0 and self.total_bytes_received > 0:
                avg_download_speed = (self.total_bytes_received / 1024 / 1024) / elapsed_time
            
            # 압축 비율 계산 (단순화)
            compression_ratio = 0.0
            if self.total_bytes_sent > 0:
                # 실제로는 압축 전후 크기를 비교해야 함
                compression_ratio = 0.7  # 예시값
            
            # 서킷 브레이커 열림 횟수
            circuit_breaker_opens = len([cb for cb in self.request_optimizer.circuit_breakers.values() 
                                       if cb.get_state() == "open"])
            
            stats = NetworkStats(
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=total_requests - successful_requests,
                avg_response_time=avg_response_time,
                avg_connection_time=avg_connection_time,
                avg_download_speed_mbps=avg_download_speed,
                cache_hit_rate=cache_stats['hit_rate'],
                compression_ratio=compression_ratio,
                active_connections=connection_stats['active_sessions'],
                circuit_breaker_opens=circuit_breaker_opens,
                retry_count=0,  # 실제로는 재시도 통계 수집 필요
                bytes_sent=self.total_bytes_sent,
                bytes_received=self.total_bytes_received
            )
            
            return Success(stats)
            
        except Exception as e:
            return Failure(f"Failed to collect network stats: {e}")
    
    # Public 인터페이스 메소드들
    async def get(self, url: str, headers: Dict[str, str] = None, **kwargs) -> Result[Dict[str, Any], str]:
        """GET 요청"""
        return await self._execute_request('GET', url, headers=headers, **kwargs)
    
    async def post(self, url: str, data: Any = None, json: Any = None, 
                   headers: Dict[str, str] = None, **kwargs) -> Result[Dict[str, Any], str]:
        """POST 요청"""
        return await self._execute_request('POST', url, data=data, json=json, headers=headers, **kwargs)
    
    async def put(self, url: str, data: Any = None, json: Any = None,
                  headers: Dict[str, str] = None, **kwargs) -> Result[Dict[str, Any], str]:
        """PUT 요청"""
        return await self._execute_request('PUT', url, data=data, json=json, headers=headers, **kwargs)
    
    async def delete(self, url: str, headers: Dict[str, str] = None, **kwargs) -> Result[Dict[str, Any], str]:
        """DELETE 요청"""
        return await self._execute_request('DELETE', url, headers=headers, **kwargs)
    
    async def _execute_request(self, method: str, url: str, **kwargs) -> Result[Dict[str, Any], str]:
        """요청 실행"""
        try:
            # 캐시 확인 (GET 요청만)
            if method.upper() == 'GET':
                cached_response = await self.caching_optimizer.get_cached_response(
                    url, kwargs.get('headers')
                )
                if cached_response:
                    return Success(cached_response)
            
            # 최적화된 세션 획득
            session = await self.connection_optimizer.get_optimized_session()
            
            # 요청 실행
            response_result = await self.request_optimizer.execute_request(
                session, method, url, **kwargs
            )
            
            if not response_result.is_success():
                return response_result
            
            response = response_result.unwrap()
            
            # 응답 처리
            content = await response.read()
            self.total_bytes_received += len(content)
            
            # 요청 크기 추정 (단순화)
            request_size = len(str(kwargs))
            self.total_bytes_sent += request_size
            
            # 응답 데이터 생성
            response_data = {
                'status': response.status,
                'headers': dict(response.headers),
                'content': content,
                'url': str(response.url),
                'method': method
            }
            
            # 캐시 저장
            if method.upper() == 'GET':
                await self.caching_optimizer.cache_response(
                    url, response_data, response, kwargs.get('headers')
                )
            
            return Success(response_data)
            
        except Exception as e:
            return Failure(f"Request execution failed: {e}")
    
    async def batch_requests(self, requests: List[Dict[str, Any]], max_concurrent: int = 10) -> List[Result[Dict[str, Any], str]]:
        """배치 요청"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_single(request: Dict[str, Any]) -> Result[Dict[str, Any], str]:
            async with semaphore:
                method = request.get('method', 'GET')
                url = request['url']
                kwargs = {k: v for k, v in request.items() if k not in ['method', 'url']}
                return await self._execute_request(method, url, **kwargs)
        
        tasks = [execute_single(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외를 Result로 변환
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(Failure(str(result)))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def optimize(self) -> Result[Dict[str, Any], str]:
        """네트워크 최적화 실행"""
        try:
            # 현재 통계 수집
            stats_result = await self._collect_network_stats()
            if not stats_result.is_success():
                return stats_result
            
            current_stats = stats_result.unwrap()
            
            # 개별 최적화 통계
            connection_stats = self.connection_optimizer.get_connection_stats()
            request_stats = self.request_optimizer.get_request_stats()
            cache_stats = self.caching_optimizer.get_cache_stats()
            
            # 최적화 추천사항 생성
            recommendations = self._generate_recommendations(
                current_stats, connection_stats, request_stats, cache_stats
            )
            
            # 성능 점수 계산
            performance_score = self._calculate_performance_score(current_stats)
            
            results = {
                'performance_score': performance_score,
                'current_stats': current_stats,
                'connection_stats': connection_stats,
                'request_stats': request_stats,
                'cache_stats': cache_stats,
                'recommendations': recommendations,
                'optimization_summary': {
                    'active_circuit_breakers': current_stats.circuit_breaker_opens,
                    'cache_efficiency': cache_stats['hit_rate'],
                    'connection_success_rate': connection_stats['success_rate'],
                    'request_success_rate': request_stats['success_rate']
                }
            }
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"Network optimization failed: {e}")
    
    def _generate_recommendations(self, current_stats: NetworkStats, connection_stats: Dict,
                                request_stats: Dict, cache_stats: Dict) -> List[str]:
        """최적화 추천사항 생성"""
        recommendations = []
        
        # 응답 시간 추천
        if current_stats.avg_response_time > 5.0:
            recommendations.append("High response time - consider connection pooling optimization")
        
        # 연결 성능 추천
        if connection_stats['success_rate'] < 0.9:
            recommendations.append("Low connection success rate - check network stability")
        
        # 캐시 성능 추천
        if cache_stats['hit_rate'] < 0.3:
            recommendations.append("Low cache hit rate - review caching strategy")
        elif cache_stats['hit_rate'] > 0.8:
            recommendations.append("Excellent cache performance - consider increasing cache size")
        
        # 서킷 브레이커 추천
        if current_stats.circuit_breaker_opens > 0:
            recommendations.append(f"Circuit breakers active ({current_stats.circuit_breaker_opens}) - investigate service issues")
        
        # 압축 추천
        if current_stats.compression_ratio < 0.5 and current_stats.bytes_sent > 1024 * 1024:
            recommendations.append("Low compression ratio - enable compression for large payloads")
        
        # 대역폭 사용률 추천
        if current_stats.avg_download_speed_mbps < 1.0 and current_stats.total_requests > 100:
            recommendations.append("Low download speed - consider connection optimization")
        
        return recommendations
    
    def _calculate_performance_score(self, stats: NetworkStats) -> float:
        """성능 점수 계산 (0-100)"""
        score = 100.0
        
        # 응답 시간 평가
        if stats.avg_response_time > 10.0:
            score -= 40
        elif stats.avg_response_time > 5.0:
            score -= 20
        elif stats.avg_response_time > 2.0:
            score -= 10
        
        # 성공률 평가
        if stats.total_requests > 0:
            success_rate = stats.successful_requests / stats.total_requests
            score += (success_rate - 0.8) * 50  # 80% 이상이면 보너스
        
        # 캐시 성능 평가
        score += stats.cache_hit_rate * 20  # 최대 20점 보너스
        
        # 서킷 브레이커 패널티
        score -= stats.circuit_breaker_opens * 10
        
        return max(0.0, min(100.0, score))
    
    def get_current_stats(self) -> Result[NetworkStats, str]:
        """현재 네트워크 통계"""
        if not self.stats_history:
            return Failure("No statistics available")
        
        return Success(self.stats_history[-1])
    
    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            
            # 연결 세션 정리
            await self.connection_optimizer.cleanup_sessions()
            
            # 캐시 정리
            self.caching_optimizer.clear_cache()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")

# 전역 optimizer 인스턴스
_network_optimizer: Optional[NetworkOptimizer] = None

def get_network_optimizer(config: Optional[NetworkOptimizationConfig] = None) -> NetworkOptimizer:
    """네트워크 optimizer 싱글톤 인스턴스 반환"""
    global _network_optimizer
    if _network_optimizer is None:
        _network_optimizer = NetworkOptimizer(config)
    return _network_optimizer

async def optimize_network_performance(strategy: NetworkOptimizationStrategy = NetworkOptimizationStrategy.BALANCED) -> Result[Dict[str, Any], str]:
    """네트워크 성능 최적화 실행"""
    config = NetworkOptimizationConfig(strategy=strategy)
    optimizer = get_network_optimizer(config)
    
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    
    return await optimizer.optimize()