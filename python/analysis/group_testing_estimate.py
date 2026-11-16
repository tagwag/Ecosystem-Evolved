"""Estimate how many corridor tests GROUP TESTING needs to classify every neuron combination up to size k,
versus testing each combination once (brute force). Pure arithmetic + a Monte Carlo check; no worm simulation.

Model (assumption): removing more neurons never rescues navigation (monotone). A combination breaks navigation iff
it contains a 'minimal breaking set'. q[j] = number of minimal breaking sets of size j (unknown; 3 scenarios).
Already-broken single neurons are removed from the pool first (they are known from the singles phase).

Stage 1 (clearing): random tests that remove m neurons at once. A test PASSES if it contains no breaking set; a
passing test clears every combination inside it. Need every clean k-combination inside >= R passing tests (R = 2
guards against a broken set passing by luck). Per test, a given clean k-set is inside with p_in = C(n-k,m-k)/C(n,m),
and the test passes with ~P_pass = exp(-sum_j q_j * C(n-j,m-j)/C(n,m)). Choose m to minimise tests.
Stage 2 (finding the breaking sets): each minimal breaking set of size j is pinned down from a failing test by
adaptive halving, ~ j*log2(m) + j tests, x3 for repeats against noise.
"""
import math
from math import comb, lgamma, exp, log

def lc(n, k):
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) if 0 <= k <= n else -math.inf

def p_in(n, m, k):
    return exp(lc(n - k, m - k) - lc(n, m)) if m >= k else 0.0

def tests_needed(n, k, q, R=2, target=0.1):
    best = None
    for m in range(k, n + 1):
        pp = exp(-sum(qj * p_in(n, m, j) for j, qj in q.items()))
        c = p_in(n, m, k) * pp
        if c <= 0:
            continue
        # Poisson coverage: expected clean k-sets covered < R times must be < target
        N = exp(lc(n, k))
        lo, hi = 0.0, 1e12
        for _ in range(200):                      # bisection on lambda
            lam = (lo + hi) / 2
            tail = sum(exp(-lam) * lam ** r / math.factorial(r) for r in range(R))
            if N * tail > target: lo = lam
            else: hi = lam
        T = hi / c
        dec = sum(qj * (j * math.log2(max(m, 2)) + j) * 3 for j, qj in q.items() if j <= k)
        tot = T + dec
        if best is None or tot < best[0]:
            best = (tot, m, T, dec, pp)
    return best

SCEN = {
    'few':    {2: 20,  3: 100,  4: 500,   5: 2_000,   6: 8_000,   7: 30_000},
    'medium': {2: 200, 3: 1_000, 4: 5_000, 5: 20_000,  6: 80_000,  7: 300_000},
    'many':   {2: 2_000, 3: 10_000, 4: 50_000, 5: 200_000, 6: 800_000, 7: 3_000_000},
}
RATES = (1_000, 2_500)          # corridor tests per second on the RTX 3080 with 4 brains (estimate, see notes)

def fmt(s):
    for u, d in (('years', 3.156e7), ('days', 86400), ('h', 3600), ('min', 60)):
        if s >= d: return f'{s / d:.1f} {u}'
    return f'{s:.0f} s'

if __name__ == '__main__':
    for n in (200, 300):
        print(f'\n=== {n} neurons in the pool ===')
        for k in (3, 4, 5, 6, 7):
            bf = comb(n, k)
            print(f'k={k}: brute force {bf:.3g} tests = {fmt(bf / RATES[1])} .. {fmt(bf / RATES[0])}')
            for name, q in SCEN.items():
                qk = {j: v for j, v in q.items() if j <= k}
                tot, m, T, dec, pp = tests_needed(n, k, qk)
                print(f'   {name:6s}: {tot:.3g} tests (best m={m}, pass rate {pp:.2f}, clearing {T:.3g}, finding {dec:.3g})'
                      f' = {fmt(tot / RATES[1])} .. {fmt(tot / RATES[0])}   ({bf / tot:,.0f}x fewer than brute force)')
