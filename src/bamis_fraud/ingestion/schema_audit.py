"""
Audite empiriquement la structure REELLE du CSV brut BAMIS avant tout
traitement. Le dictionnaire de donnees du cahier des charges annonce 23
colonnes ; l'audit montre que les lignes reelles contiennent 26 a 28
champs (voir configs/schema_map.yaml pour le mapping reconstruit).

Cause : les champs de date (TRANSACTION_DATE, REQUEST_DATE, RESPONSE_DATE)
exportent une fraction sub-seconde separee par une virgule non protegee
("15:05:44,421000000" = 421 ms), lue par un parseur CSV standard comme une
colonne supplementaire. Ne JAMAIS charger ce fichier avec pd.read_csv
sans passer par ce module au prealable.

Usage :
    python -m bamis_fraud.ingestion.schema_audit --input data/raw/DATASET_ESP-2026.csv
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$")
TEL_RE = re.compile(r"^TEL\d+$")
SERVICE_RE = re.compile(r"^SERVICE_\d+$")
INT_RE = re.compile(r"^\d+$")
FLOAT_RE = re.compile(r"^\d+\.\d+$")

MAX_POSITIONS = 32  # marge de securite au-dela des 26-28 champs observes


@dataclass
class ColumnProfile:
    position: int
    type_counts: Counter = field(default_factory=Counter)
    n_seen: int = 0
    n_nonempty: int = 0
    sample_values: list = field(default_factory=list)
    distinct_nonempty_values: set = field(default_factory=set)
    distinct_capped: bool = False

    def observe(self, value: str) -> None:
        self.n_seen += 1
        if value == "":
            self.type_counts["EMPTY"] += 1
            return
        self.n_nonempty += 1
        if len(self.sample_values) < 6:
            self.sample_values.append(value)
        if not self.distinct_capped:
            self.distinct_nonempty_values.add(value)
            if len(self.distinct_nonempty_values) > 5000:
                # colonne a trop forte cardinalite pour etre un label/categorie -> on arrete de collecter
                self.distinct_capped = True
                self.distinct_nonempty_values.clear()

        if DATE_RE.match(value):
            self.type_counts["DATE"] += 1
        elif TEL_RE.match(value):
            self.type_counts["TEL"] += 1
        elif SERVICE_RE.match(value):
            self.type_counts["SERVICE"] += 1
        elif INT_RE.match(value):
            self.type_counts["INT"] += 1
        elif FLOAT_RE.match(value):
            self.type_counts["FLOAT"] += 1
        else:
            self.type_counts["OTHER"] += 1

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "n_seen": self.n_seen,
            "n_nonempty": self.n_nonempty,
            "pct_nonempty": round(100 * self.n_nonempty / self.n_seen, 4) if self.n_seen else 0.0,
            "type_counts": dict(self.type_counts),
            "sample_values": self.sample_values,
            "n_distinct_nonempty": (
                "capped(>5000)" if self.distinct_capped else len(self.distinct_nonempty_values)
            ),
            "distinct_values_if_low_cardinality": (
                sorted(self.distinct_nonempty_values)
                if (not self.distinct_capped and len(self.distinct_nonempty_values) <= 20)
                else None
            ),
        }


def count_fields_per_row(path: str | Path, max_rows: Optional[int] = None) -> Counter:
    """Compte le nombre de champs (apres split CSV) par ligne. Revele
    immediatement si le fichier a une structure de colonnes homogene ou non."""
    counts: Counter = Counter()
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header declare
        for i, row in enumerate(reader):
            counts[len(row)] += 1
            if max_rows is not None and i + 1 >= max_rows:
                break
    return counts


def profile_column_positions(
    path: str | Path, max_rows: Optional[int] = None
) -> dict[int, ColumnProfile]:
    """Profile chaque position de colonne (motif de type dominant, taux de
    vides, echantillon de valeurs, cardinalite) sur l'ensemble (ou un sous-
    ensemble) du fichier. Sert a reconstruire le mapping colonne->nom metier
    independamment de l'ordre declare par le cahier des charges."""
    profiles: dict[int, ColumnProfile] = {
        i: ColumnProfile(position=i) for i in range(MAX_POSITIONS)
    }
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for i, row in enumerate(reader):
            for pos, value in enumerate(row):
                if pos >= MAX_POSITIONS:
                    break
                profiles[pos].observe(value)
            if max_rows is not None and i + 1 >= max_rows:
                break
    return profiles


def find_binary_flag_candidates(profiles: dict[int, ColumnProfile], max_rate: float = 0.05) -> list[dict]:
    """Cherche parmi les colonnes numeriques de faible cardinalite un
    candidat plausible pour une colonne cible binaire (ex. label de fraude,
    prevalence attendue de l'ordre de 1% d'apres le cahier des charges).
    Ne conclut rien seul -- sert d'indice a verifier manuellement."""
    candidates = []
    for pos, prof in profiles.items():
        if prof.n_nonempty == 0 or prof.distinct_capped:
            continue
        vals = prof.distinct_nonempty_values
        if vals and vals.issubset({"0", "1"}):
            rate_nonempty = prof.n_nonempty / prof.n_seen if prof.n_seen else 0
            candidates.append(
                {
                    "position": pos,
                    "distinct_values": sorted(vals),
                    "pct_nonempty": round(100 * rate_nonempty, 4),
                    "type_counts": dict(prof.type_counts),
                }
            )
    return candidates


def field_count_report(path: str | Path, max_rows: Optional[int] = None) -> dict:
    counts = count_fields_per_row(path, max_rows=max_rows)
    total = sum(counts.values())
    return {
        "n_rows_scanned": total,
        "field_count_distribution": {str(k): v for k, v in sorted(counts.items())},
        "n_declared_header_columns": 23,
    }


def run_full_audit(path: str | Path, max_rows: Optional[int] = None) -> dict:
    """Point d'entree principal : audit complet, retourne un dict pret a
    serialiser en JSON pour outputs/reports/schema_audit_report.json."""
    path = Path(path)
    fc_report = field_count_report(path, max_rows=max_rows)
    profiles = profile_column_positions(path, max_rows=max_rows)
    profile_dicts = {str(pos): prof.to_dict() for pos, prof in profiles.items() if prof.n_seen > 0}
    binary_candidates = find_binary_flag_candidates(profiles)
    return {
        "source_file": str(path),
        "field_count_report": fc_report,
        "column_profiles": profile_dicts,
        "binary_flag_candidates": binary_candidates,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Chemin du CSV brut a auditer")
    parser.add_argument(
        "--max-rows", type=int, default=None, help="Limiter l'audit aux N premieres lignes (debug)"
    )
    parser.add_argument(
        "--output",
        default="outputs/reports/schema_audit_report.json",
        help="Chemin du rapport JSON de sortie",
    )
    args = parser.parse_args()

    report = run_full_audit(args.input, max_rows=args.max_rows)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Lignes analysees : {report['field_count_report']['n_rows_scanned']}")
    print("Distribution du nombre de champs par ligne :")
    for k, v in report["field_count_report"]["field_count_distribution"].items():
        print(f"  {k} champs : {v} lignes")
    if report["binary_flag_candidates"]:
        print("\nColonnes candidates a un flag binaire (0/1) -- a verifier manuellement :")
        for c in report["binary_flag_candidates"]:
            print(f"  position {c['position']} : {c['distinct_values']}, {c['pct_nonempty']}% non-vide")
    else:
        print("\nAucune colonne binaire 0/1 candidate trouvee dans les positions scannees.")
    print(f"\nRapport complet ecrit dans {out_path}")


if __name__ == "__main__":
    main()
