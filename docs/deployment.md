# Deployment

## Local (Docker Compose)
See README. Services: postgres 16, neo4j 5 community, redis 7, kafka (apache/kafka, single-node KRaft, internal only), backend (:8000), frontend (:3000). All configuration comes from `.env`.

## Notes
- `NEXT_PUBLIC_API_URL` is baked into the frontend at build time and must be the URL the browser uses.
- Set `ENV=production` to enforce a strong `JWT_SECRET` (>=32 chars); put the API behind TLS and set `CORS_ORIGINS` explicitly.
- Run a single backend replica in this phase (migrations on start, in-process consumers and relay). The relay uses SKIP LOCKED, but consumers and background execution are not yet designed for scale-out.
- Kubernetes manifests, managed-service configuration, and secrets management are roadmap items, not provided.
