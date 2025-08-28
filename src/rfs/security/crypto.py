"""
RFS Cryptography (RFS v4.1)

암호화 및 해싱 시스템
"""

import base64
import hashlib
import hmac
import json
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from hashlib import _Hash

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


class HashAlgorithm(Enum):
    """해시 알고리즘"""

    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    PBKDF2 = "pbkdf2"
    SCRYPT = "scrypt"


class EncryptionAlgorithm(Enum):
    """암호화 알고리즘"""

    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    RSA_OAEP = "rsa_oaep"
    CHACHA20 = "chacha20"


@dataclass
class EncryptionResult:
    """암호화 결과"""

    encrypted_data: bytes
    nonce: Optional[bytes] = None
    tag: Optional[bytes] = None
    salt: Optional[bytes] = None


@dataclass
class KeyPair:
    """키 쌍"""

    private_key: bytes
    public_key: bytes
    algorithm: str = "RSA"


class CryptoManager:
    """암호화 관리자"""

    def __init__(self):
        self.backend = default_backend() if CRYPTOGRAPHY_AVAILABLE else None

    def _check_cryptography(self) -> Result[None, str]:
        """cryptography 라이브러리 체크"""
        if not CRYPTOGRAPHY_AVAILABLE:
            return Failure(
                "cryptography 라이브러리가 필요합니다: pip install cryptography"
            )
        return Success(None)

    def generate_key(self, length=32) -> bytes:
        """대칭키 생성"""
        return secrets.token_bytes(length)

    def generate_salt(self, length=16) -> bytes:
        """솔트 생성"""
        return secrets.token_bytes(length)

    def generate_nonce(self, length=12) -> bytes:
        """논스 생성"""
        return secrets.token_bytes(length)

    def encrypt_aes_gcm(
        self, data: bytes, key: bytes, nonce=None
    ) -> Result[EncryptionResult, str]:
        """AES-GCM 암호화"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            if nonce is None:
                nonce = self.generate_nonce(12)

            cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=self.backend)

            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(data) + encryptor.finalize()

            return Success(
                EncryptionResult(
                    encrypted_data=ciphertext, nonce=nonce, tag=encryptor.tag
                )
            )

        except Exception as e:
            return Failure(f"AES-GCM 암호화 실패: {str(e)}")

    def decrypt_aes_gcm(
        self, encrypted_result: EncryptionResult, key: bytes
    ) -> Result[bytes, str]:
        """AES-GCM 복호화"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(encrypted_result.nonce, encrypted_result.tag),
                backend=self.backend,
            )

            decryptor = cipher.decryptor()
            plaintext = decryptor.update(encrypted_result.encrypted_data) + decryptor.finalize()

            return Success(plaintext)

        except Exception as e:
            return Failure(f"AES-GCM 복호화 실패: {str(e)}")

    def encrypt_aes_cbc(
        self, data: bytes, key: bytes, iv=None
    ) -> Result[EncryptionResult, str]:
        """AES-CBC 암호화"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            if iv is None:
                iv = self.generate_nonce(16)  # AES 블록 크기

            # PKCS7 패딩 추가
            padding_length = 16 - (len(data) % 16)
            padded_data = data + bytes([padding_length] * padding_length)

            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=self.backend)

            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()

            return Success(EncryptionResult(encrypted_data=ciphertext, nonce=iv))

        except Exception as e:
            return Failure(f"AES-CBC 암호화 실패: {str(e)}")

    def decrypt_aes_cbc(
        self, encrypted_result: EncryptionResult, key: bytes
    ) -> Result[bytes, str]:
        """AES-CBC 복호화"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(encrypted_result.nonce),
                backend=self.backend,
            )

            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_result.encrypted_data) + decryptor.finalize()

            # PKCS7 패딩 제거
            padding_length = padded_data[-1]
            plaintext = padded_data[:-padding_length]

            return Success(plaintext)

        except Exception as e:
            return Failure(f"AES-CBC 복호화 실패: {str(e)}")

    def generate_rsa_keypair(self, key_size=2048) -> Result[KeyPair, str]:
        """RSA 키쌍 생성"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=key_size, backend=self.backend
            )

            public_key = private_key.public_key()

            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            return Success(
                KeyPair(private_key=private_pem, public_key=public_pem, algorithm="RSA")
            )

        except Exception as e:
            return Failure(f"RSA 키쌍 생성 실패: {str(e)}")

    def encrypt_rsa(self, data: bytes, public_key_pem: bytes) -> Result[bytes, str]:
        """RSA 암호화"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem, backend=self.backend
            )

            ciphertext = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return Success(ciphertext)

        except Exception as e:
            return Failure(f"RSA 암호화 실패: {str(e)}")

    def decrypt_rsa(
        self, encrypted_data: bytes, private_key_pem: bytes
    ) -> Result[bytes, str]:
        """RSA 복호화"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem, password=None, backend=self.backend
            )

            plaintext = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return Success(plaintext)

        except Exception as e:
            return Failure(f"RSA 복호화 실패: {str(e)}")

    def sign_data(self, data: bytes, private_key_pem: bytes) -> Result[bytes, str]:
        """데이터 서명"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem, password=None, backend=self.backend
            )

            # RSA 키에 대해서만 PSS 패딩을 사용
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
            if isinstance(private_key, RSAPrivateKey):
                signature = private_key.sign(
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            else:
                # 다른 키 타입에 대해서는 기본 sign 방법 사용
                signature = private_key.sign(data)

            return Success(signature)

        except Exception as e:
            return Failure(f"데이터 서명 실패: {str(e)}")

    def verify_signature(
        self, data: bytes, signature: bytes, public_key_pem: bytes
    ) -> Result[bool, str]:
        """서명 검증"""
        check_result = self._check_cryptography()
        if check_result.is_failure():
            failure_result = check_result
            return Failure(failure_result.unwrap_error())

        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem, backend=self.backend
            )

            # RSA 키에 대해서만 PSS 패딩을 사용
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
            if isinstance(public_key, RSAPublicKey):
                public_key.verify(
                    signature,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            else:
                # 다른 키 타입에 대해서는 기본 verify 방법 사용
                public_key.verify(signature, data)

            return Success(True)

        except Exception:
            return Success(False)

    def hash_data(
        self,
        data: bytes,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        salt=None,
    ) -> Result[bytes, str]:
        """데이터 해싱"""
        try:
            match algorithm:
                case HashAlgorithm.SHA256:
                    if salt:
                        hasher = hashlib.sha256(salt)
                    else:
                        hasher = hashlib.sha256()
                    hasher.update(data)
                    return Success(hasher.digest())

                case HashAlgorithm.SHA512:
                    if salt:
                        hasher = hashlib.sha512(salt)
                    else:
                        hasher = hashlib.sha512()
                    hasher.update(data)
                    return Success(hasher.digest())

                case HashAlgorithm.BLAKE2B:
                    if salt:
                        hasher: Any = hashlib.blake2b(
                            salt=salt[:16]
                        )  # blake2b는 최대 16바이트 솔트
                    else:
                        hasher: Any = hashlib.blake2b()
                    hasher.update(data)
                    return Success(hasher.digest())

                case HashAlgorithm.PBKDF2:
                    if salt is None:
                        salt = self.generate_salt()
                    hashed = hashlib.pbkdf2_hmac("sha256", data, salt, 100000)
                    return Success(salt + hashed)  # 솔트와 해시를 함께 반환

                case _:
                    return Failure(f"지원하지 않는 해시 알고리즘: {algorithm}")

        except Exception as e:
            return Failure(f"해싱 실패: {str(e)}")

    def verify_hash(
        self,
        data: bytes,
        hashed_data: bytes,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> Result[bool, str]:
        """해시 검증"""
        try:
            if algorithm == HashAlgorithm.PBKDF2:
                # 첫 16바이트는 솔트
                salt = hashed_data[:16]
                stored_hash = hashed_data[16:]

                computed_hash = hashlib.pbkdf2_hmac("sha256", data, salt, 100000)
                return Success(hmac.compare_digest(stored_hash, computed_hash))

            else:
                # 일반 해시의 경우
                hash_result = self.hash_data(data, algorithm)
                if hash_result.is_failure():
                    failure_result = hash_result
                    return Failure(failure_result.unwrap_error())

                computed_hash = hash_result.unwrap()
                return Success(hmac.compare_digest(hashed_data, computed_hash))

        except Exception as e:
            return Failure(f"해시 검증 실패: {str(e)}")


# 전역 암호화 관리자
_crypto_manager = CryptoManager()


# 편의 함수들
def encrypt(
    data: Union[str, bytes],
    key: bytes,
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
) -> Result[EncryptionResult, str]:
    """데이터 암호화"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    match algorithm:
        case EncryptionAlgorithm.AES_256_GCM:
            return _crypto_manager.encrypt_aes_gcm(data, key)
        case EncryptionAlgorithm.AES_256_CBC:
            return _crypto_manager.encrypt_aes_cbc(data, key)
        case _:
            return Failure(f"지원하지 않는 암호화 알고리즘: {algorithm}")


def decrypt(
    encrypted_result: EncryptionResult,
    key: bytes,
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
) -> Result[bytes, str]:
    """데이터 복호화"""
    match algorithm:
        case EncryptionAlgorithm.AES_256_GCM:
            return _crypto_manager.decrypt_aes_gcm(encrypted_result, key)
        case EncryptionAlgorithm.AES_256_CBC:
            return _crypto_manager.decrypt_aes_cbc(encrypted_result, key)
        case _:
            return Failure(f"지원하지 않는 복호화 알고리즘: {algorithm}")


def hash_password(password: str, salt=None) -> Result[str, str]:
    """비밀번호 해싱"""
    hash_result = _crypto_manager.hash_data(
        password.encode(), HashAlgorithm.PBKDF2, salt
    )
    if hash_result.is_success():
        return Success(base64.b64encode(hash_result.unwrap()).decode())
    failure_result = hash_result
    return Failure(failure_result.unwrap_error())


def verify_password(password: str, hashed_password: str) -> Result[bool, str]:
    """비밀번호 검증"""
    try:
        hashed_bytes = base64.b64decode(hashed_password)
        return _crypto_manager.verify_hash(
            password.encode(), hashed_bytes, HashAlgorithm.PBKDF2
        )
    except Exception as e:
        return Failure(f"비밀번호 검증 실패: {str(e)}")


def generate_salt(length=16) -> bytes:
    """솔트 생성"""
    return _crypto_manager.generate_salt(length)


def generate_key(length=32) -> bytes:
    """키 생성"""
    return _crypto_manager.generate_key(length)


def hash_data(
    data: Union[str, bytes],
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    salt=None,
) -> Result[str, str]:
    """데이터 해싱 (Base64 인코딩)"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    hash_result = _crypto_manager.hash_data(data, algorithm, salt)
    if hash_result.is_success():
        return Success(base64.b64encode(hash_result.unwrap()).decode())
    failure_result = hash_result
    return Failure(failure_result.unwrap_error())


def verify_hash(
    data: Union[str, bytes],
    hashed_data: str,
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
) -> Result[bool, str]:
    """해시 검증"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    try:
        hashed_bytes = base64.b64decode(hashed_data)
        return _crypto_manager.verify_hash(data, hashed_bytes, algorithm)
    except Exception as e:
        return Failure(f"해시 검증 실패: {str(e)}")


def sign_data(data: Union[str, bytes], private_key: bytes) -> Result[str, str]:
    """데이터 서명 (Base64 인코딩)"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    sign_result = _crypto_manager.sign_data(data, private_key)
    if sign_result.is_success():
        return Success(base64.b64encode(sign_result.unwrap()).decode())
    failure_result = sign_result
    return Failure(failure_result.unwrap_error())


def verify_signature(
    data: Union[str, bytes], signature: str, public_key: bytes
) -> Result[bool, str]:
    """서명 검증"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    try:
        signature_bytes = base64.b64decode(signature)
        return _crypto_manager.verify_signature(data, signature_bytes, public_key)
    except Exception as e:
        return Failure(f"서명 검증 실패: {str(e)}")


def generate_keypair(key_size=2048) -> Result[KeyPair, str]:
    """키쌍 생성"""
    return _crypto_manager.generate_rsa_keypair(key_size)
