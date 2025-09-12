#!/bin/bash

# RFS Framework Cloud Run Deployment Script
# Version: 4.6.3
# 
# 사용법:
#   ./scripts/deploy-cloud-run.sh [environment] [service-name] [project-id]
#
# 예시:
#   ./scripts/deploy-cloud-run.sh production rfs-service my-gcp-project
#   ./scripts/deploy-cloud-run.sh staging rfs-service-staging my-gcp-project

set -e  # 에러 발생 시 즉시 종료

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 기본값 설정
ENVIRONMENT=${1:-production}
SERVICE_NAME=${2:-rfs-service}
PROJECT_ID=${3:-$(gcloud config get-value project)}
REGION=${REGION:-us-central1}
IMAGE_TAG=${IMAGE_TAG:-latest}

# 환경별 설정
case "$ENVIRONMENT" in
    production|prod)
        RFS_ENVIRONMENT="production"
        MAX_INSTANCES=100
        MIN_INSTANCES=1
        MEMORY=1Gi
        CPU=2
        CONCURRENCY=80
        LOG_LEVEL=INFO
        ;;
    staging|stage)
        RFS_ENVIRONMENT="test"
        MAX_INSTANCES=10
        MIN_INSTANCES=0
        MEMORY=512Mi
        CPU=1
        CONCURRENCY=40
        LOG_LEVEL=INFO
        ;;
    development|dev)
        RFS_ENVIRONMENT="development"
        MAX_INSTANCES=3
        MIN_INSTANCES=0
        MEMORY=256Mi
        CPU=1
        CONCURRENCY=20
        LOG_LEVEL=DEBUG
        ;;
    *)
        echo -e "${RED}Error: Unknown environment '$ENVIRONMENT'${NC}"
        echo "Usage: $0 [production|staging|development] [service-name] [project-id]"
        exit 1
        ;;
esac

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RFS Framework Cloud Run Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "Service: ${GREEN}$SERVICE_NAME${NC}"
echo -e "Project: ${GREEN}$PROJECT_ID${NC}"
echo -e "Region: ${GREEN}$REGION${NC}"
echo ""

# 1. 프로젝트 확인
echo -e "${YELLOW}1. Checking GCP project...${NC}"
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: Project ID not specified${NC}"
    echo "Please specify project ID as third argument or set it with: gcloud config set project PROJECT_ID"
    exit 1
fi
gcloud config set project $PROJECT_ID
echo -e "${GREEN}✓ Using project: $PROJECT_ID${NC}"

# 2. 필요한 API 활성화
echo -e "${YELLOW}2. Enabling required APIs...${NC}"
gcloud services enable run.googleapis.com \
    containerregistry.googleapis.com \
    cloudbuild.googleapis.com \
    cloudtasks.googleapis.com \
    redis.googleapis.com \
    monitoring.googleapis.com \
    --quiet
echo -e "${GREEN}✓ APIs enabled${NC}"

# 3. Docker 이미지 빌드 및 푸시
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME:$IMAGE_TAG"
echo -e "${YELLOW}3. Building Docker image...${NC}"
echo -e "Image: ${GREEN}$IMAGE_NAME${NC}"

# Dockerfile 존재 여부 확인
if [ ! -f "Dockerfile" ] && [ ! -f "Dockerfile.prod" ]; then
    echo -e "${RED}Error: Dockerfile not found${NC}"
    echo "Please create a Dockerfile or Dockerfile.prod in the project root"
    exit 1
fi

# 적절한 Dockerfile 선택
DOCKERFILE="Dockerfile"
if [ -f "Dockerfile.prod" ]; then
    DOCKERFILE="Dockerfile.prod"
fi

# Cloud Build 사용하여 빌드 및 푸시
gcloud builds submit --tag $IMAGE_NAME --file $DOCKERFILE .
echo -e "${GREEN}✓ Docker image built and pushed${NC}"

# 4. Cloud Run 서비스 배포
echo -e "${YELLOW}4. Deploying to Cloud Run...${NC}"

# 환경변수 설정
ENV_VARS="ENVIRONMENT=$ENVIRONMENT"
ENV_VARS="$ENV_VARS,RFS_ENVIRONMENT=$RFS_ENVIRONMENT"
ENV_VARS="$ENV_VARS,LOG_LEVEL=$LOG_LEVEL"
ENV_VARS="$ENV_VARS,RFS_LOG_LEVEL=$LOG_LEVEL"
ENV_VARS="$ENV_VARS,SERVICE_NAME=$SERVICE_NAME"
ENV_VARS="$ENV_VARS,GCP_PROJECT_ID=$PROJECT_ID"
ENV_VARS="$ENV_VARS,RFS_ENABLE_COLD_START_OPTIMIZATION=true"
ENV_VARS="$ENV_VARS,RFS_CLOUD_RUN_MAX_INSTANCES=$MAX_INSTANCES"

# 추가 환경변수 (있는 경우)
if [ -n "$REDIS_URL" ]; then
    ENV_VARS="$ENV_VARS,RFS_REDIS_URL=$REDIS_URL"
fi
if [ -n "$API_KEY" ]; then
    ENV_VARS="$ENV_VARS,API_KEY=$API_KEY"
fi

# Cloud Run 배포
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory $MEMORY \
    --cpu $CPU \
    --timeout 60 \
    --concurrency $CONCURRENCY \
    --min-instances $MIN_INSTANCES \
    --max-instances $MAX_INSTANCES \
    --set-env-vars="$ENV_VARS" \
    --service-account="${SERVICE_ACCOUNT:-$PROJECT_ID@appspot.gserviceaccount.com}" \
    --quiet

echo -e "${GREEN}✓ Service deployed successfully${NC}"

# 5. 서비스 URL 가져오기
echo -e "${YELLOW}5. Getting service URL...${NC}"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region $REGION \
    --format 'value(status.url)')

if [ -z "$SERVICE_URL" ]; then
    echo -e "${RED}Warning: Could not retrieve service URL${NC}"
else
    echo -e "${GREEN}✓ Service URL: $SERVICE_URL${NC}"
    
    # 6. 헬스체크
    echo -e "${YELLOW}6. Running health check...${NC}"
    HEALTH_ENDPOINT="$SERVICE_URL/health"
    
    # 서비스가 시작될 때까지 대기 (최대 30초)
    MAX_ATTEMPTS=6
    ATTEMPT=1
    
    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
        echo -e "Attempt $ATTEMPT/$MAX_ATTEMPTS..."
        
        if curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT | grep -q "200"; then
            echo -e "${GREEN}✓ Health check passed!${NC}"
            break
        else
            if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
                echo -e "${YELLOW}⚠ Health check failed after $MAX_ATTEMPTS attempts${NC}"
                echo "The service may still be starting up. Please check manually."
            else
                echo "Waiting 5 seconds before retry..."
                sleep 5
            fi
        fi
        
        ATTEMPT=$((ATTEMPT + 1))
    done
fi

# 7. 배포 정보 출력
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Service: ${GREEN}$SERVICE_NAME${NC}"
echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "Region: ${GREEN}$REGION${NC}"
echo -e "Image: ${GREEN}$IMAGE_NAME${NC}"
echo -e "URL: ${GREEN}$SERVICE_URL${NC}"
echo -e "Max Instances: ${GREEN}$MAX_INSTANCES${NC}"
echo -e "Min Instances: ${GREEN}$MIN_INSTANCES${NC}"
echo -e "Memory: ${GREEN}$MEMORY${NC}"
echo -e "CPU: ${GREEN}$CPU${NC}"
echo ""

# 8. 로그 확인 명령어 제공
echo -e "${BLUE}Useful commands:${NC}"
echo -e "View logs: ${YELLOW}gcloud run services logs read $SERVICE_NAME --region $REGION${NC}"
echo -e "Stream logs: ${YELLOW}gcloud run services logs tail $SERVICE_NAME --region $REGION${NC}"
echo -e "Service details: ${YELLOW}gcloud run services describe $SERVICE_NAME --region $REGION${NC}"
echo -e "Update traffic: ${YELLOW}gcloud run services update-traffic $SERVICE_NAME --region $REGION${NC}"
echo ""

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"