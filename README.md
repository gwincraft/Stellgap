# Stellgap
Stellgap calculates the shear Alfvén gap structure for 3D configurations (stellarators, RFPs, 3D tokamaks)

These codes are used to calculate shear Alfven continua for 3D configurations, both with and without sound wave coupling effects. The associated paper is D. A. Spong, R. Sanchez, A. Weller, "Shear Alfvén continua in stellarators," Phys. Plasmas 10 (2003) 3217–3224.

Running the Stellgap Microservice (gprechel)
This document describes how to set up and run the Stellgap microservice. The core computational logic has been rewritten in Python, simplifying the setup process.

There are two ways to run the application: using Docker Compose (recommended for a complete setup) or running the components manually.

Prerequisites
For the Docker setup:
Docker
Docker Compose
For the manual setup:
Python 3.8+
A running Redis instance.
Running with Docker Compose (Recommended)
Using Docker Compose is the simplest way to get the entire application stack (master API, worker, and Redis) running.

Build and Start the Services

From the root directory of the repository, run the following command:

docker-compose up --build
This will:

Build the Docker images for the master and worker services using their respective Dockerfiles.
Start the containers for the master API, the worker, and the Redis message broker.
The master API will be accessible at http://localhost:8000. You can view the interactive API documentation at http://localhost:8000/docs.
Shutting Down

To stop all the running services, press Ctrl+C in the terminal, and then run:

docker-compose down
Running Manually
If you prefer to run the services locally without Docker, follow these steps.

1. Start Redis
You need a Redis server running. If you have one installed locally, ensure it's started. Alternatively, you can easily start one using Docker:

docker run -d -p 6379:6379 redis
2. Install Dependencies
Create and activate a Python virtual environment (recommended):

python3 -m venv venv
source venv/bin/activate
(On Windows, the activation command is venv\Scripts\activate)

Install the required packages:

pip install -r requirements.txt
3. Run the Services
You will need two separate terminal sessions to run the master and worker services. Make sure the Python virtual environment is activated in both.

Terminal 1: Start the Worker

The worker connects to Redis and waits for jobs to process.

python -m worker.app.main
You should see a message indicating that the worker process has started.

Terminal 2: Start the Master API

The master service runs the FastAPI application that receives requests to start calculations.

uvicorn master.app.main:app --host 0.0.0.0 --port 8000
The API will now be running and accessible at http://localhost:8000.

