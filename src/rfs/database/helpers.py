"""
Database Helper Functions
데이터베이스 헬퍼 함수들
"""

from typing import Any, Dict

from tortoise import Tortoise


def get_tortoise_url(config: dict) -> str:
    """Tortoise ORM 연결 URL 생성

    Args:
        config: 데이터베이스 설정 딕셔너리

    Returns:
        str: Tortoise ORM 연결 URL

    Raises:
        ValueError: 지원하지 않는 데이터베이스 타입인 경우
    """
    db_type = config.get("type", "sqlite")

    if db_type == "sqlite":
        path = config.get("database_path", "test.db")
        return f"sqlite://{path}"
    elif db_type == "postgres":
        host = config.get("host", "localhost")
        port = config.get("port", 5432)
        user = config.get("user", "postgres")
        password = config.get("password", "")
        database = config.get("database", "test")
        return f"postgres://{user}:{password}@{host}:{port}/{database}"
    elif db_type == "mysql":
        host = config.get("host", "localhost")
        port = config.get("port", 3306)
        user = config.get("user", "root")
        password = config.get("password", "")
        database = config.get("database", "test")
        return f"mysql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"지원하지 않는 데이터베이스 타입: {db_type}")


async def create_test_connection(config: Dict[str, Any]) -> None:
    """테스트용 데이터베이스 연결 생성

    Args:
        config: 데이터베이스 설정 딕셔너리
    """
    db_url = get_tortoise_url(config)
    await Tortoise.init(db_url=db_url, modules={"models": ["rfs.database.models"]})
    await Tortoise.generate_schemas()


def get_database_config(env="test") -> Dict[str, Any]:
    """환경별 데이터베이스 설정 반환

    Args:
        env: 환경 이름 (test, development, production)

    Returns:
        Dict[str, Any]: 데이터베이스 설정 딕셔너리
    """
    configs = {
        "test": {"type": "sqlite", "database_path": ":memory:"},
        "development": {"type": "sqlite", "database_path": "dev.db"},
        "production": {
            "type": "postgres",
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "",
            "database": "rfs_prod",
        },
    }
    return configs.get(env, configs["test"])


async def close_test_connection() -> None:
    """테스트 연결 종료"""
    await Tortoise.close_connections()
