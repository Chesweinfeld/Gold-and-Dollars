"""Gastner-Newman diffusion cartogram.

Gastner, M. T. and Newman, M. E. J., "Diffusion-based method for producing
density-equalizing maps", PNAS 101:20 (2004), 7499-7504.

The density field is diffused to uniformity; every point of the plane is
carried along by the induced velocity field v = -grad(rho)/rho.  Diffusion is
solved spectrally with a cosine transform, which imposes zero-flux (Neumann)
boundaries -- mass stays inside the frame.
"""

import numpy as np
from scipy.fft import dctn, idctn


class DiffusionCartogram:
    def __init__(self, rho0, extent, blur=1.0):
        """rho0: (ny, nx) positive density grid. extent: (x0, x1, y0, y1)."""
        self.ny, self.nx = rho0.shape
        self.x0, self.x1, self.y0, self.y1 = extent
        self.Lx = self.x1 - self.x0
        self.Ly = self.y1 - self.y0
        self.dx = self.Lx / self.nx
        self.dy = self.Ly / self.ny

        rho = np.asarray(rho0, dtype=float)
        if blur:
            rho = _gaussian_blur(rho, blur)
        self.rhohat = dctn(rho, type=2, norm="ortho")

        # Decay rates for the cosine modes: exp(-(kx^2 + ky^2) t).
        kx = np.pi * np.arange(self.nx) / self.Lx
        ky = np.pi * np.arange(self.ny) / self.Ly
        self.decay = ky[:, None] ** 2 + kx[None, :] ** 2

    def density(self, t):
        return idctn(self.rhohat * np.exp(-self.decay * t), type=2, norm="ortho")

    def velocity(self, t):
        """v = -grad(rho)/rho on the grid, evaluated at time t."""
        rho = self.density(t)
        rho = np.maximum(rho, 1e-12 * rho.max())
        gy, gx = np.gradient(rho, self.dy, self.dx)
        return -gx / rho, -gy / rho

    def _interp(self, field, px, py):
        """Bilinear sample of a cell-centred grid at world coordinates."""
        fx = (px - self.x0) / self.dx - 0.5
        fy = (py - self.y0) / self.dy - 0.5
        ix = np.clip(np.floor(fx).astype(int), 0, self.nx - 2)
        iy = np.clip(np.floor(fy).astype(int), 0, self.ny - 2)
        tx = np.clip(fx - ix, 0.0, 1.0)
        ty = np.clip(fy - iy, 0.0, 1.0)
        return (
            field[iy, ix] * (1 - tx) * (1 - ty)
            + field[iy, ix + 1] * tx * (1 - ty)
            + field[iy + 1, ix] * (1 - tx) * ty
            + field[iy + 1, ix + 1] * tx * ty
        )

    def transform(self, pts, n_steps=120, t_end=None, report=None):
        """Carry points from t=0 to t=t_end along the diffusion flow.

        Time steps grow geometrically: the field moves fast at the start and
        the tail is a long slow relaxation, so uniform steps waste effort.
        """
        if t_end is None:
            # Relax until the slowest resolvable mode has decayed away.
            t_end = 4.0 / self.decay[0, 1] if self.decay[0, 1] > 0 else 1.0
        t_start = t_end * 1e-6
        times = np.concatenate([[0.0], np.geomspace(t_start, t_end, n_steps)])

        p = np.array(pts, dtype=float)
        for a, b in zip(times[:-1], times[1:]):
            h = b - a
            vx, vy = self.velocity(a)
            k1x = self._interp(vx, p[:, 0], p[:, 1])
            k1y = self._interp(vy, p[:, 0], p[:, 1])
            mx = p[:, 0] + 0.5 * h * k1x
            my = p[:, 1] + 0.5 * h * k1y
            vx2, vy2 = self.velocity(a + 0.5 * h)
            p[:, 0] += h * self._interp(vx2, mx, my)
            p[:, 1] += h * self._interp(vy2, mx, my)
            np.clip(p[:, 0], self.x0, self.x1, out=p[:, 0])
            np.clip(p[:, 1], self.y0, self.y1, out=p[:, 1])
            if report is not None:
                report(b, p)
        return p

    def uniformity(self, t):
        """Spread of the density field at time t; 0 means fully equalised."""
        rho = self.density(t)
        return float(rho.std() / rho.mean())


def _gaussian_blur(a, sigma):
    from scipy.ndimage import gaussian_filter

    return gaussian_filter(a, sigma, mode="nearest")
