# StudyOS — Database Backup & Disaster Recovery

## 1. Authoritative Databases

- **Production:** MongoDB Atlas (`MONGODB_URI`, database configured by `MONGODB_DB_NAME`).
- **Local Development:** SQLite database file (`data/aetherlearn.db`).

## 2. Backup Procedures

### Manual JSON / Binary Export (Recommended Before Major Releases)

1. Never store backups inside the Git repository. Store backups in an external secure directory outside the workspace.
2. Export MongoDB Atlas collections using `mongodump` or an authenticated read-only Python export script (`db[collection].find({})`) to an encrypted/private local path.
3. Back up local development SQLite safely using SQLite's online backup API (`sqlite3.Connection.backup`) rather than copying `.db` files while WAL writes are active.

### Hosting Limitations (Free Tier)

- **MongoDB Atlas M0 (Free Tier):** Does not include automated continuous cloud snapshots or point-in-time recovery. Manual periodic exports (`mongodump` / JSON snapshot) are required before destructive schema or baseline operations.
- **Vercel Free Serverless Tier (`/tmp`):** `/tmp/brainova_data` is ephemeral per serverless container. User-uploaded binary files (audio uploads, source files, generated mentor images) stored in `/tmp` do not survive container recycling, while structured metadata persists in MongoDB Atlas.

## 3. Restore & Verification Procedure

1. Verify the target environment (`STUDYOS_ENV`, `MONGODB_DB_NAME`, `AETHER_DB_PATH`) before running any restore.
2. Restore MongoDB collections from the verified backup archive using `mongorestore` or batched `ReplaceOne(..., upsert=True)` operations.
3. Increment `_meta_sync.global_seq` in MongoDB (`bump_mongo_global_seq(db)`) so all warm Vercel serverless instances detect the new authoritative state on their next request.
4. Verify restoration integrity by checking:
   - `GET /api/health` returns `HTTP 200 {"status": "ok", "database": "ok"}`.
   - `schema_migrations` contains all expected versions.
   - Sample user login and ownership-protected reads succeed.
