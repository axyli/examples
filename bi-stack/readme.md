# 🚀 BI Analytics Stack (Postgres + Metabase + Superset + Grafana)

Полностью готовый стек аналитики в Docker Compose — разворачивает базу данных PostgreSQL и три аналитические платформы:
- [Metabase](https://www.metabase.com/)
- [Apache Superset](https://superset.apache.org/)
- [Grafana](https://grafana.com/)

---

## 🧱 Состав проекта

| Сервис | Порт | Назначение |
|---------|------|-------------|
| **Postgres** | `5432` | Хранилище данных |
| **Metabase** | `3000` | Простая BI-платформа, визуализация без кода |
| **Grafana** | `3001` | Дашборды и мониторинг |
| **Superset** | `8088` | Мощный BI-инструмент от Apache |

---

## Запуск проекта

1. Клонируем репозиторий (или копируем docker-compose.yml)

```
version: "3.9"

services:
  postgres:
    image: postgres:14
    container_name: postgres
    restart: always
    environment:
      POSTGRES_USER: bi_user
      POSTGRES_PASSWORD: bi_pass
      POSTGRES_DB: bi_db
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data

  metabase:
    image: metabase/metabase:latest
    container_name: metabase
    restart: always
    ports:
      - "3000:3000"
    environment:
      MB_DB_FILE: /metabase-data/metabase.db
    volumes:
      - ./data/metabase:/metabase-data
    depends_on:
      - postgres

  superset:
    image: apache/superset:latest
    container_name: superset
    restart: always
    ports:
      - "8088:8088"
    environment:
      - SUPERSET_SECRET_KEY=superset_secret
    volumes:
      - ./data/superset:/app/superset_home
    depends_on:
      - postgres

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: always
    ports:
      - "3001:3001"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./data/grafana:/var/lib/grafana
    depends_on:
      - postgres



```


zkvhvhd

