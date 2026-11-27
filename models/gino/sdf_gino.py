"""Gino's body as a signed distance field -> marching cubes -> high-res mesh (.npz).
Blender coords: x forward (nose at +x), y left, z up, feet on z=0. Units match the site."""
import numpy as np, sys
from skimage.measure import marching_cubes

def rotm(rx=0, ry=0, rz=0):
    rx, ry, rz = np.radians([rx, ry, rz])
    X = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Y = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Z = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    return (Z @ Y @ X).astype(np.float32)

def local(p, c, rot):
    q = p - np.asarray(c, np.float32)
    if rot is not None: q = q @ rotm(*rot)          # world -> local (row vectors, R^T applied)
    return q

def ell(p, c, r, rot=None):
    q = local(p, c, rot); r = np.asarray(r, np.float32)
    k0 = np.linalg.norm(q / r, axis=1); k1 = np.linalg.norm(q / (r * r), axis=1)
    return k0 * (k0 - 1) / np.maximum(k1, 1e-6)

def cap(p, a, b, ra, rb):
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32); pa = p - a; ba = b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return np.linalg.norm(pa - h[:, None] * ba, axis=1) - (ra + (rb - ra) * h)

def rbox(p, c, b, r, rot=None):
    q = np.abs(local(p, c, rot)) - (np.asarray(b, np.float32) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0) - r

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1); return b + (a - b) * h - k * h * (1 - h)

def sub(a, b, k):   # carve b out of a
    return -smin(-a, b, k)

def gino(p):
    d = ell(p, (-0.05, 0, 0.80), (0.80, 0.45, 0.43))                 # barrel
    d = smin(d, ell(p, (-0.50, 0, 0.85), (0.47, 0.46, 0.46)), 0.18)   # high round rump
    d = smin(d, ell(p, (0.40, 0, 0.76), (0.36, 0.37, 0.38)), 0.16)    # chest
    d = smin(d, ell(p, (-0.05, 0, 0.55), (0.62, 0.41, 0.28)), 0.17)   # belly
    d = smin(d, cap(p, (0.42, 0, 0.88), (0.76, 0, 1.03), 0.33, 0.27), 0.14)   # thick short neck
    # head: rounded cranium, deep blunt muzzle, heavy cheeks (built 1.1x around the neck joint)
    hc = np.array([0.72, 0, 1.02], np.float32); HS = 1.1; p0 = p; p = hc + (p0 - hc) / HS
    h = ell(p, (0.86, 0, 1.15), (0.30, 0.235, 0.235))
    h = smin(h, ell(p, (0.98, 0, 1.00), (0.30, 0.225, 0.19)), 0.08)            # cheeks / masseters
    h = smin(h, rbox(p, (1.19, 0, 1.03), (0.21, 0.155, 0.185), 0.09, (0, -4, 0)), 0.09)   # deep muzzle block
    h = smin(h, ell(p, (1.13, 0, 0.88), (0.22, 0.125, 0.08)), 0.06)              # lower jaw
    for s in (-1, 1):
        h = smin(h, ell(p, (0.93, s * 0.195, 1.255), (0.075, 0.05, 0.028)), 0.04)            # brow ridge
        h = sub(h, ell(p, (0.955, s * 0.222, 1.205), (0.045, 0.03, 0.04)), 0.012)            # eye socket
        ear = ell(p, (0.73, s * 0.175, 1.33), (0.052, 0.03, 0.052), (s * -12, 0, s * 20))
        ear = sub(ear, ell(p, (0.738, s * 0.197, 1.337), (0.036, 0.018, 0.038), (s * -12, 0, s * 20)), 0.01)
        h = smin(h, ear, 0.025)
        h = sub(h, ell(p, (1.372, s * 0.062, 1.172), (0.012, 0.03, 0.009), (s * 32, -40, 0)), 0.008)   # nostril slits on the top front edge
        h = sub(h, cap(p, (1.395, s * 0.02, 0.93), (1.22, s * 0.13, 0.905), 0.008, 0.005), 0.01)       # mouth line
    h = sub(h, rbox(p, (1.405, 0, 0.98), (0.02, 0.004, 0.05), 0.004), 0.008)                        # split upper lip
    h = h * HS; p = p0
    d = smin(d, h, 0.12)
    # legs: short, mostly hidden under the barrel
    for s in (-1, 1):
        y = s * 0.24
        leg = cap(p, (0.42, y, 0.62), (0.46, y, 0.2), 0.15, 0.1)
        leg = smin(leg, cap(p, (0.46, y, 0.2), (0.48, y, 0.06), 0.092, 0.07), 0.05)
        foot = ell(p, (0.52, y, 0.038), (0.09, 0.075, 0.04))
        for o in (-0.045, -0.015, 0.015, 0.045):
            foot = smin(foot, ell(p, (0.585, y + o * 1.1, 0.026), (0.03, 0.021, 0.026)), 0.012)
        leg = smin(leg, foot, 0.04)
        d = smin(d, leg, 0.09)
        y = s * 0.27
        hind = ell(p, (-0.60, s * 0.29, 0.62), (0.30, 0.16, 0.30))
        hind = smin(hind, cap(p, (-0.62, y, 0.42), (-0.66, y, 0.09), 0.13, 0.08), 0.06)
        foot = ell(p, (-0.6, y, 0.038), (0.14, 0.078, 0.04))
        for o in (-0.04, 0.0, 0.04):
            foot = smin(foot, ell(p, (-0.475, y + o * 1.1, 0.027), (0.034, 0.023, 0.027)), 0.012)
        hind = smin(hind, foot, 0.04)
        d = smin(d, hind, 0.1)
    return d

def build(h=0.008, out='gino_high.npz'):
    lo = np.array([-1.15, -0.62, -0.02], np.float32); hi = np.array([1.52, 0.62, 1.52], np.float32)
    n = np.ceil((hi - lo) / h).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i], dtype=np.float32) * h for i in range(3)]
    vol = np.empty(n, np.float32)
    for i, x in enumerate(xs):            # one x-slab at a time keeps memory small
        Y, Z = np.meshgrid(ys, zs, indexing='ij')
        P = np.stack([np.full(Y.size, x, np.float32), Y.ravel(), Z.ravel()], 1)
        vol[i] = gino(P).reshape(Y.shape)
    verts, faces, normals, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
    verts += lo
    np.savez(out, verts=verts.astype(np.float32), faces=faces.astype(np.int32))
    print('verts', len(verts), 'faces', len(faces))

if __name__ == '__main__':
    build(float(sys.argv[1]) if len(sys.argv) > 1 else 0.008, sys.argv[2] if len(sys.argv) > 2 else 'gino_high.npz')
