# StudyOS — Database Environment Configuration

> Never commit actual credentials, passwords, JWT secrets, or connection strings to Git or frontend bundles (`VITE_*`).

## 1. Environment Variables (Names Only)

| Variable | Required In | Purpose |
|---|---|---|
| `STUDYOS_ENV` | Optional (`production`, `development`, `test`) | Explicitly selects database authority mode. Defaults to `production` when `VERCEL=1` or `RENDER=1`, `test` for temporary test DBs, and `development` locally. |
| `MONGODB_URI` | **Required in Production** | MongoDB Atlas connection URI used by the backend only. Production fails closed (`503`) if missing. |
| `MONGODB_DB_NAME` | Optional (default: `brainova`) | Target MongoDB database name. Use distinct names if separating staging and production clusters. |
| `AETHER_DB_PATH` | Optional (Local / Test) | Overrides the SQLite file path (defaults to `data/aetherlearn.db` locally, `/tmp/brainova_data/aetherlearn.db` on Vercel). |
| `BRAINOVA_DATA_DIR` | Optional (Local / Test) | Overrides the root directory for SQLite and media subdirectories (`uploads`, `audio`, `videos`, `mentor_images`). |
| `AETHER_JWT_SECRET` | **Recommended in Production** | Signing secret for HS256 session JWTs. Must be set to a fixed high-entropy value in Vercel so sessions survive cold starts. |
| `AETHER_MASTER_KEY` | **Recommended in Production** | 32-byte key (64 hex chars or base64) used for AES-256-GCM encryption of user API keys in `user_preferences`. |
| `BRAINOVA_DISABLE_MONGO_SYNC` | Optional (`1` for offline local/test) | Explicitly disables MongoDB connections for offline local development or isolated testing. |
| `BRAINOVA_MAX_AUDIO_UPLOAD_MB` | Optional (default: `15`) | Maximum allowed size in MB for user-uploaded focus audio files. |

## 2. Environment Setup

- **Local Development:** Leave `STUDYOS_ENV` unset (or set `STUDYOS_ENV=development`). SQLite (`data/aetherlearn.db`) is authoritative.
- **Automated Testing:** Set `AETHER_DB_PATH` to a temporary directory path; tests run completely isolated from both `data/aetherlearn.db` and MongoDB Atlas.
- **Vercel Production:** Configure `MONGODB_URI`, `AETHER_JWT_SECRET`, and `AETHER_MASTER_KEY` in Vercel Project Settings -> Environment Variables.
