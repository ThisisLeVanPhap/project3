# Docker local demo

This Docker setup is intentionally local-demo oriented and keeps the current architecture intact:

- `postgres` runs the application database
- `app` runs the Spring Boot service
- inside `app`, Spring still spawns tenant-scoped Python model server processes from the bundled `chatbot/` code when chat traffic arrives
- `chatbot-api` is optional and is only for direct FastAPI smoke-testing or eval work; it is not the default backend runtime path

## Prerequisites

- Docker Desktop with Compose support
- enough disk space for Python dependencies and model cache downloads

## Start the default demo stack

From the repo root:

```bash
docker compose up --build
```

Detached mode:

```bash
docker compose up --build -d
```

This starts:

- PostgreSQL on `localhost:5432`
- Spring Boot on `localhost:8080`

## Stop the stack

```bash
docker compose down
```

Remove containers plus database volume:

```bash
docker compose down -v
```

## Optional standalone chatbot API

If you want the FastAPI chatbot service available directly on `localhost:8000` for manual checks:

```bash
docker compose --profile chatbot-api up --build
```

## Environment assumptions

Default ports:

- app: `8080`
- postgres: `5432`
- standalone chatbot API: `8000`
- tenant-scoped spawned chatbot processes inside `app`: `8101-8199`

Main env vars used by Compose:

- `POSTGRES_DB` default `global_admin`
- `POSTGRES_USER` default `postgres`
- `POSTGRES_PASSWORD` default `admin`
- `APP_PORT` default `8080`
- `BASE_MODEL` default `TinyLlama/TinyLlama-1.1B-Chat-v1.0` for a more practical CPU local demo warmup
- `MESSENGER_VERIFY_TOKEN` default `woodchat_secret`
- `LLM_PORT_START` default `8101`
- `LLM_PORT_END` default `8199`
- `LLM_STARTUP_TIMEOUT_MS` default `600000` for slower first model warmup in Docker

Optional standalone chatbot env vars:

- `CHATBOT_KB_DIR` default `/app/kb/article`
- `CHATBOT_BASE_MODEL`
- `CHATBOT_LORA_ADAPTER`
- `CHATBOT_TOKENIZER_PATH`

## KB and model asset notes

The Compose setup mounts these host folders into containers so local content changes do not require an image rebuild:

- `./chatbot/kb`
- `./chatbot/adapters`
- `./chatbot/out`
- `./chatbot/logs`

Important tenant note:

- the default demo path preserves the current behavior where Spring reads each tenant's `kb_dir` from Postgres and injects it into the spawned Python process
- for the Dockerized `app` container, tenant `kb_dir` values in the database should point to container-visible paths such as `/opt/app/chatbot/kb/article` or `/opt/app/chatbot/kb/castlery`
- if your database still contains host-only Windows paths like `F:\...`, update those tenant rows for Docker use
- the seeded `demo_tenant` row is initialized by Flyway with the Docker-visible default `/opt/app/chatbot/kb/article` when `kb_dir` is empty, so the local demo no longer needs a manual SQL update

## Expected run flow

1. Start Compose with `docker compose up --build`
2. Wait for Postgres healthcheck and Spring startup
3. Open [http://localhost:8080/admin](http://localhost:8080/admin)
4. Create tenant/chatbot/channel bindings as usual, or reuse the seeded `demo_tenant`
5. Send a web, Messenger, or Telegram message
6. Spring launches the tenant-specific Python model server on first use and continues using the existing chat, buyer-flow, purchase-request, and channel continuity logic
7. Expect the first chat request to take several minutes on a cold model download; later requests reuse the warm tenant process

## Verified local-demo note

The Docker demo stack is configured to default to `TinyLlama/TinyLlama-1.1B-Chat-v1.0` inside containers because the larger Qwen default used in code was not practical to warm up on CPU in a repeatable local Docker demo.

If you want to use a different model in Docker, override `BASE_MODEL` for the `app` service or `CHATBOT_BASE_MODEL` for the optional standalone chatbot container.

## Limitations

- I did not convert the backend to call the standalone `chatbot-api` container by default, because that would weaken the current tenant-specific KB-per-process behavior
- first model warmup can still take time, especially when downloading model artifacts into the shared Hugging Face cache volume
