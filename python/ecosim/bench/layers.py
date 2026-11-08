"""Worm-brain layers: which kind of information each neuron handles (approximate, after WormAtlas / Cook et al. 2019).

    sensory   senses the outside world (smell, touch, temperature, oxygen, light, ...)
    inter1    first-layer interneurons: "is it getting better or worse" (food search: AIA, AIB, AIY, AIZ, ...)
    inter2    other interneurons: head steering, speed, arousal (RIA, RIB, RIM, RIS, ...)
    command   go forward / go backward decision (AVA, AVB, AVD, AVE, PVC)
    motor     motor neurons (body and head muscles)
    pharynx   the feeding organ's own small nervous system (incl. NSM, the serotonin "on food" neuron)
    muscle    body-wall muscles
Real neurons often do several jobs, so this is a useful simplification, not the truth.
"""
import re

import numpy as np

LAYER_CLASSES = {
    'sensory': 'ADE ADF ADL AFD ALM ALN AQR ASE ASG ASH ASI ASJ ASK AVM AWA AWB AWC BAG CEP FLP IL1 IL2 OLL OLQ '
               'PDE PHA PHB PHC PLM PLN PQR PVD PVM SAA SDQ URB URX URY',
    'inter1': 'AIA AIB AIM AIN AIY AIZ ADA AUA RIP',
    'inter2': 'RIA RIB RIC RIF RIG RIH RIM RIR RIS RMG ALA AVF AVG AVH AVJ AVK AVL DVA DVC PVN PVP PVQ PVR PVT PVW '
              'LUA BDU PDA PDB',
    'command': 'AVA AVB AVD AVE PVC',
    'motor': 'AS DA DB DD VA VB VC VD RMD RME RMF RMH SMB SMD SAB SIA SIB RIV URA HSN DVB',
    'pharynx': 'I1 I2 I3 I4 I5 I6 M1 M2 M3 M4 M5 MC MI NSM',
}
LAYERS = list(LAYER_CLASSES) + ['muscle']
_SUFFIX = re.compile(r'(L|R|DL|DR|VL|VR|D|V|\d+)?')


def neuron_class(name):
    if 'BWM' in name:
        return 'BWM', 'muscle'
    best = None
    for layer, s in LAYER_CLASSES.items():
        for c in s.split():
            if name.startswith(c) and _SUFFIX.fullmatch(name[len(c):]) and (best is None or len(c) > len(best[0])):
                best = (c, layer)
    return best or (name, 'inter2')


def layer_of(conn):
    """Array (N,) of layer names, one per neuron/muscle in the connectome."""
    return np.array([neuron_class(n)[1] for n in conn.names])


def resolve(conn, targets):
    """Neuron indices for a list of targets: neuron names (ASHL), classes (ASH = ASHL+ASHR), or layer names."""
    lay = layer_of(conn)
    cls = np.array([neuron_class(n)[0] for n in conn.names])
    idx = set()
    for t in ([targets] if isinstance(targets, str) else targets):
        if t in LAYERS:
            idx |= set(np.flatnonzero(lay == t).tolist())
        elif t in conn.idx:
            idx.add(conn.idx[t])
        else:
            hit = np.flatnonzero(cls == t)
            if not len(hit):
                raise ValueError(f'unknown neuron, class or layer: {t!r}')
            idx |= set(hit.tolist())
    return sorted(idx)
