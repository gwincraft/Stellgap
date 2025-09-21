# Stellgap
Stellgap calculates the shear Alfvén gap structure for 3D configurations (stellarators, RFPs, 3D tokamaks)

These codes are used to calculate shear Alfven continua for 3D configurations, both with and without sound wave coupling effects. The associated paper is D. A. Spong, R. Sanchez, A. Weller, "Shear Alfvén continua in stellarators," Phys. Plasmas 10 (2003) 3217–3224.
The workflow is as follows:

(a) prepare a VMEC equilibrium for the case of interest

(b) Run xbooz_xform (from Stellopt code suite) to convert from VMEC coordinates to Boozer coordinates. This run needs the in_booz.* file, which tells it what range of m/n modes to use and the selected surfaces to use from the VMEC run. Typically, the first and last of the VMEC surfaces are removed, because they can sometimes have noisy data.

(c) Using the boozmn.* file produced in (b), run xmetric_ver* to extract needed data and calculate the metric elements used in the continuum calculation. This produces a file called tae_data_boozer which is used as input for xstgap.

(d) The continuum calculation is done by xstgap*. There are two versions: one with sound wave couplings (xstgap_snd_ver*) and one without (xstgap). In addition to ae_data_boozer, these use the input files fourier.dat and plasma.dat. Fourier.dat specifies the set of fourier modes used to represent the continuum eigenmodes and plasma.dat contains information/profiles for the the plasma. The first line of fourier.dat gives the field periods and the surface grid parameters ith and izt used for calculating theta/zeta dependent coefficients of the continuum equation. It is important that these values for ith and izt are exactly the same as were used in the metric_element_create.f code.

(e) After running xstgap, the post-processing code (either post_process.f or post_process_snd.f) should be run. This produces a text file called alfven_post which contains columns of radial coordinate, frequency, dominant m and dominant n. Typically, the frequency vs. radius is plotted as a scatter plot. The code stelgp_to_silo.f is provided to convert data from alfven_post to a Visit silo file. This allows plotting the continua using the Visit software with the option to color code the points with either the dominant m or n.


Compilation scripts are provided for the different codes in the files whose name begins with “bld”. These will need to be edited, depending on what compiler is being used and where the needed libraries are located. Stellgap is constructed so that it can be compiled either as a serial version or a parallel version using precompilation flags. When running in parallel the number of surfaces requested will be divided by the number of processors and each group of surfaces allocated to a different processor. At the end of the run, all processors will write their results out to separate files, with names containing the processor number. These must be concatenated together in the post-processing step (e.g., as done in the post_process_snd.f code).

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

