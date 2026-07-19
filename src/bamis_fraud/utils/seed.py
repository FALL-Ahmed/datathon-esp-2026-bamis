"""
Fixation unique et centralisee de toutes les graines aleatoires (numpy,
random) -- exigence explicite du cahier des charges ("fixez vos graines
aleatoires ; le jury doit pouvoir rejouer vos resultats"). A appeler en
tout debut de chaque script d'entrainement.
"""
from __future__ import annotations

import random

import numpy as np


def set_global_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
