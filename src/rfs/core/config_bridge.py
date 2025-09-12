"""
RFS Framework 설정 브리지

Cloud Run 및 기타 환경에서 RFS Framework 설정을 자동으로 연결합니다.
환경변수를 RFS Framework가 기대하는 형식으로 변환하여 
배포 시 설정 문제를 방지합니다.

Version: 4.6.3
"""

import os
import logging
from typing import Literal, Optional, Dict, Any

# 로거 설정
logger = logging.getLogger(__name__)

# RFS Framework 환경 타입
RFSEnvironment = Literal["development", "test", "production"]


def get_rfs_environment() -> RFSEnvironment:
    """
    애플리케이션 ENVIRONMENT를 RFS 형식으로 변환합니다.
    
    환경 매핑 규칙:
    - production, prod → production
    - staging, stage, test, testing → test
    - development, dev, develop → development
    - 기타 → development (기본값)
    
    Returns:
        RFSEnvironment: RFS Framework 환경 설정값
    """
    # 먼저 RFS_ENVIRONMENT 확인
    rfs_env = os.getenv("RFS_ENVIRONMENT")
    if rfs_env:
        return rfs_env.lower()  # type: ignore
    
    # ENVIRONMENT 환경변수 확인
    app_env = os.getenv("ENVIRONMENT", "development").lower()
    
    # 매핑 규칙 적용
    if app_env in ("production", "prod"):
        return "production"
    elif app_env in ("staging", "stage", "test", "testing"):
        return "test"
    elif app_env in ("development", "dev", "develop"):
        return "development"
    else:
        logger.warning(f"알 수 없는 환경 '{app_env}', 기본값 'development' 사용")
        return "development"


def bridge_environment_variables() -> Dict[str, str]:
    """
    일반 환경변수를 RFS Framework 환경변수로 브리지합니다.
    
    매핑 규칙:
    - ENVIRONMENT → RFS_ENVIRONMENT
    - LOG_LEVEL → RFS_LOG_LEVEL
    - DEBUG → RFS_DEBUG
    - PORT → RFS_PORT (Cloud Run 지원)
    
    Returns:
        Dict[str, str]: 설정된 환경변수 맵
    """
    bridged = {}
    
    # RFS_ENVIRONMENT 설정 (항상 기본값 보장)
    if not os.getenv("RFS_ENVIRONMENT"):
        rfs_env = get_rfs_environment()
        os.environ["RFS_ENVIRONMENT"] = rfs_env
        bridged["RFS_ENVIRONMENT"] = rfs_env
        logger.info(f"RFS_ENVIRONMENT를 '{rfs_env}'로 설정")
    
    # RFS_LOG_LEVEL 설정
    if not os.getenv("RFS_LOG_LEVEL"):
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        os.environ["RFS_LOG_LEVEL"] = log_level
        bridged["RFS_LOG_LEVEL"] = log_level
    
    # RFS_DEBUG 설정 (development 환경에서만 true)
    if not os.getenv("RFS_DEBUG"):
        is_debug = str(os.getenv("DEBUG", "false")).lower()
        if is_debug == "false" and get_rfs_environment() == "development":
            is_debug = "true"
        os.environ["RFS_DEBUG"] = is_debug
        bridged["RFS_DEBUG"] = is_debug
    
    # Cloud Run 특수 환경변수 처리
    if os.getenv("K_SERVICE"):  # Cloud Run 환경 감지
        # PORT 환경변수 브리지
        if port := os.getenv("PORT"):
            os.environ.setdefault("RFS_PORT", port)
            bridged["RFS_PORT"] = port
        
        # Cloud Run 관련 설정
        os.environ.setdefault("RFS_ENABLE_COLD_START_OPTIMIZATION", "true")
        os.environ.setdefault("RFS_CLOUD_RUN_MAX_INSTANCES", "100")
        
    return bridged


def ensure_rfs_configured() -> bool:
    """
    RFS Framework 설정이 올바르게 구성되었는지 보장합니다.
    멱등성을 제공하여 여러 번 호출해도 안전합니다.
    
    Returns:
        bool: 설정 성공 여부
    """
    try:
        # 환경변수 브리지
        bridged = bridge_environment_variables()
        
        # 설정 검증
        rfs_env = os.getenv("RFS_ENVIRONMENT")
        if not rfs_env:
            raise ValueError("RFS_ENVIRONMENT가 설정되지 않았습니다")
        
        if rfs_env not in ("development", "test", "production"):
            raise ValueError(f"유효하지 않은 RFS_ENVIRONMENT: {rfs_env}")
        
        # 프로덕션 환경 추가 검증
        if rfs_env == "production":
            # 프로덕션에서는 DEBUG가 false여야 함
            if os.getenv("RFS_DEBUG", "false").lower() == "true":
                logger.warning("프로덕션 환경에서 DEBUG가 활성화되어 있습니다")
        
        if bridged:
            logger.info(f"RFS Framework 환경변수 브리지 완료: {list(bridged.keys())}")
        
        return True
        
    except Exception as e:
        # 개발 환경에서는 경고만, 프로덕션에서는 실패
        env = os.getenv("ENVIRONMENT", "development")
        if env in ("production", "prod"):
            logger.error(f"RFS Framework 설정 실패: {str(e)}")
            raise RuntimeError(f"RFS Framework 설정 실패: {str(e)}")
        else:
            logger.warning(f"RFS Framework 설정 경고: {str(e)}")
            return False


def get_config_for_cloud_run() -> Dict[str, Any]:
    """
    Cloud Run 배포를 위한 추천 설정을 반환합니다.
    
    Returns:
        Dict[str, Any]: Cloud Run 최적화 설정
    """
    return {
        "environment": "production",
        "enable_cold_start_optimization": True,
        "cloud_run_max_instances": int(os.getenv("MAX_INSTANCES", "100")),
        "cloud_run_cpu_limit": os.getenv("CPU_LIMIT", "1000m"),
        "cloud_run_memory_limit": os.getenv("MEMORY_LIMIT", "512Mi"),
        "log_level": "INFO",
        "log_format": "json",
        "enable_tracing": True,
        "enable_performance_monitoring": True,
        "metrics_export_interval": 60,
    }


# 모듈 임포트 시 자동 실행 (선택적)
# 주의: 이 코드는 필요한 경우에만 활성화하세요
# ensure_rfs_configured()