"""A tiny evolvable brain for run-and-tumble (chemotaxis).

Inputs  : smell now, smell change since last tick (scaled), energy level, bias
Hidden  : small recurrent layer (gives the cell a short memory)
Outputs : tumble probability, swim-speed fraction

Every agent's brain is a flat vector of weights (its "genome"). All agents are simulated at once
with batched matrix math, so a population of hundreds runs fast.
"""
import numpy as np

N_IN, N_OUT = 4, 2


def genome_size(hidden):
    return N_IN * hidden + hidden * hidden + hidden + hidden * N_OUT + N_OUT


def unpack(genomes, hidden):
    """genomes: (P, G) -> weight tensors with a leading population axis."""
    P = genomes.shape[0]
    i = 0
    def take(n, shape):
        nonlocal i
        w = genomes[:, i:i + n].reshape((P,) + shape); i += n
        return w
    W_in = take(N_IN * hidden, (N_IN, hidden))
    W_rec = take(hidden * hidden, (hidden, hidden))
    b_h = take(hidden, (hidden,))
    W_out = take(hidden * N_OUT, (hidden, N_OUT))
    b_o = take(N_OUT, (N_OUT,))
    return W_in, W_rec, b_h, W_out, b_o


class Brains:
    def __init__(self, genomes, hidden):
        self.hidden = hidden
        self.W_in, self.W_rec, self.b_h, self.W_out, self.b_o = unpack(genomes, hidden)
        self.h = np.zeros((genomes.shape[0], hidden))

    def step(self, x):
        """x: (P, N_IN) -> (tumble_prob, speed_frac), each (P,)."""
        pre = np.einsum('pi,pih->ph', x, self.W_in) + np.einsum('pk,pkh->ph', self.h, self.W_rec) + self.b_h
        self.h = np.tanh(pre)
        out = np.einsum('ph,pho->po', self.h, self.W_out) + self.b_o
        sig = 1.0 / (1.0 + np.exp(-out))
        return sig[:, 0], sig[:, 1]
