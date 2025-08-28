"""
RFS JWT Service (RFS v4.1)

JWT 토큰 서비스
"""

import json
import time
from typing import Any, Dict, Optional

from ..core.result import Failure, Result, Success
from .auth import JWTAuthProvider, TokenType, User


class JWTService:
    """JWT 서비스"""

    def __init__(
        self,
        secret_key=None,
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    ):
        """JWT 서비스 초기화

        Args:
            secret_key: JWT 서명용 비밀키
            algorithm: JWT 알고리즘 (HS256, RS256 등)
            access_token_expire_minutes: 액세스 토큰 만료 시간 (분)
            refresh_token_expire_days: 리프레시 토큰 만료 시간 (일)
        """
        self.secret_key = secret_key or "your-secret-key-change-in-production"
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire_minutes * 60
        self.refresh_token_expire = refresh_token_expire_days * 24 * 60 * 60
        self.auth_provider = JWTAuthProvider(
            secret_key=self.secret_key, algorithm=algorithm
        )

    async def create_access_token(
        self,
        user_id: str,
        user: Optional[Dict[str, Any]] = None,
        roles=None,
        permissions=None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> Result[str, str]:
        """액세스 토큰 생성

        Args:
            user_id: 사용자 ID
            user: 사용자 정보
            roles: 사용자 역할 리스트
            permissions: 사용자 권한 리스트
            additional_claims: 추가 클레임

        Returns:
            Result[str, str]: JWT 액세스 토큰 또는 오류
        """
        try:
            current_time = int(time.time())
            payload = {
                "user_id": user_id,
                "user": user or {},
                "roles": roles or [],
                "permissions": permissions or [],
                "token_type": TokenType.ACCESS.value,
                "iat": current_time,
                "exp": current_time + self.access_token_expire,
            }

            if additional_claims:
                payload.update(additional_claims)

            token = self.auth_provider._encode_jwt(payload)
            return Success(token)
        except Exception as e:
            return Failure(f"액세스 토큰 생성 실패: {str(e)}")

    async def create_refresh_token(
        self,
        user_id: str,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> Result[str, str]:
        """리프레시 토큰 생성

        Args:
            user_id: 사용자 ID
            additional_claims: 추가 클레임

        Returns:
            Result[str, str]: JWT 리프레시 토큰 또는 오류
        """
        try:
            current_time = int(time.time())
            payload = {
                "user_id": user_id,
                "token_type": TokenType.REFRESH.value,
                "iat": current_time,
                "exp": current_time + self.refresh_token_expire,
            }

            if additional_claims:
                payload.update(additional_claims)

            token = self.auth_provider._encode_jwt(payload)
            return Success(token)
        except Exception as e:
            return Failure(f"리프레시 토큰 생성 실패: {str(e)}")

    async def verify_token(
        self,
        token: str,
        token_type=None,
    ) -> Result[Dict[str, Any], str]:
        """토큰 검증

        Args:
            token: JWT 토큰
            token_type: 예상 토큰 타입

        Returns:
            Result[Dict[str, Any], str]: 토큰 페이로드 또는 오류
        """
        try:
            # JWT 디코딩
            decode_result = self.auth_provider._decode_jwt(token)
            if decode_result.is_failure():
                return decode_result

            payload = decode_result.value

            # 토큰 타입 확인
            if token_type and payload.get("token_type") != token_type.value:
                return Failure(f"잘못된 토큰 타입: {payload.get('token_type')}")

            # 만료 시간 확인
            current_time = int(time.time())
            exp = payload.get("exp")
            if exp and current_time > exp:
                return Failure("토큰이 만료되었습니다")

            return Success(payload)
        except Exception as e:
            return Failure(f"토큰 검증 실패: {str(e)}")

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> Result[tuple[str, str], str]:
        """리프레시 토큰으로 액세스 토큰 갱신

        Args:
            refresh_token: 리프레시 토큰

        Returns:
            Result[tuple[str, str], str]: (새 액세스 토큰, 새 리프레시 토큰) 또는 오류
        """
        # 리프레시 토큰 검증
        verify_result = await self.verify_token(refresh_token, TokenType.REFRESH)
        if verify_result.is_failure():
            return Failure(f"리프레시 토큰 검증 실패: {verify_result.error}")

        payload = verify_result.value
        user_id = payload.get("user_id")

        if not user_id:
            return Failure("리프레시 토큰에 사용자 ID가 없습니다")

        # 새 액세스 토큰 생성
        access_token_result = await self.create_access_token(user_id)
        if access_token_result.is_failure():
            return Failure(f"액세스 토큰 생성 실패: {access_token_result.error}")

        # 새 리프레시 토큰 생성 (선택적)
        refresh_token_result = await self.create_refresh_token(user_id)
        if refresh_token_result.is_failure():
            return Failure(f"리프레시 토큰 생성 실패: {refresh_token_result.error}")

        return Success((access_token_result.value, refresh_token_result.value))

    async def revoke_token(self, token: str) -> Result[bool, str]:
        """토큰 폐기 (블랙리스트 추가)

        Args:
            token: 폐기할 토큰

        Returns:
            Result[bool, str]: 성공 여부
        """
        # 프로덕션에서는 Redis나 데이터베이스를 사용한 토큰 블랙리스트 관리 필요
        return Success(True)

    async def decode_token(self, token: str) -> Result[Dict[str, Any], str]:
        """토큰 디코딩 (검증 없이)

        Args:
            token: JWT 토큰

        Returns:
            Result[Dict[str, Any], str]: 토큰 페이로드 또는 오류
        """
        try:
            import base64

            parts = token.split(".")
            if len(parts) != 3:
                return Failure("잘못된 JWT 형식")

            # 페이로드 디코딩 (검증 없이)
            payload_str = parts[1]
            # Base64 패딩 추가
            payload_str += "=" * (4 - len(payload_str) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_str)
            payload = json.loads(payload_bytes.decode("utf-8"))

            return Success(payload)
        except Exception as e:
            return Failure(f"토큰 디코딩 실패: {str(e)}")
