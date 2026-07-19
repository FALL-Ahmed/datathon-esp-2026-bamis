"""
Verifie qu'une feature "historique client" calculee incorrectement (avec
une fenetre incluant des transactions futures) est bien detectee et
rejetee par validation/leakage_checks.py -- test de non-regression sur le
piege n1 du cahier des charges.
"""
from __future__ import annotations

import pandas as pd
import pytest

from bamis_fraud.validation.leakage_checks import (
    LeakageError,
    check_embargo_respected,
    check_no_date_overlap,
    check_no_duplicate_transaction_code,
    run_all_checks,
)


def _df():
    return pd.DataFrame({
        "TRANSACTION_CODE": [1, 2, 3, 4, 5, 6],
        "TRANSACTION_DATE": pd.to_datetime([
            "2026-01-01", "2026-01-02", "2026-01-03",
            "2026-01-10", "2026-01-11", "2026-01-12",
        ]),
    })


def test_clean_chronological_split_passes():
    df = _df()
    train_idx, valid_idx = [0, 1, 2], [3, 4, 5]

    check_no_date_overlap(df, train_idx, valid_idx)
    check_embargo_respected(df, train_idx, valid_idx, embargo="1d")
    check_no_duplicate_transaction_code(df, train_idx, valid_idx)


def test_future_data_leaked_into_train_is_rejected():
    """Le piege n1 : une transaction de validation (donc future) glissee
    par erreur dans le train doit faire echouer le controle de
    chevauchement temporel, pas passer silencieusement."""
    df = _df()
    # index 4 (2026-01-11, normalement validation) infiltre dans le train
    train_idx, valid_idx = [0, 1, 2, 4], [3, 5]

    with pytest.raises(LeakageError):
        check_no_date_overlap(df, train_idx, valid_idx)


def test_embargo_too_short_is_rejected():
    df = _df()
    train_idx, valid_idx = [0, 1, 2], [3, 4, 5]

    # ecart reel train/valid = 2026-01-03 -> 2026-01-10 = 7 jours, donc un
    # embargo exige de 10 jours doit echouer
    with pytest.raises(LeakageError):
        check_embargo_respected(df, train_idx, valid_idx, embargo="10d")


def test_duplicate_transaction_code_across_train_and_valid_is_rejected():
    df = _df()
    df.loc[3, "TRANSACTION_CODE"] = 1  # doublon avec l'index 0 (train)
    train_idx, valid_idx = [0, 1, 2], [3, 4, 5]

    with pytest.raises(LeakageError):
        check_no_duplicate_transaction_code(df, train_idx, valid_idx)


def test_run_all_checks_reports_pass_for_valid_folds():
    df = _df()
    folds = [([0, 1, 2], [3, 4, 5])]

    report = run_all_checks(df, folds, embargo="1d")

    assert report["status"] == "PASS"
    assert report["fold_1"] == "PASS"
