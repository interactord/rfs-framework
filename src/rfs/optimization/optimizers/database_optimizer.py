"""
Database Optimization Engine for RFS Framework

데이터베이스 성능 최적화, 쿼리 최적화, 연결 풀 관리
- 쿼리 성능 분석 및 최적화
- 인덱스 최적화 추천
- 연결 풀 튜닝 및 관리
- 데이터베이스 모니터링 및 분석
"""

import asyncio
import time
import re
import hashlib
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict, Counter
import threading
import weakref

from rfs.core.result import Result, Success, Failure
from rfs.core.config import get_config
from rfs.reactive.mono import Mono
from rfs.events.event import Event

class DatabaseType(Enum):
    """데이터베이스 유형"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"

class QueryType(Enum):
    """쿼리 유형"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    ALTER = "alter"
    INDEX = "index"

class OptimizationPriority(Enum):
    """최적화 우선순위"""
    CRITICAL = "critical"      # 즉시 최적화 필요
    HIGH = "high"             # 높은 우선순위
    MEDIUM = "medium"         # 중간 우선순위
    LOW = "low"               # 낮은 우선순위

@dataclass
class DatabaseThresholds:
    """데이터베이스 임계값 설정"""
    slow_query_seconds: float = 1.0           # 느린 쿼리 임계값
    connection_pool_min: int = 5              # 최소 연결 수
    connection_pool_max: int = 20             # 최대 연결 수
    connection_timeout_seconds: float = 30.0  # 연결 타임아웃
    query_cache_size_mb: int = 100            # 쿼리 캐시 크기
    max_concurrent_queries: int = 100         # 최대 동시 쿼리
    index_usage_threshold: float = 0.1        # 인덱스 사용률 임계값

@dataclass
class QueryStats:
    """쿼리 통계"""
    query_hash: str
    query_type: QueryType
    execution_count: int
    total_duration: float
    avg_duration: float
    min_duration: float
    max_duration: float
    affected_rows: int
    index_usage: float
    cache_hit_rate: float
    error_count: int
    last_execution: datetime
    optimization_suggestions: List[str] = field(default_factory=list)

@dataclass
class ConnectionPoolStats:
    """연결 풀 통계"""
    total_connections: int
    active_connections: int
    idle_connections: int
    waiting_connections: int
    total_acquisitions: int
    avg_acquisition_time: float
    timeout_count: int
    error_count: int
    pool_efficiency: float

@dataclass
class DatabaseOptimizationConfig:
    """데이터베이스 최적화 설정"""
    database_type: DatabaseType = DatabaseType.POSTGRESQL
    thresholds: DatabaseThresholds = field(default_factory=DatabaseThresholds)
    enable_query_caching: bool = True
    enable_connection_pooling: bool = True
    enable_query_analysis: bool = True
    enable_index_analysis: bool = True
    monitoring_interval_seconds: float = 60.0
    auto_optimization: bool = False  # 자동 최적화는 위험할 수 있으므로 기본 비활성화

class QueryAnalyzer:
    """쿼리 분석기"""
    
    def __init__(self, database_type: DatabaseType):
        self.database_type = database_type
        self.query_patterns = self._initialize_patterns()
        self.performance_rules = self._initialize_performance_rules()
    
    def _initialize_patterns(self) -> Dict[str, re.Pattern]:
        """쿼리 패턴 초기화"""
        patterns = {
            'select': re.compile(r'^\s*SELECT\s+', re.IGNORECASE),
            'insert': re.compile(r'^\s*INSERT\s+', re.IGNORECASE),
            'update': re.compile(r'^\s*UPDATE\s+', re.IGNORECASE),
            'delete': re.compile(r'^\s*DELETE\s+', re.IGNORECASE),
            'create': re.compile(r'^\s*CREATE\s+', re.IGNORECASE),
            'alter': re.compile(r'^\s*ALTER\s+', re.IGNORECASE),
            'index': re.compile(r'^\s*CREATE\s+.*INDEX\s+', re.IGNORECASE),
            
            # 성능에 영향을 주는 패턴들
            'select_star': re.compile(r'SELECT\s+\*\s+FROM', re.IGNORECASE),
            'no_where': re.compile(r'(UPDATE|DELETE)(?!.*WHERE)', re.IGNORECASE),
            'cartesian_join': re.compile(r'FROM\s+\w+\s*,\s*\w+(?!.*WHERE.*=)', re.IGNORECASE),
            'function_in_where': re.compile(r'WHERE\s+\w*\([^)]*\)\s*[=<>]', re.IGNORECASE),
            'like_leading_wildcard': re.compile(r'LIKE\s+[\'"]%', re.IGNORECASE),
            'or_condition': re.compile(r'WHERE.*OR', re.IGNORECASE),
        }
        
        return patterns
    
    def _initialize_performance_rules(self) -> List[Dict[str, Any]]:
        """성능 규칙 초기화"""
        rules = [
            {
                'name': 'avoid_select_star',
                'pattern': 'select_star',
                'severity': 'medium',
                'suggestion': 'Avoid SELECT * - specify only needed columns'
            },
            {
                'name': 'missing_where_clause',
                'pattern': 'no_where',
                'severity': 'high',
                'suggestion': 'UPDATE/DELETE without WHERE clause affects all rows'
            },
            {
                'name': 'cartesian_product',
                'pattern': 'cartesian_join',
                'severity': 'critical',
                'suggestion': 'Potential cartesian product - add JOIN conditions'
            },
            {
                'name': 'function_on_indexed_column',
                'pattern': 'function_in_where',
                'severity': 'medium',
                'suggestion': 'Functions on indexed columns prevent index usage'
            },
            {
                'name': 'leading_wildcard_like',
                'pattern': 'like_leading_wildcard',
                'severity': 'medium',
                'suggestion': 'LIKE with leading wildcard prevents index usage'
            },
            {
                'name': 'or_condition_performance',
                'pattern': 'or_condition',
                'severity': 'low',
                'suggestion': 'OR conditions may prevent index usage - consider UNION'
            }
        ]
        
        return rules
    
    def analyze_query(self, query: str) -> Result[Dict[str, Any], str]:
        """쿼리 분석"""
        try:
            analysis = {
                'query_type': self._detect_query_type(query),
                'complexity_score': self._calculate_complexity(query),
                'performance_issues': self._detect_performance_issues(query),
                'index_recommendations': self._recommend_indexes(query),
                'optimization_suggestions': []
            }
            
            # 성능 문제에 따른 최적화 제안
            for issue in analysis['performance_issues']:
                analysis['optimization_suggestions'].append(issue['suggestion'])
            
            return Success(analysis)
            
        except Exception as e:
            return Failure(f"Query analysis failed: {e}")
    
    def _detect_query_type(self, query: str) -> QueryType:
        """쿼리 유형 탐지"""
        query_clean = query.strip().upper()
        
        if query_clean.startswith('SELECT'):
            return QueryType.SELECT
        elif query_clean.startswith('INSERT'):
            return QueryType.INSERT
        elif query_clean.startswith('UPDATE'):
            return QueryType.UPDATE
        elif query_clean.startswith('DELETE'):
            return QueryType.DELETE
        elif query_clean.startswith('CREATE'):
            return QueryType.CREATE
        elif query_clean.startswith('ALTER'):
            return QueryType.ALTER
        else:
            return QueryType.SELECT  # 기본값
    
    def _calculate_complexity(self, query: str) -> float:
        """쿼리 복잡도 계산 (0-100)"""
        complexity = 0.0
        query_upper = query.upper()
        
        # 기본 복잡도
        complexity += 10
        
        # JOIN 개수
        join_count = query_upper.count(' JOIN ')
        complexity += join_count * 15
        
        # 서브쿼리 개수
        subquery_count = query_upper.count('(SELECT')
        complexity += subquery_count * 20
        
        # GROUP BY, ORDER BY, HAVING
        if 'GROUP BY' in query_upper:
            complexity += 10
        if 'ORDER BY' in query_upper:
            complexity += 5
        if 'HAVING' in query_upper:
            complexity += 15
        
        # UNION
        union_count = query_upper.count(' UNION ')
        complexity += union_count * 10
        
        # WITH (CTE)
        if query_upper.startswith('WITH'):
            complexity += 20
        
        return min(100.0, complexity)
    
    def _detect_performance_issues(self, query: str) -> List[Dict[str, Any]]:
        """성능 문제 탐지"""
        issues = []
        
        for rule in self.performance_rules:
            pattern = self.query_patterns.get(rule['pattern'])
            if pattern and pattern.search(query):
                issues.append({
                    'name': rule['name'],
                    'severity': rule['severity'],
                    'suggestion': rule['suggestion']
                })
        
        return issues
    
    def _recommend_indexes(self, query: str) -> List[str]:
        """인덱스 추천"""
        recommendations = []
        query_upper = query.upper()
        
        # WHERE 절 컬럼 추출 (단순화된 버전)
        where_match = re.search(r'WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+HAVING|$)', query_upper)
        if where_match:
            where_clause = where_match.group(1)
            
            # 등호 조건 컬럼 추출
            equality_columns = re.findall(r'(\w+)\s*=', where_clause)
            for col in equality_columns:
                recommendations.append(f"Consider index on column: {col.lower()}")
        
        # ORDER BY 컬럼 추출
        order_match = re.search(r'ORDER\s+BY\s+(.*?)(?:\s+LIMIT|\s+OFFSET|$)', query_upper)
        if order_match:
            order_clause = order_match.group(1)
            order_columns = re.findall(r'(\w+)', order_clause)
            for col in order_columns:
                recommendations.append(f"Consider index for ORDER BY: {col.lower()}")
        
        return recommendations
    
    def generate_query_hash(self, query: str) -> str:
        """쿼리 해시 생성 (파라미터 정규화)"""
        # 파라미터를 플레이스홀더로 대체하여 정규화
        normalized = re.sub(r"'[^']*'", "'?'", query)  # 문자열 리터럴
        normalized = re.sub(r'\b\d+\b', '?', normalized)  # 숫자 리터럴
        normalized = re.sub(r'\s+', ' ', normalized.strip())  # 공백 정규화
        
        return hashlib.md5(normalized.encode()).hexdigest()

class ConnectionPoolOptimizer:
    """연결 풀 최적화"""
    
    def __init__(self, config: DatabaseOptimizationConfig):
        self.config = config
        self.pool_stats = ConnectionPoolStats(
            total_connections=0,
            active_connections=0,
            idle_connections=0,
            waiting_connections=0,
            total_acquisitions=0,
            avg_acquisition_time=0.0,
            timeout_count=0,
            error_count=0,
            pool_efficiency=0.0
        )
        self.acquisition_times: deque = deque(maxlen=1000)
        self.lock = threading.Lock()
    
    def record_connection_acquisition(self, duration: float, success: bool) -> None:
        """연결 획득 기록"""
        with self.lock:
            self.pool_stats.total_acquisitions += 1
            self.acquisition_times.append(duration)
            
            if self.acquisition_times:
                self.pool_stats.avg_acquisition_time = sum(self.acquisition_times) / len(self.acquisition_times)
            
            if not success:
                self.pool_stats.error_count += 1
    
    def record_connection_timeout(self) -> None:
        """연결 타임아웃 기록"""
        with self.lock:
            self.pool_stats.timeout_count += 1
    
    def update_pool_state(self, total: int, active: int, idle: int, waiting: int) -> None:
        """풀 상태 업데이트"""
        with self.lock:
            self.pool_stats.total_connections = total
            self.pool_stats.active_connections = active
            self.pool_stats.idle_connections = idle
            self.pool_stats.waiting_connections = waiting
            
            # 풀 효율성 계산
            if total > 0:
                self.pool_stats.pool_efficiency = active / total
    
    def analyze_pool_performance(self) -> Dict[str, Any]:
        """풀 성능 분석"""
        analysis = {
            'current_stats': self.pool_stats,
            'recommendations': [],
            'optimal_pool_size': self._calculate_optimal_pool_size(),
            'performance_score': self._calculate_performance_score()
        }
        
        # 추천사항 생성
        if self.pool_stats.avg_acquisition_time > 0.1:  # 100ms 이상
            analysis['recommendations'].append("Connection acquisition time is high - consider increasing pool size")
        
        if self.pool_stats.pool_efficiency < 0.3:  # 30% 미만
            analysis['recommendations'].append("Low pool efficiency - consider reducing pool size")
        elif self.pool_stats.pool_efficiency > 0.9:  # 90% 이상
            analysis['recommendations'].append("High pool utilization - consider increasing pool size")
        
        if self.pool_stats.timeout_count > 0:
            analysis['recommendations'].append("Connection timeouts detected - increase pool size or timeout duration")
        
        return analysis
    
    def _calculate_optimal_pool_size(self) -> Tuple[int, int]:
        """최적 풀 크기 계산"""
        current_min = self.config.thresholds.connection_pool_min
        current_max = self.config.thresholds.connection_pool_max
        
        # 사용률 기반 조정
        if self.pool_stats.pool_efficiency > 0.8:
            # 높은 사용률 - 풀 크기 증가 고려
            optimal_max = min(current_max + 5, 50)
        elif self.pool_stats.pool_efficiency < 0.3:
            # 낮은 사용률 - 풀 크기 감소 고려
            optimal_max = max(current_max - 5, 10)
        else:
            optimal_max = current_max
        
        optimal_min = max(optimal_max // 4, 2)  # 최소값은 최대값의 1/4
        
        return optimal_min, optimal_max
    
    def _calculate_performance_score(self) -> float:
        """성능 점수 계산 (0-100)"""
        score = 100.0
        
        # 획득 시간 평가
        if self.pool_stats.avg_acquisition_time > 0.5:  # 500ms 이상
            score -= 40
        elif self.pool_stats.avg_acquisition_time > 0.1:  # 100ms 이상
            score -= 20
        
        # 타임아웃 평가
        if self.pool_stats.total_acquisitions > 0:
            timeout_rate = self.pool_stats.timeout_count / self.pool_stats.total_acquisitions
            score -= timeout_rate * 100
        
        # 효율성 평가
        if 0.4 <= self.pool_stats.pool_efficiency <= 0.8:
            score += 10  # 적절한 효율성 보너스
        
        return max(0.0, min(100.0, score))

class IndexOptimizer:
    """인덱스 최적화"""
    
    def __init__(self, database_type: DatabaseType):
        self.database_type = database_type
        self.index_usage_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'scan_count': 0,
            'lookup_count': 0,
            'update_count': 0,
            'size_mb': 0,
            'last_used': None,
            'efficiency_score': 0.0
        })
    
    def record_index_usage(self, index_name: str, usage_type: str, scan_cost: float = 0) -> None:
        """인덱스 사용 기록"""
        stats = self.index_usage_stats[index_name]
        
        if usage_type == 'scan':
            stats['scan_count'] += 1
        elif usage_type == 'lookup':
            stats['lookup_count'] += 1
        elif usage_type == 'update':
            stats['update_count'] += 1
        
        stats['last_used'] = datetime.now()
        
        # 효율성 점수 계산
        total_usage = stats['scan_count'] + stats['lookup_count']
        if total_usage > 0:
            scan_ratio = stats['scan_count'] / total_usage
            lookup_ratio = stats['lookup_count'] / total_usage
            
            # 룩업이 더 효율적 (점수 높음)
            stats['efficiency_score'] = (lookup_ratio * 100) + (scan_ratio * 20)
    
    def analyze_index_performance(self) -> Dict[str, Any]:
        """인덱스 성능 분석"""
        analysis = {
            'total_indexes': len(self.index_usage_stats),
            'unused_indexes': [],
            'inefficient_indexes': [],
            'recommended_indexes': [],
            'optimization_summary': {}
        }
        
        current_time = datetime.now()
        
        for index_name, stats in self.index_usage_stats.items():
            total_usage = stats['scan_count'] + stats['lookup_count']
            
            # 사용되지 않는 인덱스
            if total_usage == 0 or (stats['last_used'] and 
                                   (current_time - stats['last_used']).days > 30):
                analysis['unused_indexes'].append({
                    'name': index_name,
                    'reason': 'Not used in last 30 days',
                    'recommendation': 'Consider dropping this index'
                })
            
            # 비효율적인 인덱스
            elif stats['efficiency_score'] < 30:  # 30점 미만
                analysis['inefficient_indexes'].append({
                    'name': index_name,
                    'efficiency_score': stats['efficiency_score'],
                    'scan_count': stats['scan_count'],
                    'lookup_count': stats['lookup_count'],
                    'recommendation': 'Index causes more scans than lookups'
                })
        
        # 최적화 요약
        analysis['optimization_summary'] = {
            'indexes_to_drop': len(analysis['unused_indexes']),
            'indexes_to_review': len(analysis['inefficient_indexes']),
            'potential_space_savings': self._calculate_space_savings(analysis['unused_indexes'])
        }
        
        return analysis
    
    def _calculate_space_savings(self, unused_indexes: List[Dict]) -> Dict[str, float]:
        """공간 절약 계산"""
        total_size = 0
        for index_info in unused_indexes:
            index_name = index_info['name']
            if index_name in self.index_usage_stats:
                total_size += self.index_usage_stats[index_name].get('size_mb', 0)
        
        return {
            'total_mb': total_size,
            'estimated_performance_gain': min(total_size * 0.1, 20)  # 대략적인 성능 향상
        }
    
    def generate_index_recommendations(self, query_stats: Dict[str, QueryStats]) -> List[str]:
        """쿼리 통계 기반 인덱스 추천"""
        recommendations = []
        column_usage = Counter()
        
        # 쿼리에서 자주 사용되는 컬럼 분석
        for stats in query_stats.values():
            # 실제 구현에서는 쿼리 파싱을 통해 WHERE, JOIN, ORDER BY 컬럼 추출
            # 여기서는 단순화된 버전
            if stats.avg_duration > 1.0 and stats.execution_count > 10:
                recommendations.append(f"Consider indexing for frequently slow query: {stats.query_hash[:8]}")
        
        return recommendations

class QueryOptimizer:
    """쿼리 최적화"""
    
    def __init__(self, database_type: DatabaseType):
        self.database_type = database_type
        self.query_analyzer = QueryAnalyzer(database_type)
        self.query_cache: Dict[str, Any] = {}
        self.query_stats: Dict[str, QueryStats] = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record_query_execution(self, query: str, duration: float, affected_rows: int = 0, 
                             error: Optional[str] = None) -> None:
        """쿼리 실행 기록"""
        query_hash = self.query_analyzer.generate_query_hash(query)
        query_type = self.query_analyzer._detect_query_type(query)
        
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = QueryStats(
                query_hash=query_hash,
                query_type=query_type,
                execution_count=0,
                total_duration=0.0,
                avg_duration=0.0,
                min_duration=float('inf'),
                max_duration=0.0,
                affected_rows=0,
                index_usage=0.0,
                cache_hit_rate=0.0,
                error_count=0,
                last_execution=datetime.now()
            )
        
        stats = self.query_stats[query_hash]
        stats.execution_count += 1
        stats.total_duration += duration
        stats.avg_duration = stats.total_duration / stats.execution_count
        stats.min_duration = min(stats.min_duration, duration)
        stats.max_duration = max(stats.max_duration, duration)
        stats.affected_rows += affected_rows
        stats.last_execution = datetime.now()
        
        if error:
            stats.error_count += 1
    
    def get_query_from_cache(self, query_hash: str) -> Optional[Any]:
        """캐시에서 쿼리 결과 조회"""
        if query_hash in self.query_cache:
            self.cache_hits += 1
            return self.query_cache[query_hash]
        else:
            self.cache_misses += 1
            return None
    
    def cache_query_result(self, query_hash: str, result: Any) -> None:
        """쿼리 결과 캐시"""
        # 간단한 LRU 구현 (실제로는 더 정교한 캐시 필요)
        if len(self.query_cache) > 1000:  # 최대 1000개
            # 가장 오래된 항목 제거 (단순화된 버전)
            oldest_key = next(iter(self.query_cache))
            del self.query_cache[oldest_key]
        
        self.query_cache[query_hash] = {
            'result': result,
            'cached_at': datetime.now()
        }
    
    def analyze_slow_queries(self, threshold_seconds: float = 1.0) -> List[Dict[str, Any]]:
        """느린 쿼리 분석"""
        slow_queries = []
        
        for query_hash, stats in self.query_stats.items():
            if stats.avg_duration > threshold_seconds:
                analysis = self.query_analyzer.analyze_query("")  # 실제로는 원본 쿼리 필요
                
                slow_queries.append({
                    'query_hash': query_hash,
                    'stats': stats,
                    'analysis': analysis.unwrap() if analysis.is_success() else {},
                    'priority': self._calculate_optimization_priority(stats)
                })
        
        # 우선순위 순으로 정렬
        slow_queries.sort(key=lambda x: (
            x['priority'].value,
            -x['stats'].execution_count * x['stats'].avg_duration
        ))
        
        return slow_queries
    
    def _calculate_optimization_priority(self, stats: QueryStats) -> OptimizationPriority:
        """최적화 우선순위 계산"""
        impact_score = stats.execution_count * stats.avg_duration
        
        if stats.avg_duration > 10.0 or impact_score > 1000:
            return OptimizationPriority.CRITICAL
        elif stats.avg_duration > 5.0 or impact_score > 500:
            return OptimizationPriority.HIGH
        elif stats.avg_duration > 2.0 or impact_score > 100:
            return OptimizationPriority.MEDIUM
        else:
            return OptimizationPriority.LOW
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / max(1, total_requests)
        
        return {
            'cache_size': len(self.query_cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'total_queries_tracked': len(self.query_stats)
        }

class DatabaseOptimizer:
    """데이터베이스 최적화 엔진"""
    
    def __init__(self, config: Optional[DatabaseOptimizationConfig] = None):
        self.config = config or DatabaseOptimizationConfig()
        
        self.query_optimizer = QueryOptimizer(self.config.database_type)
        self.connection_pool_optimizer = ConnectionPoolOptimizer(self.config)
        self.index_optimizer = IndexOptimizer(self.config.database_type)
        
        self.monitoring_task: Optional[asyncio.Task] = None
        self.performance_history: deque = deque(maxlen=100)
        self.is_running = False
    
    async def initialize(self) -> Result[bool, str]:
        """데이터베이스 최적화 엔진 초기화"""
        try:
            if self.config.monitoring_interval_seconds > 0:
                await self.start_monitoring()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Database optimizer initialization failed: {e}")
    
    async def start_monitoring(self) -> Result[bool, str]:
        """데이터베이스 모니터링 시작"""
        if self.is_running:
            return Success(True)
            
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            return Success(True)
            
        except Exception as e:
            return Failure(f"Failed to start database monitoring: {e}")
    
    async def stop_monitoring(self) -> Result[bool, str]:
        """데이터베이스 모니터링 중지"""
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
            return Failure(f"Failed to stop database monitoring: {e}")
    
    async def _monitoring_loop(self) -> None:
        """데이터베이스 모니터링 루프"""
        while self.is_running:
            try:
                performance_data = await self._collect_performance_data()
                self.performance_history.append({
                    'timestamp': datetime.now(),
                    'data': performance_data
                })
                
                # 자동 최적화 (활성화된 경우)
                if self.config.auto_optimization:
                    await self._auto_optimize(performance_data)
                
                await asyncio.sleep(self.config.monitoring_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Database monitoring error: {e}")
                await asyncio.sleep(self.config.monitoring_interval_seconds)
    
    async def _collect_performance_data(self) -> Dict[str, Any]:
        """성능 데이터 수집"""
        return {
            'query_stats': dict(self.query_optimizer.query_stats),
            'connection_stats': self.connection_pool_optimizer.pool_stats,
            'cache_stats': self.query_optimizer.get_cache_stats(),
            'index_stats': dict(self.index_optimizer.index_usage_stats)
        }
    
    async def _auto_optimize(self, performance_data: Dict[str, Any]) -> None:
        """자동 최적화 (주의: 프로덕션에서는 신중하게 사용)"""
        # 여기서는 로그만 남기고 실제 최적화는 수동 승인 후 실행
        
        # 느린 쿼리 탐지
        slow_queries = self.query_optimizer.analyze_slow_queries(
            self.config.thresholds.slow_query_seconds
        )
        
        if slow_queries:
            critical_queries = [q for q in slow_queries 
                              if q['priority'] == OptimizationPriority.CRITICAL]
            if critical_queries:
                print(f"CRITICAL: {len(critical_queries)} critical slow queries detected")
        
        # 연결 풀 성능 확인
        pool_analysis = self.connection_pool_optimizer.analyze_pool_performance()
        if pool_analysis['performance_score'] < 50:
            print(f"WARNING: Connection pool performance score: {pool_analysis['performance_score']}")
    
    # Public 인터페이스 메소드들
    async def analyze_query_performance(self, query: str) -> Result[Dict[str, Any], str]:
        """쿼리 성능 분석"""
        try:
            analysis_result = self.query_optimizer.query_analyzer.analyze_query(query)
            if not analysis_result.is_success():
                return analysis_result
            
            analysis = analysis_result.unwrap()
            
            # 쿼리 해시로 기존 통계 확인
            query_hash = self.query_optimizer.query_analyzer.generate_query_hash(query)
            if query_hash in self.query_optimizer.query_stats:
                analysis['historical_stats'] = self.query_optimizer.query_stats[query_hash]
            
            return Success(analysis)
            
        except Exception as e:
            return Failure(f"Query performance analysis failed: {e}")
    
    def record_query_execution(self, query: str, duration: float, 
                             affected_rows: int = 0, error: Optional[str] = None) -> None:
        """쿼리 실행 기록"""
        self.query_optimizer.record_query_execution(query, duration, affected_rows, error)
    
    def record_connection_event(self, event_type: str, duration: float = 0, success: bool = True) -> None:
        """연결 이벤트 기록"""
        if event_type == 'acquisition':
            self.connection_pool_optimizer.record_connection_acquisition(duration, success)
        elif event_type == 'timeout':
            self.connection_pool_optimizer.record_connection_timeout()
    
    def update_connection_pool_state(self, total: int, active: int, idle: int, waiting: int = 0) -> None:
        """연결 풀 상태 업데이트"""
        self.connection_pool_optimizer.update_pool_state(total, active, idle, waiting)
    
    def record_index_usage(self, index_name: str, usage_type: str, scan_cost: float = 0) -> None:
        """인덱스 사용 기록"""
        self.index_optimizer.record_index_usage(index_name, usage_type, scan_cost)
    
    async def optimize(self) -> Result[Dict[str, Any], str]:
        """데이터베이스 최적화 실행"""
        try:
            # 종합 분석 수행
            slow_queries = self.query_optimizer.analyze_slow_queries(
                self.config.thresholds.slow_query_seconds
            )
            
            connection_analysis = self.connection_pool_optimizer.analyze_pool_performance()
            index_analysis = self.index_optimizer.analyze_index_performance()
            cache_stats = self.query_optimizer.get_cache_stats()
            
            # 최적화 추천사항 생성
            recommendations = self._generate_optimization_recommendations(
                slow_queries, connection_analysis, index_analysis, cache_stats
            )
            
            # 성능 점수 계산
            performance_score = self._calculate_overall_performance_score(
                slow_queries, connection_analysis, index_analysis, cache_stats
            )
            
            results = {
                'performance_score': performance_score,
                'slow_queries': slow_queries,
                'connection_analysis': connection_analysis,
                'index_analysis': index_analysis,
                'cache_stats': cache_stats,
                'recommendations': recommendations,
                'optimization_summary': {
                    'critical_issues': len([q for q in slow_queries if q['priority'] == OptimizationPriority.CRITICAL]),
                    'high_priority_issues': len([q for q in slow_queries if q['priority'] == OptimizationPriority.HIGH]),
                    'total_recommendations': len(recommendations)
                }
            }
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"Database optimization failed: {e}")
    
    def _generate_optimization_recommendations(self, slow_queries: List, connection_analysis: Dict,
                                             index_analysis: Dict, cache_stats: Dict) -> List[str]:
        """최적화 추천사항 생성"""
        recommendations = []
        
        # 쿼리 최적화 추천
        critical_queries = [q for q in slow_queries if q['priority'] == OptimizationPriority.CRITICAL]
        if critical_queries:
            recommendations.append(f"URGENT: Optimize {len(critical_queries)} critical slow queries")
        
        high_priority_queries = [q for q in slow_queries if q['priority'] == OptimizationPriority.HIGH]
        if high_priority_queries:
            recommendations.append(f"Optimize {len(high_priority_queries)} high-priority slow queries")
        
        # 연결 풀 추천
        recommendations.extend(connection_analysis.get('recommendations', []))
        
        # 인덱스 추천
        if index_analysis['unused_indexes']:
            recommendations.append(f"Consider dropping {len(index_analysis['unused_indexes'])} unused indexes")
        
        if index_analysis['inefficient_indexes']:
            recommendations.append(f"Review {len(index_analysis['inefficient_indexes'])} inefficient indexes")
        
        # 캐시 추천
        if cache_stats['hit_rate'] < 0.5:
            recommendations.append("Low query cache hit rate - consider cache optimization")
        
        return recommendations
    
    def _calculate_overall_performance_score(self, slow_queries: List, connection_analysis: Dict,
                                           index_analysis: Dict, cache_stats: Dict) -> float:
        """전체 성능 점수 계산 (0-100)"""
        score = 100.0
        
        # 느린 쿼리 패널티
        critical_count = len([q for q in slow_queries if q['priority'] == OptimizationPriority.CRITICAL])
        high_count = len([q for q in slow_queries if q['priority'] == OptimizationPriority.HIGH])
        
        score -= critical_count * 15  # 크리티컬 쿼리당 15점 감점
        score -= high_count * 10      # 높은 우선순위 쿼리당 10점 감점
        
        # 연결 풀 성능
        pool_score = connection_analysis.get('performance_score', 100)
        score = (score + pool_score) / 2  # 평균 계산
        
        # 캐시 성능
        cache_bonus = cache_stats['hit_rate'] * 10  # 최대 10점 보너스
        score += cache_bonus
        
        # 인덱스 최적화 상태
        if index_analysis['unused_indexes']:
            score -= len(index_analysis['unused_indexes']) * 2
        
        return max(0.0, min(100.0, score))
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보"""
        if not self.performance_history:
            return {}
        
        latest = self.performance_history[-1]
        return {
            'timestamp': latest['timestamp'],
            'total_queries_tracked': len(self.query_optimizer.query_stats),
            'cache_hit_rate': self.query_optimizer.get_cache_stats()['hit_rate'],
            'connection_pool_efficiency': self.connection_pool_optimizer.pool_stats.pool_efficiency,
            'total_indexes_tracked': len(self.index_optimizer.index_usage_stats)
        }
    
    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            
            # 캐시 정리
            self.query_optimizer.query_cache.clear()
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")

# 전역 optimizer 인스턴스
_database_optimizer: Optional[DatabaseOptimizer] = None

def get_database_optimizer(config: Optional[DatabaseOptimizationConfig] = None) -> DatabaseOptimizer:
    """데이터베이스 optimizer 싱글톤 인스턴스 반환"""
    global _database_optimizer
    if _database_optimizer is None:
        _database_optimizer = DatabaseOptimizer(config)
    return _database_optimizer

async def optimize_database_performance(database_type: DatabaseType = DatabaseType.POSTGRESQL) -> Result[Dict[str, Any], str]:
    """데이터베이스 성능 최적화 실행"""
    config = DatabaseOptimizationConfig(database_type=database_type)
    optimizer = get_database_optimizer(config)
    
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    
    return await optimizer.optimize()