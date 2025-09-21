import numpy as np

def read_fourier_dat(job_dir):
    """
    Reads and parses the fourier.dat file.

    Args:
        job_dir (str): The directory where the fourier.dat file is located.

    Returns:
        dict: A dictionary containing the Fourier parameters.
    """
    fourier_params = {}
    path = f"{job_dir}/fourier.dat"
    with open(path, 'r') as f:
        # First line: nfp, ith, izt, mode_family
        line = f.readline()
        parts = line.split()
        fourier_params['nfp'] = int(parts[0])
        fourier_params['ith'] = int(parts[1])
        fourier_params['izt'] = int(parts[2])
        fourier_params['mode_family'] = int(parts[3])

        # Calculated parameters
        fourier_params['mpol'] = int(fourier_params['ith'] * 2 / 5)
        fourier_params['ntor'] = int(fourier_params['izt'] * 2 / 5)
        fourier_params['nznt'] = fourier_params['ith'] * fourier_params['izt']
        fourier_params['mnmx'] = (2 * fourier_params['ntor'] + 1) * fourier_params['mpol'] - fourier_params['ntor']

        # Second line: ntors
        line = f.readline()
        ntors = int(line.strip())
        fourier_params['ntors'] = ntors

        # Subsequent lines: nw, mwl, mwu
        nw = []
        mwl = []
        mwu = []
        for _ in range(ntors):
            line = f.readline()
            parts = line.split()
            nw.append(int(parts[0]))
            mwl.append(int(parts[1]))
            mwu.append(int(parts[2]))

        fourier_params['nw'] = np.array(nw)
        fourier_params['mwl'] = np.array(mwl)
        fourier_params['mwu'] = np.array(mwu)

    return fourier_params


import re

def read_plasma_dat(job_dir):
    """
    Reads and parses the plasma.dat file (Fortran namelist format).

    Args:
        job_dir (str): The directory where the plasma.dat file is located.

    Returns:
        dict: A dictionary containing the plasma parameters.
    """
    plasma_params = {'nion': np.zeros(10)}  # Default for nion
    path = f"{job_dir}/plasma.dat"
    with open(path, 'r') as f:
        # Read the whole file and replace newlines with spaces for easier parsing
        content = f.read().replace('\n', ' ')

        # Find the content within the namelist block
        match = re.search(r'&plasma_input(.*)/', content, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError("Invalid plasma.dat format: namelist block not found.")
        nl_content = match.group(1)

        # Regex to find `key = value` pairs. The value part is tricky.
        # This regex captures a key, and then everything until the next key= or end of string.
        pattern = re.compile(r"(\w+)\s*=\s*(.*?)(?=\s+\w+\s*=|$)", re.IGNORECASE)
        matches = pattern.findall(nl_content)

        for key, value in matches:
            key = key.lower().strip()
            value = value.strip()

            # Clean up trailing comma if it exists
            if value.endswith(','):
                value = value[:-1].strip()

            # Handle different types
            if key == 'nion':
                # Values can be separated by spaces or commas
                nion_values = [float(v) for v in value.replace(',', ' ').split()]
                plasma_params['nion'][:len(nion_values)] = nion_values
            elif value.lower() in ['.true.', 't']:
                plasma_params[key] = True
            elif value.lower() in ['.false.', 'f']:
                plasma_params[key] = False
            elif value.startswith("'") and value.endswith("'"):
                plasma_params[key] = value[1:-1]
            elif value.startswith('"') and value.endswith('"'):
                plasma_params[key] = value[1:-1]
            else:
                try:
                    plasma_params[key] = float(value)
                except ValueError:
                    plasma_params[key] = value  # Keep as string if not float

    return plasma_params


def read_tae_data_boozer(job_dir, irads, ith, izt):
    """
    Reads and parses the tae_data_boozer file.

    Args:
        job_dir (str): The directory where the file is located.
        irads (int): Number of radial surfaces.
        ith (int): Number of poloidal grid points.
        izt (int): Number of toroidal grid points.

    Returns:
        dict: A dictionary containing the parsed data as numpy arrays.
    """
    path = f"{job_dir}/tae_data_boozer"

    # Pre-allocate numpy arrays
    data = {
        'lrfp': False, # Hardcoded as in the Fortran code
        'iotac': np.zeros(irads),
        'phipc': np.zeros(irads),
        'nsurf': np.zeros(irads),
        'bfield': np.zeros((izt, ith, irads)),
        'gsssup': np.zeros((izt, ith, irads)),
        'rjacob': np.zeros((izt, ith, irads)),
        # These are not used in the python version but read in Fortran
        'theta_tae': np.zeros(ith),
        'zeta_tae': np.zeros(izt)
    }

    with open(path, 'r') as f:
        # The first line for 'lrfp' is skipped as it's hardcoded to false in the source.
        # If it were to be read, it would be:
        # lrfp_line = f.readline().strip()
        # data['lrfp'] = lrfp_line.upper() in ['.TRUE.', 'T']

        for ir in range(irads):
            # Read header line for the radial surface
            header_line = f.readline()
            nn = int(header_line[1:4])
            data['nsurf'][ir] = float(nn)
            data['iotac'][ir] = float(header_line[6:21])
            data['phipc'][ir] = float(header_line[23:38])
            # dum1, dum2 are ignored

            # Read the grid data
            for i in range(izt):
                for j in range(ith):
                    # Line 1
                    line1 = f.readline()
                    data['zeta_tae'][i] = float(line1[27:51]) # ZETA_TAE(I)
                    data['theta_tae'][j] = float(line1[1:25]) # THETA_TAE(J)
                    data['bfield'][i, j, ir] = float(line1[53:77])
                    data['gsssup'][i, j, ir] = float(line1[79:103])
                    # dm1 ignored

                    # Line 2
                    line2 = f.readline()
                    data['rjacob'][i, j, ir] = float(line2[105:129])
                    # dm2, dm3, dm4, dm5 ignored

            # Post-processing rjacob
            if not data['lrfp']:
                if data['phipc'][ir] != 0:
                    data['rjacob'][:, :, ir] /= data['phipc'][ir]

    return data


from scipy.interpolate import CubicSpline
from scipy.linalg import eig

# ------------------------------------------------------------------------------
# Fourier and Convolution Helpers (from fourier_lib)
# ------------------------------------------------------------------------------

def ccc(i, j, k):
    """Calculates the 1D integral of cos(i*x)*cos(j*x)*cos(k*x) from 0 to 2*PI."""
    result = 0.0
    izeros = 0
    if i == 0: izeros += 1
    if j == 0: izeros += 1
    if k == 0: izeros += 1

    if izeros != 0:
        if izeros == 3: return 4.0
        if izeros == 2: return 0.0
        if izeros == 1:
            if i == 0 and j*j == k*k: return 2.0
            if j == 0 and i*i == k*k: return 2.0
            if k == 0 and i*i == j*j: return 2.0
        return 0.0
    else: # izeros == 0
        if k == (i - j): result += 1.0
        if k == (i + j): result += 1.0
        if k == (j - i): result += 1.0
        if k == -(i + j): result += 1.0
        return result

def css(k, i, j):
    """Calculates the 1D integral of cos(k*x)*sin(i*x)*sin(j*x) from 0 to 2*PI."""
    if i == 0 or j == 0: return 0.0
    if k == 0:
        return 2.0 if i*i == j*j else 0.0

    result = 0.0
    if k == (i - j): result += 1.0
    if k == (i + j): result -= 1.0
    if k == (j - i): result += 1.0
    if k == -(i + j): result -= 1.0
    return result

def ccc_convolve(m1, n1, m2, n2, meq, neq):
    """Calculates the 2D integral of cos*cos*cos."""
    sm1, sm2, sn1, sn2, smeq, sneq = [np.sign(x) if x != 0 else 1 for x in [m1, m2, n1, n2, meq, neq]]
    m1a, n1a, m2a, n2a, meqa, neqa = abs(m1), abs(n1), abs(m2), abs(n2), abs(meq), abs(neq)

    tht_int1 = ccc(m1a, m2a, meqa)
    zeta_int1 = ccc(n1a, n2a, neqa)
    tht_int2 = css(meqa, m1a, m2a)
    zeta_int2 = css(neqa, n1a, n2a)
    tht_int3 = css(m1a, m2a, meqa)
    zeta_int3 = css(n1a, n2a, neqa)
    tht_int4 = css(m2a, m1a, meqa)
    zeta_int4 = css(n2a, n1a, neqa)

    ans = tht_int1*zeta_int1 \
        + tht_int2*zeta_int2*sm1*sm2*sn1*sn2 \
        + tht_int3*zeta_int3*sm2*smeq*sn2*sneq \
        + tht_int4*zeta_int4*sm1*smeq*sn1*sneq
    return ans

def scs_convolve(m1, n1, m2, n2, meq, neq):
    """Calculates the 2D integral of sin*cos*sin."""
    sm1, sm2, sn1, sn2, smeq, sneq = [np.sign(x) if x != 0 else 1 for x in [m1, m2, n1, n2, meq, neq]]
    m1a, n1a, m2a, n2a, meqa, neqa = abs(m1), abs(n1), abs(m2), abs(n2), abs(meq), abs(neq)

    tht_int1 = css(meqa, m1a, m2a)
    zeta_int1 = ccc(n1a, n2a, neqa)
    tht_int2 = ccc(m1a, m2a, meqa)
    zeta_int2 = css(neqa, n1a, n2a)
    tht_int3 = css(m2a, m1a, meqa)
    zeta_int3 = css(n1a, n2a, neqa)
    tht_int4 = css(m1a, m2a, meqa)
    zeta_int4 = css(n2a, n1a, neqa)

    ans = tht_int1*zeta_int1*sm1*sm2 \
        + tht_int2*zeta_int2*sn1*sn2 \
        - tht_int3*zeta_int3*sm1*smeq*sn2*sneq \
        - tht_int4*zeta_int4*sm2*smeq*sn1*sneq
    return ans

def setup_fourier_space(f_params):
    """Sets up the grid and mode numbers for Fourier transforms."""
    mpol, ntor, nfp = f_params['mpol'], f_params['ntor'], f_params['nfp']
    ith, izt, nznt, mnmx = f_params['ith'], f_params['izt'], f_params['nznt'], f_params['mnmx']

    rm = np.zeros(mnmx)
    rn = np.zeros(mnmx)
    mn = 0
    for m in range(mpol):
        nl = -ntor if m != 0 else 0
        for n in range(nl, ntor + 1):
            rm[mn] = float(m)
            rn[mn] = float(n * nfp)
            mn += 1

    twopi = 2.0 * np.pi
    ztgrd = np.array([twopi * (i / (nfp * izt)) for i in range(izt) for j in range(ith)])
    thtgrd = np.array([twopi * (j / ith) for i in range(izt) for j in range(ith)])

    cos_to_F = np.zeros((nznt, mnmx))
    for i in range(nznt):
        arg = -rn * ztgrd[i] + rm * thtgrd[i]
        dnorm = 2.0 / nznt
        # For DC component (m=0, n=0), dnorm is halved.
        dnorm_factors = np.ones(mnmx)
        dnorm_factors[ (rm == 0) & (rn == 0) ] = 0.5
        cos_to_F[i, :] = np.cos(arg) * dnorm * dnorm_factors

    return {'rm': rm, 'rn': rn, 'cos_to_F': cos_to_F}

def to_fourier(f_grid, cos_to_F):
    """Performs the custom Fourier transform."""
    f_flat = f_grid.flatten(order='F')  # Match Fortran's column-major order
    return np.dot(f_flat, cos_to_F)

def setup_convolution_space(f_params):
    """Sets up the mode numbers for the convolution matrices."""
    ntors, nw, mwl, mwu = f_params['ntors'], f_params['nw'], f_params['mwl'], f_params['mwu']

    im_col, in_col, rm_col, rn_col = [], [], [], []
    for n_idx in range(ntors):
        for m in range(mwl[n_idx], mwu[n_idx] + 1):
            im_col.append(m)
            in_col.append(nw[n_idx])
            rm_col.append(float(m))
            rn_col.append(float(nw[n_idx]))

    return {
        'mn_col': len(im_col),
        'im_col': np.array(im_col), 'in_col': np.array(in_col),
        'rm_col': np.array(rm_col), 'rn_col': np.array(rn_col)
    }

# ------------------------------------------------------------------------------
# Main Stellgap Calculation
# ------------------------------------------------------------------------------

def run_stellgap(job_dir, ir_start, ir_end, irads, ir_fine_scl, outfile_worker):
    """
    Python implementation of the stellgap_worker.f logic.
    """
    # --- 1. Read input data ---
    print("Reading input data...")
    fourier_params = read_fourier_dat(job_dir)
    plasma_params = read_plasma_dat(job_dir)
    boozer_data = read_tae_data_boozer(job_dir, irads, fourier_params['ith'], fourier_params['izt'])

    # Unpack params
    ith, izt = fourier_params['ith'], fourier_params['izt']
    lrfp = boozer_data['lrfp']
    mass_proton = 1.67e-27
    ion_to_proton_mass = plasma_params['ion_to_proton_mass']
    mass_ion = mass_proton * ion_to_proton_mass
    ion_density_0 = plasma_params['ion_density_0']
    twopi = 2.0 * np.pi
    mu0 = 2.0e-7 * twopi
    scale_khz = (1.0e3 * twopi)**2

    # --- 2. Setup coordinates and spaces ---
    print("Setting up coordinate and Fourier spaces...")
    fourier_space = setup_fourier_space(fourier_params)
    conv_space = setup_convolution_space(fourier_params)
    mn_col = conv_space['mn_col']

    # Radial coordinates
    rho_coarse = boozer_data['nsurf'] / boozer_data['nsurf'][-1]
    rho_fine = np.linspace(rho_coarse[0], rho_coarse[-1], ir_fine_scl)

    # --- 3. Interpolate equilibrium data to fine grid ---
    print("Interpolating equilibrium data...")
    bfield_lrg = np.zeros((izt, ith, ir_fine_scl))
    gsssup_lrg = np.zeros((izt, ith, ir_fine_scl))
    rjacob_lrg = np.zeros((izt, ith, ir_fine_scl))

    for i in range(izt):
        for j in range(ith):
            cs = CubicSpline(rho_coarse, boozer_data['bfield'][i, j, :], bc_type='natural')
            bfield_lrg[i, j, :] = cs(rho_fine)
            cs = CubicSpline(rho_coarse, boozer_data['gsssup'][i, j, :], bc_type='natural')
            gsssup_lrg[i, j, :] = cs(rho_fine)
            cs = CubicSpline(rho_coarse, boozer_data['rjacob'][i, j, :], bc_type='natural')
            rjacob_lrg[i, j, :] = cs(rho_fine)

    cs_iota = CubicSpline(rho_coarse, boozer_data['iotac'], bc_type='natural')
    iota_r = cs_iota(rho_fine)

    iotac_inv = 1.0 / boozer_data['iotac']
    cs_iota_inv = CubicSpline(rho_coarse, iotac_inv, bc_type='natural')
    iota_r_inv = cs_iota_inv(rho_fine)

    # --- 4. Main loop over radial surfaces ---
    print(f"Starting main calculation loop for surfaces {ir_start} to {ir_end}...")
    with open(outfile_worker, 'w') as f_out:
        for ir in range(ir_start - 1, ir_end): # Python is 0-indexed
            r_pt = rho_fine[ir]

            # Calculate ion density profile
            ion_profile = int(plasma_params.get('ion_profile', 2))
            if ion_profile == 0:
                if iota_r[0] != 0:
                    ion_density_irr = (iota_r[ir] / iota_r[0])**2
                else:
                    ion_density_irr = 0.0
            elif ion_profile == 1:
                # Polynomial fit: nion(1) + nion(2)*rho + ...
                # In python, this is nion[0] + nion[1]*r_pt + ...
                nion_coeffs = plasma_params['nion']
                ion_density_irr = np.polyval(nion_coeffs[::-1], r_pt)
            elif ion_profile == 2:
                ion_density_irr = 1.0
            elif ion_profile == 3:
                # Power law: (1 - aion*(r_pt**bion))**cion
                aion = plasma_params.get('aion', 0)
                bion = plasma_params.get('bion', 0)
                cion = plasma_params.get('cion', 0)
                ion_density_irr = (1.0 - aion * (r_pt**bion))**cion
            else:
                ion_density_irr = 1.0

            mu0_rho_ion_ir = mu0 * mass_ion * ion_density_0 * ion_density_irr * scale_khz

            # Calculate f1, f3a, f3b, f3c on the grid for this radial surface
            bfield_ir = bfield_lrg[:, :, ir]
            gsssup_ir = gsssup_lrg[:, :, ir]
            rjacob_ir = rjacob_lrg[:, :, ir]

            f1 = (gsssup_ir * rjacob_ir) / (bfield_ir**2)
            if not lrfp:
                f3c = gsssup_ir / (rjacob_ir * bfield_ir**2)
                f3b = iota_r[ir] * f3c
                f3a = iota_r[ir] * f3b
            else:
                f3a = gsssup_ir / (rjacob_ir * bfield_ir**2)
                f3b = f3a * iota_r_inv[ir]
                f3c = f3b * iota_r_inv[ir]

            # Fourier transform the coefficients
            f1_nm = to_fourier(f1, fourier_space['cos_to_F'])
            f3a_nm = to_fourier(f3a, fourier_space['cos_to_F'])
            f3b_nm = to_fourier(f3b, fourier_space['cos_to_F'])
            f3c_nm = to_fourier(f3c, fourier_space['cos_to_F'])

            # Build A and B matrices
            amat = np.zeros((mn_col, mn_col))
            bmat = np.zeros((mn_col, mn_col))

            for i in range(mn_col):
                for j in range(mn_col):
                    ni, mi = conv_space['in_col'][i], conv_space['im_col'][i]
                    nj, mj = conv_space['in_col'][j], conv_space['im_col'][j]

                    # Sum over equilibrium modes
                    for ieq in range(fourier_params['mnmx']):
                        meq, neq = fourier_space['rm'][ieq], fourier_space['rn'][ieq]

                        ccci = ccc_convolve(mi, ni, mj, nj, meq, neq)
                        scsi = scs_convolve(mi, ni, mj, nj, meq, neq)

                        bmat[i,j] -= ccci * f1_nm[ieq] * mu0_rho_ion_ir

                        amat[i,j] -= (scsi * (f3a_nm[ieq] * conv_space['rm_col'][i] * conv_space['rm_col'][j] -
                                             f3b_nm[ieq] * conv_space['rm_col'][j] * conv_space['rn_col'][i] -
                                             f3b_nm[ieq] * conv_space['rn_col'][j] * conv_space['rm_col'][i] +
                                             f3c_nm[ieq] * conv_space['rn_col'][j] * conv_space['rn_col'][i]))

            # Solve the generalized eigenvalue problem: amat * x = w * bmat * x
            try:
                # Use eig for non-symmetric matrices, as in the Fortran code (dggev)
                eigvals, eigvects = eig(amat, bmat)
            except np.linalg.LinAlgError:
                print(f"ERROR: Eigenvalue computation failed for surface {ir+1}.")
                continue

            # Find dominant mode and write output
            for i in range(mn_col):
                eig_max = np.max(np.abs(eigvects[:, i]))
                j_max_index = np.argmax(np.abs(eigvects[:, i]))
                m_emax = conv_space['im_col'][j_max_index]
                n_emax = conv_space['in_col'][j_max_index]

                # Fortran code writes alfr, alfi, beta. eigvals are complex.
                # The Fortran code uses dggev which returns alfr, alfi, beta.
                # The eigenvalue is (alfr + i*alfi)/beta. Here, eigvals are the direct eigenvalues.
                # We write the complex eigenvalue components.
                f_out.write(f"{r_pt:15.7e} {eigvals[i].real:15.7e} {eigvals[i].imag:15.7e} {1.0:15.7e} {m_emax:4d} {n_emax:4d}\n")

    print("Calculation finished.")
