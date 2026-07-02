import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_users(client):
    response = client.get('/users')
    assert response.status_code == 200
    assert len(response.get_json()) == 2

def test_get_user_found(client):
    response = client.get('/users/1')
    assert response.status_code == 200
    assert response.get_json()['name'] == 'Alice'

def test_get_user_not_found(client):
    response = client.get('/users/999')
    assert response.status_code == 404

def test_create_user(client):
    response = client.post('/users', json={"name": "Charlie", "email": "charlie@example.com"})
    assert response.status_code == 201
    assert response.get_json()['name'] == 'Charlie'

def test_create_user_missing_fields(client):
    response = client.post('/users', json={"name": "Dave"})
    assert response.status_code == 400