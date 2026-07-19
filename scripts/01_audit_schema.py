"""
Etape 1/10 du pipeline -- OBLIGATOIRE avant tout le reste.
Audite la structure reelle du CSV brut (voir bamis_fraud.ingestion.schema_audit)
et ecrit le rapport dans outputs/reports/schema_audit_report.json.

A chaque nouvelle livraison de fichier (notamment un futur fichier de
test), relancer ce script en premier et comparer le rapport a
configs/schema_map.yaml -- si la structure a change, ne pas continuer le
pipeline sans revalider le mapping.

Usage :
    python scripts/01_audit_schema.py --input data/raw/DATASET_ESP-2026.csv
"""
from __future__ import annotations

import argparse

from bamis_fraud.ingestion.schema_audit import main as schema_audit_main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/DATASET_ESP-2026.csv")
    parser.add_argument("--output", default="outputs/reports/schema_audit_report.json")
    args, _ = parser.parse_known_args()

    import sys

    sys.argv = ["schema_audit", "--input", args.input, "--output", args.output]
    schema_audit_main()


if __name__ == "__main__":
    main()
