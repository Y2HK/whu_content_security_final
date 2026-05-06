import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    response = await client.post('/api/v1/auth/login', json={'username': 'teacher', 'password': 'teacher123'})
    assert response.status_code == 200
    assert response.json()['data']['access_token']
