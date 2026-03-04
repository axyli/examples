# Incident Management System

## 1. Физическая модель данных

### 1.1 Incident Service

#### Таблица: incident

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Уникальный идентификатор обращения |
| patient_id | UUID | — | Идентификатор пациента |
| direction_id | UUID | FK → directions.id | Направление обращения |
| status | VARCHAR(50) | FK → incident_status_dict.code | Статус: `PENDING_ASSIGNMENT` / `AWAITING_CONFIRMATION` / `IN_PROGRESS` / `COMPLETED` |
| priority | VARCHAR(20) | — | Срочность: `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |
| payload | JSONB | — | Детали обращения (симптомы, заметки) |
| version | BIGINT | — | Версия для Optimistic Locking |
| created_at | TIMESTAMP | — | Дата создания |
| updated_at | TIMESTAMP | — | Дата обновления |

**Индексы:** `(direction_id, status)`, `(status, created_at)`

#### Таблица: incident_assignment

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Уникальный идентификатор назначения |
| incident_id | UUID | FK → incident.id | Связь с обращением |
| crew_id | UUID | FK → crews.id | Назначенная бригада |
| status | VARCHAR(50) | FK → assignment_status_dict.code | Статус: `AWAITING_CONFIRMATION` / `CONFIRMED` / `REJECTED` |
| reject_reason | VARCHAR(50) | FK → reject_reason_dict.code | Причина отказа: `CREW_REJECTED` / `TIMEOUT` / `CREW_UNAVAILABLE` |
| expires_at | TIMESTAMP | — | Время истечения таймера (`created_at + 2 min`) |
| assigned_by | UUID | — | Диспетчер, создавший назначение |
| confirmed_by | UUID | — | Врач, подтвердивший назначение |
| workstation_id | UUID | — | Рабочее место диспетчера |
| version | BIGINT | — | Версия для Optimistic Locking |
| created_at | TIMESTAMP | — | Дата создания |
| updated_at | TIMESTAMP | — | Дата изменения |

**Ограничения:**
- `UNIQUE(incident_id) WHERE status IN ('AWAITING_CONFIRMATION', 'CONFIRMED')`
- `CHECK (expires_at > created_at)`

#### Таблица: idempotency_keys

| Поле | Тип | Описание |
|------|-----|----------|
| key | VARCHAR | PK |
| user_id | UUID | Пользователь, инициировавший запрос |
| request_hash | VARCHAR | Хэш запроса (body + path) |
| response_payload | JSONB | Результат предыдущей операции |
| status | VARCHAR | `IN_PROGRESS` / `COMPLETED` / `FAILED` |
| saga_timeout | TIMESTAMP | `created_at + 30s` — таймаут на сагу |
| created_at | TIMESTAMP | Дата создания |

#### Таблица: audit_log

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Идентификатор записи |
| entity_type | VARCHAR | — | `INCIDENT` / `ASSIGNMENT` / `CREW` |
| entity_id | UUID | — | ID сущности |
| action | VARCHAR | — | `CREATED` / `ASSIGNED` / `CONFIRMED` / `REJECTED` / `COMPLETED` |
| performed_by | UUID | — | Пользователь (из токена) |
| workstation_id | UUID | — | Рабочее место пользователя |
| idempotency_key | UUID | — | Ключ идемпотентности (для трассировки) |
| payload | JSONB | — | Дополнительные данные |
| created_at | TIMESTAMP | — | Время события |

#### Таблица: outbox_events

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Идентификатор события |
| aggregate_id | UUID | — | ID агрегата |
| aggregate_type | VARCHAR | — | `incident` / `assignment` / `crew` |
| event_type | VARCHAR | — | Тип события |
| payload | JSONB | — | Данные события |
| status | VARCHAR | — | `NEW` / `SENT` / `FAILED` |
| retry_count | INT | — | Количество попыток |
| created_at | TIMESTAMP | — | Дата создания |
| sent_at | TIMESTAMP | — | Дата публикации |

### 1.2 Crew Service

#### Таблица: crews

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Уникальный идентификатор бригады |
| direction_id | UUID | FK → directions.id | Направление бригады |
| name | VARCHAR | — | Название/номер бригады |
| status | VARCHAR | FK → crew_status_dict.code | Статус: `FREE` / `RESERVED` / `BUSY` / `OFFLINE` |
| members_count | INT | — | Количество сотрудников |
| current_incident_id | UUID | — | Текущее обращение (если статус BUSY) |
| version | BIGINT | — | Optimistic Locking |
| updated_at | TIMESTAMP | — | Дата изменения |

#### Таблица: crew_members

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| crew_id | UUID | PK, FK → crews.id | Идентификатор бригады |
| user_id | UUID | PK | Идентификатор врача |
| role | VARCHAR | — | Роль в бригаде |
| joined_at | TIMESTAMP | — | Дата присоединения |

### 1.3 Notification Service

#### Таблица: notifications

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Идентификатор уведомления |
| user_id | UUID | — | Получатель уведомления |
| type | VARCHAR | — | `ASSIGNMENT_REQUESTED` / `ASSIGNMENT_CONFIRMED` / `ASSIGNMENT_REJECTED` / `SYSTEM_ALERT` |
| payload | JSONB | — | Данные уведомления |
| status | VARCHAR | — | `NEW` / `SENT` / `ACKED` / `FAILED` |
| retry_count | INT | — | Попытки отправки |
| created_at | TIMESTAMP | — | Дата создания |
| delivered_at | TIMESTAMP | — | Дата доставки |
| acknowledged_at | TIMESTAMP | — | Дата подтверждения получения |

### 1.4 Справочники

#### Таблица: directions
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | PK |
| name | VARCHAR | Название направления |
| is_active | BOOLEAN | Активно ли направление |
| created_at | TIMESTAMP | Дата создания |

#### Таблица: incident_status_dict
| Поле | Тип | Описание |
|------|-----|----------|
| code | VARCHAR | PK: `PENDING_ASSIGNMENT`, `AWAITING_CONFIRMATION`, `IN_PROGRESS`, `COMPLETED` |
| description | VARCHAR | Описание статуса |

#### Таблица: assignment_status_dict
| Поле | Тип | Описание |
|------|-----|----------|
| code | VARCHAR | PK: `AWAITING_CONFIRMATION`, `CONFIRMED`, `REJECTED` |
| description | VARCHAR | Описание статуса |

#### Таблица: crew_status_dict
| Поле | Тип | Описание |
|------|-----|----------|
| code | VARCHAR | PK: `FREE`, `RESERVED`, `BUSY`, `OFFLINE` |
| description | VARCHAR | Описание статуса |

#### Таблица: reject_reason_dict
| Поле | Тип | Описание |
|------|-----|----------|
| code | VARCHAR | PK: `CREW_REJECTED`, `TIMEOUT`, `CREW_UNAVAILABLE` |
| description | VARCHAR | Описание причины |

---

## 2. Методы backend (по сервисам)

### 2.1 Incident Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| **POST /incidents/{id}/assign** | path: incident_id, body: crew_id, headers: Authorization, Idempotency-Key, X-Workstation-ID | **202 Accepted** + AssignmentResponse | Асинхронный запуск Saga назначения |
| **POST /assignments/{id}/confirm** | path: assignment_id, headers: Authorization, Idempotency-Key, X-Workstation-ID | **200 OK** + ConfirmResponse | Подтверждение назначения врачом |
| **POST /assignments/{id}/reject** | path: assignment_id, headers: Authorization, X-Workstation-ID, body: reason | **200 OK** + RejectResponse | Отказ или таймаут |
| **POST /incidents/{id}/complete** | path: incident_id, headers: Authorization, X-Workstation-ID | **200 OK** | Завершение обращения |
| **GET /incidents** | query: status, direction_id, created_from, created_to, limit, offset | **200 OK** + список | Список обращений с фильтрацией |
| **GET /incidents/{id}** | path: incident_id | **200 OK** + IncidentDetailResponse | Детали обращения с историей |
| **GET /incidents/{id}/history** | path: incident_id, query: limit, offset | **200 OK** + список | Аудит действий |

### 2.2 Crew Service (внешние методы)

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| **GET /crews** | query: status, direction_id, limit, offset | **200 OK** + список | Доступные бригады |
| **GET /crews/{id}** | path: crew_id | **200 OK** + CrewResponse | Детали бригады |

### 2.3 Crew Service (внутренние методы для Saga)

| Метод | Триггер | Действие | Выходное событие |
|-------|---------|----------|------------------|
| `ReserveCrew` | Событие `IncidentAssignmentRequested` | Проверка и резервирование бригады | `CrewReserved` / `CrewReservationFailed` |
| `SetCrewBusy` | Событие `AssignmentConfirmed` | Перевод бригады в статус BUSY | `CrewBecameBusy` |
| `FreeCrew` | Событие `AssignmentRejected` | Освобождение бригады | `CrewBecameFree` |

### 2.4 Notification Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| **GET /notifications** | query: status, limit, offset | **200 OK** + список | Список уведомлений |
| **POST /notifications/ack** | header: X-WebSocket-Session-ID, body: notification_id | **200 OK** | Подтверждение доставки |
| **POST /notifications/heartbeat** | header: X-WebSocket-Session-ID | **200 OK** | Поддержка WebSocket сессии |

### 2.5 Auth Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| POST /login | body: username/password | JWT token | Авторизация |
| GET /me | header: Authorization | user info, roles, direction | Информация о пользователе |

---

## 3. Event-Driven Saga: Назначение обращения

### 3.1 Полный поток с обработкой всех граничных случаев
ппп


### 3.2 Критические точки консистентности

#### 3.2.1 Защита от Race Condition (таймер vs подтверждение)

```sql
-- В обработчике /confirm используем оптимистичную блокировку
UPDATE incident_assignment 
SET status = 'CONFIRMED', 
    version = version + 1,
    confirmed_by = :user_id,
    updated_at = NOW()
WHERE id = :assignment_id 
  AND status = 'AWAITING_CONFIRMATION'
  AND expires_at > NOW()
  AND version = :old_version;

-- Проверяем, обновилась ли строка
IF (row_count = 0) THEN
    -- Проверяем причину: таймаут или уже обработано
    SELECT status, expires_at INTO current_status, expires 
    FROM incident_assignment WHERE id = :assignment_id;
    
    IF (expires <= NOW()) THEN
        RETURN 409, 'ASSIGNMENT_EXPIRED';
    ELSE
        RETURN 409, 'ASSIGNMENT_ALREADY_PROCESSED';
    END IF;
END IF;
```
#### 3.2.2 Scheduler для обработки таймаутов
``` sql
-- Фоновый процесс, запускается каждые 10 секунд
-- Используем SELECT ... FOR UPDATE SKIP LOCKED для batch-обработки
BEGIN;
SELECT id, incident_id, crew_id
FROM incident_assignment
WHERE status = 'AWAITING_CONFIRMATION'
AND expires_at < NOW()
LIMIT 100
FOR UPDATE SKIP LOCKED;

-- Для каждой найденной записи:
-- 1. Публикуем AssignmentRejected
-- 2. Обновляем статус в отдельной транзакции
COMMIT;
```

#### 3.2.3 Таймаут на сагу (Saga Timeout)
``` sql
-- Фоновый процесс для очистки зависших idempotency ключей
UPDATE idempotency_keys
SET status = 'FAILED'
WHERE status = 'IN_PROGRESS'
AND saga_timeout < NOW();
```

# 3.3 Топики Kafka

| Топик | Тип события | Продюсер | Консьюмеры | Описание |
|-------|-------------|----------|------------|----------|
| `incident.assignments.requested` | `IncidentAssignmentRequested` | Incident Service | Crew Service | Запрос на резервирование бригады |
| `crew.reservation.events` | `CrewReserved` / `CrewReservationFailed` | Crew Service | Incident Service | Результат резервирования |
| `incident.assignments.lifecycle` | `IncidentAwaitingConfirmation` / `IncidentInProgress` / `IncidentPendingAssignment` | Incident Service | Notification Service | Изменения статуса обращения |
| `assignment.confirmed` | `AssignmentConfirmed` | Incident Service | Crew Service | Врач подтвердил назначение |
| `assignment.rejected` | `AssignmentRejected` | Incident Service | Crew Service | Отказ или таймаут |
| `crew.status.updated` | `CrewBecameBusy` / `CrewBecameFree` | Crew Service | Incident Service | Изменения статуса бригады |
| `notification.events` | Все события для уведомлений | Все сервисы | Notification Service | События, требующие уведомлений |

---

## 4. Детализированное описание методов API

### 4.1 Метод: POST /incidents/{incident_id}/assign — Назначение обращения

#### Входные параметры

| Параметр | Тип | Где | Обязательный | Описание |
|----------|-----|-----|--------------|----------|
| `incident_id` | string (uuid) | path | Да | Идентификатор обращения |
| `crew_id` | string (uuid) | body | Да | Идентификатор бригады |
| `Idempotency-Key` | string | header | Да | Уникальный ключ идемпотентности |
| `X-Workstation-ID` | string (uuid) | header | Да | Рабочее место диспетчера |
| `Authorization` | string (JWT) | header | Да | Токен авторизации |

####   Детализированный алгоритм
   
1. Аутентификация и авторизация
   1.1. Извлечь JWT из заголовка Authorization
   1.2. Проверить подпись и срок действия токена
   1.3. Извлечь роли пользователя
   1.4. Если роль != "DISPATCHER" → вернуть 403 FORBIDDEN_ROLE
   1.5. Извлечь direction_id пользователя из токена

2. Проверка идемпотентности
   2.1. SELECT * FROM idempotency_keys WHERE key = :Idempotency-Key AND user_id = :user_id
   2.2. IF запись существует:
   - IF status = 'IN_PROGRESS' AND saga_timeout > NOW() → вернуть 409 IDEMPOTENCY_IN_PROGRESS
   - IF status = 'IN_PROGRESS' AND saga_timeout <= NOW() → UPDATE status = 'FAILED'
   - IF status = 'COMPLETED' → вернуть сохраненный response_payload (202)
   - IF status = 'FAILED' → продолжить выполнение (перезапуск)
   2.3. ELSE: INSERT INTO idempotency_keys (key, user_id, request_hash, status, saga_timeout)
   VALUES (:key, :user_id, :hash, 'IN_PROGRESS', NOW() + interval '30 seconds')

3. Валидация обращения
   3.1. SELECT i.*, d.name FROM incident i
   JOIN directions d ON i.direction_id = d.id
   WHERE i.id = :incident_id FOR UPDATE
   3.2. IF NOT FOUND → вернуть 404 INCIDENT_NOT_FOUND
   3.3. IF i.status != 'PENDING_ASSIGNMENT' → вернуть 409 INCIDENT_INVALID_STATUS
   3.4. IF i.direction_id != :user_direction_id → вернуть 403 DIRECTION_MISMATCH

4. Проверка бригады (синхронный запрос в Crew Service)
   4.1. GET /internal/crews/:crew_id?check_availability=true
   4.2. IF crew.status != 'FREE' → вернуть 409 CREW_NOT_AVAILABLE
   4.3. IF crew.direction_id != i.direction_id → вернуть 403 DIRECTION_MISMATCH

5. Публикация события в Kafka (начало Saga)
   5.1. Создать событие IncidentAssignmentRequested
   5.2. Записать событие в outbox_events (status = 'NEW')
   5.3. COMMIT (транзакция шагов 3-5)

6. Ответ клиенту (до завершения Saga!)
   6.1. Вернуть 202 Accepted с телом:
 ``` {
   "assignment_id": null,
   "incident_id": :incident_id,
   "crew_id": :crew_id,
   "status": "PENDING",
   "message": "Assignment initiated, waiting for crew response"
   }
   ```


#### Обработка ошибок

| Код ошибки | HTTP статус | Условие возникновения |
|------------|-------------|------------------------|
| `UNAUTHORIZED` | 401 | JWT отсутствует или невалиден |
| `FORBIDDEN_ROLE` | 403 | Пользователь не диспетчер |
| `DIRECTION_MISMATCH` | 403 | Направление бригады ≠ направлению обращения |
| `INCIDENT_NOT_FOUND` | 404 | Обращение с указанным ID не существует |
| `INCIDENT_INVALID_STATUS` | 409 | Статус обращения ≠ PENDING_ASSIGNMENT |
| `CREW_NOT_FOUND` | 404 | Бригада не найдена |
| `CREW_NOT_AVAILABLE` | 409 | Статус бригады ≠ FREE |
| `IDEMPOTENCY_IN_PROGRESS` | 409 | Запрос с этим ключом уже выполняется |
| `IDEMPOTENCY_CONFLICT` | 409 | Тот же ключ, но другой request_hash |

---

### 4.2 Метод: POST /assignments/{assignment_id}/confirm — Подтверждение назначения

#### Входные параметры

| Параметр | Тип | Где | Обязательный | Описание |
|----------|-----|-----|--------------|----------|
| `assignment_id` | string (uuid) | path | Да | Идентификатор назначения |
| `Idempotency-Key` | string | header | Да | Уникальный ключ идемпотентности |
| `X-Workstation-ID` | string (uuid) | header | Да | Рабочее место врача |
| `Authorization` | string (JWT) | header | Да | Токен авторизации |

#### Детализированный алгоритм

1. Аутентификация и авторизация
   1.1. Извлечь JWT из заголовка Authorization
   1.2. Проверить подпись и срок действия токена
   1.3. Извлечь user_id и roles пользователя
   1.4. IF роль != "DOCTOR" → вернуть 403 FORBIDDEN_ROLE

2. Проверка идемпотентности
   2.1. SELECT * FROM idempotency_keys WHERE key = :Idempotency-Key AND user_id = :user_id
   2.2. IF запись существует:
   - IF status = 'COMPLETED' → вернуть сохраненный response_payload (200)
   - IF status = 'IN_PROGRESS' → вернуть 409 IDEMPOTENCY_IN_PROGRESS
   2.3. ELSE: INSERT INTO idempotency_keys (key, user_id, request_hash, status)
   VALUES (:key, :user_id, :hash, 'IN_PROGRESS')

3. Получение назначения с блокировкой
   3.1. SELECT ia.*, i.direction_id, i.status as incident_status,
   c.direction_id as crew_direction, c.status as crew_status
   FROM incident_assignment ia
   JOIN incident i ON ia.incident_id = i.id
   JOIN crews c ON ia.crew_id = c.id
   WHERE ia.id = :assignment_id
   FOR UPDATE
   3.2. IF NOT FOUND → вернуть 404 ASSIGNMENT_NOT_FOUND

4. Валидация прав врача
   4.1. SELECT 1 FROM crew_members
   WHERE crew_id = ia.crew_id AND user_id = :user_id
   4.2. IF NOT FOUND → вернуть 403 FORBIDDEN_OPERATION

5. Валидация состояния назначения  
   5.1. IF ia.status != 'AWAITING_CONFIRMATION' →
   вернуть 409 ASSIGNMENT_ALREADY_PROCESSED
   5.2. IF ia.expires_at < NOW() →
   вернуть 409 ASSIGNMENT_EXPIRED

6. Оптимистичное обновление  
   6.1. UPDATE incident_assignment
   SET status = 'CONFIRMED',
   version = version + 1,
   confirmed_by = :user_id,
   updated_at = NOW()
   WHERE id = :assignment_id
   AND status = 'AWAITING_CONFIRMATION'
   AND expires_at > NOW()
   AND version = :old_version
   6.2. IF rows_affected = 0:
   - SELECT status FROM incident_assignment WHERE id = :assignment_id
   - IF status = 'CONFIRMED' → 409 ASSIGNMENT_ALREADY_PROCESSED
   - IF status = 'REJECTED' → 409 ASSIGNMENT_ALREADY_PROCESSED
   - IF expires_at <= NOW() → 409 ASSIGNMENT_EXPIRED
   - ELSE → 409 CONCURRENT_MODIFICATION

7. Публикация событий и завершение
   7.1. Создать событие AssignmentConfirmed
   7.2. Записать в outbox_events
   7.3. UPDATE idempotency_keys SET status = 'COMPLETED', response_payload = :response
   7.4. COMMIT
   7.5. Вернуть 200 OK с ConfirmResponse


#### Сценарии race condition и их обработка

| Сценарий | Результат |
|----------|-----------|
| Таймер и confirm одновременно | Победитель определяется version. Проигравший получает 409 |
| Два врача одной бригады | Первый успешно обновляет, второй получает 409 |
| Confirm после таймаута | 409 ASSIGNMENT_EXPIRED |
| Повторный confirm с тем же ключом | 200 OK с сохраненным ответом |

#### Примеры ответов

**Успешное подтверждение (200 OK)**
```json
{
  "assignment_id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",
  "incident_id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",
  "status": "CONFIRMED",
  "confirmed_at": "2026-03-04T12:29:31.123Z",
  "confirmed_by": "5a7e334f-9210-4f07-b8e1-0f9b8a12c4a1"
}
```
**Ошибка race condition (409 Conflict)**

```json
{
"code": "CONCURRENT_MODIFICATION",
"message": "Assignment was modified by another request",
"details": {
"current_status": "REJECTED",
"reason": "TIMEOUT"
},
"request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
"timestamp": "2026-03-04T12:29:31.456Z"
}```


