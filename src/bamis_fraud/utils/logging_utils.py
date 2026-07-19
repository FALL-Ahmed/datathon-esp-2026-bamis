"""
ROLE
----
Configuration centralisee du logging (format, niveau, sortie fichier) pour
les scripts du pipeline -- indispensable pour tracer une execution
reproductible sur 1,6M lignes (piege classique : "livrer un code qui ne
fonctionne que sur l'ordinateur d'un membre").

Usage :
    from bamis_fraud.utils.logging_utils import get_logger
    logger = get_logger(__name__)
    logger.info("...")
"""
from __future__ import annotations

import logging
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def get_logger(name: str, log_file: str | Path = "outputs/reports/pipeline_run.log") -> logging.Logger:
    """Logger console + fichier partage entre tous les appels (memes
    handlers reutilises si le logger existe deja -- evite les lignes
    dupliquees quand get_logger est appele plusieurs fois pour le meme nom,
    ce qui arrive typiquement quand un script est reimporte)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
