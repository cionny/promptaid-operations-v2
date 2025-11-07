"""pytest configuration and fixtures."""

import sys
import asyncio
from pathlib import Path
import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="function")
async def cleanup_browsers():
    """Ensure browser resources are cleaned up between tests."""
    yield
    # Give async tasks time to complete
    await asyncio.sleep(0.5)
