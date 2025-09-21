import redis
import json
import os
import subprocess
import time

# --- Connection Settings (loaded from environment variables) ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
# ------------------------------------------------------------------------------------

def process_jobs():
    """
    Connects to Redis and continuously listens for jobs to process.
    """
    print("Worker process started...")
    # It's better to create a new connection for a long-running process
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

    while True:
        try:
            # Blocking pop from the jobs queue
            _, message_json = redis_conn.brpop("stellgap:jobs")
            message = json.loads(message_json)

            job_id = message.get("job_id")
            chunk_id = message.get("chunk_id")
            job_dir = message.get("job_dir")
            ir_start = message.get("ir_start")
            ir_end = message.get("ir_end")
            irads = message.get("irads")
            ir_fine_scl = message.get("ir_fine_scl")

            if not all([job_id, job_dir, ir_start, ir_end, irads, ir_fine_scl]):
                print(f"ERROR: Received invalid job message: {message}")
                continue

            print(f"Received job {job_id}, chunk {chunk_id}. Processing surfaces {ir_start}-{ir_end}.")

            # Define file paths
            worker_input_filename = f"worker_input_{chunk_id}.dat"
            worker_output_filename = f"worker_output_{chunk_id}.txt"
            worker_input_filepath = os.path.join(job_dir, worker_input_filename)
            worker_output_filepath = os.path.join(job_dir, worker_output_filename)

            # 1. Create the worker_input.dat file
            # The Fortran code expects the output file path inside this file.
            with open(worker_input_filepath, "w") as f:
                f.write(f"{ir_start}\n")
                f.write(f"{ir_end}\n")
                # The Fortran code reads the filename and uses it directly.
                # It will be created inside the CWD, which is job_dir.
                f.write(f"{worker_output_filename}\n")

            # 2. Run the Fortran executable
            # Assumes xstgap_worker is in the PATH.
            worker_cmd = ["xstgap_worker", str(irads), str(ir_fine_scl)]

            # The Fortran code reads files from the current directory.
            # So, we must run the subprocess with `cwd=job_dir`.
            process = subprocess.run(
                worker_cmd,
                cwd=job_dir,
                capture_output=True,
                text=True
            )

            if process.returncode != 0:
                print(f"ERROR: Fortran worker failed for job {job_id}, chunk {chunk_id}.")
                print(f"STDOUT: {process.stdout}")
                print(f"STDERR: {process.stderr}")
                # Optionally, push an error message to a different Redis queue
                continue

            # 3. Publish result back to Redis
            result_message = {
                "job_id": job_id,
                "chunk_id": chunk_id,
                "output_file": worker_output_filepath, # The master will need the full path
                "status": "success"
            }
            redis_conn.lpush("stellgap:results", json.dumps(result_message))
            print(f"Finished job {job_id}, chunk {chunk_id}.")

        except Exception as e:
            print(f"An error occurred in the worker loop: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
            try:
                redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
                print("Worker reconnected to Redis.")
            except Exception as redis_e:
                print(f"Failed to reconnect to Redis: {redis_e}")
                time.sleep(5) # Wait before retrying the main loop


if __name__ == "__main__":
    process_jobs()
