"""
마지막 커버리지 100% 달성을 위한 테스트

누락된 라인 378을 테스트
"""

import asyncio

import pytest

from rfs.async_tasks.base import CallableTask, TaskGroup


class TestTaskGroupFailFast:
    """TaskGroup fail_fast 모드 성공 경로 테스트"""

    @pytest.mark.asyncio
    async def test_fail_fast_success_path(self):
        """fail_fast 모드에서 모든 작업이 성공하는 경우"""

        async def task1(**kwargs):
            await asyncio.sleep(0.01)
            return "result1"

        async def task2(**kwargs):
            await asyncio.sleep(0.01)
            return "result2"

        async def task3(**kwargs):
            await asyncio.sleep(0.01)
            return "result3"

        # fail_fast=True로 설정
        group = TaskGroup(
            tasks=[CallableTask(task1), CallableTask(task2), CallableTask(task3)],
            fail_fast=True,
        )

        # 모든 작업이 성공해야 함
        results = await group.execute({})

        # 결과 확인 - fail_fast 모드에서도 모든 작업이 완료됨
        assert len(results) == 3
        assert set(results) == {"result1", "result2", "result3"}
