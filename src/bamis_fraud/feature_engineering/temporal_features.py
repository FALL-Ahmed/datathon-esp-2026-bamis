"""
ROLE
----
Features purement temporelles : heure de la journee, nuit (F-01), jour de
semaine, regularite d'activite (volet C "Regularite"), et surtout l'ecart
REQUEST_DATE / RESPONSE_DATE signale explicitement par le cahier des
charges comme "signal secondaire d'automatisation" (un ecart tres court et
tres regulier trahit un script plutot qu'un humain).

FEATURES PRODUITES
-------------------
- hour_of_day, is_night, is_weekend
- request_response_latency_ms
- latency_regularity_score (variance de la latence sur les N dernieres
  operations du meme client -> faible variance = suspect)
- activity_regularity_index (volet C valeur)

ENTREES
-------
- data/processed/transactions_clean.parquet

SORTIES
-------
- data/features/temporal_features.parquet
"""
