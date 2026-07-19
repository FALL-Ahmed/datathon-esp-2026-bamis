"""
Verifie que ingestion/loader.py produit le bon nombre de colonnes et le bon
typage a partir d'un extrait du CSV brut (fixture de quelques lignes),
et surtout que les dates avec fraction sub-seconde sont correctement
fusionnees (cf. schema_audit.py) plutot que de decaler les colonnes
suivantes.
"""
from __future__ import annotations

import pandas as pd

from bamis_fraud.ingestion.loader import CORE_POSITIONS, cast_dtypes, merge_datetime_fraction, read_raw_rows


def test_merge_datetime_fraction_preserves_subsecond_precision():
    date_part = pd.Series(["01/03/26 10:15:30", "02/03/26 08:00:00"])
    fraction_ns = pd.Series([123456789, 0])

    merged = merge_datetime_fraction(date_part, fraction_ns)

    assert merged.iloc[0] == pd.Timestamp("2026-03-01 10:15:30.123456789")
    assert merged.iloc[1] == pd.Timestamp("2026-03-02 08:00:00")


def test_merge_datetime_fraction_handles_missing_fraction():
    date_part = pd.Series(["01/03/26 10:15:30"])
    fraction_ns = pd.Series([None])

    merged = merge_datetime_fraction(date_part, fraction_ns)

    assert merged.iloc[0] == pd.Timestamp("2026-03-01 10:15:30")


def test_cast_dtypes_merges_date_pairs_and_types_amounts():
    df = pd.DataFrame({
        "TRANSACTION_DATE__date_part": ["01/03/26 10:15:30"],
        "TRANSACTION_DATE__fraction_ns": [500],
        "REQUEST_DATE__date_part": ["01/03/26 10:15:28"],
        "REQUEST_DATE__fraction_ns": [0],
        "RESPONSE_DATE__date_part": ["01/03/26 10:15:29"],
        "RESPONSE_DATE__fraction_ns": [0],
        "TRANSACTION_CODE": ["1001"],
        "TRANSACTION_AMOUNT": ["50000.5"],
        "TRANSACTION_FEES": ["100"],
        "SERVICE_CODE": ["SERVICE_01"],
        "TRANSACTION_STATUS": ["AUTORISEE"],
    })

    out = cast_dtypes(df)

    # les 6 colonnes brutes date_part/fraction_ns disparaissent, remplacees
    # par une seule colonne datetime64 par champ de date
    for raw_col in ["TRANSACTION_DATE__date_part", "TRANSACTION_DATE__fraction_ns"]:
        assert raw_col not in out.columns
    assert out["TRANSACTION_DATE"].iloc[0] == pd.Timestamp("2026-03-01 10:15:30.000000500")
    assert out["TRANSACTION_AMOUNT"].dtype == "float64"
    assert out["TRANSACTION_AMOUNT"].iloc[0] == 50000.5
    assert str(out["SERVICE_CODE"].dtype) == "category"


def test_read_raw_rows_truncates_to_core_positions_regardless_of_extra_fields(tmp_path):
    """Certaines lignes du CSV source ont jusqu'a 30 champs au lieu de 26
    (voir schema_map.yaml) -- read_raw_rows doit toujours ne garder que les
    CORE_POSITIONS premiers, sans planter ni decaler."""
    header = [f"col_{i}" for i in range(CORE_POSITIONS)]
    short_row = [str(i) for i in range(CORE_POSITIONS)]
    long_row = [str(i) for i in range(CORE_POSITIONS + 4)]  # 4 champs surnumeraires

    csv_path = tmp_path / "raw.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        f.write(",".join(short_row) + "\n")
        f.write(",".join(long_row) + "\n")

    _, rows = read_raw_rows(csv_path)

    assert len(rows) == 2
    assert all(len(r) == CORE_POSITIONS for r in rows)
    # les valeurs des CORE_POSITIONS premieres colonnes ne doivent pas avoir
    # decale a cause des champs surnumeraires de la deuxieme ligne
    assert rows[1][0] == "0"
    assert rows[1][CORE_POSITIONS - 1] == str(CORE_POSITIONS - 1)
