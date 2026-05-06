import pytest


@pytest.mark.asyncio
async def test_students_requires_auth(client):
    response = await client.get('/api/v1/students')
    assert response.status_code == 401
