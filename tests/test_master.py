import pytest
from fastapi.testclient import TestClient
import json
from unittest.mock import MagicMock, patch
import uuid
import os

# Set a dummy environment variable to avoid errors if not set
os.environ['POSTGRES_DB'] = 'testdb'

@pytest.fixture
def client(mocker):
    """
    This fixture provides a TestClient for the master app.
    It mocks all external dependencies (redis, postgres, multiprocessing)
    *before* importing the app to ensure the lifespan manager uses the mocks.
    """
    mocker.patch('redis.Redis', return_value=MagicMock())
    mocker.patch('psycopg2.connect', return_value=MagicMock())
    mocker.patch('multiprocessing.Process')

    # Import the app here, after the mocks are in place
    from master.app.main import app

    with TestClient(app) as test_client:
        yield test_client

def test_create_job(client):
    # The app state is populated by the lifespan manager with MOCKED connections
    app = client.app
    mock_redis_conn = app.state.redis_conn
    mock_pg_conn = app.state.pg_conn

    mock_files = {
        "tae_data_boozer": ("tae_data_boozer.txt", b"mock data", "text/plain"),
        "fourier_dat": ("fourier.dat", b"mock data", "text/plain"),
        "plasma_dat": ("plasma.dat", b"mock data", "text/plain"),
    }

    response = client.post("/jobs", files=mock_files)

    assert response.status_code == 202
    response_json = response.json()
    job_id = response_json["job_id"]
    assert job_id

    mock_pg_conn.cursor.assert_called()
    mock_pg_conn.commit.assert_called()
    assert mock_redis_conn.lpush.call_count == 4

def test_get_job_status_found(client):
    app = client.app
    mock_pg_conn = app.state.pg_conn
    mock_cursor = mock_pg_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchone.return_value = ('processing', 2, 4)

    test_job_id = str(uuid.uuid4())
    response = client.get(f"/jobs/{test_job_id}")

    assert response.status_code == 200
    mock_cursor.execute.assert_called_with(
        "SELECT status, completed_chunks, num_chunks FROM jobs WHERE job_id = %s", (test_job_id,)
    )

def test_get_job_result_completed(client):
    app = client.app
    mock_pg_conn = app.state.pg_conn
    mock_cursor = mock_pg_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchone.return_value = ('completed',)

    job_id = str(uuid.uuid4())
    job_dir = os.path.join("/tmp/stellgap_jobs", job_id)
    result_file = os.path.join(job_dir, "alfven_post")

    os.makedirs(job_dir, exist_ok=True)
    with open(result_file, "w") as f:
        f.write("mock result data")

    response = client.get(f"/jobs/{job_id}/result")

    assert response.status_code == 200
    assert response.text == "mock result data"

    os.remove(result_file)
    os.rmdir(job_dir)
