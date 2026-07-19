"""
Etape 10/10 -- orchestrateur bout-en-bout. Enchaine les scripts 01 a 09 puis
le bonus seuil (scripts/bonus_recommend_thresholds.py) dans l'ordre,
s'arrete au premier echec (fail fast), journalise la duree de chaque etape
(utils/logging_utils.py) dans outputs/reports/pipeline_run.log.

Usage :
    python scripts/run_all.py --config configs/config.yaml
    python scripts/run_all.py --skip-training   # reutilise models/catboost_v1.cbm existant

C'est la commande unique que le jury doit pouvoir lancer pour tout
regenerer sans intervention manuelle (exigence explicite du cahier des
charges, section 7 : "le jury doit pouvoir rejouer vos resultats").

Chaque etape est lancee comme un sous-processus independant (meme
interpreteur Python que celui utilise pour run_all.py) plutot
qu'importee dans le meme process : ca reproduit exactement ce qu'un membre
du jury ferait a la main ("python scripts/0X_....py"), et evite tout
conflit entre les argparse de scripts differents partageant le meme
sys.argv.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from bamis_fraud.utils.logging_utils import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

# (etiquette, chemin du script, accepte --config ?)
STEPS: list[tuple[str, str, bool]] = [
    ("01 - audit du schema brut", "scripts/01_audit_schema.py", False),
    ("02 - ingestion + nettoyage", "scripts/02_build_dataset.py", False),
    ("03 - feature engineering (volet A)", "scripts/03_build_features.py", True),
    ("04 - graphe (bonus : mules, circuits fermes)", "scripts/04_build_graph_features.py", False),
    ("05 - entrainement du modele", "scripts/05_train_model.py", False),
    ("06 - scoring des transactions (volet A)", "scripts/06_predict_fraud.py", False),
    ("07 - consommation de budget (volet B)", "scripts/07_compute_budget.py", True),
    ("08 - classement des clients (volet C)", "scripts/08_score_customers.py", True),
    ("09 - generation des 3 CSV de soumission", "scripts/09_generate_submission.py", False),
    ("bonus - seuils personnalises par risque", "scripts/bonus_recommend_thresholds.py", False),
]


def run_step(label: str, script: str, pass_config: bool, config_path: str, skip: bool) -> float:
    if skip:
        logger.info("SKIP  %s (--skip-training)", label)
        return 0.0

    cmd = [sys.executable, script]
    if pass_config:
        cmd += ["--config", config_path]

    logger.info("DEBUT %s", label)
    t0 = time.time()
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    elapsed = time.time() - t0

    if result.returncode != 0:
        logger.error("ECHEC %s (code %d, %.1fs) -- arret du pipeline", label, result.returncode, elapsed)
        sys.exit(result.returncode)

    logger.info("OK    %s (%.1fs)", label, elapsed)
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="saute l'etape 05 (entrainement) et reutilise models/catboost_v1.cbm deja present",
    )
    args = parser.parse_args()

    logger.info("=== Pipeline BAMIS Fraud Detection -- %d etapes ===", len(STEPS))
    t_start = time.time()
    durations: dict[str, float] = {}

    for label, script, pass_config in STEPS:
        skip = args.skip_training and script.endswith("05_train_model.py")
        durations[label] = run_step(label, script, pass_config, args.config, skip)

    total = time.time() - t_start
    logger.info("=== Pipeline termine en %.1fs (%.1f min) ===", total, total / 60)
    for label, elapsed in durations.items():
        logger.info("  %-45s %6.1fs", label, elapsed)


if __name__ == "__main__":
    main()
