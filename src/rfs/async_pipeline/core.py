"""
AsyncPipeline - 통합 비동기 파이프라인 시스템

동기/비동기 함수를 혼재하여 사용할 수 있는 우아한 파이프라인 구현.
함수형 프로그래밍의 pipe 패턴을 비동기 환경에서 확장한 것입니다.
"""

import asyncio
import inspect
from typing import Any, Awaitable, Callable, List, TypeVar, Union

from .async_result import AsyncResult
from ..core.result import Result, Success, Failure

T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E')

# 파이프라인에서 사용 가능한 함수 타입들
SyncOperation = Callable[[T], U]
AsyncOperation = Callable[[T], Awaitable[U]]
SyncResultOperation = Callable[[T], Result[U, E]]
AsyncResultOperation = Callable[[T], AsyncResult[U, E]]
AsyncResultAwaitableOperation = Callable[[T], Awaitable[Result[U, E]]]

PipelineOperation = Union[
    SyncOperation,
    AsyncOperation, 
    SyncResultOperation,
    AsyncResultOperation,
    AsyncResultAwaitableOperation
]


class AsyncPipeline:
    """
    비동기/동기 함수 혼재 파이프라인 
    
    특징:
    - 동기와 비동기 함수를 자동으로 감지하여 처리
    - Result 패턴과 일반 값 모두 지원
    - 에러 발생 시 즉시 중단 (fail-fast)
    - 타입 안전성 보장
    - 함수형 프로그래밍의 pipe 패턴 확장
    
    Example:
        >>> def validate_input(data: str) -> Result[str, str]:
        ...     return Success(data) if data else Failure("Empty input")
        ...
        >>> async def fetch_data(query: str) -> dict:
        ...     # 비동기 데이터 조회
        ...     return {"result": query.upper()}
        ...
        >>> def format_output(data: dict) -> str:
        ...     return f"Result: {data['result']}"
        ...
        >>> pipeline = AsyncPipeline([validate_input, fetch_data, format_output])
        >>> result = await pipeline.execute("hello")
        >>> await result.unwrap_async()  # "Result: HELLO"
    """
    
    def __init__(self, operations: List[PipelineOperation]):
        """
        AsyncPipeline 생성자
        
        Args:
            operations: 파이프라인을 구성하는 연산들의 리스트
        """
        self.operations = operations
        self._operation_metadata = [
            self._analyze_operation(op) for op in operations
        ]
    
    def _analyze_operation(self, operation: PipelineOperation) -> dict[str, Any]:
        """
        연산의 메타데이터 분석
        
        Args:
            operation: 분석할 연산
            
        Returns:
            dict: 연산 메타데이터 (타입, 시그니처 등)
        """
        metadata = {
            'function': operation,
            'name': getattr(operation, '__name__', str(operation)),
            'is_async': asyncio.iscoroutinefunction(operation),
            'signature': inspect.signature(operation) if callable(operation) else None
        }
        
        # 반환 타입 힌트 분석
        if metadata['signature']:
            return_annotation = metadata['signature'].return_annotation
            if return_annotation != inspect.Signature.empty:
                metadata['return_annotation'] = return_annotation
                metadata['returns_result'] = self._is_result_type(return_annotation)
                metadata['returns_async_result'] = self._is_async_result_type(return_annotation)
            else:
                metadata['returns_result'] = False
                metadata['returns_async_result'] = False
        else:
            metadata['returns_result'] = False
            metadata['returns_async_result'] = False
            
        return metadata
    
    def _is_result_type(self, type_hint: Any) -> bool:
        """
        타입 힌트가 Result 타입인지 확인
        
        Args:
            type_hint: 검사할 타입 힌트
            
        Returns:
            bool: Result 타입 여부
        """
        # Result 타입 검사 (타입 힌트 문자열 포함)
        type_str = str(type_hint)
        return 'Result[' in type_str or type_hint.__class__.__name__ == 'Result'
    
    def _is_async_result_type(self, type_hint: Any) -> bool:
        """
        타입 힌트가 AsyncResult 타입인지 확인
        
        Args:
            type_hint: 검사할 타입 힌트
            
        Returns:
            bool: AsyncResult 타입 여부
        """
        type_str = str(type_hint)
        return 'AsyncResult[' in type_str or type_hint.__class__.__name__ == 'AsyncResult'
    
    async def execute(self, initial_value: Any) -> AsyncResult[Any, Any]:
        """
        파이프라인 실행
        
        Args:
            initial_value: 초기 입력 값
            
        Returns:
            AsyncResult[Any, Any]: 최종 실행 결과
        """
        current_result = AsyncResult.from_value(initial_value)
        
        for i, (operation, metadata) in enumerate(zip(self.operations, self._operation_metadata)):
            try:
                current_result = await self._execute_operation(
                    current_result, 
                    operation, 
                    metadata,
                    step_index=i
                )
                
                # 에러 발생 시 즉시 중단
                if await current_result.is_failure():
                    break
                    
            except Exception as e:
                # 예외 발생 시 컨텍스트 정보와 함께 실패 처리
                error_message = f"파이프라인 {i}단계 ({metadata['name']})에서 실패: {str(e)}"
                return AsyncResult.from_error(error_message)
        
        return current_result
    
    async def _execute_operation(
        self, 
        current_result: AsyncResult[Any, Any],
        operation: PipelineOperation,
        metadata: dict[str, Any],
        step_index: int
    ) -> AsyncResult[Any, Any]:
        """
        단일 연산 실행
        
        Args:
            current_result: 현재 결과
            operation: 실행할 연산
            metadata: 연산 메타데이터
            step_index: 단계 인덱스
            
        Returns:
            AsyncResult[Any, Any]: 연산 실행 결과
        """
        # 현재 결과가 실패인 경우 그대로 반환
        if await current_result.is_failure():
            return current_result
        
        # 현재 값 추출
        current_value = await current_result.unwrap_async()
        
        # 연산 타입에 따라 실행 방식 결정
        if metadata['is_async']:
            return await self._execute_async_operation(
                current_value, operation, metadata, step_index
            )
        else:
            return await self._execute_sync_operation(
                current_value, operation, metadata, step_index
            )
    
    async def _execute_async_operation(
        self,
        value: Any,
        operation: PipelineOperation,
        metadata: dict[str, Any],
        step_index: int
    ) -> AsyncResult[Any, Any]:
        """
        비동기 연산 실행
        
        Args:
            value: 입력 값
            operation: 비동기 연산
            metadata: 연산 메타데이터  
            step_index: 단계 인덱스
            
        Returns:
            AsyncResult[Any, Any]: 실행 결과
        """
        try:
            result = await operation(value)
            
            # 결과 타입에 따라 처리
            if isinstance(result, AsyncResult):
                return result
            elif hasattr(result, 'is_success'):  # Result 타입
                return AsyncResult.from_result(result)
            else:
                # 일반 값
                return AsyncResult.from_value(result)
                
        except Exception as e:
            error_context = {
                'step': step_index,
                'operation': metadata['name'],
                'input_value': str(value)[:100],  # 긴 값은 잘라서 표시
                'error': str(e),
                'error_type': type(e).__name__
            }
            return AsyncResult.from_error(error_context)
    
    async def _execute_sync_operation(
        self,
        value: Any,
        operation: PipelineOperation,
        metadata: dict[str, Any],
        step_index: int
    ) -> AsyncResult[Any, Any]:
        """
        동기 연산 실행
        
        Args:
            value: 입력 값
            operation: 동기 연산
            metadata: 연산 메타데이터
            step_index: 단계 인덱스
            
        Returns:
            AsyncResult[Any, Any]: 실행 결과
        """
        try:
            result = operation(value)
            
            # 결과 타입에 따라 처리
            if isinstance(result, AsyncResult):
                return result
            elif hasattr(result, 'is_success'):  # Result 타입
                return AsyncResult.from_result(result)
            else:
                # 일반 값
                return AsyncResult.from_value(result)
                
        except Exception as e:
            error_context = {
                'step': step_index,
                'operation': metadata['name'],
                'input_value': str(value)[:100],
                'error': str(e),
                'error_type': type(e).__name__
            }
            return AsyncResult.from_error(error_context)
    
    def add_operation(self, operation: PipelineOperation) -> 'AsyncPipeline':
        """
        새로운 연산을 파이프라인에 추가
        
        Args:
            operation: 추가할 연산
            
        Returns:
            AsyncPipeline: 새로운 파이프라인 인스턴스
        """
        new_operations = self.operations + [operation]
        return AsyncPipeline(new_operations)
    
    def prepend_operation(self, operation: PipelineOperation) -> 'AsyncPipeline':
        """
        파이프라인 앞에 연산 추가
        
        Args:
            operation: 추가할 연산
            
        Returns:
            AsyncPipeline: 새로운 파이프라인 인스턴스
        """
        new_operations = [operation] + self.operations
        return AsyncPipeline(new_operations)
    
    def compose(self, other_pipeline: 'AsyncPipeline') -> 'AsyncPipeline':
        """
        다른 파이프라인과 결합
        
        Args:
            other_pipeline: 결합할 파이프라인
            
        Returns:
            AsyncPipeline: 결합된 파이프라인
        """
        combined_operations = self.operations + other_pipeline.operations
        return AsyncPipeline(combined_operations)
    
    async def execute_with_context(
        self, 
        initial_value: Any,
        context: dict[str, Any] | None = None
    ) -> tuple[AsyncResult[Any, Any], dict[str, Any]]:
        """
        컨텍스트 정보와 함께 파이프라인 실행
        
        Args:
            initial_value: 초기 입력 값
            context: 실행 컨텍스트
            
        Returns:
            tuple: (실행 결과, 실행 정보)
        """
        import time
        
        execution_context = context or {}
        start_time = time.time()
        
        # 실행 정보 추적
        execution_info = {
            'start_time': start_time,
            'operations_count': len(self.operations),
            'steps_completed': 0,
            'steps_details': []
        }
        
        current_result = AsyncResult.from_value(initial_value)
        
        for i, (operation, metadata) in enumerate(zip(self.operations, self._operation_metadata)):
            step_start = time.time()
            
            try:
                current_result = await self._execute_operation(
                    current_result, 
                    operation, 
                    metadata,
                    step_index=i
                )
                
                step_info = {
                    'step': i,
                    'operation': metadata['name'],
                    'duration': time.time() - step_start,
                    'success': await current_result.is_success()
                }
                execution_info['steps_details'].append(step_info)
                execution_info['steps_completed'] = i + 1
                
                # 에러 발생 시 중단
                if await current_result.is_failure():
                    break
                    
            except Exception as e:
                step_info = {
                    'step': i,
                    'operation': metadata['name'],
                    'duration': time.time() - step_start,
                    'success': False,
                    'error': str(e)
                }
                execution_info['steps_details'].append(step_info)
                execution_info['steps_completed'] = i + 1
                
                error_message = f"파이프라인 {i}단계에서 예외: {str(e)}"
                current_result = AsyncResult.from_error(error_message)
                break
        
        execution_info['total_duration'] = time.time() - start_time
        execution_info['success'] = await current_result.is_success()
        
        return current_result, execution_info
    
    def __repr__(self) -> str:
        operation_names = [meta['name'] for meta in self._operation_metadata]
        return f"AsyncPipeline({' → '.join(operation_names)})"


# === 편의 함수들 ===

def async_pipe(*operations: PipelineOperation) -> AsyncPipeline:
    """
    비동기 파이프라인 생성 편의 함수
    
    Args:
        *operations: 파이프라인을 구성할 연산들
        
    Returns:
        AsyncPipeline: 생성된 파이프라인
        
    Example:
        >>> pipeline = async_pipe(
        ...     validate_input,
        ...     fetch_data,
        ...     transform_data,
        ...     save_result
        ... )
        >>> result = await pipeline.execute(initial_data)
    """
    return AsyncPipeline(list(operations))


async def execute_async_pipeline(
    operations: List[PipelineOperation],
    initial_value: Any
) -> AsyncResult[Any, Any]:
    """
    파이프라인 직접 실행 편의 함수
    
    Args:
        operations: 실행할 연산들
        initial_value: 초기 입력 값
        
    Returns:
        AsyncResult[Any, Any]: 실행 결과
        
    Example:
        >>> result = await execute_async_pipeline(
        ...     [validate, process, save],
        ...     input_data
        ... )
    """
    pipeline = AsyncPipeline(operations)
    return await pipeline.execute(initial_value)


class AsyncPipelineBuilder:
    """
    AsyncPipeline을 빌더 패턴으로 구축하기 위한 헬퍼 클래스
    
    Example:
        >>> pipeline = (AsyncPipelineBuilder()
        ...     .add_validation(validate_input)
        ...     .add_processing(process_data)
        ...     .add_transformation(transform_result)
        ...     .add_persistence(save_to_db)
        ...     .build())
        >>> result = await pipeline.execute(data)
    """
    
    def __init__(self):
        self._operations: List[PipelineOperation] = []
    
    def add_operation(self, operation: PipelineOperation, name: str | None = None) -> 'AsyncPipelineBuilder':
        """
        일반 연산 추가
        
        Args:
            operation: 추가할 연산
            name: 연산 이름 (선택적)
            
        Returns:
            AsyncPipelineBuilder: 체이닝을 위한 빌더 인스턴스
        """
        if name:
            operation.__name__ = name
        self._operations.append(operation)
        return self
    
    def add_validation(self, validator: PipelineOperation) -> 'AsyncPipelineBuilder':
        """검증 단계 추가"""
        return self.add_operation(validator, f"validation_{len(self._operations)}")
    
    def add_processing(self, processor: PipelineOperation) -> 'AsyncPipelineBuilder':
        """처리 단계 추가"""
        return self.add_operation(processor, f"processing_{len(self._operations)}")
    
    def add_transformation(self, transformer: PipelineOperation) -> 'AsyncPipelineBuilder':
        """변환 단계 추가"""
        return self.add_operation(transformer, f"transformation_{len(self._operations)}")
    
    def add_persistence(self, persister: PipelineOperation) -> 'AsyncPipelineBuilder':
        """저장 단계 추가"""
        return self.add_operation(persister, f"persistence_{len(self._operations)}")
    
    def add_conditional(
        self, 
        condition: Callable[[Any], bool], 
        true_operation: PipelineOperation,
        false_operation: PipelineOperation | None = None
    ) -> 'AsyncPipelineBuilder':
        """
        조건부 연산 추가
        
        Args:
            condition: 조건 함수
            true_operation: 조건이 참일 때 실행할 연산
            false_operation: 조건이 거짓일 때 실행할 연산 (선택적)
        """
        def conditional_operation(value):
            if condition(value):
                return true_operation(value)
            elif false_operation:
                return false_operation(value)
            else:
                return value
        
        return self.add_operation(conditional_operation, f"conditional_{len(self._operations)}")
    
    def build(self) -> AsyncPipeline:
        """
        빌더에서 AsyncPipeline 생성
        
        Returns:
            AsyncPipeline: 구축된 파이프라인
        """
        return AsyncPipeline(self._operations.copy())
    
    def __len__(self) -> int:
        return len(self._operations)
    
    def __repr__(self) -> str:
        return f"AsyncPipelineBuilder({len(self._operations)} operations)"


# === 고급 파이프라인 유틸리티 ===

async def parallel_pipeline_execution(
    pipelines: List[AsyncPipeline],
    initial_values: List[Any]
) -> List[AsyncResult[Any, Any]]:
    """
    여러 파이프라인을 병렬로 실행
    
    Args:
        pipelines: 실행할 파이프라인들
        initial_values: 각 파이프라인의 초기 값들
        
    Returns:
        List[AsyncResult]: 각 파이프라인의 실행 결과들
    """
    if len(pipelines) != len(initial_values):
        raise ValueError("파이프라인 수와 초기값 수가 일치하지 않습니다")
    
    tasks = [
        pipeline.execute(initial_value)
        for pipeline, initial_value in zip(pipelines, initial_values)
    ]
    
    return await asyncio.gather(*tasks)