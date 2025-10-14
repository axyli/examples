## Запуск проекта

### Клонируем репозиторий (или копируем docker-compose.yml)
```
git clone https://github.com/yourusername/bi-stack.git
cd bi-stack 
```

### Создаем папки для данных
``` 
mkdir -p data/postgres data/metabase data/superset data/grafana
```

### Запускаем всё
```
sudo docker compose up -d
```

### Проверяем, что контейнеры запущены:

``` 
sudo docker ps 
```

### Доступ к сервисам

| Сервис	       |URL	| Данные для входа|
|---------------|------|-------------|
| **Metabase**|http://localhost:3000 | создается при первом запуске|
| **Grafana** |	http://localhost:3001 |admin / admin|
| **Superset** |http://localhost:8088 |создается вручную (см. ниже)

### Подключение к PostgreSQL

Все BI-инструменты подключаются к базе по имени контейнера postgres.
``` yaml
Host: postgres
Port: 5432
Database: bi_db
User: bi_user
Password: bi_pass 
```

### Metabase

1. Перейди на http://localhost:3000  
2. При первом запуске создай пользователя
3. Добавь базу PostgreSQL с настройками выше

Metabase подключится автоматически ✅

### Grafana

1. Перейди на http://localhost:3001
2. Логин: admin / admin 
3. Зайди в Меню → ⚙️ Connections → Data sources → Add data source 
4. Выбери PostgreSQL, введи:
```
Host: postgres:5432
Database: bi_db
User: bi_user
Password: bi_pass
SSL Mode: disable
```
5. Нажми Save & Test

### Superset

Если Superset не инициализирован — создай админа:

```
sudo docker exec -it superset superset fab create-admin \
--username admin \
--firstname Admin \
--lastname User \
--email admin@example.com \
--password admin 

sudo docker exec -it superset superset db upgrade
sudo docker exec -it superset superset init
```

Затем открой http://localhost:8088  
войди admin / admin 

Добавь базу:

postgresql://bi_user:bi_pass@postgres:5432/bi_db

## Как это работает

Postgres — база данных (хранилище).

Metabase, Grafana и Superset — BI-инструменты, подключающиеся к базе по внутренней docker-сети.

Все данные сохраняются в папке ./data/, чтобы не потерялись при перезапуске.

Можно добавлять свои SQL-таблицы и использовать их во всех трёх инструментах.

### Полезные команды

```
##Остановить все контейнеры
sudo docker compose down

##Перезапустить
sudo docker compose restart

## Смотреть логи (например, Metabase)
sudo docker logs -f metabase

```

### И, немножко полезнотей, дальше по аналогии все должно быть понятно =)
как добавить тестовую таблицу:
```
sudo docker exec -it postgres psql -U bi_user -d bi_db -c "
CREATE TABLE sales (
id SERIAL PRIMARY KEY,
country VARCHAR(50),
revenue INT
);
INSERT INTO sales (country, revenue) VALUES
('USA', 1200),
('Germany', 900),
('France', 1100),
('Japan', 1500);
"
```

