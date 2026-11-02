"""GPU version of the Step 3 worm brain (WormBrains2), using PyTorch.

Same equations as worm2.WormBrains2.step, run on the graphics card. The world, eating and
evolution stay on the CPU in NumPy; only the brain math moves. Each tick sends 3 numbers per
worm to the GPU and gets 3 back, which is cheap.

Use:  python -m ecosim.step3 run hunger_scarce 1 --gpu
      python -m ecosim.gpu_check            # checks the GPU and compares CPU vs GPU results

Results match the NumPy brain to float32 rounding, not bit-for-bit, so GPU runs and CPU runs
of the same seed can drift apart over many generations. Compare GPU runs with GPU runs.
"""
import numpy as np
import torch

from .connectome import Connectome, SENSORS
from .worm2 import Layout, Opts, readout_names, N_OUT, WormBrains2


def pick_device(want='cuda'):
    if want == 'cuda' and torch.cuda.is_available():
        return torch.device('cuda')
    return torch.device('cpu')


class WormBrainsTorch:
    chem_scale, gap_scale, inhibition, tau, dt, adapt = (WormBrains2.chem_scale, WormBrains2.gap_scale,
                                                         WormBrains2.inhibition, WormBrains2.tau,
                                                         WormBrains2.dt, WormBrains2.adapt)

    def __init__(self, conn: Connectome, genomes, opts: Opts, device=None):
        dev = self.device = device or pick_device()
        P, N = len(genomes), conn.N
        L = self.L = Layout(conn, opts)
        self.opts = opts
        f32 = dict(dtype=torch.float32, device=dev)
        t = lambda a: torch.as_tensor(np.asarray(a, np.float32), **f32)

        # build the weight matrices on the CPU exactly like the NumPy brain, then copy once
        mult = 1.0 + np.clip(genomes[:, :L.E], -3, 3)
        W = np.zeros((P, N, N), np.float32)
        np.add.at(W, (slice(None), conn.pre, conn.post), (conn.w_norm * mult * self.chem_scale).astype(np.float32))
        self.W = t(W)
        self.G = t(conn.G * self.gap_scale)
        self.G_deg = t(conn.G_deg * self.gap_scale)
        sg = genomes[:, L.sens]
        self.g_on, self.g_off, self.g_lvl = [t(np.exp(np.clip(sg[:, i], -3, 3))) for i in range(3)]
        self.D = t(genomes[:, L.dev].reshape(P, L.R, N_OUT) * 10.0)
        self.Dl = t(genomes[:, L.lvl].reshape(P, L.R, N_OUT) * 3.0)
        self.d_bias = t(genomes[:, L.bias])
        self.rec = t(genomes[:, L.rec] * opts.receptor_scale) if opts.hunger else None
        self.v = torch.zeros((P, N), **f32)
        self.rd = torch.as_tensor(conn.ids(readout_names(conn, opts)), device=dev)
        self.rbar = torch.zeros((P, len(self.rd)), **f32)
        self.s_on, self.s_off, self.s_lvl = (torch.as_tensor(conn.ids(SENSORS[k]), device=dev)
                                             for k in ('on', 'off', 'level'))
        self._t = t

    @torch.no_grad()
    def step(self, smell, d_smell, H):
        t = self._t
        smell, d_smell = t(smell), t(d_smell)
        v = self.v
        r = torch.tanh(torch.clamp(v, min=0))
        I = torch.bmm(r.unsqueeze(1), self.W).squeeze(1)              # same as einsum('pn,pnm->pm')
        I += v @ self.G - self.G_deg * v
        I -= self.inhibition * r.mean(1, keepdim=True)
        I[:, self.s_on] += (self.g_on * torch.clamp(d_smell, min=0))[:, None]
        I[:, self.s_off] += (self.g_off * torch.clamp(-d_smell, min=0))[:, None]
        I[:, self.s_lvl] += (self.g_lvl * smell)[:, None]
        if self.rec is not None:
            I += t(H)[:, None] * self.rec
        self.v = v + self.dt / self.tau * (-v + I)
        r = torch.tanh(torch.clamp(self.v, min=0))
        x = r[:, self.rd]
        dev = x - self.rbar
        self.rbar += self.adapt * (x - self.rbar)
        o = (torch.einsum('pr,pro->po', dev, self.D) + torch.einsum('pr,pro->po', x, self.Dl) + self.d_bias)
        speed_frac = torch.sigmoid(o[:, 0] + 1.0)
        p_reverse = torch.sigmoid(o[:, 1] - 2.0) * 0.3
        turn = torch.tanh(o[:, 2]) * 0.4
        out = torch.stack([p_reverse, speed_frac, turn]).cpu().numpy().astype(np.float64)
        return out[0], out[1], out[2]

    # for hooks that read brain state (readout analysis): NumPy copies on demand
    @property
    def v_np(self):
        return self.v.cpu().numpy()
