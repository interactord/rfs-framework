"""
Workflow Automation Module (RFS v4)

개발자 워크플로우 자동화 시스템
- CI/CD 파이프라인 자동화
- Git 워크플로우 관리
- 테스트 자동화
- 코드 품질 관리
- 배포 자동화
"""

from .automation import ActionRunner, AutomationEngine, WorkflowTrigger
from .ci_cd import CICDManager, DeploymentStrategy, PipelineConfig
from .code_quality import CodeQualityManager, QualityConfig, QualityGate
from .git_workflow import BranchStrategy, GitWorkflowManager, MergeStrategy

__all__ = [
    # CI/CD 자동화
    "CICDManager",
    "PipelineConfig",
    "DeploymentStrategy",
    # Git 워크플로우
    "GitWorkflowManager",
    "BranchStrategy",
    "MergeStrategy",
    # 코드 품질
    "CodeQualityManager",
    "QualityConfig",
    "QualityGate",
    # 자동화 엔진
    "AutomationEngine",
    "WorkflowTrigger",
    "ActionRunner",
]
