program post_process_cli
      implicit none

      real*8, allocatable :: omega(:,:)
      real*8, allocatable :: alpha_r(:,:), alpha_i(:,:), beta(:,:)
      real*8, allocatable :: omega_r(:,:), omega_i(:,:)
      complex*16, allocatable :: omega2(:,:)
      real*8, allocatable :: temp(:)
      real*8 :: r_pt, lam_min,
     1   lam_max, cond_no, lambda_real, pi, xnrm,
     2   phi_norm, psi_norm
      integer :: nang2, irads, iopt, m_emax, n_emax,
     1    itot, m_emax_psi, n_emax_psi, isym_pos
      integer :: i, ir, istat
      real*8 :: fnorm
      character(len=256) :: arg, line
      integer :: n_args, i_arg
      character(len=30) :: temp_concat_file

      temp_concat_file = "all_alfven_spec.tmp"

      pi = 4.*atan(1.d0)

      ! Concatenate input files passed as command-line arguments
      open(unit=10, file=temp_concat_file, status="replace")
      n_args = command_argument_count()
      do i_arg = 1, n_args
          call get_command_argument(i_arg, arg)
          open(unit=11, file=trim(arg), status="old")
          do
              read(11, '(A)', end=111) line
              write(10, '(A)') trim(line)
          end do
111       continue
          close(unit=11)
      end do
      close(unit=10)

      open(unit=4,file=temp_concat_file,status="old")
      open(unit=7,file="alfven_post",status="unknown")
      open(unit=9,file="cond_no",status="unknown")
      open(unit=8,file="data_post",status="old")
      read(8,*) iopt, nang2, irads, isym_pos
c     if positive-definite matrix option is used in stellgap
c      (subroutine DSYGV) then isym_pos = 1
c     if general matrix option is used in stellgap
c      (subroutine DGEGV) then isym_pos = 0
c      isym_pos = 0
      write(*,*) iopt,nang2,irads, isym_pos
      allocate(omega(irads,nang2),stat=istat)
      allocate(omega2(irads,nang2),stat=istat)
      allocate(omega_r(irads,nang2),stat=istat)
      allocate(omega_i(irads,nang2),stat=istat)
      allocate(beta(irads,nang2),stat=istat)
      allocate(alpha_r(irads,nang2),stat=istat)
      allocate(alpha_i(irads,nang2),stat=istat)
      allocate(temp(nang2),stat=istat)
      itot = irads*nang2
c      fnorm = 1./(2000.*pi)    !converts omega from radians/sec to kHz
      fnorm = 1.      !conversion to kHz is now done in stellgap
      write(7,'(i10)') itot
      lam_min = 1.d+10
      lam_max = -1.d+10
      do ir=1,irads
       do i=1,nang2
        if(isym_pos .eq. 1) then
        read(4,'(2(e15.7,2x),i4,2x,i4)', end=222) r_pt, omega(ir,i),
     1   m_emax, n_emax
       temp(i) = omega(ir,i)**2
       write(7,'(2(e15.7,2x),i4,2x,i4)') r_pt, omega(ir,i)*fnorm,
     1   m_emax, n_emax

       else if(isym_pos .eq. 0) then
	read(4,'(4(e15.7,2x),i4,3(2x,i4),2(2x,e15.7))', end=222)
     1     r_pt, alpha_r(ir,i),
     2     alpha_i(ir,i),beta(ir,i),m_emax, n_emax,
     3     m_emax_psi, n_emax_psi, phi_norm, psi_norm
         xnrm = sqrt(phi_norm**2 + psi_norm**2)
c      alpha_r(ir,i) = abs(alpha_r(ir,i))
      if(beta(ir,i) .gt. 0.d0) then
         lambda_real = alpha_r(ir,i)/beta(ir,i)
         if(lambda_real .gt. 0.) then
           lam_min = min(lam_min,abs(lambda_real))
           lam_max = max(lam_max,abs(lambda_real))
         endif
         lambda_imag = alpha_i(ir,i)/beta(ir,i)
         omega2(ir,i) = dcmplx(lambda_real,lambda_imag)
       else if(beta(ir,i) .le. 0.d0) then
         omega2(ir,i) = 1.e+10
       endif
       omega_r(ir,i) = real(cdsqrt(omega2(ir,i)))
       omega_i(ir,i) = imag(cdsqrt(omega2(ir,i)))
       if(omega_i(ir,i) .eq. 0.d0) then
        if(r_pt .lt. 0.99) then
         write(7,'(2(e15.7,2x),i4,2x,i4,2(2x,e15.7))')
     1     r_pt, omega_r(ir,i)*fnorm,
     2     m_emax, n_emax, phi_norm/xnrm, psi_norm/xnrm
        end if
       end if

       endif

       end do
       if(isym_pos .eq. 1) then
         lam_min = minval(temp)
         lam_max = maxval(temp)
       endif
       if(lam_min .ne. 0.) cond_no = lam_max/lam_min
       write(9,'(e15.7,2x,e15.7)') r_pt, cond_no
c       write(*,*) r_pt, cond_no
       end do
222  continue
     close(unit=4)
     close(unit=7)
     close(unit=8)
     close(unit=9)
     call system("rm " // trim(temp_concat_file))
     end program post_process_cli
c
