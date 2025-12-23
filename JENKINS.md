# Jenkins Setup Notes

## Prerequisites on the cloud server
- Docker Engine installed and running.
- Docker Compose v2 (`docker compose`) available.
- Jenkins agent user added to the `docker` group and re-login applied.
- Port `8000` open in the server firewall/security group.

## Pipeline configuration
1. Create a new Pipeline job and point it at this repo.
2. Set the pipeline script to use the `Jenkinsfile` from SCM.
3. Provide environment variables:
   - `ENV_FILE` (recommended): a Jenkins "Secret file" credential path containing the runtime `.env`.

## Env file rules
- The pipeline requires a real `.env` (secrets are not stored in git).
- If `ENV_FILE` is set, the pipeline copies it to `.env`.
- If neither `ENV_FILE` nor a workspace `.env` exists, the build fails fast.

## Deploy behavior
- `docker compose down` then `docker compose up -d --build`.
- Service binds `0.0.0.0:8000` as defined in `docker-compose.yml`.
