# Logique du CRUD documents :
# - création : hash du fichier, dédoublonnage, mise en file d'ingestion ;
# - modification : suppression des chunks existants puis réindexation ;
# - suppression : document, chunks et fichier stocké.

