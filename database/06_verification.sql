-- Vérification de la migration 06 : présence des objets de classement, permissions et dimensions.
SET search_path TO rag_sys, public;

SELECT 'table categorie', COUNT(*) FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'categorie';
SELECT 'table type_document', COUNT(*) FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'type_document';
SELECT 'table tag', COUNT(*) FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'tag';
SELECT 'table document_tag', COUNT(*) FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'document_tag';
SELECT 'table regle_classement', COUNT(*) FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'regle_classement';
SELECT 'permission classement.gerer', COUNT(*) FROM permission WHERE code = 'classement.gerer';
SELECT 'permission statistiques.globales', COUNT(*) FROM permission WHERE code = 'statistiques.globales';
SELECT 'vue_document_stats', COUNT(*) FROM information_schema.views WHERE table_schema = 'rag_sys' AND table_name = 'vue_document_stats';
