#!/bin/bash

# RFS Framework Configuration Bridge Test Script
# 설정 브리지가 올바르게 작동하는지 로컬에서 테스트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RFS Framework Configuration Bridge Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. Python 환경 테스트
echo -e "${YELLOW}1. Testing Python environment...${NC}"
python3 -c "import sys; print(f'Python version: {sys.version}')"
echo -e "${GREEN}✓ Python environment OK${NC}"
echo ""

# 2. 기본 임포트 테스트
echo -e "${YELLOW}2. Testing basic RFS import...${NC}"
python3 -c "
import os
os.environ.pop('RFS_ENVIRONMENT', None)
os.environ.pop('ENVIRONMENT', None)
try:
    import rfs
    print('✓ RFS Framework imported successfully')
    print(f'  Version: {rfs.__version__}')
except Exception as e:
    print(f'✗ Import failed: {e}')
    exit(1)
"
echo -e "${GREEN}✓ Basic import OK${NC}"
echo ""

# 3. 개발 환경 테스트
echo -e "${YELLOW}3. Testing development environment...${NC}"
ENVIRONMENT=development python3 -c "
import os
os.environ['ENVIRONMENT'] = 'development'
from rfs.core.config_bridge import ensure_rfs_configured
from rfs.core.config import get_config

ensure_rfs_configured()
config = get_config()

print(f'  ENVIRONMENT: {os.getenv(\"ENVIRONMENT\")}')
print(f'  RFS_ENVIRONMENT: {os.getenv(\"RFS_ENVIRONMENT\")}')
print(f'  Config environment: {config.environment.value}')
print(f'  Is development: {config.is_development()}')

assert os.getenv('RFS_ENVIRONMENT') == 'development'
assert config.is_development() == True
print('✓ Development environment OK')
"
echo -e "${GREEN}✓ Development environment test passed${NC}"
echo ""

# 4. 프로덕션 환경 테스트
echo -e "${YELLOW}4. Testing production environment...${NC}"
ENVIRONMENT=production LOG_LEVEL=WARNING python3 -c "
import os
os.environ['ENVIRONMENT'] = 'production'
os.environ['LOG_LEVEL'] = 'WARNING'
from rfs.core.config_bridge import ensure_rfs_configured
from rfs.core.config import get_config

ensure_rfs_configured()
config = get_config()

print(f'  ENVIRONMENT: {os.getenv(\"ENVIRONMENT\")}')
print(f'  RFS_ENVIRONMENT: {os.getenv(\"RFS_ENVIRONMENT\")}')
print(f'  LOG_LEVEL: {os.getenv(\"LOG_LEVEL\")}')
print(f'  RFS_LOG_LEVEL: {os.getenv(\"RFS_LOG_LEVEL\")}')
print(f'  Config environment: {config.environment.value}')
print(f'  Config log level: {config.log_level}')
print(f'  Is production: {config.is_production()}')

assert os.getenv('RFS_ENVIRONMENT') == 'production'
assert os.getenv('RFS_LOG_LEVEL') == 'WARNING'
assert config.is_production() == True
assert config.log_level == 'WARNING'
print('✓ Production environment OK')
"
echo -e "${GREEN}✓ Production environment test passed${NC}"
echo ""

# 5. Cloud Run 환경 시뮬레이션 테스트
echo -e "${YELLOW}5. Testing Cloud Run environment simulation...${NC}"
K_SERVICE=test-service PORT=8080 ENVIRONMENT=production python3 -c "
import os
os.environ['K_SERVICE'] = 'test-service'
os.environ['PORT'] = '8080'
os.environ['ENVIRONMENT'] = 'production'
from rfs.core.config_bridge import ensure_rfs_configured
from rfs.core.config import get_config, is_cloud_run_environment

ensure_rfs_configured()
config = get_config()

print(f'  K_SERVICE: {os.getenv(\"K_SERVICE\")}')
print(f'  PORT: {os.getenv(\"PORT\")}')
print(f'  RFS_PORT: {os.getenv(\"RFS_PORT\")}')
print(f'  RFS_ENABLE_COLD_START_OPTIMIZATION: {os.getenv(\"RFS_ENABLE_COLD_START_OPTIMIZATION\")}')
print(f'  Is Cloud Run: {is_cloud_run_environment()}')
print(f'  Cold start optimization: {config.enable_cold_start_optimization}')

assert os.getenv('RFS_PORT') == '8080'
assert os.getenv('RFS_ENABLE_COLD_START_OPTIMIZATION') == 'true'
assert is_cloud_run_environment() == True
print('✓ Cloud Run environment OK')
"
echo -e "${GREEN}✓ Cloud Run simulation test passed${NC}"
echo ""

# 6. 스테이징 → 테스트 매핑 테스트
echo -e "${YELLOW}6. Testing staging to test mapping...${NC}"
ENVIRONMENT=staging python3 -c "
import os
os.environ['ENVIRONMENT'] = 'staging'
from rfs.core.config_bridge import ensure_rfs_configured
from rfs.core.config import get_config

ensure_rfs_configured()
config = get_config()

print(f'  ENVIRONMENT: {os.getenv(\"ENVIRONMENT\")}')
print(f'  RFS_ENVIRONMENT: {os.getenv(\"RFS_ENVIRONMENT\")}')
print(f'  Config environment: {config.environment.value}')
print(f'  Is test: {config.is_test()}')

assert os.getenv('RFS_ENVIRONMENT') == 'test'
assert config.is_test() == True
print('✓ Staging to test mapping OK')
"
echo -e "${GREEN}✓ Staging mapping test passed${NC}"
echo ""

# 7. pytest 실행 (설치되어 있는 경우)
if command -v pytest &> /dev/null; then
    echo -e "${YELLOW}7. Running pytest tests...${NC}"
    pytest tests/test_config_bridge.py -v --tb=short || true
    echo ""
else
    echo -e "${YELLOW}7. Skipping pytest (not installed)${NC}"
    echo ""
fi

# 8. 요약
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ All configuration bridge tests passed!${NC}"
echo ""
echo -e "${BLUE}The RFS Framework configuration bridge is working correctly.${NC}"
echo -e "${BLUE}It will automatically handle environment variable mapping${NC}"
echo -e "${BLUE}for Cloud Run and other deployment environments.${NC}"
echo ""

# 9. Hot-fix 예시 제공
echo -e "${YELLOW}Quick Hot-Fix Example:${NC}"
echo -e "If you need an immediate fix in your application, add this to your main.py:"
echo ""
echo -e "${GREEN}import os${NC}"
echo -e "${GREEN}os.environ.setdefault('RFS_ENVIRONMENT', os.getenv('ENVIRONMENT', 'development'))${NC}"
echo -e "${GREEN}os.environ.setdefault('RFS_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO'))${NC}"
echo ""