import pytest
import json
from unittest.mock import MagicMock, patch
import os

# Mock redis before the worker's main module imports it
import sys
mock_redis_module = MagicMock()
sys.modules['redis'] = mock_redis_module

# Now import the function to be tested
from worker.app.main import process_jobs

@pytest.fixture
def mock_redis_conn():
    """Fixture to provide a mock Redis connection."""
    return MagicMock()

@patch('worker.app.stellgap_py.run_stellgap')
def test_process_single_job_success(mock_run_stellgap, mock_redis_conn, tmp_path):
    # --- Setup ---
    # 1. Create a temporary directory to act as the shared job directory
    job_dir = tmp_path / "test-job-123"
    job_dir.mkdir()

    # 2. Define the job message that the worker will receive from Redis
    job_message = {
        "job_id": "test-job-123",
        "chunk_id": 0,
        "job_dir": str(job_dir),
        "ir_start": 1,
        "ir_end": 32,
        "irads": 41,
        "ir_fine_scl": 128
    }

    # 3. Configure the mock Redis connection to return this single job,
    #    and then raise an exception to stop the worker's infinite loop.
    mock_redis_conn.brpop.side_effect = [
        ('stellgap:jobs', json.dumps(job_message)),
        KeyboardInterrupt  # Use a specific, expected exception to halt the loop
    ]

    # 4. Patch the redis.Redis() call to return our configured mock object
    with patch('worker.app.main.redis.Redis', return_value=mock_redis_conn):
        # --- Execution ---
        # Run the worker's main processing function. Expect it to stop via KeyboardInterrupt.
        with pytest.raises(KeyboardInterrupt):
            process_jobs()

    # --- Assertions ---
    # 1. Verify that the Python stellgap function was called with the correct arguments
    mock_run_stellgap.assert_called_once_with(
        job_dir=str(job_dir),
        ir_start=1,
        ir_end=32,
        irads=41,
        ir_fine_scl=128,
        outfile_worker=os.path.join(str(job_dir), "worker_output_0.txt")
    )

    # 2. Verify that the success message was pushed back to the 'stellgap:results' queue
    mock_redis_conn.lpush.assert_called_once()
    redis_call_args = mock_redis_conn.lpush.call_args[0]
    assert redis_call_args[0] == "stellgap:results"
    result_data = json.loads(redis_call_args[1])
    assert result_data == {
        "job_id": "test-job-123",
        "chunk_id": 0,
        "output_file": os.path.join(str(job_dir), "worker_output_0.txt"),
        "status": "success"
    }

@patch('worker.app.stellgap_py.run_stellgap')
def test_process_job_failure(mock_run_stellgap, mock_redis_conn, tmp_path):
    # --- Setup ---
    # 1. Configure the mock to raise an exception, simulating a failure
    mock_run_stellgap.side_effect = Exception("Python calculation error")

    # 2. Set up job directory and message as before
    job_dir = tmp_path / "test-job-456"
    job_dir.mkdir()
    job_message = {
        "job_id": "test-job-456",
        "chunk_id": 1,
        "job_dir": str(job_dir),
        "ir_start": 33,
        "ir_end": 64,
        "irads": 41,
        "ir_fine_scl": 128
    }
    mock_redis_conn.brpop.side_effect = [
        ('stellgap:jobs', json.dumps(job_message)),
        KeyboardInterrupt
    ]

    # --- Execution ---
    with patch('worker.app.main.redis.Redis', return_value=mock_redis_conn):
        with pytest.raises(KeyboardInterrupt):
            process_jobs()

    # --- Assertions ---
    # 1. Verify the Python stellgap function was called
    mock_run_stellgap.assert_called_once()

    # 2. Crucially, verify that NO success message was pushed to Redis
    mock_redis_conn.lpush.assert_not_called()
