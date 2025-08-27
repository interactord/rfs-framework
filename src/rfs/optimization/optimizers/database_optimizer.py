"""
Database Optimization Engine for RFS Framework

데이터베이스 성능 최적화, 쿼리 최적화, 연결 풀 관리
- 쿼리 성능 분석 및 최적화
- 인덱스 최적화 추천
- 연결 풀 튜닝 및 관리
- 데이터베이스 모니터링 및 분석
"""

import asyncio
import hashlib
import re
import threading
import time
import weakref
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono


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

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DatabaseThresholds:
    """데이터베이스 임계값 설정"""

    slow_query_seconds: float = 1.0
    connection_pool_min = 5
    connection_pool_max = 20
    connection_timeout_seconds: float = 30.0
    query_cache_size_mb = 100
    max_concurrent_queries = 100
    index_usage_threshold: float = 0.1


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
    enable_query_caching = True
    enable_connection_pooling = True
    enable_query_analysis = True
    enable_index_analysis = True
    monitoring_interval_seconds: float = 60.0
    auto_optimization = False


class QueryAnalyzer:
    """쿼리 분석기"""

    def __init__(self, database_type: DatabaseType):
        self.database_type = database_type
        self.query_patterns = self._initialize_patterns()
        self.performance_rules = self._initialize_performance_rules()

    def _initialize_patterns(self) -> Dict[str, re.Pattern]:
        """쿼리 패턴 초기화"""
        patterns = {
            "select": re.compile("^\\s*SELECT\\s+", re.IGNORECASE),
            "insert": re.compile("^\\s*INSERT\\s+", re.IGNORECASE),
            "update": re.compile("^\\s*UPDATE\\s+", re.IGNORECASE),
            "delete": re.compile("^\\s*DELETE\\s+", re.IGNORECASE),
            "create": re.compile("^\\s*CREATE\\s+", re.IGNORECASE),
            "alter": re.compile("^\\s*ALTER\\s+", re.IGNORECASE),
            "index": re.compile("^\\s*CREATE\\s+.*INDEX\\s+", re.IGNORECASE),
            "select_star": re.compile("SELECT\\s+\\*\\s+FROM", re.IGNORECASE),
            "no_where": re.compile("(UPDATE|DELETE)(?!.*WHERE)", re.IGNORECASE),
            "cartesian_join": re.compile(
                "FROM\\s+\\w+\\s*,\\s*\\w+(?!.*WHERE)", re.IGNORECASE
            ),
            "function_in_where": re.compile(
                "WHERE\\s+\\w*\\([^)]*\\)\\s*[=<>]", re.IGNORECASE
            ),
            "like_leading_wildcard": re.compile("LIKE\\s+[\\'\"]%", re.IGNORECASE),
            "or_condition": re.compile("WHERE.*OR", re.IGNORECASE),
        }
        return patterns

    def _initialize_performance_rules(self) -> List[Dict[str, Any]]:
        """성능 규칙 초기화"""
        rules = [
            {
                "name": "avoid_select_star",
                "pattern": "select_star",
                "severity": "medium",
                "suggestion": "Avoid SELECT * - specify only needed columns",
            },
            {
                "name": "missing_where_clause",
                "pattern": "no_where",
                "severity": "high",
                "suggestion": "UPDATE/DELETE without WHERE clause affects all rows",
            },
            {
                "name": "cartesian_product",
                "pattern": "cartesian_join",
                "severity": "critical",
                "suggestion": "Potential cartesian product - add JOIN conditions",
            },
            {
                "name": "function_on_indexed_column",
                "pattern": "function_in_where",
                "severity": "medium",
                "suggestion": "Functions on indexed columns prevent index usage",
            },
            {
                "name": "leading_wildcard_like",
                "pattern": "like_leading_wildcard",
                "severity": "medium",
                "suggestion": "LIKE with leading wildcard prevents index usage",
            },
            {
                "name": "or_condition_performance",
                "pattern": "or_condition",
                "severity": "low",
                "suggestion": "OR conditions may prevent index usage - consider UNION",
            },
        ]
        return rules

    def analyze_query(self, query: str) -> Result[Dict[str, Any], str]:
        """쿼리 분석"""
        try:
            analysis = {
                "query_type": self._detect_query_type(query),
                "complexity_score": self._calculate_complexity(query),
                "performance_issues": self._detect_performance_issues(query),
                "index_recommendations": self._recommend_indexes(query),
                "optimization_suggestions": [],
            }
            for issue in analysis.get("performance_issues"):
                analysis["optimization_suggestions"] = analysis.get(
                    "optimization_suggestions", []
                ) + [issue.get("suggestion")]
            return Success(analysis)
        except Exception as e:
            return Failure(f"Query analysis failed: {e}")

    def _detect_query_type(self, query: str) -> QueryType:
        """쿼리 유형 탐지"""
        query_clean = query.strip().upper()
        if query_clean.startswith("SELECT"):
            return QueryType.SELECT
        elif query_clean.startswith("INSERT"):
            return QueryType.INSERT
        elif query_clean.startswith("UPDATE"):
            return QueryType.UPDATE
        elif query_clean.startswith("DELETE"):
            return QueryType.DELETE
        elif query_clean.startswith("CREATE"):
            return QueryType.CREATE
        elif query_clean.startswith("ALTER"):
            return QueryType.ALTER
        else:
            return QueryType.SELECT

    def _calculate_complexity(self, query: str) -> float:
        """쿼리 복잡도 계산 (0-100)"""
        complexity = 0.0
        query_upper = query.upper()
        complexity = complexity + 10
        join_count = query_upper.count(" JOIN ")
        complexity = complexity + join_count * 15
        subquery_count = query_upper.count("(SELECT")
        complexity = complexity + subquery_count * 20
        if "GROUP BY" in query_upper:
            complexity = complexity + 10
        if "ORDER BY" in query_upper:
            complexity = complexity + 5
        if "HAVING" in query_upper:
            complexity = complexity + 15
        union_count = query_upper.count(" UNION ")
        complexity = complexity + union_count * 10
        if query_upper.startswith("WITH"):
            complexity = complexity + 20
        return min(100.0, complexity)

    def _detect_performance_issues(self, query: str) -> List[Dict[str, Any]]:
        """성능 문제 탐지"""
        issues = []
        for rule in self.performance_rules:
            pattern = self.query_patterns.get(rule["pattern"])
            if pattern and pattern.search(query):
                issues = issues + [
                    {
                        "name": rule.get("name"),
                        "severity": rule.get("severity"),
                        "suggestion": rule.get("suggestion"),
                    }
                ]
        return issues

    def _recommend_indexes(self, query: str) -> List[str]:
        """인덱스 추천"""
        recommendations = []
        query_upper = query.upper()
        where_match = re.search(
            "WHERE\\s+(.*?)(?:\\s+GROUP\\s+BY|\\s+ORDER\\s+BY|\\s+HAVING|$)",
            query_upper,
        )
        if where_match:
            where_clause = where_match.group(1)
            equality_columns = re.findall(r"(\w+)\s*=", where_clause)
            for col in equality_columns:
                recommendations = recommendations + [
                    f"Consider index on column: {col.lower()}"
                ]
        order_match = re.search(
            "ORDER\\s+BY\\s+(.*?)(?:\\s+LIMIT|\\s+OFFSET|$)", query_upper
        )
        if order_match:
            order_clause = order_match.group(1)
            order_columns = re.findall("(\\w+)", order_clause)
            for col in order_columns:
                recommendations = recommendations + [
                    f"Consider index for ORDER BY: {col.lower()}"
                ]
        return recommendations

    def generate_query_hash(self, query: str) -> str:
        """쿼리 해시 생성 (파라미터 정규화)"""
        normalized = re.sub("'[^']*'", "'?'", query)
        normalized = re.sub("\\b\\d+\\b", "?", normalized)
        normalized = re.sub("\\s+", " ", normalized.strip())
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
            pool_efficiency=0.0,
        )
        self.acquisition_times: deque = deque(maxlen=1000)
        self.lock = threading.Lock()

    def record_connection_acquisition(self, duration: float, success: bool) -> None:
        """연결 획득 기록"""
        with self.lock:
            self.pool_stats.total_acquisitions = self.pool_stats.total_acquisitions + 1
            self.acquisition_times = self.acquisition_times + [duration]
            if self.acquisition_times:
                self.pool_stats.avg_acquisition_time = sum(
                    self.acquisition_times
                ) / len(self.acquisition_times)
            if not success:
                self.pool_stats.error_count = self.pool_stats.error_count + 1

    def record_connection_timeout(self) -> None:
        """연결 타임아웃 기록"""
        with self.lock:
            self.pool_stats.timeout_count = self.pool_stats.timeout_count + 1

    def update_pool_state(
        self, total: int, active: int, idle: int, waiting: int
    ) -> None:
        """풀 상태 업데이트"""
        with self.lock:
            self.pool_stats.total_connections = total
            self.pool_stats.active_connections = active
            self.pool_stats.idle_connections = idle
            self.pool_stats.waiting_connections = waiting
            if total > 0:
                self.pool_stats.pool_efficiency = active / total

    def analyze_pool_performance(self) -> Dict[str, Any]:
        """풀 성능 분석"""
        analysis = {
            "current_stats": self.pool_stats,
            "recommendations": [],
            "optimal_pool_size": self._calculate_optimal_pool_size(),
            "performance_score": self._calculate_performance_score(),
        }
        if self.pool_stats.avg_acquisition_time > 0.1:
            analysis["recommendations"] = analysis.get("recommendations") + [
                "Connection acquisition time is high - consider increasing pool size"
            ]
        if self.pool_stats.pool_efficiency < 0.3:
            analysis["recommendations"] = analysis.get("recommendations") + [
                "Low pool efficiency - consider reducing pool size"
            ]
        elif self.pool_stats.pool_efficiency > 0.9:
            analysis["recommendations"] = analysis.get("recommendations") + [
                "High pool utilization - consider increasing pool size"
            ]
        if self.pool_stats.timeout_count > 0:
            analysis["recommendations"] = analysis.get("recommendations") + [
                "Connection timeouts detected - increase pool size or timeout duration"
            ]
        return analysis

    def _calculate_optimal_pool_size(self) -> Tuple[int, int]:
        """최적 풀 크기 계산"""
        current_min = self.config.thresholds.connection_pool_min
        current_max = self.config.thresholds.connection_pool_max
        if self.pool_stats.pool_efficiency > 0.8:
            optimal_max = min(current_max + 5, 50)
        elif self.pool_stats.pool_efficiency < 0.3:
            optimal_max = max(current_max - 5, 10)
        else:
            optimal_max = current_max
        optimal_min = max(optimal_max // 4, 2)
        return (optimal_min, optimal_max)

    def _calculate_performance_score(self) -> float:
        """성능 점수 계산 (0-100)"""
        score = 100.0
        if self.pool_stats.avg_acquisition_time > 0.5:
            score = score - 40
        elif self.pool_stats.avg_acquisition_time > 0.1:
            score = score - 20
        if self.pool_stats.total_acquisitions > 0:
            timeout_rate = (
                self.pool_stats.timeout_count / self.pool_stats.total_acquisitions
            )
            score = score - timeout_rate * 100
        if 0.4 <= self.pool_stats.pool_efficiency <= 0.8:
            score = score + 10
        return max(0.0, min(100.0, score))


class IndexOptimizer:
    """인덱스 최적화"""

    def __init__(self, database_type: DatabaseType):
        self.database_type = database_type
        self.index_usage_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "scan_count": 0,
                "lookup_count": 0,
                "update_count": 0,
                "size_mb": 0,
                "last_used": None,
                "efficiency_score": 0.0,
            }
        )

    def record_index_usage(self, index_name: str, usage_type: str, scan_cost=0) -> None:
        """인덱스 사용 기록"""
        stats = self.index_usage_stats[index_name]
        match usage_type:
            case "scan":
                stats["scan_count"] = stats["scan_count"] + 1
            case "lookup":
                stats["lookup_count"] = stats["lookup_count"] + 1
            case "update":
                stats["update_count"] = stats["update_count"] + 1
        stats["last_used"] = {"last_used": datetime.now()}
        total_usage = stats["scan_count"] + stats["lookup_count"]
        if total_usage > 0:
            scan_ratio = stats["scan_count"] / total_usage
            lookup_ratio = stats["lookup_count"] / total_usage
            stats["efficiency_score"] = {
                "efficiency_score": lookup_ratio * 100 + scan_ratio * 20
            }

    def analyze_index_performance(self) -> Dict[str, Any]:
        """인덱스 성능 분석"""
        analysis = {
            "total_indexes": len(self.index_usage_stats),
            "unused_indexes": [],
            "inefficient_indexes": [],
            "recommended_indexes": [],
            "optimization_summary": {},
        }
        current_time = datetime.now()
        for index_name, stats in self.index_usage_stats.items():
            total_usage = stats["scan_count"] + stats["lookup_count"]
            if total_usage == 0 or (
                stats["last_used"] and (current_time - stats.get("last_used")).days > 30
            ):
                analysis["unused_indexes"] = analysis.get("unused_indexes") + [
                    {
                        "name": index_name,
                        "reason": "Not used in last 30 days",
                        "recommendation": "Consider dropping this index",
                    }
                ]
            elif stats.get("efficiency_score") < 30:
                analysis["inefficient_indexes"] = analysis.get(
                    "inefficient_indexes"
                ) + [
                    {
                        "name": index_name,
                        "efficiency_score": stats.get("efficiency_score"),
                        "scan_count": stats.get("scan_count"),
                        "lookup_count": stats.get("lookup_count"),
                        "recommendation": "Index causes more scans than lookups",
                    }
                ]
        analysis["optimization_summary"] = {
            "optimization_summary": {
                "indexes_to_drop": len(analysis.get("unused_indexes")),
                "indexes_to_review": len(analysis.get("inefficient_indexes")),
                "potential_space_savings": self._calculate_space_savings(
                    analysis.get("unused_indexes")
                ),
            }
        }
        return analysis

    def _calculate_space_savings(self, unused_indexes: List[Dict]) -> Dict[str, float]:
        """공간 절약 계산"""
        total_size = 0
        for index_info in unused_indexes:
            index_name = index_info["name"]
            if index_name in self.index_usage_stats:
                total_size = total_size + self.index_usage_stats[index_name].get(
                    "size_mb", 0
                )
        return {
            "total_mb": total_size,
            "estimated_performance_gain": min(total_size * 0.1, 20),
        }

    def generate_index_recommendations(
        self, query_stats: Dict[str, QueryStats]
    ) -> List[str]:
        """쿼리 통계 기반 인덱스 추천"""
        recommendations = []
        column_usage = Counter()
        for stats in query_stats.values():
            if stats.avg_duration > 1.0 and stats.execution_count > 10:
                recommendations = recommendations + [
                    f"Consider indexing for frequently slow query: {stats.query_hash[:8]}"
                ]
        return recommendations


class QueryOptimizer:
    """쿼리 최적화"""

    def __init__(self, database_type: DatabaseType):
        self.database_type = database_type
        self.query_analyzer = QueryAnalyzer(database_type)
        self.query_cache = {}
        self.query_stats = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def record_query_execution(
        self,
        query: str,
        duration: float,
        affected_rows=0,
        error=None,
    ) -> None:
        """쿼리 실행 기록"""
        query_hash = self.query_analyzer.generate_query_hash(query)
        query_type = self.query_analyzer._detect_query_type(query)
        if query_hash not in self.query_stats:
            self.query_stats = {
                **self.query_stats,
                query_hash: QueryStats(
                    query_hash=query_hash,
                    query_type=query_type,
                    execution_count=0,
                    total_duration=0.0,
                    avg_duration=0.0,
                    min_duration=float("inf"),
                    max_duration=0.0,
                    affected_rows=0,
                    index_usage=0.0,
                    cache_hit_rate=0.0,
                    error_count=0,
                    last_execution=datetime.now(),
                ),
            }
        stats = self.query_stats[query_hash]
        stats.execution_count = stats.execution_count + 1
        stats.total_duration = stats.total_duration + duration
        stats.avg_duration = stats.total_duration / stats.execution_count
        stats.min_duration = min(stats.min_duration, duration)
        stats.max_duration = max(stats.max_duration, duration)
        stats.affected_rows = stats.affected_rows + affected_rows
        stats.last_execution = datetime.now()
        if error:
            stats.error_count = stats.error_count + 1

    def get_query_from_cache(self, query_hash: str) -> Optional[Any]:
        """캐시에서 쿼리 결과 조회"""
        if query_hash in self.query_cache:
            self.cache_hits = self.cache_hits + 1
            return self.query_cache[query_hash]
        else:
            self.cache_misses = self.cache_misses + 1
            return None

    def cache_query_result(self, query_hash: str, result: Any) -> None:
        """쿼리 결과 캐시"""
        if len(self.query_cache) > 1000:
            oldest_key = next(iter(self.query_cache))
            del self.query_cache[oldest_key]
        self.query_cache = {
            **self.query_cache,
            query_hash: {"result": result, "cached_at": datetime.now()},
        }

    def analyze_slow_queries(self, threshold_seconds=1.0) -> List[Dict[str, Any]]:
        """느린 쿼리 분석"""
        slow_queries = []
        for query_hash, stats in self.query_stats.items():
            if stats.avg_duration > threshold_seconds:
                analysis = self.query_analyzer.analyze_query("")
                slow_queries = slow_queries + [
                    {
                        "query_hash": query_hash,
                        "stats": stats,
                        "analysis": analysis.unwrap() if analysis.is_success() else {},
                        "priority": self._calculate_optimization_priority(stats),
                    }
                ]
        slow_queries.sort(
            key=lambda x: (
                x.get("priority").value,
                -x.get("stats").execution_count * x.get("stats").avg_duration,
            )
        )
        return slow_queries

    def _calculate_optimization_priority(
        self, stats: QueryStats
    ) -> OptimizationPriority:
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
            "cache_size": len(self.query_cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "total_queries_tracked": len(self.query_stats),
        }


class DatabaseOptimizer:
    """데이터베이스 최적화 엔진"""

    def __init__(self, config=None):
        self.config = config or DatabaseOptimizationConfig()
        self.query_optimizer = QueryOptimizer(self.config.database_type)
        self.connection_pool_optimizer = ConnectionPoolOptimizer(self.config)
        self.index_optimizer = IndexOptimizer(self.config.database_type)
        self.monitoring_task = None
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
                self.performance_history = self.performance_history + [
                    {"timestamp": datetime.now(), "data": performance_data}
                ]
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
            "query_stats": dict(self.query_optimizer.query_stats),
            "connection_stats": self.connection_pool_optimizer.pool_stats,
            "cache_stats": self.query_optimizer.get_cache_stats(),
            "index_stats": dict(self.index_optimizer.index_usage_stats),
        }

    async def _auto_optimize(self, performance_data: Dict[str, Any]) -> None:
        """자동 최적화 (주의: 프로덕션에서는 신중하게 사용)"""
        slow_queries = self.query_optimizer.analyze_slow_queries(
            self.config.thresholds.slow_query_seconds
        )
        if slow_queries:
            critical_queries = [
                q
                for q in slow_queries
                if q.get("priority") == OptimizationPriority.CRITICAL
            ]
            if critical_queries:
                print(
                    f"CRITICAL: {len(critical_queries)} critical slow queries detected"
                )
        pool_analysis = self.connection_pool_optimizer.analyze_pool_performance()
        if pool_analysis.get("performance_score") < 50:
            print(
                f"WARNING: Connection pool performance score: {pool_analysis.get('performance_score')}"
            )

    async def analyze_query_performance(
        self, query: str
    ) -> Result[Dict[str, Any], str]:
        """쿼리 성능 분석"""
        try:
            analysis_result = self.query_optimizer.query_analyzer.analyze_query(query)
            if not analysis_result.is_success():
                return analysis_result
            analysis = analysis_result.unwrap()
            query_hash = self.query_optimizer.query_analyzer.generate_query_hash(query)
            if query_hash in self.query_optimizer.query_stats:
                analysis["historical_stats"] = {
                    "historical_stats": self.query_optimizer.query_stats[query_hash]
                }
            return Success(analysis)
        except Exception as e:
            return Failure(f"Query performance analysis failed: {e}")

    def record_query_execution(
        self,
        query: str,
        duration: float,
        affected_rows=0,
        error=None,
    ) -> None:
        """쿼리 실행 기록"""
        self.query_optimizer.record_query_execution(
            query, duration, affected_rows, error
        )

    def record_connection_event(
        self, event_type: str, duration=0, success=True
    ) -> None:
        """연결 이벤트 기록"""
        if event_type == "acquisition":
            self.connection_pool_optimizer.record_connection_acquisition(
                duration, success
            )
        elif event_type == "timeout":
            self.connection_pool_optimizer.record_connection_timeout()

    def update_connection_pool_state(
        self, total: int, active: int, idle: int, waiting=0
    ) -> None:
        """연결 풀 상태 업데이트"""
        self.connection_pool_optimizer.update_pool_state(total, active, idle, waiting)

    def record_index_usage(self, index_name: str, usage_type: str, scan_cost=0) -> None:
        """인덱스 사용 기록"""
        self.index_optimizer.record_index_usage(index_name, usage_type, scan_cost)

    async def optimize(self) -> Result[Dict[str, Any], str]:
        """데이터베이스 최적화 실행"""
        try:
            slow_queries = self.query_optimizer.analyze_slow_queries(
                self.config.thresholds.slow_query_seconds
            )
            connection_analysis = (
                self.connection_pool_optimizer.analyze_pool_performance()
            )
            index_analysis = self.index_optimizer.analyze_index_performance()
            cache_stats = self.query_optimizer.get_cache_stats()
            recommendations = self._generate_optimization_recommendations(
                slow_queries, connection_analysis, index_analysis, cache_stats
            )
            performance_score = self._calculate_overall_performance_score(
                slow_queries, connection_analysis, index_analysis, cache_stats
            )
            results = {
                "performance_score": performance_score,
                "slow_queries": slow_queries,
                "connection_analysis": connection_analysis,
                "index_analysis": index_analysis,
                "cache_stats": cache_stats,
                "recommendations": recommendations,
                "optimization_summary": {
                    "critical_issues": len(
                        [
                            q
                            for q in slow_queries
                            if q.get("priority") == OptimizationPriority.CRITICAL
                        ]
                    ),
                    "high_priority_issues": len(
                        [
                            q
                            for q in slow_queries
                            if q.get("priority") == OptimizationPriority.HIGH
                        ]
                    ),
                    "total_recommendations": len(recommendations),
                },
            }
            return Success(results)
        except Exception as e:
            return Failure(f"Database optimization failed: {e}")

    def _generate_optimization_recommendations(
        self,
        slow_queries: List,
        connection_analysis: Dict,
        index_analysis: Dict,
        cache_stats: Dict,
    ) -> List[str]:
        """최적화 추천사항 생성"""
        recommendations = []
        critical_queries = [
            q for q in slow_queries if q["priority"] == OptimizationPriority.CRITICAL
        ]
        if critical_queries:
            recommendations = recommendations + [
                f"URGENT: Optimize {len(critical_queries)} critical slow queries"
            ]
        high_priority_queries = [
            q for q in slow_queries if q["priority"] == OptimizationPriority.HIGH
        ]
        if high_priority_queries:
            recommendations = recommendations + [
                f"Optimize {len(high_priority_queries)} high-priority slow queries"
            ]
        recommendations = recommendations + connection_analysis.get(
            "recommendations", []
        )
        if index_analysis.get("unused_indexes"):
            recommendations = recommendations + [
                f"Consider dropping {len(index_analysis.get('unused_indexes'))} unused indexes"
            ]
        if index_analysis.get("inefficient_indexes"):
            recommendations = recommendations + [
                f"Review {len(index_analysis.get('inefficient_indexes'))} inefficient indexes"
            ]
        if cache_stats.get("hit_rate") < 0.5:
            recommendations = recommendations + [
                "Low query cache hit rate - consider cache optimization"
            ]
        return recommendations

    def _calculate_overall_performance_score(
        self,
        slow_queries: List,
        connection_analysis: Dict,
        index_analysis: Dict,
        cache_stats: Dict,
    ) -> float:
        """전체 성능 점수 계산 (0-100)"""
        score = 100.0
        critical_count = len(
            [q for q in slow_queries if q["priority"] == OptimizationPriority.CRITICAL]
        )
        high_count = len(
            [q for q in slow_queries if q["priority"] == OptimizationPriority.HIGH]
        )
        score = score - critical_count * 15
        score = score - high_count * 10
        pool_score = connection_analysis.get("performance_score", 100)
        score = (score + pool_score) / 2
        cache_bonus = cache_stats["hit_rate"] * 10
        score = score + cache_bonus
        if index_analysis.get("unused_indexes"):
            score = score - len(index_analysis["unused_indexes"]) * 2
        return max(0.0, min(100.0, score))

    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보"""
        if not self.performance_history:
            return {}
        latest = self.performance_history[-1]
        return {
            "timestamp": latest.get("timestamp"),
            "total_queries_tracked": len(self.query_optimizer.query_stats),
            "cache_hit_rate": self.query_optimizer.get_cache_stats()["hit_rate"],
            "connection_pool_efficiency": self.connection_pool_optimizer.pool_stats.pool_efficiency,
            "total_indexes_tracked": len(self.index_optimizer.index_usage_stats),
        }

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            query_cache = {}
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_database_optimizer = None


def get_database_optimizer(
    config=None,
) -> DatabaseOptimizer:
    """데이터베이스 optimizer 싱글톤 인스턴스 반환"""
    # global _database_optimizer - removed for functional programming
    if _database_optimizer is None:
        _database_optimizer = DatabaseOptimizer(config)
    return _database_optimizer


async def optimize_database_performance(
    database_type: DatabaseType = DatabaseType.POSTGRESQL,
) -> Result[Dict[str, Any], str]:
    """데이터베이스 성능 최적화 실행"""
    config = DatabaseOptimizationConfig(database_type=database_type)
    optimizer = get_database_optimizer(config)
    init_result = await optimizer.initialize()
    if not init_result.is_success():
        return init_result
    return await optimizer.optimize()
