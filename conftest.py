"""
pytest configuration for RFS Framework
"""

import sys
from pathlib import Path

# Add src to Python path for testing
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
import asyncio
from typing import AsyncGenerator


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_setup() -> AsyncGenerator[None, None]:
    """Setup for async tests"""
    yield
    # Cleanup after test
    await asyncio.sleep(0)  # Allow any pending tasks to complete


# Test markers
pytest_plugins = []