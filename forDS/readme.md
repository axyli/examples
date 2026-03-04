# Incident Management: Event-Driven Saga

Решение управляет назначением бригады на обращение и подтверждением врачом через Event-Driven Saga с использованием Kafka.  
Incident Service выступает **оркестратором**, Crew Service и Notification Service — исполнителями.

---

## 1. Физическая модель данных

### 1.1 Incident Service

#### Таблица: `incident`

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор обращения |
| patient_id | UUID | — | Идентификатор пациента |
| direction_id | UUID | FK → directions.id | Направление обращения |
| status | VARCHAR(50) | FK → incident_status_dict.code | Статус обращения (NEW / ASSIGNED_WAITING_CONFIRMATION / IN_PROGRESS / COMPLETED) |
| payload | JSONB | — | Детали обращения: симптомы, срочность, заметки диспетчера |
| version | BIGINT | — | Версия для Optimistic Locking |
| created_at | TIMESTAMP | — | Дата создания |
| updated_at | TIMESTAMP | — | Дата обновления |

**Индексы:** `(direction_id, status)`

#### Таблица: `incident_assignment`

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор назначения |
| incident_id | UUID | FK → incident.id | Связь с обращением |
| crew_id | UUID | FK → crews.id | Назначенная бригада |
| status | VARCHAR(50) | FK → assignment_status_dict.code | Статус назначения (PENDING_RESERVE / WAITING_CONFIRMATION / ACCEPTED / REJECTED) |
| reject_reason | VARCHAR(50) | FK → reject_reason_dict.code, NULL | Причина отказа |
| expires_at | TIMESTAMP | — | Время истечения таймера (2 минуты) |
| assigned_by | UUID | — | Диспетчер, создавший назначение |
| handled_by | UUID | — | Врач, принявший назначение |
| workstation_id | UUID | — | Рабочее место диспетчера |
| created_at | TIMESTAMP | — | Дата создания |
| updated_at | TIMESTAMP | — | Дата изменения |

**Ограничение:** `UNIQUE(incident_id) WHERE status IN ('PENDING_RESERVE','WAITING_CONFIRMATION','ACCEPTED')`

#### Таблица: `idempotency_keys`

| Поле | Тип | Описание |
| ----- | ----- | ----- |
| key | VARCHAR | PK |
| user_id | UUID | Пользователь, инициировавший запрос |
| request_hash | VARCHAR | Хэш запроса |
| response_payload | JSONB | Результат предыдущей операции |
| status | VARCHAR (IN_PROGRESS / COMPLETED / FAILED) | Статус выполнения |
| created_at | TIMESTAMP | Дата создания |

#### Таблица: `audit_log`

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Идентификатор записи |
| entity_type | VARCHAR | — | Тип сущности: INCIDENT / ASSIGNMENT / CREW |
| entity_id | UUID | — | ID сущности |
| action | VARCHAR | — | Тип действия |
| performed_by | UUID | — | Пользователь (из токена) |
| workstation_id | UUID | — | Рабочее место пользователя |
| payload | JSONB | — | Дополнительные данные |
| created_at | TIMESTAMP | — | Время события |

#### Таблица: `outbox_events`

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Идентификатор события |
| aggregate_id | UUID | — | ID агрегата (incident / assignment / crew) |
| aggregate_type | VARCHAR | — | Тип агрегата |
| event_type | VARCHAR | — | Тип события |
| payload | JSONB | — | Данные события |
| status | VARCHAR | NEW / SENT / FAILED | Статус события |
| retry_count | INT | — | Количество попыток |
| created_at | TIMESTAMP | — | Дата создания |
| sent_at | TIMESTAMP | — | Дата публикации |

---

### 1.2 Crew Service

#### Таблица: `crews`

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор бригады |
| direction_id | UUID | FK → directions.id | Направление бригады |
| status | VARCHAR | FK → crew_status_dict.code | Статус бригады (FREE / RESERVED / BUSY / OFFLINE) |
| version | BIGINT | — | Optimistic Locking |
| updated_at | TIMESTAMP | — | Дата изменения |

---

### 1.3 Notification Service

#### Таблица: `notifications`

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Идентификатор уведомления |
| user_id | UUID | — | Получатель уведомления |
| type | VARCHAR | — | Тип события (REQUEST_ASSIGN, REQUEST_REJECTED, SYSTEM_ALERT) |
| payload | JSONB | — | Данные уведомления |
| status | VARCHAR | NEW / SENT / ACKED / FAILED | Статус уведомления |
| retry_count | INT | — | Попытки отправки |
| created_at | TIMESTAMP | — | Дата создания |
| delivered_at | TIMESTAMP | — | Дата доставки |
| acknowledged_at | TIMESTAMP | — | Дата подтверждения получения |

---

### 1.4 Reference Data

* `directions`: id, name, is_active, created_at
* `crew_status_dict`: code, description
* `incident_status_dict`: code, description
* `assignment_status_dict`: code, description
* `reject_reason_dict`: code, description

---

## 2. Методы backend

### Incident Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| POST /v1/incidents/{id}/assign | path: incident_id, body: crew_id, header: Authorization (JWT), Idempotency-Key | 201 Created + assignment_id / 403 / 404 / 409 / 500 | Назначение обращения диспетчером через оркестрируемую Saga |
| POST /v1/assignments/{id}/accept | path: assignment_id, header: Authorization (JWT), Idempotency-Key | 200 OK / 403 / 404 / 409 / 500 | Подтверждение назначения врачем |
| POST /v1/assignments/{id}/reject | path: assignment_id, header: Authorization (JWT) | 200 OK / 403 / 404 / 409 / 500 | Отказ назначения |
| POST /v1/incidents/{id}/complete | path: incident_id, header: Authorization (JWT) | 200 OK / 403 / 404 / 500 | Завершение обращения |
| GET /v1/incidents | query: filters | list of incidents | Список обращений |
| GET /v1/incidents/{id} | path: incident_id | incident detail | Детали обращения |
| GET /v1/incidents/{id}/history | path: incident_id | audit log | Аудит действий по обращению |

### Crew Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| GET /v1/crews?status=FREE | query: status | list of crews | Доступные бригады |
| internal ReserveCrew | internal | — | Команда Saga, атомарное резервирование бригады |

### Notification Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| GET /v1/notifications | query: filters | list of notifications | Список уведомлений |
| WS ACK handler | payload: notification_id | 200 OK | Подтверждение доставки |
| WS heartbeat | — | 200 OK | Поддержка сессии |

### Auth Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| POST /v1/login | body: username/password | JWT token | Авторизация |
| GET /v1/me | header: Authorization (JWT) | user info | Информация о текущем пользователе |

---

## 3. Event-Driven Saga: Назначение обращения

### 3.1 Overview

Incident Service **оркестрирует Saga**:

1. Синхронная проверка прав, статуса и идемпотентности
2. Публикация события `IncidentAssignmentRequested` в Kafka (`incident.assignments.requested`)
3. Crew Service подписан на топик → резервирует бригаду (`FREE → RESERVED`)
4. Crew Service публикует `CrewReserved` или `CrewReservationFailed` (`crew.assignments.status`)
5. Incident Service обновляет `incident_assignment` и `incident.status`, публикует `IncidentAssigned`

---

### 3.2 Логика шагов

#### 1. Проверка авторизации (синхронно)

* Из JWT: `user_id`, `role`, `workstation_id`, `direction_id`
* Невалидный токен → **401**
* Роль != `DISPATCHER` → **403**

#### 2. Проверка идемпотентности (синхронно)

* Таблица `idempotency_keys`
* Статусы: `IN_PROGRESS` / `COMPLETED`
* `COMPLETED` → вернуть сохранённый результат
* `IN_PROGRESS` → **409**
* Нет записи → создать `IN_PROGRESS`

#### 3. Проверка обращения (синхронно)

* Таблица `incident`: `id`, `status`, `direction_id`
* Существует? → иначе **404**
* Направление совпадает? → иначе **403**
* Статус = `NEW` → иначе **409**

#### 4. Публикация события назначения (асинхронно)

* Топик: `incident.assignments.requested`
* Payload:

```json
{
  "incident_id": "...",
  "crew_id": "...",
  "requested_by": "...",
  "expires_at": "..."
}
```
### 5. Обработка события в Crew Service

* Подписка на топик: `incident.assignments.requested`
* Проверка бригады:
    * существует (`id` есть в базе)
    * статус = `FREE`
    * направление совпадает с обращением

* Результаты проверки:
    * **SUCCESS** → `status = RESERVED`, публикация события `CrewReserved`
    * **FAIL** → публикация события `CrewReservationFailed`

* Топик публикации: `crew.assignments.status`
* Пример payload:

```json
{
  "crew_id": "...",
  "incident_id": "...",
  "status": "RESERVED" // или "FAILED"
}
```
### 6. Incident Service — обработка результата

**CrewReserved:**

* Создать запись `incident_assignment` в своей БД
* Обновить `incident.status = ASSIGNED_WAITING_CONFIRMATION`
* Добавить запись в `audit_log`
* Опубликовать событие `IncidentAssigned` в топик `incident.assignments.assigned`

**CrewReservationFailed:**

* Отметить `Idempotency-Key = FAILED`
* Вернуть клиенту **409 Conflict**

---

### 7. Подтверждение назначения врачом

* Метод: `POST /v1/assignments/{assignment_id}/accept`
* Проверка:
    * `Idempotency-Key`
    * Таймаут: `expires_at > now()`
* Обновления:
    * Crew: `RESERVED → BUSY`
    * Incident: `ASSIGNED_WAITING_CONFIRMATION → IN_PROGRESS`
* Публикации:
    * Событие `AssignmentAccepted` → топик `assignment.accepted`
    * Crew Service публикует `CrewBusy` → топик `crew.status.updated`
    * Notification Service получает уведомление через `incident.assignments.inprogress`

---

### 8. Отказ / Timeout

* Метод: `POST /v1/assignments/{assignment_id}/reject` или истёк таймер
* Обновления:
    * Crew: `RESERVED → FREE` (событие `CrewFreed`)
    * Incident: `incident_assignment.status = REJECTED`, `incident.status = NEW`
* Все действия (Audit, Outbox, Notification) происходят через Kafka

---

### 3.3 Пример ответа на успешное назначение

```json
{
  "assignment_id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",
  "incident_id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",
  "crew_id": "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",
  "status": "WAITING_CONFIRMATION",
  "expires_at": "2026-03-04T12:30:00Z"
}

```

### 3.4 Возможные ошибки

* **401** — пользователь не авторизован
* **403** — недостаточно прав
* **404** — обращение или бригада не найдены
* **409** — обращение уже назначено
* **409** — бригада недоступна
* **409** — повторный `Idempotency-Key`
* **500** — внутренняя ошибка

---

### 4. Ключевые архитектурные моменты

* **Saga:** Incident Service — оркестратор всех шагов
* **Compensation:** Reject / Timeout → возврат статусов
* **Idempotency:** ключи защищают от повторной обработки
* **Concurrency:** conditional updates + partial unique index предотвращают гонки
* **Outbox pattern:** атомарность записи событий и публикации в Kafka
* **Асинхронность и eventual consistency:** фронт и Notification Service получают данные с небольшой задержкой
* **Audit:** все действия фиксируются с `user_id` и `workstation_id`
