"""
Point d'entree unique pour charger les transactions brutes en DataFrame
propre et correctement type, en s'appuyant sur le mapping reconstruit par
schema_audit.py (configs/schema_map.yaml) plutot que sur l'ordre naif des
colonnes du cahier des charges.

Gere :
- le parsing tolerant du nombre de champs variable par ligne (26 a 30,
  voir configs/schema_map.yaml) -- seules les 26 positions "core" (0-25),
  presentes sur 100% des lignes, sont conservees ; les champs surnumeraires
  (quasi-integralement vides) sont ignores.
- la reconstruction des dates avec fraction sub-seconde (fusion des paires
  DATE + fraction en un seul datetime64[ns])
- le typage explicite (montants en float64, codes en category)
- la mise en quarantaine des lignes a date manifestement aberrante (63
  lignes datees de 2003 identifiees lors de l'audit -- cf. schema_map.yaml)

Usage :
    python -m bamis_fraud.ingestion.loader --input data/raw/DATASET_ESP-2026.csv
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

CORE_POSITIONS = 26  # positions 0-25, presentes sur 100% des lignes (voir schema_map.yaml)

# annee plancher plausible pour une transaction BAMIS -- le service a demarre
# courant 2022 d'apres l'audit (premiere annee avec un volume significatif).
# Tout ce qui est anterieur est une anomalie de date source, pas une vraie
# transaction historique.
MIN_PLAUSIBLE_YEAR = 2020


def load_schema_map(path: str | Path = "configs/schema_map.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _column_names_from_schema_map(schema_map: dict) -> list[str]:
    columns = schema_map["columns"]
    names = []
    for pos in range(CORE_POSITIONS):
        entry = columns.get(pos) or columns.get(str(pos))
        names.append(entry["name"] if entry else f"col_{pos}")
    return names


def read_raw_rows(
    csv_path: str | Path, max_rows: Optional[int] = None
) -> tuple[list[str], list[list[str]]]:
    """Lecture tolerante du CSV brut : ne conserve que les CORE_POSITIONS
    premiers champs de chaque ligne, quel que soit le nombre total de champs
    reellement present (26 a 30, cf. schema_map.yaml). Plus robuste qu'un
    pd.read_csv standard face a des lignes de longueur variable."""
    rows: list[list[str]] = []
    with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader):
            if len(row) < CORE_POSITIONS:
                # ligne tronquee de maniere inattendue -- on la complete avec
                # des vides plutot que de planter, mais elle sera detectable
                # via validators.py (taux de vide anormal)
                row = row + [""] * (CORE_POSITIONS - len(row))
            rows.append(row[:CORE_POSITIONS])
            if max_rows is not None and i + 1 >= max_rows:
                break
    return header, rows


def merge_datetime_fraction(date_part: pd.Series, fraction_ns: pd.Series) -> pd.Series:
    """Fusionne une paire (date_part 'DD/MM/YY HH:MM:SS', fraction_ns) en un
    seul datetime64[ns]. C'est le correctif direct du probleme identifie en
    section 0 de ARCHITECTURE.md (virgule non protegee dans le CSV source)."""
    base = pd.to_datetime(date_part, format="%d/%m/%y %H:%M:%S", errors="coerce")
    frac = pd.to_numeric(fraction_ns, errors="coerce").fillna(0).astype("int64")
    return base + pd.to_timedelta(frac, unit="ns")


def cast_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Applique le typage explicite : fusion des 3 paires date+fraction,
    montants en float64, colonnes categorielles a faible cardinalite en
    category. Ne devine rien sur les colonnes encore a confidence 'low'
    dans schema_map.yaml -- elles restent en string brute."""
    df = df.copy()

    df["TRANSACTION_DATE"] = merge_datetime_fraction(
        df["TRANSACTION_DATE__date_part"], df["TRANSACTION_DATE__fraction_ns"]
    )
    df["REQUEST_DATE"] = merge_datetime_fraction(
        df["REQUEST_DATE__date_part"], df["REQUEST_DATE__fraction_ns"]
    )
    df["RESPONSE_DATE"] = merge_datetime_fraction(
        df["RESPONSE_DATE__date_part"], df["RESPONSE_DATE__fraction_ns"]
    )
    df = df.drop(
        columns=[
            "TRANSACTION_DATE__date_part",
            "TRANSACTION_DATE__fraction_ns",
            "REQUEST_DATE__date_part",
            "REQUEST_DATE__fraction_ns",
            "RESPONSE_DATE__date_part",
            "RESPONSE_DATE__fraction_ns",
        ]
    )

    df["TRANSACTION_CODE"] = pd.to_numeric(df["TRANSACTION_CODE"], errors="coerce").astype("Int64")
    df["TRANSACTION_AMOUNT"] = pd.to_numeric(df["TRANSACTION_AMOUNT"], errors="coerce")
    df["TRANSACTION_FEES"] = pd.to_numeric(df["TRANSACTION_FEES"], errors="coerce")

    for col in ["SERVICE_CODE", "TRANSACTION_STATUS"]:
        df[col] = df[col].astype("category")

    return df


def quarantine_invalid_dates(
    df: pd.DataFrame, min_year: int = MIN_PLAUSIBLE_YEAR
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Isole les lignes dont TRANSACTION_DATE est anterieure a min_year (ex.
    les 63 lignes datees de 2003 identifiees lors de l'audit complet -- cf.
    schema_map.yaml, date_range_observed). Une seule ligne mal datee dans une
    fenetre expanding suffit a fausser tout l'historique 'ancien' d'un
    client -- ces lignes ne doivent JAMAIS entrer dans le feature engineering
    sans traitement explicite."""
    is_valid = df["TRANSACTION_DATE"].dt.year >= min_year
    return df.loc[is_valid].copy(), df.loc[~is_valid].copy()


def load_transactions(
    csv_path: str | Path,
    schema_map_path: str | Path = "configs/schema_map.yaml",
    max_rows: Optional[int] = None,
) -> pd.DataFrame:
    schema_map = load_schema_map(schema_map_path)
    names = _column_names_from_schema_map(schema_map)
    _, rows = read_raw_rows(csv_path, max_rows=max_rows)
    df = pd.DataFrame(rows, columns=names)
    df = cast_dtypes(df)
    return df


def main() -> None:
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--schema-map", default="configs/schema_map.yaml")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--output", default="data/interim/transactions_raw_typed.parquet")
    parser.add_argument(
        "--quarantine-output", default="data/interim/transactions_quarantined_dates.parquet"
    )
    args = parser.parse_args()

    t0 = time.time()
    df = load_transactions(args.input, args.schema_map, max_rows=args.max_rows)
    print(f"Charge {len(df):,} lignes en {time.time() - t0:.1f}s")

    clean, quarantined = quarantine_invalid_dates(df)
    print(f"  dont {len(quarantined)} lignes mises en quarantaine (date < {MIN_PLAUSIBLE_YEAR})")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(out_path, index=False)
    print(f"Ecrit {len(clean):,} lignes propres dans {out_path}")

    if len(quarantined) > 0:
        q_path = Path(args.quarantine_output)
        q_path.parent.mkdir(parents=True, exist_ok=True)
        quarantined.to_parquet(q_path, index=False)
        print(f"Ecrit {len(quarantined)} lignes en quarantaine dans {q_path}")

    print("\nApercu :")
    print(clean.dtypes)
    print("\nPlage de dates (donnees propres) :", clean["TRANSACTION_DATE"].min(), "->", clean["TRANSACTION_DATE"].max())
    print("Montant : min", clean["TRANSACTION_AMOUNT"].min(), "max", clean["TRANSACTION_AMOUNT"].max())


if __name__ == "__main__":
    main()
