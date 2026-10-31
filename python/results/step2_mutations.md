# Mutation report: runs/step2_worm

Chemical synapses: 4562
- strengthened >2x: 0
- weakened <0.5x (same sign): 34
- silenced (~0): 43
- sign flipped (excit <-> inhib): 7

## Most strengthened synapses
       VA11 -> VB10     (excit) x+1.33
       PHCR -> PHCL     (excit) x+1.38
       AS01 -> DB01     (excit) x+1.63
       VA06 -> VB05     (excit) x+1.29
       DD06 -> dBWMR24  (excit) x+1.62
      SMBDL -> SDQR     (excit) x+1.31
       VA12 -> PHCR     (excit) x+1.64
        PVR -> PVM      (excit) x+1.12
       VA09 -> vBWML17  (excit) x+1.68
       PHAL -> PHAR     (excit) x+1.16
       VD13 -> vBWML23  (inhib) x+1.32
       VC05 -> VC04     (excit) x+1.15
       PVCR -> PDER     (excit) x+1.31
       VD04 -> VB03     (excit) x+1.73
       AVAL -> VA07     (excit) x+1.32

## Most weakened synapses
       AIYL -> AWAL     (excit) x+0.00
        DVB -> PDA      (inhib) x+0.65
       DA07 -> DB06     (excit) x+0.65
       LUAR -> PDB      (excit) x+0.72
       VB08 -> vBWMR20  (excit) x-1.19
       AVHL -> AVFR     (excit) x-1.00
       DA06 -> DB05     (excit) x+0.80
       RIPR -> OLQDR    (excit) x-1.00
       DB06 -> VD08     (excit) x+0.00
       VD08 -> VB07     (excit) x+0.63
       AWCR -> ASIR     (excit) x+0.53
       AINL -> ASIL     (excit) x+0.65
        RIH -> ADFR     (excit) x-1.00
       DB06 -> dBWMR18  (excit) x+0.00
       DB06 -> dBWML18  (excit) x+0.00

## Neurons whose wiring changed most (sum of synapse-strength change)
       VA11  +0.42  (out +0.30, in +0.12)
       PHCR  +0.34  (out +0.27, in +0.07)
       DD06  +0.30  (out +0.21, in +0.09)
      SMBDL  +0.28  (out +0.25, in +0.04)
       VB10  +0.28  (out +0.02, in +0.26)
       VC05  +0.27  (out +0.14, in +0.13)
    vBWML23  +0.22  (out +0.00, in +0.22)
       VB05  +0.21  (out +0.03, in +0.18)
       SDQR  +0.21  (out +0.07, in +0.14)
       VA09  +0.19  (out +0.17, in +0.03)
    ...
       DB06  -2.28  (out -1.93, in -0.35)
       AIYL  -1.14  (out -1.16, in +0.02)
       AWAL  -0.68  (out -0.16, in -0.53)
       DA07  -0.54  (out -0.40, in -0.14)
       AS03  -0.52  (out -0.52, in +0.00)
        DVB  -0.51  (out -0.53, in +0.02)
       LUAR  -0.48  (out -0.43, in -0.05)
    vBWMR20  -0.38  (out +0.00, in -0.38)
       VB07  -0.36  (out -0.13, in -0.23)
        RIH  -0.36  (out -0.31, in -0.06)

## Evolved sensor gains
    ON-sensor gain (ASEL)            x2.85
    OFF-sensor gain (ASER/AWC)       x6.47
    level-sensor gain (AWA)          x4.11

## Motor decoder: which neurons drive speed / reversal / turning (top 6 each)
    speed     AVDR -0.62, AVBR +0.47, AIBR -0.43, AIZR -0.42, AVAR -0.31, RMDVL +0.31
    reversal  AVBR -0.52, SMDDR -0.41, RMDDL +0.41, AVDR -0.39, RIAL -0.39, SMDVR -0.38
    turning   AVDR -0.87, SMDDL +0.75, RMDDR -0.58, AIZR +0.51, SMDVL -0.48, AVBR +0.47