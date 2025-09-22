import numpy as np
import os

def post_process_results(job_dir, worker_files, iopt, nang2, irads, isym_pos):
    """
    Combines and processes the raw output from the stellgap workers.
    This function is a Python port of the post_process_cli.f Fortran code.

    Args:
        job_dir (str): The directory for the job.
        worker_files (list): A list of paths to the worker output files.
        iopt (int): Metadata parameter (not used in this script but kept for consistency).
        nang2 (int): Metadata parameter (number of eigenvalues per surface).
        irads (int): Metadata parameter (number of radial surfaces).
        isym_pos (int): Flag to determine parsing logic (0 for general matrix, 1 for symmetric).
    """
    alfven_post_path = os.path.join(job_dir, "alfven_post")
    cond_no_path = os.path.join(job_dir, "cond_no")

    # In Fortran, itot is calculated, but we just process all lines.
    # We will write the total number of lines at the end.
    output_lines = []
    cond_no_lines = []

    all_lines = []
    for file_path in worker_files:
        with open(file_path, 'r') as f:
            all_lines.extend(f.readlines())

    # The Fortran code processes data in a (irads, nang2) loop.
    # Here, we process line by line, assuming the input is correctly ordered.
    # We need to group lines by radial point (r_pt) to calculate cond_no.
    lines_by_rpt = {}
    for line in all_lines:
        parts = line.strip().split()
        if not parts:
            continue
        r_pt = float(parts[0])
        if r_pt not in lines_by_rpt:
            lines_by_rpt[r_pt] = []
        lines_by_rpt[r_pt].append(line)

    # Sort by r_pt to process in the correct order
    sorted_rpts = sorted(lines_by_rpt.keys())

    for r_pt in sorted_rpts:
        temp_lambdas = []
        lam_min = 1e10
        lam_max = -1e10

        for line in lines_by_rpt[r_pt]:
            parts = [p for p in line.strip().split() if p]

            if isym_pos == 1:
                # Format: r_pt, omega, m_emax, n_emax
                omega = float(parts[1])
                m_emax = int(parts[2])
                n_emax = int(parts[3])

                temp_lambdas.append(omega**2)

                # The Fortran code applies a `fnorm`, but it's set to 1.0.
                output_lines.append(f"{r_pt:15.7e} {omega:15.7e} {m_emax:4d} {n_emax:4d}\n")

            else: # isym_pos == 0
                # Format: r_pt, alpha_r, alpha_i, beta, m_emax, n_emax, m_emax_psi, n_emax_psi, phi_norm, psi_norm
                # Note: The Python worker writes eigvals directly, not alpha/beta.
                # The worker output is: r_pt, eigval.real, eigval.imag, 1.0, m_emax, n_emax
                # This matches the Fortran format if alpha_r=eigval.real, alpha_i=eigval.imag, beta=1.0
                r_pt_val = float(parts[0])
                alpha_r = float(parts[1])
                alpha_i = float(parts[2])
                beta = float(parts[3])
                m_emax = int(parts[4])
                n_emax = int(parts[5])

                # These fields are not in the current python worker output, but were in the fortran version
                # We'll assign dummy values for now.
                phi_norm = 1.0
                psi_norm = 0.0

                if beta > 0:
                    lambda_real = alpha_r / beta
                    if lambda_real > 0:
                        lam_min = min(lam_min, abs(lambda_real))
                        lam_max = max(lam_max, abs(lambda_real))
                    lambda_imag = alpha_i / beta
                    omega2 = complex(lambda_real, lambda_imag)
                else:
                    omega2 = complex(1e10, 0)

                omega = np.sqrt(omega2)
                omega_r = omega.real
                omega_i = omega.imag

                # The Fortran code has a condition to only write if omega_i is zero and r_pt is less than 0.99
                if omega_i == 0.0 and r_pt_val < 0.99:
                    xnrm = np.sqrt(phi_norm**2 + psi_norm**2)
                    output_lines.append(f"{r_pt_val:15.7e} {omega_r:15.7e} {m_emax:4d} {n_emax:4d} {phi_norm/xnrm:15.7e} {psi_norm/xnrm:15.7e}\n")


        if isym_pos == 1:
            if temp_lambdas:
                lam_min = min(temp_lambdas)
                lam_max = max(temp_lambdas)

        cond_no = lam_max / lam_min if lam_min != 0 else 0
        cond_no_lines.append(f"{r_pt:15.7e} {cond_no:15.7e}\n")


    # Write the output files
    with open(alfven_post_path, 'w') as f:
        f.write(f"{len(output_lines):10d}\n")
        f.writelines(output_lines)

    with open(cond_no_path, 'w') as f:
        f.writelines(cond_no_lines)

    print(f"Post-processing complete. Output written to {alfven_post_path}")
