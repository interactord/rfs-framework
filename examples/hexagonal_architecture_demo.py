"""
RFS v4.1 Hexagonal Architecture Demo
헥사고날 아키텍처 패턴을 사용한 User Management 시스템 예제

이 예제는 다음을 시연합니다:
1. @Port, @Adapter, @UseCase, @Controller 어노테이션 사용법
2. 레이어 간의 의존성 주입
3. 깔끔한 아키텍처와 관심사의 분리
4. 테스트 가능한 설계

아키텍처 레이어:
- Domain Layer: 비즈니스 로직 및 Port 인터페이스
- Application Layer: UseCase (비즈니스 시나리오)
- Infrastructure Layer: Adapter (외부 시스템 연동)
- Presentation Layer: Controller (사용자 인터페이스)
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

# RFS 코어 imports
from rfs.core import (
    Port, Adapter, Component, UseCase, Controller,
    AnnotationRegistry, AnnotationProcessor, ProcessingContext,
    Result, Success, Failure
)


# ==========================================
# Domain Layer (비즈니스 로직 & 도메인 모델)
# ==========================================

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass
class User:
    """User 도메인 모델"""
    id: str
    email: str
    name: str
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def activate(self) -> None:
        """사용자 활성화"""
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.now()
    
    def deactivate(self) -> None:
        """사용자 비활성화"""
        self.status = UserStatus.INACTIVE
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (직렬화용)"""
        result = asdict(self)
        result['status'] = self.status.value
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result


@dataclass
class CreateUserRequest:
    """사용자 생성 요청"""
    email: str
    name: str


@dataclass
class UpdateUserRequest:
    """사용자 업데이트 요청"""
    name=None
    status=None


# Domain Layer - Ports (인터페이스)
@Port(name="user_repository", description="사용자 데이터 저장소 인터페이스")
class UserRepository(ABC):
    """사용자 저장소 Port"""
    
    @abstractmethod
    async def save(self, user: User) -> Result[User, str]:
        """사용자 저장"""
        pass
    
    @abstractmethod
    async def find_by_id(self, user_id: str) -> Result[Optional[User], str]:
        """ID로 사용자 조회"""
        pass
    
    @abstractmethod
    async def find_by_email(self, email: str) -> Result[Optional[User], str]:
        """이메일로 사용자 조회"""
        pass
    
    @abstractmethod
    async def find_all(self) -> Result[List[User], str]:
        """모든 사용자 조회"""
        pass
    
    @abstractmethod
    async def delete(self, user_id: str) -> Result[bool, str]:
        """사용자 삭제"""
        pass


@Port(name="email_service", description="이메일 발송 서비스 인터페이스")
class EmailService(ABC):
    """이메일 서비스 Port"""
    
    @abstractmethod
    async def send_welcome_email(self, user: User) -> Result[bool, str]:
        """환영 이메일 발송"""
        pass
    
    @abstractmethod
    async def send_notification(self, user: User, message: str) -> Result[bool, str]:
        """알림 이메일 발송"""
        pass


@Port(name="audit_logger", description="감사 로그 인터페이스")
class AuditLogger(ABC):
    """감사 로깅 Port"""
    
    @abstractmethod
    async def log_user_action(self, user_id: str, action: str, details: Dict[str, Any]) -> None:
        """사용자 액션 로깅"""
        pass


# ==========================================
# Infrastructure Layer (외부 시스템 어댑터)
# ==========================================

@Adapter(port="user_repository", name="memory_user_repository", profile="development")
class MemoryUserRepository(UserRepository):
    """메모리 기반 사용자 저장소 (개발용)"""
    
    def __init__(self):
        self._users={}
    
    async def save(self, user: User) -> Result[User, str]:
        """사용자 저장"""
        try:
            self._users[user.id] = user
            return Success(user)
        except Exception as e:
            return Failure(f"Failed to save user: {str(e)}")
    
    async def find_by_id(self, user_id: str) -> Result[Optional[User], str]:
        """ID로 사용자 조회"""
        try:
            user = self._users.get(user_id)
            return Success(user)
        except Exception as e:
            return Failure(f"Failed to find user: {str(e)}")
    
    async def find_by_email(self, email: str) -> Result[Optional[User], str]:
        """이메일로 사용자 조회"""
        try:
            for user in self._users.values():
                if user.email == email:
                    return Success(user)
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to find user by email: {str(e)}")
    
    async def find_all(self) -> Result[List[User], str]:
        """모든 사용자 조회"""
        try:
            return Success(list(self._users.values()))
        except Exception as e:
            return Failure(f"Failed to find all users: {str(e)}")
    
    async def delete(self, user_id: str) -> Result[bool, str]:
        """사용자 삭제"""
        try:
            if user_id in self._users:
                del self._users[user_id]
                return Success(True)
            return Success(False)
        except Exception as e:
            return Failure(f"Failed to delete user: {str(e)}")


@Adapter(port="email_service", name="mock_email_service", profile="development")
class MockEmailService(EmailService):
    """모의 이메일 서비스 (개발/테스트용)"""
    
    def __init__(self):
        self.sent_emails: List[Dict[str, Any]] = []
    
    async def send_welcome_email(self, user: User) -> Result[bool, str]:
        """환영 이메일 발송 (모의)"""
        try:
            email_data = {
                "type": "welcome",
                "to": user.email,
                "subject": f"환영합니다, {user.name}님!",
                "sent_at": datetime.now().isoformat()
            }
            self.sent_emails.append(email_data)
            print(f"📧 Welcome email sent to {user.email}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to send welcome email: {str(e)}")
    
    async def send_notification(self, user: User, message: str) -> Result[bool, str]:
        """알림 이메일 발송 (모의)"""
        try:
            email_data = {
                "type": "notification",
                "to": user.email,
                "message": message,
                "sent_at": datetime.now().isoformat()
            }
            self.sent_emails.append(email_data)
            print(f"📧 Notification sent to {user.email}: {message}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to send notification: {str(e)}")


@Adapter(port="audit_logger", name="console_audit_logger", profile="development")
class ConsoleAuditLogger(AuditLogger):
    """콘솔 감사 로거 (개발용)"""
    
    async def log_user_action(self, user_id: str, action: str, details: Dict[str, Any]) -> None:
        """사용자 액션 로깅"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "action": action,
            "details": details
        }
        print(f"📝 AUDIT LOG: {log_entry}")


# ==========================================
# Application Layer (비즈니스 시나리오)
# ==========================================

@UseCase(name="create_user_use_case", 
         dependencies=["user_repository", "email_service", "audit_logger"])
class CreateUserUseCase:
    """사용자 생성 유스케이스"""
    
    def __init__(self, user_repository: UserRepository, 
                 email_service: EmailService, audit_logger: AuditLogger):
        self.user_repository = user_repository
        self.email_service = email_service
        self.audit_logger = audit_logger
    
    async def execute(self, request: CreateUserRequest) -> Result[User, str]:
        """사용자 생성 실행"""
        try:
            # 1. 이메일 중복 체크
            existing_result = await self.user_repository.find_by_email(request.email)
            if existing_result.is_failure():
                return existing_result
            
            if existing_result.value is not None:
                return Failure(f"User with email {request.email} already exists")
            
            # 2. 새 사용자 생성
            user = User(
                id=str(uuid.uuid4()),
                email=request.email,
                name=request.name
            )
            
            # 3. 사용자 저장
            save_result = await self.user_repository.save(user)
            if save_result.is_failure():
                return save_result
            
            # 4. 환영 이메일 발송 (실패해도 사용자 생성은 성공으로 처리)
            email_result = await self.email_service.send_welcome_email(user)
            if email_result.is_failure():
                print(f"⚠️ Failed to send welcome email: {email_result.error}")
            
            # 5. 감사 로그
            await self.audit_logger.log_user_action(
                user.id, "CREATE_USER", 
                {"email": user.email, "name": user.name}
            )
            
            return Success(user)
            
        except Exception as e:
            return Failure(f"Failed to create user: {str(e)}")


@UseCase(name="get_user_use_case", dependencies=["user_repository"])
class GetUserUseCase:
    """사용자 조회 유스케이스"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def execute(self, user_id: str) -> Result[Optional[User], str]:
        """사용자 조회 실행"""
        return await self.user_repository.find_by_id(user_id)


@UseCase(name="update_user_use_case", 
         dependencies=["user_repository", "email_service", "audit_logger"])
class UpdateUserUseCase:
    """사용자 업데이트 유스케이스"""
    
    def __init__(self, user_repository: UserRepository,
                 email_service: EmailService, audit_logger: AuditLogger):
        self.user_repository = user_repository
        self.email_service = email_service
        self.audit_logger = audit_logger
    
    async def execute(self, user_id: str, request: UpdateUserRequest) -> Result[User, str]:
        """사용자 업데이트 실행"""
        try:
            # 1. 기존 사용자 조회
            user_result = await self.user_repository.find_by_id(user_id)
            if user_result.is_failure():
                return user_result
            
            if user_result.value is None:
                return Failure(f"User {user_id} not found")
            
            user = user_result.value
            changes = {}
            
            # 2. 변경사항 적용
            if request.name is not None:
                changes["name"] = {"old": user.name, "new": request.name}
                user.name = request.name
            
            if request.status is not None:
                changes["status"] = {"old": user.status.value, "new": request.status.value}
                user.status = request.status
            
            user.updated_at = datetime.now()
            
            # 3. 사용자 저장
            save_result = await self.user_repository.save(user)
            if save_result.is_failure():
                return save_result
            
            # 4. 상태 변경 시 알림 이메일
            if request.status is not None:
                notification_message = f"계정 상태가 {request.status.value}로 변경되었습니다."
                await self.email_service.send_notification(user, notification_message)
            
            # 5. 감사 로그
            await self.audit_logger.log_user_action(
                user.id, "UPDATE_USER", changes
            )
            
            return Success(user)
            
        except Exception as e:
            return Failure(f"Failed to update user: {str(e)}")


@UseCase(name="list_users_use_case", dependencies=["user_repository"])
class ListUsersUseCase:
    """사용자 목록 조회 유스케이스"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def execute(self) -> Result[List[User], str]:
        """사용자 목록 조회 실행"""
        return await self.user_repository.find_all()


# ==========================================
# Presentation Layer (사용자 인터페이스)
# ==========================================

@Controller(route="/api/users", name="user_controller",
            dependencies=["create_user_use_case", "get_user_use_case", 
                         "update_user_use_case", "list_users_use_case"])
class UserController:
    """사용자 관리 컨트롤러"""
    
    def __init__(self, create_user_use_case: CreateUserUseCase,
                 get_user_use_case: GetUserUseCase,
                 update_user_use_case: UpdateUserUseCase,
                 list_users_use_case: ListUsersUseCase):
        self.create_user_use_case = create_user_use_case
        self.get_user_use_case = get_user_use_case
        self.update_user_use_case = update_user_use_case
        self.list_users_use_case = list_users_use_case
    
    async def create_user(self, request: CreateUserRequest) -> Dict[str, Any]:
        """POST /api/users - 사용자 생성"""
        result = await self.create_user_use_case.execute(request)
        
        if result.is_success():
            return {
                "success": True,
                "data": result.value.to_dict(),
                "message": "User created successfully"
            }
        else:
            return {
                "success": False,
                "error": result.error,
                "message": "Failed to create user"
            }
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """GET /api/users/{user_id} - 사용자 조회"""
        result = await self.get_user_use_case.execute(user_id)
        
        if result.is_success():
            if result.value is not None:
                return {
                    "success": True,
                    "data": result.value.to_dict()
                }
            else:
                return {
                    "success": False,
                    "error": "User not found",
                    "status_code": 404
                }
        else:
            return {
                "success": False,
                "error": result.error
            }
    
    async def update_user(self, user_id: str, request: UpdateUserRequest) -> Dict[str, Any]:
        """PUT /api/users/{user_id} - 사용자 업데이트"""
        result = await self.update_user_use_case.execute(user_id, request)
        
        if result.is_success():
            return {
                "success": True,
                "data": result.value.to_dict(),
                "message": "User updated successfully"
            }
        else:
            return {
                "success": False,
                "error": result.error
            }
    
    async def list_users(self) -> Dict[str, Any]:
        """GET /api/users - 사용자 목록 조회"""
        result = await self.list_users_use_case.execute()
        
        if result.is_success():
            return {
                "success": True,
                "data": [user.to_dict() for user in result.value],
                "count": len(result.value)
            }
        else:
            return {
                "success": False,
                "error": result.error
            }


# ==========================================
# 애플리케이션 부트스트래핑 및 데모
# ==========================================

async def bootstrap_application() -> AnnotationRegistry:
    """애플리케이션 부트스트래핑"""
    print("🚀 RFS v4.1 Hexagonal Architecture Demo Starting...")
    
    # 1. 레지스트리 및 프로세서 생성
    registry = AnnotationRegistry(current_profile="development")
    processor = AnnotationProcessor(registry)
    
    # 2. 모든 어노테이션 클래스 수집
    classes = [
        # Ports
        UserRepository, EmailService, AuditLogger,
        # Adapters  
        MemoryUserRepository, MockEmailService, ConsoleAuditLogger,
        # Use Cases
        CreateUserUseCase, GetUserUseCase, UpdateUserUseCase, ListUsersUseCase,
        # Controllers
        UserController
    ]
    
    # 3. 클래스들 등록
    context = ProcessingContext(
        profile="development",
        resolve_dependencies=True,
        validate_architecture=True
    )
    
    result = processor.process_classes(classes, context)
    
    # 4. 등록 결과 출력
    print(f"✅ Registered {result.total_registered}/{result.total_scanned} classes")
    print(f"   Processing time: {result.processing_time_ms:.2f}ms")
    
    if result.validation_errors:
        print(f"❌ Validation errors: {result.validation_errors}")
        return None
    
    if result.warnings:
        print(f"⚠️ Warnings: {result.warnings}")
    
    # 5. 등록 통계 출력
    stats = registry.get_registration_stats()
    print(f"📊 Registration Statistics:")
    for type_name, count in stats["by_type"].items():
        print(f"   {type_name}: {count}")
    
    # 6. Port 정보 출력
    port_info = registry.get_port_info()
    print(f"🔌 Ports and Adapters:")
    for port_name, info in port_info.items():
        print(f"   {port_name}: {info['adapter_count']} adapter(s)")
    
    return registry


async def run_demo_scenarios(registry: AnnotationRegistry):
    """데모 시나리오 실행"""
    print("\n🎬 Running Demo Scenarios...")
    
    # Controller 인스턴스 획득
    controller = registry.get("user_controller")
    
    print("\n=== Scenario 1: Create Users ===")
    
    # 사용자 생성
    alice_request = CreateUserRequest(email="alice@example.com", name="Alice Johnson")
    alice_response = await controller.create_user(alice_request)
    print(f"Create Alice: {alice_response}")
    
    bob_request = CreateUserRequest(email="bob@example.com", name="Bob Smith")
    bob_response = await controller.create_user(bob_request)
    print(f"Create Bob: {bob_response}")
    
    # 중복 이메일 테스트
    duplicate_request = CreateUserRequest(email="alice@example.com", name="Alice Duplicate")
    duplicate_response = await controller.create_user(duplicate_request)
    print(f"Duplicate email test: {duplicate_response}")
    
    print("\n=== Scenario 2: Get Users ===")
    
    # 사용자 목록 조회
    users_response = await controller.list_users()
    print(f"List users: {users_response}")
    
    # 특정 사용자 조회
    if alice_response["success"]:
        alice_id = alice_response["data"]["id"]
        user_response = await controller.get_user(alice_id)
        print(f"Get Alice: {user_response}")
    
    print("\n=== Scenario 3: Update User ===")
    
    # 사용자 업데이트
    if alice_response["success"]:
        alice_id = alice_response["data"]["id"]
        update_request = UpdateUserRequest(
            name="Alice Johnson-Smith",
            status=UserStatus.INACTIVE
        )
        update_response = await controller.update_user(alice_id, update_request)
        print(f"Update Alice: {update_response}")
    
    print("\n=== Scenario 4: Final State ===")
    
    # 최종 상태 확인
    final_users = await controller.list_users()
    print(f"Final users: {final_users}")


async def main():
    """메인 함수"""
    try:
        # 애플리케이션 부트스트래핑
        registry = await bootstrap_application()
        
        if registry is None:
            print("❌ Application bootstrap failed!")
            return
        
        # 데모 시나리오 실행
        await run_demo_scenarios(registry)
        
        print("\n✅ Demo completed successfully!")
        
        # 이메일 서비스에서 보낸 이메일들 확인
        email_service = registry.get_by_port("email_service")
        if hasattr(email_service, 'sent_emails'):
            print(f"\n📧 Total emails sent: {len(email_service.sent_emails)}")
            for email in email_service.sent_emails:
                print(f"   {email}")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    """
    이 데모를 실행하려면:
    
    1. 터미널에서 다음 명령어로 실행:
       python examples/hexagonal_architecture_demo.py
    
    2. 또는 pytest로 테스트:
       pytest examples/hexagonal_architecture_demo.py -v -s
    """
    asyncio.run(main())