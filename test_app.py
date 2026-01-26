"""Tests for the Flask API."""
import pytest
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_simple_assertion():
    """Simple test to verify testing framework works."""
    assert 1 == 1


def test_hello_world(client):
    """Test the /hello_world endpoint returns correct response."""
    response = client.get('/hello_world')
    assert response.status_code == 200
    assert response.get_json() == {"hello": "world"}
