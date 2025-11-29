# Secret Santa – FastAPI + Vanilla Frontend

Небольшое веб‑приложение «Тайный Санта» с интерфейсом на русском языке. Дайте ссылку друзьям, соберите их пожелания и запустите распределение, когда будете готовы. Каждый участник получает личную ссылку и видит только своего получателя.

## Quickstart

1) Install dependencies (ideally in a venv):
```bash
pip install -r requirements.txt
```

2) Run the API + frontend:
```bash
uvicorn main:app --reload
```

3) Open http://localhost:8000 in your browser. The same `index.html` is served from FastAPI, so you do not need a separate static server.

### Docker

Build and run:
```bash
docker build -t secret-santa .
docker run -it --rm -p 8000:8000 secret-santa
```

Then open http://localhost:8000.

To persist data outside the container, mount a volume and (optionally) point `DATA_FILE` to a directory:
```bash
docker run -it --rm -p 8000:8000 \
  -e DATA_FILE=/data \
  -v $(pwd)/data:/data \
  secret-santa
```

### Docker Compose (Traefik + HTTPS)

Prereqs:
- Откройте 80/443 на сервере и укажите реальный домен.
- Создайте файл `.env` рядом с `docker-compose.yml`, например:
```
DOMAIN=example.com
LE_EMAIL=you@example.com
ADMIN_SECRET=santaadmin
```

Запуск (Traefik запросит сертификат у Let's Encrypt):
```bash
docker compose --env-file .env up -d
```

Сервисы:
- `app` — FastAPI + фронтенд, хранит данные в томе `app_data` (`DATA_FILE=/data/data.json`).
- `traefik` — балансировщик и TLS (HTTP→HTTPS редирект, сертификаты в томе `traefik_letsencrypt`).

## Environment

Optional env var:
- `ADMIN_SECRET`: secret required for organizer endpoints (default: `santaadmin`).
- `DATA_FILE`: путь к JSON‑файлу, где хранятся участники и результаты (по умолчанию `data.json` рядом с `main.py`). Если указать путь к директории, файл `data.json` будет создан внутри нее.

## API (FastAPI)

- `POST /participants` – Body: `{"name": "Jane", "giftPreference": "Books"}`. Adds a participant and returns their id plus a personal link.
- `GET /participants/{participant_id}/preference` – Self-service fetch of the participant's own gift preference by their personal link.
- `PATCH /participants/{participant_id}/preference` – Self-service update of the participant's gift preference by their personal link.
- `GET /participants?secret=...` – Organizer-only list of all participants.
- `PATCH /participants/{participant_id}?secret=...` – Organizer-only update of gift preference (можно очищать поле).
- `DELETE /participants/{participant_id}?secret=...` – Organizer-only removal (доступно до распределения).
- `POST /shuffle?secret=...` – Organizer-only. Shuffles assignments (no self-pairings) and prevents re-shuffling.
- `GET /assignment/{participant_id}` – Returns the single assignment for that participant once shuffled.

## Frontend flows

- **Участник**: Заполнить имя и пожелания, получить личную ссылку вида `/my-assignment/{id}` и сохранить ее.
- **Получатель**: Перейти по личной ссылке после распределения, чтобы увидеть, кому дарить и его пожелания.
- **Организатор**: Добавить `?admin=1` к URL, ввести секрет (по умолчанию `santaadmin`), обновить список участников и нажать «Провести распределение».

## Notes

- Данные сохраняются в `data.json` (или в путь из `DATA_FILE`), поэтому переживают перезапуск контейнера/процесса.
- CORS открыт для удобства локального тестирования.
