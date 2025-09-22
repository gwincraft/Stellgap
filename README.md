# Stellgap Microservice

Stellgap calculates the shear Alfvén gap structure for 3D configurations (stellarators, RFPs, 3D tokamaks). The core computational engine in this repository is a Python-based microservice, which is a port of the original legacy Fortran implementation.

The associated paper for the original physics code is D. A. Spong, R. Sanchez, A. Weller, "Shear Alfvén continua in stellarators," Phys. Plasmas 10 (2003) 3217–3224.

## Workflow Overview

The microservice automates the entire calculation workflow. The user initiates a job by making a request to the master server's API, which then orchestrates the following steps:

1.  **Pre-processing**: The service ingests a `boozmn.dat` file (from a VMEC/BOOZ_XFORM run), and calculates the necessary metric tensor elements, generating the `tae_data_boozer` file internally.
2.  **Parallel Calculation**: The main `stellgap` calculation is divided into chunks and distributed to multiple worker processes. Each worker runs a portion of the calculation in parallel.
3.  **Post-processing**: Once all workers have completed, their results are collected and post-processed to generate the final `alfven_post` output file, which contains the continuum data.

## Running the Stellgap Microservice

This document describes how to set up and run the Stellgap microservice. The entire computational logic, including pre- and post-processing, is written in Python, simplifying the setup process.

There are two ways to run the application: using Docker Compose (recommended for a complete setup) or running the components manually.

### Prerequisites

For the Docker setup:
*   Docker
*   Docker Compose

For the manual setup:
*   Python 3.8+
*   A running Redis instance.

### Running with Docker Compose (Recommended)

Using Docker Compose is the simplest way to get the entire application stack (master API, worker, and Redis) running.

**Build and Start the Services**

From the root directory of the repository, run the following command:
```bash
docker-compose up --build
```
This will:
*   Build the Docker images for the master and worker services.
*   Start containers for the master API, the worker, and the Redis message broker.

The master API will be accessible at `http://localhost:8000`. You can view the interactive API documentation at `http://localhost:8000/docs`.

Note: Building in such a way will spawn a single worker container.  To spawn multiple worker (example of 4) containers.  Worker containers share system resources, but are responsible for handling chunks in parallel.

```bash
docker-compose up --build --scale worker=4
```

**Shutting Down**

To stop all the running services, press Ctrl+C in the terminal where compose is running, and then run:
```bash
docker-compose down
```

### Running Manually

If you prefer to run the services locally without Docker, follow these steps.

**1. Start Redis**

You need a Redis server running. If you have one installed locally, ensure it's started. Alternatively, you can easily start one using Docker:
```bash
docker run -d -p 6379:6379 redis
```

**2. Install Dependencies**

Create and activate a Python virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate
# On Windows, use `venv\Scripts\activate`
```
Install the required packages:
```bash
pip install -r requirements.txt
```

**3. Run the Services**

You will need two separate terminal sessions to run the master and worker services. Make sure the Python virtual environment is activated in both.

**Terminal 1: Start the Worker**
```bash
python -m worker.app.main
```
You should see a message indicating that the worker process has started and is waiting for jobs.

**Terminal 2: Start the Master API**
```bash
uvicorn master.app.main:app --host 0.0.0.0 --port 8000
```
The API will now be running and accessible at `http://localhost:8000`.

### Using the API

To start a new calculation, you send a `POST` request to the `/jobs` endpoint. The request must be a `multipart/form-data` request containing the following three files:

*   `boozmn_file`: The `boozmn.dat` file from your equilibrium calculation.
*   `fourier_dat`: The `fourier.dat` file specifying the Fourier modes.
*   `plasma_dat`: The `plasma.dat` file containing plasma profiles and parameters.

You can easily do this using the interactive documentation at `http://localhost:8000/docs` or with a tool like `curl`:

```bash
curl -X 'POST' \
  'http://localhost:8000/jobs' \
  -H 'accept: application/json' \
  -F 'boozmn_file=@/path/to/your/boozmn.dat' \
  -F 'fourier_dat=@/path/to/your/fourier.dat' \
  -F 'plasma_dat=@/path/to/your/plasma.dat'
```

The API will respond with a `job_id`. You can use this ID to check the job's status and retrieve the final results.

## Visualizing Results

The primary output of a successful job is the `alfven_post` file, which contains the calculated continuum data. This repository includes a Fortran-based utility to convert this file into the Silo format, which can be visualized with tools like VisIt.

### Visualization Prerequisites

To compile the visualization utility, you will need:
*   A Fortran compiler (e.g., `gfortran` or `ifort`).
*   The Silo library installed on your system.

### Compiling the Utility

A build script, `bld_silo`, is provided but contains a hardcoded path to the Silo library and may not work on your system. It is recommended to compile the utility manually.

Navigate to the root of the repository and run a command similar to the following, replacing `/path/to/your/silo/lib` with the actual path to your Silo installation's library directory:

```bash
# Using gfortran
gfortran -o xsilo stelgp_to_silo.f -I/path/to/your/silo/include -L/path/to/your/silo/lib -lsilo

# Or using ifort
ifort -o xsilo stelgp_to_silo.f -I/path/to/your/silo/include -L/path/to/your/silo/lib -lsilo
```

This will create an executable file named `xsilo`.

### Generating the Visualization File

After a job has completed and the `alfven_post` file is available in the job's output directory:

1.  Copy the `xsilo` executable and the `alfven_post` file into the same directory.
2.  Navigate to that directory and run the executable:
    ```bash
    ./xsilo
    ```
3.  This will generate a `stellgap.silo` file, which you can then open with VisIt or another compatible viewer.
