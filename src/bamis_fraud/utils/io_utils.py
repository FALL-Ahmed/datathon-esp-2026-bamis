"""
ROLE
----
Wrappers de lecture/ecriture standardises (parquet prefere a CSV en
interne pour la performance sur 1,6M lignes ; CSV reserve aux 3 livrables
finaux et aux fichiers de config lisibles par un humain).

FONCTIONS PREVUES
------------------
- read_parquet_safe(path) -> DataFrame
- write_parquet_safe(df, path) -> None
- read_config_yaml(path) -> dict
"""
