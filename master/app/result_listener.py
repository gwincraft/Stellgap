import redis
import psycopg2
import json
import os
import subprocess
import time

# --- Connection Settings (loaded from environment variables) ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
POSTGRES_DB = os.getenv("POSTGRES_DB", "stellgap_logs")
POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
SHARED_DATA_DIR = "/tmp/stellgap_jobs"
# ------------------------------------------------------------------------------------

def listen_for_results():
    """
    Connects to Redis and continuously listens for results from workers.
    """
    print("Result listener started...")
    # It's better to create new connections in a long-running background process
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    pg_conn = psycopg2.connect(
        dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, host=POSTGRES_HOST
    )

    while True:
        try:
            # Blocking pop from the results queue
            _, message_json = redis_conn.brpop("stellgap:results")
            message = json.loads(message_json)

            job_id = message.get("job_id")
            chunk_id = message.get("chunk_id")
            worker_output_file = message.get("output_file")

            if not all([job_id, worker_output_file]):
                print(f"ERROR: Received invalid message: {message}")
                continue

            print(f"Received result for job {job_id}, chunk {chunk_id}")

            with pg_conn.cursor() as cur:
                # Atomically increment completed_chunks and get the new count and total
                cur.execute(
                    """
                    UPDATE jobs
                    SET completed_chunks = completed_chunks + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = %s
                    RETURNING completed_chunks, num_chunks;
                    """,
                    (job_id,)
                )
                result = cur.fetchone()
                pg_conn.commit()

                if not result:
                    print(f"ERROR: Job ID {job_id} not found in database.")
                    continue

                completed_chunks, num_chunks = result
                print(f"Job {job_id}: {completed_chunks}/{num_chunks} chunks complete.")

                # Check if the job is finished
                if completed_chunks >= num_chunks:
                    print(f"Job {job_id} is complete. Starting post-processing.")

                    # Get the metadata needed for the data_post file
                    cur.execute(
                        "SELECT iopt, nang2, ir_fine_scl, isym_pos FROM jobs WHERE job_id = %s",
                        (job_id,)
                    )
                    meta_result = cur.fetchone()
                    if not meta_result:
                        print(f"ERROR: Could not retrieve metadata for job {job_id}")
                        continue

                    iopt, nang2, irads, isym_pos = meta_result

                    job_dir = os.path.join(SHARED_DATA_DIR, job_id)

                    # Gather all worker output files for this job
                    worker_files = sorted([
                        os.path.join(job_dir, f)
                        for f in os.listdir(job_dir)
                        if f.startswith("worker_output_")
                    ])

                    if not worker_files:
                        raise Exception("No worker output files found for completed job.")

                    # Run the post-processing Fortran executable
                    # Assumes xpost_process_cli is in the PATH
                    post_process_cmd = ["xpost_process_cli"] + worker_files

                    # Create the data_post file with the values from the database
                    data_post_content = f"{iopt} {nang2} {irads} {isym_pos}"
                    with open(os.path.join(job_dir, "data_post"), "w") as f:
                        f.write(data_post_content)

                    # We need to run the command from the job directory so it can find the input files
                    process = subprocess.run(
                        post_process_cmd,
                        cwd=job_dir,
                        capture_output=True,
                        text=True
                    )

                    if process.returncode != 0:
                        print(f"ERROR: Post-processing failed for job {job_id}.")
                        print(f"STDOUT: {process.stdout}")
                        print(f"STDERR: {process.stderr}")
                        # Update job status to 'failed'
                        cur.execute(
                            "UPDATE jobs SET status = 'failed' WHERE job_id = %s", (job_id,)
                        )
                    else:
                        print(f"Post-processing successful for job {job_id}.")
                        # Update job status to 'completed'
                        cur.execute(
                            "UPDATE jobs SET status = 'completed' WHERE job_id = %s", (job_id,)
                        )

                    pg_conn.commit()

        except Exception as e:
            print(f"An error occurred in the listener loop: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
            try:
                redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
                pg_conn = psycopg2.connect(
                    dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, host=POSTGRES_HOST
                )
                print("Listener reconnected to Redis and PostgreSQL.")
            except Exception as conn_e:
                print(f"Failed to reconnect: {conn_e}")
                time.sleep(5) # Wait before retrying the main loop


if __name__ == "__main__":
    listen_for_results()
