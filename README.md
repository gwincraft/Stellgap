# Stellgap Microservice

Stellgap is a web service that calculates the shear Alfvén gap structure for 3D magnetic configurations like stellarators, RFPs, and 3D tokamaks. It is based on the physics described in the paper: D. A. Spong, R. Sanchez, A. Weller, "Shear Alfvén continua in stellarators," Phys. Plasmas 10 (2003) 3217–3224.

This repository contains a microservice implementation where the core computational logic has been written in Python using NumPy and SciPy.

## Architecture

The application is composed of several components that work together:

-   **Master Service (`master/`)**: A FastAPI web application that provides the HTTP API for submitting jobs, checking status, and retrieving results.
-   **Worker Service (`worker/`)**: A Python process that listens for jobs on a Redis queue. It performs the intensive numerical calculations for the Stellgap analysis.
-   **Redis**: A message broker that facilitates communication between the master and worker services. The master pushes job requests to a queue, and workers pull from this queue.
-   **PostgreSQL**: A database used by the master service to store metadata about each job, such as its status and progress.

## Running the Application

There are two ways to run the application: using Docker Compose (recommended for a complete setup) or running the components manually.

### Running with Docker Compose (Recommended)

Using Docker Compose is the simplest way to get the entire application stack (master API, worker, Redis, and PostgreSQL) running.

**Prerequisites:**
-   Docker
-   Docker Compose

**1. Build and Start the Services**

From the root directory of the repository, run the following command:

```bash
docker-compose up --build
```

This will:
-   Build the Docker images for the `master` and `worker` services.
-   Start containers for the master API, one or more workers, a Redis broker, and a PostgreSQL database.

The master API will be accessible at `http://localhost:8000`. You can view the interactive API documentation (via Swagger UI) at `http://localhost:8000/docs`.

**2. Shutting Down**

To stop all the running services, press `Ctrl+C` in the terminal where `docker-compose` is running, and then run:

```bash
docker-compose down
```

### Running Manually

If you prefer to run the services locally without Docker, follow these steps.

**Prerequisites:**
-   Python 3.8+
-   A running Redis instance.
-   A running PostgreSQL instance.

**1. Start Redis and PostgreSQL**

Ensure you have Redis and PostgreSQL servers running and accessible. You can install them locally or run them via Docker:

```bash
# Start Redis
docker run -d -p 6379:6379 --name stellgap-redis redis

# Start PostgreSQL
docker run -d -p 5432:5432 --name stellgap-postgres \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=stellgap_logs \
  postgres
```

**2. Install Dependencies**

Create and activate a Python virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate
# On Windows, use: venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

**3. Configure Environment Variables**

The services connect to Redis and PostgreSQL using environment variables. If your database instances are running on different hosts or with different credentials, set the following variables:
-   `REDIS_HOST`
-   `REDIS_PORT`
-   `POSTGRES_DB`
-   `POSTGRES_USER`
-   `POSTGRES_PASSWORD`
-   `POSTGRES_HOST`

**4. Run the Services**

You will need two separate terminal sessions. Make sure the Python virtual environment is activated in both.

**Terminal 1: Start the Worker**

```bash
python -m worker.app.main
```
You should see a message indicating the worker has started and is waiting for jobs.

**Terminal 2: Start the Master API**

```bash
uvicorn master.app.main:app --host 0.0.0.0 --port 8000
```
The API will now be running and accessible at `http://localhost:8000`.

## API Usage

You can interact with the API using any HTTP client (like `curl` or `requests`) or by using the interactive documentation at `http://localhost:8000/docs`.

### 1. Submit a Job

To start a calculation, send a `POST` request to the `/jobs` endpoint. The request must be a `multipart/form-data` request containing three input files:

-   `tae_data_boozer`: The Boozer coordinate data file.
-   `fourier_dat`: The file specifying the Fourier modes.
-   `plasma_dat`: The file containing plasma information and profiles.

**Example using `curl`:**

```bash
curl -X POST "http://localhost:8000/jobs" \
     -F "tae_data_boozer=@/path/to/your/tae_data_boozer" \
     -F "fourier_dat=@/path/to/your/fourier.dat" \
     -F "plasma_dat=@/path/to/your/plasma.dat"
```

The server will respond with a unique `job_id`:

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "processing"
}
```

### 2. Check Job Status

You can check the progress of a job by sending a `GET` request to `/jobs/{job_id}`:

**Example using `curl`:**

```bash
curl -X GET "http://localhost:8000/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef"
```

The response will show the current status and progress:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "processing",
  "progress": "2/4 chunks completed"
}
```
When the job is finished, the status will change to `completed`.

### 3. Retrieve the Result

Once a job's status is `completed`, you can download the result file by sending a `GET` request to `/jobs/{job_id}/result`.

**Example using `curl`:**

```bash
curl -X GET "http://localhost:8000/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef/result" -o alfven_post
```
This will save the result to a file named `alfven_post` in your current directory.
