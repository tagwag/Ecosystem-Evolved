# Factor catalog — handbook

**What it is:** `catalog.toml` lists every environmental, population and genetic factor that published research says
affects C. elegans fitness or evolution, with **every form** of each (e.g. radiation → UV-A, UV-B, UV-C, X-ray, gamma,
alpha, beta, neutron, proton, heavy ion, radon, chronic vs acute, hotspots, solar events). It is the master list the
config-file experiment system (the "simulation IDE") is built around: any factor here can be named in a config file.

**Status of each factor** tells you whether the simulation can actually do it today:
| status | meaning |
|---|---|
| `implemented` | settable now; `sim_keys` lists the existing settings in `ecosim/config.py` |
| `partial` | a simplified version exists (e.g. temperature = hot/cold spots that cost energy, but no effect on development) |
| `planned` | on the build list |
| `not_modelled` | not in the simulation yet |

Rule for the config system: **a config that sets a factor that isn't implemented must fail with a clear
"not implemented" message.** It must never be silently ignored, or an experiment could claim to test something it didn't.

**Evidence tag** says how strong the biology is:
| tag | meaning |
|---|---|
| `EVO` | shown to drive evolution (lab evolution experiments or wild-population genetics) |
| `EFFECT` | changes fitness, traits or behaviour, but not (yet) shown to drive evolution |
| `CONTESTED` | disputed (e.g. magnetic sense) |
| `UNTESTED` | no C. elegans study found |

## Fields per factor
`category`, `evidence`, `status`, `sim_keys` (if any), `forms` (list), optional `real_range`, `model_as`, `notes`,
and `sources` (numbers → `sources.md`).

## Reading it from Python
```python
import tomllib
cat = tomllib.load(open("python/factors/catalog.toml", "rb"))
todo = [k for k, v in cat.items() if v["status"] != "implemented"]
```

## Caveats
- Built from a broad literature pass on 2026-11-13 (reviews + key papers), not a systematic review. Add factors as
  new papers turn up; keep `sources.md` numbering in sync.
- Radiation is modelled mainly as a **mutation source** (dose → extra mutations), because that is what it does
  biologically; the Chornobyl nematode study found no genome-damage signature in wild worms.
