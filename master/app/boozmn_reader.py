import numpy as np
import struct

def read_boozmn_file(file_path):
    """
    Reads a binary boozmn.xxx file (version 1.0) and returns its data.

    Args:
        file_path (str): The path to the boozmn file.

    Returns:
        dict: A dictionary containing the data from the file.
    """
    data = {}
    with open(file_path, 'rb') as f:
        # Helper to read a Fortran unformatted record
        def read_record(fmt):
            record_len_start = struct.unpack('i', f.read(4))[0]

            # For debugging: print(f"Reading record of length {record_len_start} with format '{fmt}'")

            if fmt.endswith('s'): # string format
                num_chars = int(fmt[:-1])
                content = struct.unpack(fmt, f.read(num_chars))[0]
            else:
                content = struct.unpack(fmt, f.read(struct.calcsize(fmt)))

            record_len_end = struct.unpack('i', f.read(4))[0]
            if record_len_start != record_len_end:
                raise IOError("Fortran record length mismatch!")
            return content if len(content) > 1 else content[0]

        # 1. Header Record
        nfp_b, ns_b, aspect_b, rmax_b, rmin_b, betaxis_b = read_record('iidddf')
        data['nfp_b'] = nfp_b
        data['ns_b'] = ns_b
        data['aspect_b'] = aspect_b
        data['rmax_b'] = rmax_b
        data['rmin_b'] = rmin_b
        data['betaxis_b'] = betaxis_b

        # 2. Surface Data Loop
        # Pre-allocate arrays
        data['iota_b'] = np.zeros(ns_b + 1)
        data['pres_b'] = np.zeros(ns_b + 1)
        data['beta_b'] = np.zeros(ns_b + 1)
        data['phip_b'] = np.zeros(ns_b + 1)
        data['phi_b'] = np.zeros(ns_b + 1)
        data['bvco_b'] = np.zeros(ns_b + 1)
        data['buco_b'] = np.zeros(ns_b + 1)

        for nsval in range(2, ns_b + 1):
            (data['iota_b'][nsval], data['pres_b'][nsval], data['beta_b'][nsval],
             data['phip_b'][nsval], data['phi_b'][nsval], data['bvco_b'][nsval],
             data['buco_b'][nsval]) = read_record('fffffff')

        # 3. Mode Counts
        mboz_b, nboz_b, mnboz_b = read_record('iii')
        data['mboz_b'] = mboz_b
        data['nboz_b'] = nboz_b
        data['mnboz_b'] = mnboz_b

        # 4. Version (assuming it's a float or double)
        # It's often a good idea to read unknown fields flexibly
        try:
            data['version'] = read_record('f')
        except struct.error:
            # If it fails, maybe it's not there or has a different format.
            # For this implementation, we assume it's a float.
            print("Warning: Could not read version number. Assuming format is as expected.")


        # Pre-allocate arrays for mode data
        data['ixn_b'] = np.zeros(mnboz_b, dtype=int)
        data['ixm_b'] = np.zeros(mnboz_b, dtype=int)

        # These will be populated surface by surface
        data['bmnc_b'] = np.zeros((mnboz_b, ns_b + 1))
        data['rmnc_b'] = np.zeros((mnboz_b, ns_b + 1))
        data['zmns_b'] = np.zeros((mnboz_b, ns_b + 1))
        data['pmns_b'] = np.zeros((mnboz_b, ns_b + 1))
        # The documentation calls it gmn_b, but the code uses it as gmnc_b
        data['gmnc_b'] = np.zeros((mnboz_b, ns_b + 1))


        # Loop to read the rest of the data
        while True:
            try:
                # Fortran read can end the loop gracefully
                f.seek(f.tell() + 4) # Skip start-of-record marker to check for EOF
                if not f.read(1): # Check if we are at EOF
                    break
                f.seek(f.tell() - 5) # Go back

                # 5. Surface index
                nsval = read_record('i')

                # First time through, read the mode numbers
                if nsval == 2: # Or the first surface number in the file
                    ixn_temp = read_record('i' * mnboz_b)
                    ixm_temp = read_record('i' * mnboz_b)
                    data['ixn_b'] = np.array(ixn_temp)
                    data['ixm_b'] = np.array(ixm_temp)

                # 7. Fourier Coefficients for the surface
                # The file stores them interleaved, so we read all at once
                # The format is mnboz_b * 5 floats/doubles
                # Assuming double precision ('d') based on Fortran code's use of real*8
                record_len = struct.unpack('i', f.read(4))[0]
                num_floats = record_len // 8

                if num_floats != mnboz_b * 5:
                     # Fallback to single precision if double doesn't match
                     f.seek(f.tell() - 4)
                     record_len = struct.unpack('i', f.read(4))[0]
                     num_floats = record_len // 4
                     float_type = 'f'
                else:
                    float_type = 'd'

                f.seek(f.tell() - 4) # Rewind

                all_coeffs = read_record(float_type * (mnboz_b * 5))

                # De-interleave the data
                all_coeffs_np = np.array(all_coeffs).reshape(mnboz_b, 5)

                data['bmnc_b'][:, nsval] = all_coeffs_np[:, 0]
                data['rmnc_b'][:, nsval] = all_coeffs_np[:, 1]
                data['zmns_b'][:, nsval] = all_coeffs_np[:, 2]
                data['pmns_b'][:, nsval] = all_coeffs_np[:, 3]
                data['gmnc_b'][:, nsval] = all_coeffs_np[:, 4]

            except (struct.error, IOError):
                # This can happen at the end of the file
                break

    return data
