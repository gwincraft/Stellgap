import pytest
from fastapi.testclient import TestClient
import json
from unittest.mock import MagicMock, patch
import uuid
import os
import struct
import numpy as np

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

def test_create_job(client, mocker):
    # The app state is populated by the lifespan manager with MOCKED connections
    app = client.app
    mock_redis_conn = app.state.redis_conn
    mock_pg_conn = app.state.pg_conn

    # Since we changed the API, we now need to upload a boozmn_file
    # We also need to mock the new pre-processor functions
    mocker.patch('master.app.main.read_boozmn_file', return_value={})
    mocker.patch('master.app.main.create_tae_data', return_value="mock tae data")

    mock_files = {
        "boozmn_file": ("boozmn.dat", b"mock boozmn data", "application/octet-stream"),
        "fourier_dat": ("fourier.dat", b"mock fourier data", "text/plain"),
        "plasma_dat": ("plasma.dat", b"mock plasma data", "text/plain"),
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

def test_preprocessing_integration(client, tmp_path):
    """
    An integration test for the pre-processing logic.
    It uses a real (but small) boozmn file and checks the generated
    tae_data_boozer file.
    """
    # 1. Create a dummy boozmn.dat file in memory
    # This is a highly simplified version of a real boozmn file.
    # It contains 3 surfaces (ns_b=3) and 2 fourier modes (mnboz_b=2).
    # The structure is:
    # Record 1: nfp, ns, aspect, rmax, rmin, betaxis (i, i, d, d, d, f)
    # Record 2-3: iota, pres, beta, phip, phi, bvco, buco (7*f for each surface)
    # Record 4: mboz, nboz, mnboz (i, i, i)
    # Record 5: version (f)
    # Record 6: nsval (i)
    # Record 7: ixn (i * mnboz)
    # Record 8: ixm (i * mnboz)
    # Record 9: bmnc, rmnc, zmns, pmns, gmnc (5*f * mnboz) for nsval=2
    # Record 10: nsval (i)
    # Record 11: bmnc, rmnc, zmns, pmns, gmnc (5*f * mnboz) for nsval=3

    def write_fortran_record(data, fmt):
        packed_data = struct.pack(fmt, *data)
        return struct.pack('i', len(packed_data)) + packed_data + struct.pack('i', len(packed_data))

    boozmn_content = b""
    # Rec 1
    boozmn_content += write_fortran_record((5, 3, 10.0, 2.0, 0.5, 0.05), '=iidddf')
    # Rec 2 (ns=2)
    boozmn_content += write_fortran_record(tuple(np.random.rand(7).astype(np.float32)), '=7f')
    # Rec 3 (ns=3)
    boozmn_content += write_fortran_record(tuple(np.random.rand(7).astype(np.float32)), '=7f')
    # Rec 4
    boozmn_content += write_fortran_record((2, 2, 2), '=iii')
    # Rec 5
    boozmn_content += write_fortran_record((1.0,), '=f')
    # Rec 6
    boozmn_content += write_fortran_record((2,), '=i')
    # Rec 7
    boozmn_content += write_fortran_record((0, 1), '=ii')
    # Rec 8
    boozmn_content += write_fortran_record((0, 1), '=ii')
    # Rec 9 (ns=2)
    boozmn_content += write_fortran_record(tuple(np.random.rand(10).astype(np.float32)), '=10f')
    # Rec 10
    boozmn_content += write_fortran_record((3,), '=i')
    # Rec 11 (ns=3)
    boozmn_content += write_fortran_record(tuple(np.random.rand(10).astype(np.float32)), '=10f')

    boozmn_path = tmp_path / "boozmn.dat"
    boozmn_path.write_bytes(boozmn_content)

    # 2. Create dummy fourier.dat and plasma.dat
    (tmp_path / "fourier.dat").write_text("1 1 1 1\n1\n1 1 1")
    (tmp_path / "plasma.dat").write_text("&plasma_input /")

    mock_files = {
        "boozmn_file": ("boozmn.dat", boozmn_path.open('rb'), "application/octet-stream"),
        "fourier_dat": ("fourier.dat", (tmp_path / "fourier.dat").open('rb'), "text/plain"),
        "plasma_dat": ("plasma.dat", (tmp_path / "plasma.dat").open('rb'), "text/plain"),
    }

    # 3. Call the endpoint
    response = client.post("/jobs", files=mock_files)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # 4. Check the output
    job_dir = os.path.join("/tmp/stellgap_jobs", job_id)
    tae_data_path = os.path.join(job_dir, "tae_data_boozer")
    assert os.path.exists(tae_data_path)

    # In a real scenario, we would compare the content with a "golden" file.
    # For now, we'll just check that it's not empty.
    with open(tae_data_path, 'r') as f:
        content = f.read()
        assert len(content) > 0
