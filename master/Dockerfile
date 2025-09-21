# Stage 1: Build the Fortran executable
FROM intel/oneapi-basekit:latest as builder

WORKDIR /build

# Copy Fortran source and build script
COPY post_process_cli.f .
COPY bld_post_process_cli .

# Set up MKL environment and build
SHELL ["/bin/bash", "-c"]
RUN source /opt/intel/oneapi/setvars.sh && \
    ./bld_post_process_cli

# Stage 2: Create the final Python application image
FROM python:3.9-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./master/app /app/app

# Copy the compiled Fortran executable from the builder stage
COPY --from=builder /build/xpost_process_cli /usr/local/bin/

# Expose the port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
