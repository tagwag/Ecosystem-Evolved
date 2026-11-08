"""Brain models for the GPU engine (batch3_fast.FastSim). Each one = buffers + load(genomes) + step().

    Worm2Brain   Step 2-3 worm connectome brain (worm2.WormBrains2), + hunger peptide
    GrowBrain    Step 4 growing brain (worm3.GrowBrains): 300 neurons + 95 muscles + up to 50 grown
                 neurons ("slots") + up to 150 added synapses. Every brain has the same size (empty slots
                 are zeros), which is what lets the GPU run them all in one batch.

Shared extras (any brain): starvation alarm into ASH, touch into ALM/AVM (front) and PLM/PVM (back),
worm scent into ASK/ADL, obstacle bumps into the nose-touch neurons FLP/OLQ (Step 18).
step() takes and returns the brain's state as a dict of tensors, so the engine can record it in a CUDA graph.
"""
import numpy as np
import torch

from .connectome import READOUT, SENSORS
from .worm2 import Layout, N_OUT, WormBrains2, readout_names


# Step 19 senses (channel order matters: batch3_fast fills the same order)
SENSE_NEURONS = {
    'temperature': ['AFDL', 'AFDR'],                          # AFD thermosensors (signed: hot +, cold -)
    'light': ['ASJL', 'ASJR'],                                # ASJ (LITE-1) light / UV avoidance
    'toxic': ['PHAL', 'PHAR', 'PHBL', 'PHBR'],                # phasmid chemorepellent sensors
    'predator': ['ASHL', 'ASHR'],                             # ASH polymodal nociceptor: predator scent
    'co2': ['BAGL', 'BAGR'],                                  # BAG CO2 sensors
    'o2': ['URXL', 'URXR', 'AQR', 'PQR'],                     # URX / AQR / PQR oxygen sensors
    'on_food': ['CEPDL', 'CEPDR', 'CEPVL', 'CEPVR', 'ADEL', 'ADER', 'PDEL', 'PDER'],   # dopamine: on a food lawn
}


class _Base:
    chem_scale, gap_scale, inhibition, tau, dt, adapt = (WormBrains2.chem_scale, WormBrains2.gap_scale,
                                                         WormBrains2.inhibition, WormBrains2.tau,
                                                         WormBrains2.dt, WormBrains2.adapt)

    def _common(self, conn, opts, cfg, dev):
        self.dev, self.f = dev, dict(dtype=torch.float32, device=dev)
        self.k_dt = self.dt / self.tau
        self.s_on, self.s_off, self.s_lvl = (torch.as_tensor(conn.ids(SENSORS[k]), device=dev)
                                             for k in ('on', 'off', 'level'))
        self.ash_gain = getattr(opts, 'ash_alarm', 0.0)
        self.ash = torch.as_tensor(conn.ids(['ASHL', 'ASHR']), device=dev) if self.ash_gain > 0 else None
        self.touch_gain = cfg.touch_gain if cfg.predators else 0.0
        self.t_front = torch.as_tensor(conn.ids(['ALML', 'ALMR', 'AVM']), device=dev)
        self.t_back = torch.as_tensor(conn.ids(['PLML', 'PLMR', 'PVM']), device=dev)
        self.pher_gain = cfg.pher_gain if cfg.pheromone else 0.0          # Step 11 worm scent
        self.p_lvl = torch.as_tensor(conn.ids(['ASKL', 'ASKR']), device=dev)
        self.p_up, self.p_down = (torch.as_tensor(conn.ids([n]), device=dev) for n in ('ADLL', 'ADLR'))
        self.nose_gain = cfg.nose_gain if cfg.obstacles else 0.0      # Step 18 obstacles: nose-touch neurons
        self.nose = torch.as_tensor(conn.ids(['FLPL', 'FLPR', 'OLQDL', 'OLQDR', 'OLQVL', 'OLQVR']), device=dev)
        # Step 19 extra senses: one input channel per sense, wired to the neurons real worms use for it
        self.sense_gain = cfg.sense_gain if cfg.senses else 0.0
        X = torch.zeros(len(SENSE_NEURONS), conn.N, **self.f)
        for i, names in enumerate(SENSE_NEURONS.values()):
            X[i, conn.ids(names)] = 1.0
        self.Xmap = X

    def _extras(self, I, alarm, touch, pher=None, nose=None, extra=None):
        if alarm is not None and self.ash is not None:
            I[:, self.ash] += (self.ash_gain * alarm)[:, None]
        if touch is not None and self.touch_gain > 0:
            I[:, self.t_front] += (self.touch_gain * touch[0])[:, None]
            I[:, self.t_back] += (self.touch_gain * touch[1])[:, None]
        if pher is not None and self.pher_gain > 0:          # pher = (level, change)
            g = self.pher_gain
            I[:, self.p_lvl] += (g * pher[0])[:, None]
            I[:, self.p_up] += (g * torch.clamp(pher[1], min=0))[:, None]
            I[:, self.p_down] += (g * torch.clamp(-pher[1], min=0))[:, None]
        if nose is not None and self.nose_gain > 0:          # Step 18: bumped into an obstacle -> nose touch
            I[:, self.nose] += (self.nose_gain * nose)[:, None]
        if extra is not None and self.sense_gain > 0:         # Step 19: (B, channels) sense levels
            I = I + self.sense_gain * (extra @ self.Xmap)
        return I

    @staticmethod
    def _outputs(o):
        return torch.sigmoid(o[:, 1] - 2.0) * 0.3, torch.sigmoid(o[:, 0] + 1.0), torch.tanh(o[:, 2]) * 0.4


class Worm2Brain(_Base):
    """Same equations as worm2.WormBrains2 (and as batch3_fast before the split)."""
    state_names = ('v', 'rbar')

    def __init__(self, conn, opts, cfg, B, dev):
        self._common(conn, opts, cfg, dev)
        f, N, E = self.f, conn.N, conn.n_edges
        L = self.L = Layout(conn, opts)
        self.opts = opts
        self.pre = torch.as_tensor(conn.pre, device=dev)
        M = torch.zeros(E, N, **f)
        M[torch.arange(E, device=dev), torch.as_tensor(conn.post, device=dev)] = 1.0
        self.M = M                                                          # synapse -> target map
        self.w_base = torch.as_tensor(conn.w_norm * self.chem_scale, **f)
        self.G = torch.as_tensor(conn.G * self.gap_scale, **f)
        self.G_deg = torch.as_tensor(conn.G_deg * self.gap_scale, **f)
        self.rd = torch.as_tensor(conn.ids(readout_names(conn, opts)), device=dev)
        z = lambda *s: torch.zeros(*s, **f)
        self.vals, self.g3 = z(B, E), z(B, 3)
        self.D, self.Dl, self.bias = z(B, L.R, N_OUT), z(B, L.R, N_OUT), z(B, N_OUT)
        self.rec = z(B, N) if opts.hunger else None
        self.v, self.rbar = z(B, N), z(B, L.R)

    def load(self, genomes):
        L, opts = self.L, self.opts
        g = torch.as_tensor(genomes, **self.f)
        self.vals.copy_(self.w_base * (1.0 + torch.clamp(g[:, :L.E], -3, 3)))
        self.g3.copy_(torch.exp(torch.clamp(g[:, L.sens], -3, 3)))
        self.D.copy_(g[:, L.dev].reshape(-1, L.R, N_OUT) * 10.0)
        self.Dl.copy_(g[:, L.lvl].reshape(-1, L.R, N_OUT) * 3.0)
        self.bias.copy_(g[:, L.bias])
        if self.rec is not None:
            self.rec.copy_(g[:, L.rec] * opts.receptor_scale)
        self.v.zero_(); self.rbar.zero_()

    def step(self, s, smell, d, H, alarm=None, touch=None, pher=None, nose=None, extra=None):
        v, rbar = s['v'], s['rbar']
        r = torch.tanh(torch.clamp(v, min=0))
        I = (r[:, self.pre] * self.vals) @ self.M                       # chemical synapses (sparse as a matmul)
        I = I + v @ self.G - self.G_deg * v                              # gap junctions
        I = I - self.inhibition * r.mean(1, keepdim=True)
        I[:, self.s_on] += (self.g3[:, 0] * torch.clamp(d, min=0))[:, None]
        I[:, self.s_off] += (self.g3[:, 1] * torch.clamp(-d, min=0))[:, None]
        I[:, self.s_lvl] += (self.g3[:, 2] * smell)[:, None]
        if self.rec is not None:
            I = I + H[:, None] * self.rec
        I = self._extras(I, alarm, touch, pher, nose, extra)
        v = v + self.k_dt * (-v + I)
        r = torch.tanh(torch.clamp(v, min=0))
        x = r[:, self.rd]
        dev = x - rbar
        rbar = rbar + self.adapt * dev
        o = torch.einsum('pr,pro->po', dev, self.D) + torch.einsum('pr,pro->po', x, self.Dl) + self.bias
        return {'v': v, 'rbar': rbar}, self._outputs(o)


class GrowBrain(_Base):
    """Same equations as worm3.GrowBrains (Step 4). Dense per-brain weights (Nt = 445), built on the GPU."""
    state_names = ('v', 'rbar', 'sbar')

    def __init__(self, conn, opts, cfg, B, dev):
        from .worm3 import Layout3
        self._common(conn, opts, cfg, dev)
        f = self.f
        L = self.L = Layout3(conn, opts)
        N, K, Nt = L.N, L.K, L.Nt
        self.N, self.K, self.Nt = N, K, Nt
        self.pre = torch.as_tensor(conn.pre, device=dev)
        self.post = torch.as_tensor(conn.post, device=dev)
        self.w_base = torch.as_tensor(conn.w_norm * self.chem_scale, **f)
        G = torch.zeros(Nt, Nt, **f)
        G[:N, :N] = torch.as_tensor(conn.G * self.gap_scale, **f)
        self.G, self.G_deg = G, G.sum(1)
        self.rd = torch.as_tensor(conn.ids([n for n in READOUT if n in conn.idx]), device=dev)
        self.s_on_np, self.s_off_np, self.s_lvl_np = (conn.ids(SENSORS[k]) for k in ('on', 'off', 'level'))
        z = lambda *s: torch.zeros(*s, **f)
        self.W = z(B, Nt, Nt)
        self.g3 = z(B, 3)
        self.D, self.Dl, self.bias = z(B, L.R, N_OUT), z(B, L.R, N_OUT), z(B, N_OUT)
        self.SD, self.SDl = z(B, K, N_OUT), z(B, K, N_OUT)
        self.m3 = z(B, 3, K)                     # grown copies of sensory neurons also sense (on / off / level)
        self.n_active = z(B)
        self.v, self.rbar, self.sbar = z(B, Nt), z(B, L.R), z(B, K)

    def load(self, genomes):
        L, N, K, Nt, f = self.L, self.N, self.K, self.Nt, self.f
        B = len(genomes)
        g = torch.as_tensor(genomes, **f)
        act = g[:, L.act] > 0.5                                                   # B x K
        W = self.W
        W.zero_()
        W[:, self.pre, self.post] = self.w_base * (1.0 + torch.clamp(g[:, :L.E], -3, 3))   # unique pairs
        W[:, :, N:] += (g[:, L.sin].reshape(B, K, Nt) * act[:, :, None]).transpose(1, 2)   # j -> slot k
        W[:, N:, :] += g[:, L.sout].reshape(B, K, Nt) * act[:, :, None]                    # slot k -> j
        # added synapses: merge duplicates per brain on the CPU (deterministic), then add once
        add = genomes[:, L.add].reshape(B, L.M, 3)
        used = add[:, :, 2] != 0
        if used.any():
            b, m = np.nonzero(used)
            key = b * Nt * Nt + add[b, m, 0].astype(int) * Nt + add[b, m, 1].astype(int)
            uk, inv = np.unique(key, return_inverse=True)
            wsum = np.zeros(len(uk)); np.add.at(wsum, inv, add[b, m, 2])
            Wf = W.view(-1)
            idx = torch.as_tensor(uk, device=self.dev)
            Wf[idx] = Wf[idx] + torch.as_tensor(wsum, **f)
        self.g3.copy_(torch.exp(torch.clamp(g[:, L.sens], -3, 3)))
        self.D.copy_(g[:, L.dev].reshape(B, L.R, N_OUT) * 10.0)
        self.Dl.copy_(g[:, L.lvl].reshape(B, L.R, N_OUT) * 3.0)
        self.SD.copy_(g[:, L.sdev].reshape(B, K, N_OUT) * 10.0 * act[:, :, None])
        self.SDl.copy_(g[:, L.slvl].reshape(B, K, N_OUT) * 3.0 * act[:, :, None])
        self.bias.copy_(g[:, L.bias])
        self.n_active.copy_(N + act.sum(1))
        src = np.where(genomes[:, L.act] > 0.5, genomes[:, L.src].round().astype(int), -1)
        self.m3.copy_(torch.as_tensor(np.stack([np.isin(src, self.s_on_np), np.isin(src, self.s_off_np),
                                                np.isin(src, self.s_lvl_np)], 1), **f))
        self.v.zero_(); self.rbar.zero_(); self.sbar.zero_()

    def step(self, s, smell, d, H, alarm=None, touch=None, pher=None, nose=None, extra=None):
        v, rbar, sbar, N = s['v'], s['rbar'], s['sbar'], self.N
        r = torch.tanh(torch.clamp(v, min=0))
        I = torch.bmm(r.unsqueeze(1), self.W).squeeze(1)
        I = I + v @ self.G - self.G_deg * v
        I = I - self.inhibition * (r.sum(1) / self.n_active)[:, None]
        on = self.g3[:, 0] * torch.clamp(d, min=0)
        off = self.g3[:, 1] * torch.clamp(-d, min=0)
        lvl = self.g3[:, 2] * smell
        I[:, self.s_on] += on[:, None]
        I[:, self.s_off] += off[:, None]
        I[:, self.s_lvl] += lvl[:, None]
        I[:, N:] += self.m3[:, 0] * on[:, None] + self.m3[:, 1] * off[:, None] + self.m3[:, 2] * lvl[:, None]
        I = self._extras(I, alarm, touch, pher, nose, extra)
        v = v + self.k_dt * (-v + I)
        r = torch.tanh(torch.clamp(v, min=0))
        x, xs = r[:, self.rd], r[:, N:]
        dev, devs = x - rbar, xs - sbar
        rbar = rbar + self.adapt * dev
        sbar = sbar + self.adapt * devs
        o = (torch.einsum('pr,pro->po', dev, self.D) + torch.einsum('pr,pro->po', x, self.Dl)
             + torch.einsum('pk,pko->po', devs, self.SD) + torch.einsum('pk,pko->po', xs, self.SDl) + self.bias)
        return {'v': v, 'rbar': rbar, 'sbar': sbar}, self._outputs(o)


def make_brain(conn, opts, cfg, B, dev):
    from .worm3 import Opts3
    if isinstance(opts, Opts3):
        return GrowBrain(conn, opts, cfg, B, dev)
    return Worm2Brain(conn, opts, cfg, B, dev)
