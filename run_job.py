import requests
import os

# --- Configuration ---
# The URL of the master server's API. This should be correct if you are
# running the services with the default docker-compose setup.
API_URL = "http://localhost:8000/jobs"

# --- Input File Paths ---
# IMPORTANT: Replace this with the actual path to the directory containing your input files.
#
# Example files can be found by decompressing the 'stellgap_test_problem.tar.gz'
# archive located in the root of this repository.
#
# On macOS/Linux, your path might look like: "/Users/yourname/stellgap_runs/my_first_run"
# On Windows, your path might look like: "C:\\Users\\yourname\\stellgap_runs\\my_first_run"
INPUT_DIR = "/path/to/your/input/files"

# The names of the required files. You probably won't need to change these.
BOOZMN_FILE = "boozmn.dat"
FOURIER_FILE = "fourier.dat"
PLASMA_FILE = "plasma.dat"

# --- Script ---
def run_stellgap_job():
    """
    Constructs and sends a request to the Stellgap API to start a new job.
    """
    print("--- Stellgap Job Submission Script ---")

    # Construct the full paths to the input files
    boozmn_path = os.path.join(INPUT_DIR, BOOZMN_FILE)
    fourier_path = os.path.join(INPUT_DIR, FOURIER_FILE)
    plasma_path = os.path.join(INPUT_DIR, PLASMA_FILE)

    # Check if the input files exist before trying to send them
    for file_path in [boozmn_path, fourier_path, plasma_path]:
        if not os.path.exists(file_path):
            print(f"\n[ERROR] Input file not found at: {file_path}")
            print(f"Please update the 'INPUT_DIR' variable in this script to point to the correct directory.")
            return

    # Create the multipart/form-data payload for the request
    # This dictionary will hold the files to be uploaded.
    files = {
        'boozmn_file': (os.path.basename(boozmn_path), open(boozmn_path, 'rb')),
        'fourier_dat': (os.path.basename(fourier_path), open(fourier_path, 'rb')),
        'plasma_dat': (os.path.basename(plasma_path), open(plasma_path, 'rb')),
    }

    print(f"\nAttempting to send job request to the API at: {API_URL}")

    try:
        # Send the POST request to the API
        response = requests.post(API_URL, files=files)

        # Check the response from the server
        if response.status_code == 202:  # 202 Accepted is the success code for this endpoint
            job_info = response.json()
            print("\n[SUCCESS] Job started successfully!")
            print(f"  -> Job ID: {job_info.get('job_id')}")
            print(f"  -> Status: {job_info.get('status')}")
            print("\nYou can use this Job ID to check the job's status and retrieve the results later.")
        else:
            # If the request failed, print the error information
            print(f"\n[ERROR] Failed to start job. The server responded with status code {response.status_code}.")
            print(f"Server response: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Connection failed. Could not connect to the API at {API_URL}.")
        print("Please make sure the Stellgap microservice is running. You can start it with 'docker-compose up --build'.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
    finally:
        # It's important to close the files we opened
        for file_tuple in files.values():
            file_tuple[1].close()

if __name__ == "__main__":
    run_stellgap_job()
