from httpx import ASGITransport, AsyncClient

try:
    import pytest_asyncio
except ImportError:
    import pytest

    async_fixture = pytest.fixture
else:
    async_fixture = pytest_asyncio.fixture

from app.main import app


@async_fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
