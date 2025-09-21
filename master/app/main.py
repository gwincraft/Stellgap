from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import redis
import psycopg2
import uuid
import os
import subprocess
import json
from typing import List
import multiprocessing
from .result_listener import listen_for_results

app = FastAPI()

# --- Connection Settings (loaded from environment variables) ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
POSTGRES_DB = os.getenv("POSTGRES_DB", "stellgap_logs")
POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
# --------------------------------------------------------------------------------

# Global variable to hold the listener process
listener_process = None

# Connect to Redis
try:
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    redis_conn.ping()
    print("Successfully connected to Redis")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    redis_conn = None

# Connect to PostgreSQL
try:
    pg_conn = psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST
    )
    print("Successfully connected to PostgreSQL")
except psycopg2.OperationalError as e:
    print(f"Could not connect to PostgreSQL: {e}")
    pg_conn = None

# Shared directory for job data
SHARED_DATA_DIR = "/tmp/stellgap_jobs"
os.makedirs(SHARED_DATA_DIR, exist_ok=True)

def setup_database():
    """Create the jobs table if it doesn't exist."""
    if pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id UUID PRIMARY KEY,
                    status VARCHAR(20) NOT NULL,
                    ir_fine_scl INTEGER,
                    num_chunks INTEGER,
                    completed_chunks INTEGER DEFAULT 0,
                    iopt INTEGER,
                    nang2 INTEGER,
                    isym_pos INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            pg_conn.commit()
            print("Database table 'jobs' is set up.")

@app.on_event("startup")
def on_startup():
    global listener_process
    setup_database()
    print("Starting result listener process...")
    listener_process = multiprocessing.Process(target=listen_for_results, daemon=True)
    listener_process.start()

@app.on_event("shutdown")
def on_shutdown():
    global listener_process
    if listener_process and listener_process.is_alive():
        print("Terminating result listener process...")
        listener_process.terminate()
        listener_process.join()


@app.post("/jobs", status_code=202)
async def create_job(
    ir_fine_scl: int = 128, # This should be determined from input files later
    num_workers: int = 4,   # This can be a parameter
    iopt: int = 1,          # Placeholder
    nang2: int = 10,         # Placeholder, should be from fourier.dat
    isym_pos: int = 1,      # Placeholder
    tae_data_boozer: UploadFile = File(...),
    fourier_dat: UploadFile = File(...),
    plasma_dat: UploadFile = File(...)
):
    """
    Creates and starts a new Stellgap calculation job.
    """
    if not redis_conn or not pg_conn:
        raise HTTPException(status_code=503, detail="Service unavailable: could not connect to Redis or PostgreSQL")

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(SHARED_DATA_DIR, job_id)
    os.makedirs(job_dir)

    try:
        # Save uploaded files to the job-specific directory
        with open(os.path.join(job_dir, "tae_data_boozer"), "wb") as f:
            f.write(await tae_data_boozer.read())
        with open(os.path.join(job_dir, "fourier.dat"), "wb") as f:
            f.write(await fourier_dat.read())
        with open(os.path.join(job_dir, "plasma.dat"), "wb") as f:
            f.write(await plasma_dat.read())

        # TODO: This is where the pre-processing step would run to generate
        # the large common data arrays (bfield_lrg, gsssup_lrg, etc.).
        # For now, we assume the worker has access to them or they are
        # generated from the inputs.

        # Log the new job in PostgreSQL
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_id, status, ir_fine_scl, num_chunks, iopt, nang2, isym_pos)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (job_id, 'processing', ir_fine_scl, num_workers, iopt, nang2, isym_pos)
            )
            pg_conn.commit()

        # Divide the work and publish jobs to the Redis queue
        chunk_size = ir_fine_scl // num_workers
        for i in range(num_workers):
            ir_start = i * chunk_size + 1
            ir_end = (i + 1) * chunk_size
            if i == num_workers - 1:
                ir_end = ir_fine_scl  # Ensure the last worker gets the remainder

            job_data = {
                "job_id": job_id,
                "chunk_id": i,
                "job_dir": job_dir,
                "ir_start": ir_start,
                "ir_end": ir_end,
                "irads": 41, # Placeholder, should be from input
                "ir_fine_scl": ir_fine_scl
            }
            redis_conn.lpush("stellgap:jobs", json.dumps(job_data))

    except Exception as e:
        # Clean up job directory if something goes wrong
        # os.rmdir(job_dir) # Be careful with this in production
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

    return {"job_id": job_id, "status": "processing"}


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Retrieves the status of a specific job.
    """
    if not pg_conn:
        raise HTTPException(status_code=503, detail="Service unavailable: could not connect to PostgreSQL")

    with pg_conn.cursor() as cur:
        cur.execute("SELECT status, completed_chunks, num_chunks FROM jobs WHERE job_id = %s", (job_id,))
        result = cur.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    status, completed, total = result
    return {
        "job_id": job_id,
        "status": status,
        "progress": f"{completed}/{total} chunks completed"
    }


@app.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """
    Retrieves the final result file for a completed job.
    """
    if not pg_conn:
        raise HTTPException(status_code=503, detail="Service unavailable: could not connect to PostgreSQL")

    # First, check the job status
    with pg_conn.cursor() as cur:
        cur.execute("SELECT status FROM jobs WHERE job_id = %s", (job_id,))
        result = cur.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    if result[0] != 'completed':
        raise HTTPException(status_code=400, detail=f"Job status is '{result[0]}'. Result is not yet available.")

    # If completed, return the result file
    job_dir = os.path.join(SHARED_DATA_DIR, job_id)
    result_file = os.path.join(job_dir, "alfven_post")
    if not os.path.exists(result_file):
        raise HTTPException(status_code=404, detail="Result file not found, though job is marked as complete.")

    return FileResponse(result_file, media_type="text/plain", filename="alfven_post")
