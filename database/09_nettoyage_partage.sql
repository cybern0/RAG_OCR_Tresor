-- 09 - Nettoyage : retire les tables du partage par fichier, des liens, des demandes d'accès, des favoris et des
-- notifications (fonctions abandonnées : les accès se définissent uniquement par dossier, par l'administrateur).
-- À exécuter UNE FOIS sur une base qui avait déjà reçu les anciens scripts 07 et 08 ; sans effet sur une base neuve.
-- ATTENTION : supprime définitivement les données de ces tables. Les commentaires ne sont pas touchés.
-- Commande : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/09_nettoyage_partage.sql

SET search_path TO rag_sys, public;

BEGIN;

DROP TABLE IF EXISTS document_partage;
DROP TABLE IF EXISTS document_lien_partage;
DROP TABLE IF EXISTS demande_acces;
DROP TABLE IF EXISTS notification_interne;
DROP TABLE IF EXISTS favori;

COMMIT;
