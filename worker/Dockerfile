# Stage 1: Build the Fortran executable
FROM intel/oneapi-basekit:latest as builder

WORKDIR /build

# Copy Fortran sources and build script
COPY stellgap_worker.f .
COPY Fourier_lib_convolve.f .
COPY fitpack.f .
COPY bld_stellgap_worker .

# Set up MKL environment and build
SHELL ["/bin/bash", "-c"]
RUN source /opt/intel/oneapi/setvars.sh && \
    ./bld_stellgap_worker

# Stage 2: Create the final Python application image
FROM python:3.9-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./worker/app /app/app

# Copy the compiled Fortran executable from the builder stage
COPY --from=builder /build/xstgap_worker /usr/local/bin/

# Run the worker process
CMD ["python", "-m", "app.main"]
