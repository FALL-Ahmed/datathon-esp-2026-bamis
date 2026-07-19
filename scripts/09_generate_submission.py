"""
Etape 9/10. Assemble et exporte les 3 fichiers CSV finaux exactement au
format attendu (submission/export.py), avec validation de format avant
ecriture finale.

Usage :
    python scripts/09_generate_submission.py

Sortie : outputs/submissions/soumission_fraude.csv,
         outputs/submissions/classement_clients.csv,
         outputs/submissions/consommation_enveloppes.csv
"""
from __future__ import annotations

from bamis_fraud.submission.export import main as export_main

if __name__ == "__main__":
    export_main()
