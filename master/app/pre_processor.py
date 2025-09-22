import numpy as np

def create_tae_data(boozer_data, itheta=80, izeta=80):
    """
    Generates the content for the tae_data_boozer file.
    This is a Python port of the metric_element_create_ver8.46.f Fortran code.

    Args:
        boozer_data (dict): Data from the boozmn file, read by boozmn_reader.
        itheta (int): Number of poloidal grid points.
        izeta (int): Number of toroidal grid points.

    Returns:
        str: The content of the tae_data_boozer file.
    """
    # --- Extract data from input dict ---
    nsd = boozer_data['ns_b']
    nfp = boozer_data['nfp_b']
    mnboz = boozer_data['mnboz_b']
    iota_bw = boozer_data['iota_b']
    pres_bw = boozer_data['pres_b']
    phip_bw = boozer_data['phip_b']
    bvco_bw = boozer_data['bvco_b']
    buco_bw = boozer_data['buco_b']
    ixm_b = boozer_data['ixm_b']
    ixn_b = boozer_data['ixn_b']
    rmnc_b = boozer_data['rmnc_b']
    zmns_b = boozer_data['zmns_b']
    pmns_b = boozer_data['pmns_b']
    bmnc_b = boozer_data['bmnc_b']

    twopi = 2.0 * np.pi
    mu_0 = 2.0e-7 * twopi
    p5 = 0.5

    # --- Porting the logic from metric_element_create_ver8.46.f ---

    # 1. Half-mesh quantities
    hiota = iota_bw
    hpres = mu_0 * pres_bw
    hphip = -phip_bw
    hjpol = bvco_bw
    hjtor = -buco_bw

    # 2. Migrate to full mesh
    iotaf = np.zeros(nsd + 1)
    presf = np.zeros(nsd + 1)
    jtorf = np.zeros(nsd + 1)
    jpolf = np.zeros(nsd + 1)
    phipf = np.zeros(nsd + 1)

    iotaf[2:nsd] = p5 * (hiota[2:nsd] + hiota[3:nsd+1])
    presf[2:nsd] = p5 * (hpres[2:nsd] + hpres[3:nsd+1])
    jtorf[2:nsd] = p5 * (hjtor[2:nsd] + hjtor[3:nsd+1])
    jpolf[2:nsd] = p5 * (hjpol[2:nsd] + hjpol[3:nsd+1])
    phipf[2:nsd] = p5 * (hphip[2:nsd] + hphip[3:nsd+1])

    # 3. Derivatives on full mesh
    ohs2 = float(nsd - 1)
    iotapf = ohs2 * (hiota[3:nsd+1] - hiota[2:nsd])
    prespf = ohs2 * (hpres[3:nsd+1] - hpres[2:nsd])
    jtorpf = ohs2 * (hjtor[3:nsd+1] - hjtor[2:nsd])
    jpolpf = ohs2 * (hjpol[3:nsd+1] - hjpol[2:nsd])
    phippf = ohs2 * (hphip[3:nsd+1] - hphip[2:nsd])

    # Pad to match Fortran array sizes if necessary
    iotapf = np.pad(iotapf, (2, 0), 'constant')
    prespf = np.pad(prespf, (2, 0), 'constant')
    jtorpf = np.pad(jtorpf, (2, 0), 'constant')
    jpolpf = np.pad(jpolpf, (2, 0), 'constant')
    phippf = np.pad(phippf, (2, 0), 'constant')


    # 4. Fourier coefficients on full mesh and their derivatives
    rmncbf = np.zeros((mnboz, nsd + 1))
    zmnsbf = np.zeros((mnboz, nsd + 1))
    pmnsbf = np.zeros((mnboz, nsd + 1))
    bmncbf = np.zeros((mnboz, nsd + 1))
    rmncpbf = np.zeros((mnboz, nsd + 1))
    zmnspbf = np.zeros((mnboz, nsd + 1))
    pmnspbf = np.zeros((mnboz, nsd + 1))
    bmncpbf = np.zeros((mnboz, nsd + 1))

    for k in range(1, nsd):
        rmncbf[:, k] = p5 * (rmnc_b[:, k+1] + rmnc_b[:, k])
        zmnsbf[:, k] = p5 * (zmns_b[:, k+1] + zmns_b[:, k])
        pmnsbf[:, k] = p5 * (pmns_b[:, k+1] + pmns_b[:, k])
        bmncbf[:, k] = p5 * (bmnc_b[:, k+1] + bmnc_b[:, k])

        rmncpbf[:, k] = ohs2 * (rmnc_b[:, k+1] - rmnc_b[:, k])
        zmnspbf[:, k] = ohs2 * (zmns_b[:, k+1] - zmns_b[:, k])
        pmnspbf[:, k] = ohs2 * (pmns_b[:, k+1] - pmns_b[:, k])
        bmncpbf[:, k] = ohs2 * (bmnc_b[:, k+1] - bmnc_b[:, k])

    # --- Main Loop over Flux Surfaces ---
    output_content = ""

    # Fortran code loops from ks = 2 to nsd-1
    for ks in range(2, nsd):
        phipc = phipf[ks]
        iotac = iotaf[ks]

        # Write header for the radial surface
        # Format: 1x,i3,4(2x,e15.7) -> Fortran's output format
        # We'll just create a simple header line for now.
        # The original Fortran writes more than just these two.
        output_content += f" {ks:3d} {iotac:15.7e} {phipc:15.7e}\n"

        # Grid setup
        thetang_grid, zetang_grid = np.meshgrid(
            twopi * np.arange(itheta) / (itheta - 1),
            twopi * np.arange(izeta) / (nfp * (izeta - 1))
        )

        # Fourier Inversion
        arg = (ixm_b[:, np.newaxis, np.newaxis] * thetang_grid[np.newaxis, :, :] -
               ixn_b[:, np.newaxis, np.newaxis] * zetang_grid[np.newaxis, :, :])

        cos_arg = np.cos(arg)
        sin_arg = np.sin(arg)

        bfield = np.sum(bmncbf[:, ks, np.newaxis, np.newaxis] * cos_arg, axis=0)
        rboo = np.sum(rmncbf[:, ks, np.newaxis, np.newaxis] * cos_arg, axis=0)
        zboo = np.sum(zmnsbf[:, ks, np.newaxis, np.newaxis] * sin_arg, axis=0)

        rth = -np.sum(rmncbf[:, ks, np.newaxis, np.newaxis] * ixm_b[:, np.newaxis, np.newaxis] * sin_arg, axis=0)
        rze = np.sum(rmncbf[:, ks, np.newaxis, np.newaxis] * ixn_b[:, np.newaxis, np.newaxis] * sin_arg, axis=0)
        rs = np.sum(rmncpbf[:, ks, np.newaxis, np.newaxis] * cos_arg, axis=0)
        zth = np.sum(zmnsbf[:, ks, np.newaxis, np.newaxis] * ixm_b[:, np.newaxis, np.newaxis] * cos_arg, axis=0)
        zze = -np.sum(zmnsbf[:, ks, np.newaxis, np.newaxis] * ixn_b[:, np.newaxis, np.newaxis] * cos_arg, axis=0)
        zs = np.sum(zmnspbf[:, ks, np.newaxis, np.newaxis] * sin_arg, axis=0)

        pmns_term = pmnsbf[:, ks, np.newaxis, np.newaxis] * sin_arg
        phiboo = np.sum(pmns_term, axis=0) + zetang_grid

        phith = np.sum(pmnsbf[:, ks, np.newaxis, np.newaxis] * ixm_b[:, np.newaxis, np.newaxis] * cos_arg, axis=0)
        phize = 1.0 - np.sum(pmnsbf[:, ks, np.newaxis, np.newaxis] * ixn_b[:, np.newaxis, np.newaxis] * cos_arg, axis=0)
        phis = np.sum(pmnspbf[:, ks, np.newaxis, np.newaxis] * sin_arg, axis=0)

        # Jacobian and Metric Tensor calculations
        jtorc = jtorf[ks]
        jpolc = jpolf[ks]
        num1 = (iotac * jtorc - jpolc) * phipc
        rjacob = num1 / (bfield**2)
        rboo2 = rboo**2

        gttsub = rth**2 + zth**2 + rboo2 * phith**2
        gzzsub = rze**2 + zze**2 + rboo2 * phize**2
        gtzsub = rth * rze + zth * zze + rboo2 * phith * phize

        gsssub = rs**2 + zs**2 + rboo2 * phis**2
        gstsub = rth * rs + zth * zs + rboo2 * phith * phis
        gszsub = rze * rs + zze * zs + rboo2 * phize * phis

        rjac2i = 1.0 / (rjacob**2)

        gsssup = (gttsub * gzzsub - gtzsub**2) * rjac2i
        gttsup = (gsssub * gzzsub - gszsub**2) * rjac2i
        gzzsup = (gsssub * gttsub - gstsub**2) * rjac2i
        gstsup = (gszsub * gtzsub - gstsub * gzzsub) * rjac2i
        gszsup = (gstsub * gtzsub - gttsub * gszsub) * rjac2i
        gtzsup = (gstsub * gszsub - gsssub * gtzsub) * rjac2i

        # Write data for each grid point
        for kz in range(izeta):
            for kt in range(itheta):
                output_content += (
                    f" {thetang_grid[kz, kt]:24.12e} {zetang_grid[kz, kt]:24.12e} "
                    f" {bfield[kz, kt]:24.12e} {gsssup[kz, kt]:24.12e} "
                    f" {gtzsup[kz, kt]:24.12e}\n"
                )
                output_content += (
                    f" {gttsup[kz, kt]:24.12e} {gzzsup[kz, kt]:24.12e} "
                    f" {gstsup[kz, kt]:24.12e} {gszsup[kz, kt]:24.12e} "
                    f" {rjacob[kz, kt]:24.12e}\n"
                )

    return output_content
