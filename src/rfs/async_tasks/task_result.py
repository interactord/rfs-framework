"""
RFS v4.1 Task Result Management System
작업 결과 관리 및 추적 시스템

주요 기능:
- TaskResult: 작업 결과 데이터 구조
- TaskResultStore: 결과 저장소 관리
- ResultAnalyzer: 결과 분석 및 통계
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from dataclasses import dataclass, field, asdict
from enum import Enum
import pickle
import gzip
from pathlib import Path

from ..core.result import Result, Success, Failure
from ..core.config import get_config
from .task_definition import TaskType, TaskContext


class ResultStatus(Enum):
    """결과 상태"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRY_NEEDED = "retry_needed"


@dataclass
class TaskResult:
    """작업 결과"""
    task_id: str
    task_name: str
    task_type: TaskType
    status: ResultStatus
    
    # 실행 정보
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    
    # 결과 데이터
    result_data: Any = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # 컨텍스트 정보
    context: Optional[TaskContext] = None
    retry_count: int = 0
    
    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # 성능 지표
    memory_used_mb: Optional[float] = None
    cpu_time_ms: Optional[float] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.end_time and self.execution_time_ms is None:
            delta = self.end_time - self.start_time
            self.execution_time_ms = int(delta.total_seconds() * 1000)
    
    @classmethod
    def create_success(
        cls,
        task_id: str,
        task_name: str,
        task_type: TaskType,
        result_data: Any,
        start_time: datetime,
        end_time: datetime,
        context: Optional[TaskContext] = None,
        **kwargs
    ) -> "TaskResult":
        """성공 결과 생성"""
        return cls(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            status=ResultStatus.SUCCESS,
            start_time=start_time,
            end_time=end_time,
            result_data=result_data,
            context=context,
            **kwargs
        )
    
    @classmethod
    def create_failure(
        cls,
        task_id: str,
        task_name: str,
        task_type: TaskType,
        error_message: str,
        start_time: datetime,
        end_time: datetime,
        error_type: Optional[str] = None,
        error_traceback: Optional[str] = None,
        context: Optional[TaskContext] = None,
        **kwargs
    ) -> "TaskResult":
        """실패 결과 생성"""
        return cls(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            status=ResultStatus.FAILURE,
            start_time=start_time,
            end_time=end_time,
            error_message=error_message,
            error_type=error_type,
            error_traceback=error_traceback,
            context=context,
            **kwargs
        )
    
    def is_success(self) -> bool:
        """성공 여부"""
        return self.status == ResultStatus.SUCCESS
    
    def is_failure(self) -> bool:
        """실패 여부"""
        return self.status in [ResultStatus.FAILURE, ResultStatus.TIMEOUT, ResultStatus.CANCELLED]
    
    def needs_retry(self) -> bool:
        """재시도 필요 여부"""
        return self.status == ResultStatus.RETRY_NEEDED
    
    def add_tag(self, tag: str) -> None:
        """태그 추가"""
        if tag not in self.tags:
            self.tags.append(tag)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """메타데이터 설정"""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """메타데이터 조회"""
        return self.metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        
        # datetime 객체 직렬화
        if self.start_time:
            data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        
        # 열거형 직렬화
        data["status"] = self.status.value
        data["task_type"] = self.task_type.value
        
        # 컨텍스트 직렬화
        if self.context:
            data["context"] = asdict(self.context)
            data["context"]["task_type"] = self.context.task_type.value
            data["context"]["execution_time"] = self.context.execution_time.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        """딕셔너리에서 복원"""
        # datetime 객체 복원
        if "start_time" in data and isinstance(data["start_time"], str):
            data["start_time"] = datetime.fromisoformat(data["start_time"])
        if "end_time" in data and isinstance(data["end_time"], str):
            data["end_time"] = datetime.fromisoformat(data["end_time"])
        
        # 열거형 복원
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ResultStatus(data["status"])
        if "task_type" in data and isinstance(data["task_type"], str):
            data["task_type"] = TaskType(data["task_type"])
        
        # 컨텍스트 복원
        if "context" in data and data["context"]:
            ctx_data = data["context"]
            if "task_type" in ctx_data and isinstance(ctx_data["task_type"], str):
                ctx_data["task_type"] = TaskType(ctx_data["task_type"])
            if "execution_time" in ctx_data and isinstance(ctx_data["execution_time"], str):
                ctx_data["execution_time"] = datetime.fromisoformat(ctx_data["execution_time"])
            data["context"] = TaskContext(**ctx_data)
        
        return cls(**data)


class TaskResultStore:
    """작업 결과 저장소"""
    
    def __init__(self, storage_path: Optional[str] = None, max_results: int = 10000):
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_results = max_results
        
        # 메모리 저장소
        self._results: Dict[str, TaskResult] = {}
        self._results_by_name: Dict[str, List[str]] = {}  # task_name -> [task_ids]
        self._results_by_status: Dict[ResultStatus, List[str]] = {
            status: [] for status in ResultStatus
        }
        
        # 인덱스
        self._task_ids_by_time: List[str] = []  # 시간순 정렬
        
        # 통계
        self._stats = {
            "total_results": 0,
            "success_count": 0,
            "failure_count": 0,
            "average_execution_time_ms": 0.0
        }
        
        # 자동 정리 설정
        self._cleanup_interval = timedelta(hours=1)
        self._last_cleanup = datetime.now()
        
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            asyncio.create_task(self._load_from_disk())
    
    async def store_result(self, result: TaskResult) -> Result[None, str]:
        """결과 저장"""
        try:
            # 메모리 저장
            self._results[result.task_id] = result
            
            # 인덱스 업데이트
            if result.task_name not in self._results_by_name:
                self._results_by_name[result.task_name] = []
            self._results_by_name[result.task_name].append(result.task_id)
            
            self._results_by_status[result.status].append(result.task_id)
            
            # 시간순 인덱스 업데이트 (이진 검색으로 삽입)
            self._insert_by_time(result.task_id, result.start_time)
            
            # 통계 업데이트
            self._update_statistics(result)
            
            # 디스크에 저장 (비동기)
            if self.storage_path:
                asyncio.create_task(self._save_to_disk(result))
            
            # 자동 정리
            await self._auto_cleanup()
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"Failed to store result: {e}")
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """결과 조회"""
        return self._results.get(task_id)
    
    def get_results_by_name(self, task_name: str) -> List[TaskResult]:
        """이름별 결과 조회"""
        task_ids = self._results_by_name.get(task_name, [])
        return [self._results[task_id] for task_id in task_ids if task_id in self._results]
    
    def get_results_by_status(self, status: ResultStatus) -> List[TaskResult]:
        """상태별 결과 조회"""
        task_ids = self._results_by_status.get(status, [])
        return [self._results[task_id] for task_id in task_ids if task_id in self._results]
    
    def get_recent_results(self, limit: int = 100) -> List[TaskResult]:
        """최근 결과 조회"""
        recent_ids = self._task_ids_by_time[-limit:]
        return [self._results[task_id] for task_id in reversed(recent_ids) if task_id in self._results]
    
    def get_results_in_range(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[TaskResult]:
        """시간 범위내 결과 조회"""
        results = []
        for task_id in self._task_ids_by_time:
            result = self._results.get(task_id)
            if result and start_time <= result.start_time <= end_time:
                results.append(result)
        return results
    
    async def query_results(
        self,
        task_name: Optional[str] = None,
        status: Optional[ResultStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[TaskResult]:
        """복합 조건 결과 조회"""
        results = list(self._results.values())
        
        # 필터링
        if task_name:
            results = [r for r in results if r.task_name == task_name]
        
        if status:
            results = [r for r in results if r.status == status]
        
        if start_time:
            results = [r for r in results if r.start_time >= start_time]
        
        if end_time:
            results = [r for r in results if r.start_time <= end_time]
        
        if tags:
            results = [
                r for r in results 
                if any(tag in r.tags for tag in tags)
            ]
        
        # 시간순 정렬 (최신순)
        results.sort(key=lambda r: r.start_time, reverse=True)
        
        return results[:limit]
    
    def _insert_by_time(self, task_id: str, start_time: datetime) -> None:
        """시간순 인덱스에 삽입"""
        # 이진 검색으로 삽입 위치 찾기
        left, right = 0, len(self._task_ids_by_time)
        
        while left < right:
            mid = (left + right) // 2
            mid_result = self._results.get(self._task_ids_by_time[mid])
            
            if mid_result and mid_result.start_time < start_time:
                left = mid + 1
            else:
                right = mid
        
        self._task_ids_by_time.insert(left, task_id)
    
    def _update_statistics(self, result: TaskResult) -> None:
        """통계 업데이트"""
        self._stats["total_results"] += 1
        
        if result.status == ResultStatus.SUCCESS:
            self._stats["success_count"] += 1
        elif result.is_failure():
            self._stats["failure_count"] += 1
        
        # 평균 실행 시간 업데이트
        if result.execution_time_ms:
            current_avg = self._stats["average_execution_time_ms"]
            total = self._stats["total_results"]
            new_avg = (current_avg * (total - 1) + result.execution_time_ms) / total
            self._stats["average_execution_time_ms"] = new_avg
    
    async def _auto_cleanup(self) -> None:
        """자동 정리"""
        now = datetime.now()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        if len(self._results) > self.max_results:
            # 오래된 결과 제거 (성공한 것부터)
            removal_count = len(self._results) - self.max_results
            candidates = []
            
            for task_id in self._task_ids_by_time:
                result = self._results.get(task_id)
                if result and result.status == ResultStatus.SUCCESS:
                    candidates.append(task_id)
                
                if len(candidates) >= removal_count:
                    break
            
            for task_id in candidates:
                await self._remove_result(task_id)
        
        self._last_cleanup = now
    
    async def _remove_result(self, task_id: str) -> None:
        """결과 제거"""
        result = self._results.get(task_id)
        if not result:
            return
        
        # 메모리에서 제거
        del self._results[task_id]
        
        # 인덱스에서 제거
        if result.task_name in self._results_by_name:
            self._results_by_name[result.task_name].remove(task_id)
            if not self._results_by_name[result.task_name]:
                del self._results_by_name[result.task_name]
        
        if task_id in self._results_by_status[result.status]:
            self._results_by_status[result.status].remove(task_id)
        
        if task_id in self._task_ids_by_time:
            self._task_ids_by_time.remove(task_id)
    
    async def _save_to_disk(self, result: TaskResult) -> None:
        """디스크에 저장"""
        if not self.storage_path:
            return
        
        try:
            # 날짜별 디렉토리 생성
            date_dir = self.storage_path / result.start_time.strftime("%Y-%m-%d")
            date_dir.mkdir(exist_ok=True)
            
            # 압축해서 저장
            file_path = date_dir / f"{result.task_id}.gz"
            data = result.to_dict()
            
            with gzip.open(file_path, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            # 로깅만 하고 에러는 무시
            print(f"Failed to save result to disk: {e}")
    
    async def _load_from_disk(self) -> None:
        """디스크에서 로드"""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        try:
            for date_dir in self.storage_path.iterdir():
                if not date_dir.is_dir():
                    continue
                
                for result_file in date_dir.glob("*.gz"):
                    try:
                        with gzip.open(result_file, 'rb') as f:
                            data = pickle.load(f)
                            result = TaskResult.from_dict(data)
                            
                            # 메모리에 로드 (통계는 업데이트하지 않음)
                            self._results[result.task_id] = result
                            
                            if result.task_name not in self._results_by_name:
                                self._results_by_name[result.task_name] = []
                            self._results_by_name[result.task_name].append(result.task_id)
                            
                            self._results_by_status[result.status].append(result.task_id)
                            self._insert_by_time(result.task_id, result.start_time)
                            
                    except Exception as e:
                        print(f"Failed to load result file {result_file}: {e}")
                        
        except Exception as e:
            print(f"Failed to load results from disk: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            **self._stats,
            "active_results": len(self._results),
            "unique_tasks": len(self._results_by_name),
            "success_rate": (
                self._stats["success_count"] / max(1, self._stats["total_results"])
            ) * 100
        }


class ResultAnalyzer:
    """결과 분석기"""
    
    def __init__(self, result_store: TaskResultStore):
        self.result_store = result_store
    
    def analyze_task_performance(
        self,
        task_name: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """작업 성능 분석"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        results = [
            r for r in self.result_store.get_results_by_name(task_name)
            if start_time <= r.start_time <= end_time
        ]
        
        if not results:
            return {"error": "No results found"}
        
        # 기본 통계
        total = len(results)
        successful = len([r for r in results if r.is_success()])
        failed = len([r for r in results if r.is_failure()])
        
        # 실행 시간 통계
        execution_times = [
            r.execution_time_ms for r in results
            if r.execution_time_ms is not None
        ]
        
        avg_exec_time = sum(execution_times) / len(execution_times) if execution_times else 0
        min_exec_time = min(execution_times) if execution_times else 0
        max_exec_time = max(execution_times) if execution_times else 0
        
        return {
            "task_name": task_name,
            "analysis_period_days": days,
            "total_executions": total,
            "success_count": successful,
            "failure_count": failed,
            "success_rate": (successful / total) * 100 if total > 0 else 0,
            "average_execution_time_ms": avg_exec_time,
            "min_execution_time_ms": min_exec_time,
            "max_execution_time_ms": max_exec_time,
            "recent_results": [r.to_dict() for r in results[-10:]]
        }
    
    def analyze_failure_patterns(self, days: int = 7) -> Dict[str, Any]:
        """실패 패턴 분석"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        failed_results = [
            r for r in self.result_store.get_results_in_range(start_time, end_time)
            if r.is_failure()
        ]
        
        if not failed_results:
            return {"error": "No failures found"}
        
        # 실패 원인별 분류
        failure_by_type = {}
        failure_by_task = {}
        
        for result in failed_results:
            # 에러 타입별
            error_type = result.error_type or "Unknown"
            if error_type not in failure_by_type:
                failure_by_type[error_type] = []
            failure_by_type[error_type].append(result)
            
            # 작업별
            if result.task_name not in failure_by_task:
                failure_by_task[result.task_name] = []
            failure_by_task[result.task_name].append(result)
        
        return {
            "analysis_period_days": days,
            "total_failures": len(failed_results),
            "failure_by_type": {
                error_type: len(results)
                for error_type, results in failure_by_type.items()
            },
            "failure_by_task": {
                task_name: len(results)
                for task_name, results in failure_by_task.items()
            },
            "most_common_errors": [
                {
                    "error_type": error_type,
                    "count": len(results),
                    "example_message": results[0].error_message
                }
                for error_type, results in 
                sorted(failure_by_type.items(), key=lambda x: len(x[1]), reverse=True)[:5]
            ]
        }


# 전역 결과 저장소
_default_result_store: Optional[TaskResultStore] = None


def get_default_result_store() -> TaskResultStore:
    """기본 결과 저장소 조회"""
    global _default_result_store
    if _default_result_store is None:
        config = get_config()
        storage_path = getattr(config, 'task_result_storage_path', None)
        max_results = getattr(config, 'max_task_results', 10000)
        _default_result_store = TaskResultStore(storage_path, max_results)
    return _default_result_store


def create_result_analyzer(result_store: Optional[TaskResultStore] = None) -> ResultAnalyzer:
    """결과 분석기 생성"""
    store = result_store or get_default_result_store()
    return ResultAnalyzer(store)