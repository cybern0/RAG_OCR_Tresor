# Renommages (ancien chemin vers nouveau chemin)

## Dossiers
| Ancien | Nouveau |
|---|---|
| Backend/ | backend/ (code dans backend/app/) |
| DB_vector/ | database/ |
| UI_1/ | frontend/ |
| (nouveau) | ocr_server/, docs/ |

## Backend
| Ancien | Nouveau |
|---|---|
| main.py | app/main.py |
| model/db_metier.py | app/db/metier.py |
| model/db_vect.py | app/db/vecteur.py |
| model/ocr_load.py | app/clients/ocr_paddle.py |
| model/ollama_load.py | app/clients/ollama.py |
| model/prompt_templates.py | app/prompts/templates.py |
| services/parser.py | app/services/ingestion/parser.py |
| services/crud_document.py | app/services/documents/crud.py |
| services/dist_sim_pgvect.py | app/services/retrieval/similarity_search.py |
| services/rag_chain.py | app/services/chat/rag_chain.py |
| services/chatbot_stream.py | app/services/chat/streaming.py |

## Base de données
| Ancien | Nouveau |
|---|---|
| metier.sql | 01_schema_metier.sql |
| doc_vect.sql | 02_schema_documents_vecteurs.sql |

## Frontend (src/components/ remplacé par src/features/)
| Ancien | Nouveau |
|---|---|
| components/login.tsx | features/auth/LoginPage.tsx |
| components/add_user.tsx | features/users/AddUserForm.tsx |
| components/dashboard_documents.tsx | features/documents/DashboardDocuments.tsx |
| components/add_doc.tsx | features/documents/AddDocumentForm.tsx |
| components/update_doc.tsx | features/documents/UpdateDocumentForm.tsx |
| components/chatbot.tsx | features/chat/Chatbot.tsx |
