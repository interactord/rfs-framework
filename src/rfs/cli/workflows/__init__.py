"""
Workflow Automation Module (RFS v4)

개발자 워크플로우 자동화 시스템
- CI/CD 파이프라인 자동화
- Git 워크플로우 관리
- 테스트 자동화
- 코드 품질 관리
- 배포 자동화
"""

from .ci_cd import CICDManager, PipelineConfig, DeploymentStrategy
from .git_workflow import GitWorkflowManager, BranchStrategy, MergeStrategy
from .code_quality import CodeQualityManager, QualityConfig, QualityGate
from .automation import AutomationEngine, WorkflowTrigger, ActionRunner

__all__ = [
    # CI/CD 자동화
    "CICDManager", "PipelineConfig", "DeploymentStrategy",
    
    # Git 워크플로우
    "GitWorkflowManager", "BranchStrategy", "MergeStrategy",
    
    # 코드 품질
    "CodeQualityManager", "QualityConfig", "QualityGate",
    
    # 자동화 엔진
    "AutomationEngine", "WorkflowTrigger", "ActionRunner"
]