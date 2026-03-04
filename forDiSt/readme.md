# Incident Management System

## 1. Физическая модель данных (обновленная)

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
| version | BIGINT | — | Версия для Optimistic Locking (защита от race condition) |
| created_at | TIMESTAMP | — | Дата создания |
| updated_at | TIMESTAMP | — | Дата изменения |

**Ограничения:**
- `UNIQUE(incident_id) WHERE status IN ('AWAITING_CONFIRMATION', 'CONFIRMED')` — гарантия одного активного назначения
- `CHECK (expires_at > created_at)`

#### Таблица: idempotency_keys

| Поле | Тип | Описание |
|------|-----|----------|
| key | VARCHAR | PK |
| user_id | UUID | Пользователь, инициировавший запрос |
| request_hash | VARCHAR | Хэш запроса (body + path) |
| response_payload | JSONB | Результат предыдущей операции (для COMPLETED) |
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

**Индекс:** `(entity_type, entity_id, created_at)`

#### Таблица: outbox_events

| Поле | Тип | PK/FK | Описание |
|------|-----|-------|----------|
| id | UUID | PK | Идентификатор события |
| aggregate_id | UUID | — | ID агрегата |
| aggregate_type | VARCHAR | — | `incident` / `assignment` / `crew` |
| event_type | VARCHAR | — | Тип события (например, `IncidentAssignmentRequested`) |
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

### 1.4 Справочники (Reference Data)

- **directions:** id, name, is_active, created_at
- **crew_status_dict:** code, description
- **incident_status_dict:** code, description
- **assignment_status_dict:** code, description
- **reject_reason_dict:** code, description

---

## 2. Методы backend (обновленные)

### Incident Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| **POST /incidents/{id}/assign** | path: incident_id, body: crew_id, headers: Authorization, Idempotency-Key, X-Workstation-ID | **202 Accepted** + AssignmentResponse | Асинхронный запуск Saga назначения |
| **POST /assignments/{id}/confirm** | path: assignment_id, headers: Authorization, Idempotency-Key, X-Workstation-ID | **200 OK** + ConfirmResponse | Подтверждение назначения врачом (с оптимистичной блокировкой) |
| **POST /assignments/{id}/reject** | path: assignment_id, headers: Authorization, X-Workstation-ID, body: reason (опционально) | **200 OK** + RejectResponse | Отказ или таймаут |
| **POST /incidents/{id}/complete** | path: incident_id, headers: Authorization, X-Workstation-ID | **200 OK** | Завершение обращения |
| **GET /incidents** | query: status, direction_id, created_from, created_to, limit, offset | **200 OK** + список | Список обращений с фильтрацией |
| **GET /incidents/{id}** | path: incident_id | **200 OK** + IncidentDetailResponse | Детали обращения с историей |
| **GET /incidents/{id}/history** | path: incident_id, query: limit, offset | **200 OK** + список | Аудит действий |

### Crew Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| **GET /crews** | query: status, direction_id, limit, offset | **200 OK** + список | Доступные бригады |
| *internal* `ReserveCrew` | Событие `IncidentAssignmentRequested` | Публикация `CrewReserved` / `CrewReservationFailed` | Внутренний обработчик Saga |
| *internal* `SetCrewBusy` | Событие `AssignmentConfirmed` | Публикация `CrewBecameBusy` | Внутренний обработчик |
| *internal* `FreeCrew` | Событие `AssignmentRejected` | Публикация `CrewBecameFree` | Внутренний обработчик |

### Notification Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| **GET /notifications** | query: status, limit, offset | **200 OK** + список | Список уведомлений |
| **POST /notifications/ack** | header: X-WebSocket-Session-ID, body: notification_id | **200 OK** | Подтверждение доставки (exactly-once) |
| **POST /notifications/heartbeat** | header: X-WebSocket-Session-ID | **200 OK** | Поддержка WebSocket сессии |

### Auth Service

| Метод | Входные параметры | Выходные параметры | Описание |
|-------|-------------------|---------------------|----------|
| POST /login | body: username/password | JWT token | Авторизация |
| GET /me | header: Authorization | user info, roles, direction | Информация о пользователе |

---

## 3. Event-Driven Saga: Назначение обращения (детальная спецификация)

### 3.1 Полный поток с обработкой всех граничных случаев

```mermaid
sequenceDiagram
    participant D as Диспетчер
    participant IS as Incident Service
    participant CS as Crew Service
    participant NS as Notification Service
    participant DB as Incident DB
    participant K as Kafka

    D->>IS: POST /incidents/{id}/assign
    IS->>DB: Проверка idempotency_key
    IS->>DB: Проверка incident (status=PENDING_ASSIGNMENT)
    IS->>DB: Запись idempotency_key (IN_PROGRESS)
    IS->>K: publish IncidentAssignmentRequested
    
    K-->>CS: consume IncidentAssignmentRequested
    CS->>CS: Проверка crew (status=FREE)
    CS->>CS: UPDATE crews SET status=RESERVED, version+=1
    CS->>K: publish CrewReserved
    
    K-->>IS: consume CrewReserved
    IS->>DB: START TRANSACTION
    IS->>DB: INSERT INTO incident_assignment (status=AWAITING_CONFIRMATION, expires_at=NOW()+2min)
    IS->>DB: UPDATE incident SET status=AWAITING_CONFIRMATION, version+=1
    IS->>DB: INSERT INTO audit_log
    IS->>DB: INSERT INTO outbox (IncidentAwaitingConfirmation)
    IS->>DB: UPDATE idempotency_key (status=COMPLETED, response_payload)
    IS->>DB: COMMIT
    
    IS->>K: publish IncidentAwaitingConfirmation (from outbox)
    K-->>NS: consume IncidentAwaitingConfirmation
    NS->>NS: INSERT INTO notifications (status=NEW)
    NS->>D: WebSocket: Уведомление диспетчеру
    
    Note over NS: WebSocket push бригаде
    NS->>Brigade: assignment.requested (expires_at)
    
    alt Врач подтверждает
        Brigade->>IS: POST /assignments/{id}/confirm
        IS->>DB: Проверка idempotency
        IS->>DB: UPDATE incident_assignment 
            SET status='CONFIRMED', version=version+1
            WHERE id=? AND status='AWAITING_CONFIRMATION' 
            AND expires_at>NOW() AND version=?
        
        alt Update успешен (rows_affected=1)
            IS->>K: publish AssignmentConfirmed
            K-->>CS: consume AssignmentConfirmed
            CS->>CS: UPDATE crews SET status=BUSY, version+=1
            CS->>K: publish CrewBecameBusy
            
            K-->>IS: consume CrewBecameBusy
            IS->>DB: UPDATE incident SET status=IN_PROGRESS, version+=1
            IS->>DB: INSERT INTO audit_log
            IS->>K: publish IncidentInProgress
            
            IS-->>Brigade: 200 OK (CONFIRMED)
            
        else Update не удался (конфликт или таймаут)
            IS-->>Brigade: 409 CONFLICT (ASSIGNMENT_EXPIRED или CONCURRENT_MODIFICATION)
        end
        
    else Врач отклоняет или таймаут
        alt Ручной отказ
            Brigade->>IS: POST /assignments/{id}/reject
        else Автоматический таймаут
            IS->>IS: Scheduler: SELECT * FROM incident_assignment 
                WHERE status='AWAITING_CONFIRMATION' AND expires_at<NOW()
        end
        
        IS->>DB: UPDATE incident_assignment SET status='REJECTED', version+=1
        IS->>K: publish AssignmentRejected
        
        K-->>CS: consume AssignmentRejected
        CS->>CS: UPDATE crews SET status=FREE, version+=1
        CS->>K: publish CrewBecameFree
        
        K-->>IS: consume CrewBecameFree
        IS->>DB: UPDATE incident SET status=PENDING_ASSIGNMENT, version+=1
        IS->>DB: INSERT INTO audit_log
        IS->>K: publish IncidentPendingAssignment
        
        K-->>NS: consume IncidentPendingAssignment
        NS->>D: WebSocket: Уведомление диспетчеру об отказе
        
        IS-->>Brigade: 200 OK (REJECTED)
    end
    
 ```   
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
3.2.3 Таймаут на сагу (Saga Timeout)
sql
-- Фоновый процесс для очистки зависших idempotency ключей
UPDATE idempotency_keys
SET status = 'FAILED'
WHERE status = 'IN_PROGRESS' 
  AND saga_timeout < NOW();

-- Для каждого такого ключа отправляем компенсирующее событие
-- (если бригада была зарезервирована, но мы не получили CrewReserved)
3.3 Примеры ответов
Успешное назначение (202 Accepted)
json
{
  "assignment_id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",
  "incident_id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",
  "crew_id": "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",
  "status": "AWAITING_CONFIRMATION",
  "expires_at": "2026-03-04T12:30:00Z",
  "created_at": "2026-03-04T12:28:00Z"
}
Ошибка Race Condition (409 Conflict)
json
{
  "code": "CONCURRENT_MODIFICATION",
  "message": "Assignment was modified by another request",
  "details": {
    "current_status": "CONFIRMED",
    "retry_possible": false
  },
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "timestamp": "2026-03-04T12:29:31.123Z"
}
Детали обращения с историей
json
{
  "id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",
  "patient_id": "3a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",
  "direction_id": "8b7e334f-9210-4f07-b8e1-0f9b8a12c4a5",
  "status": "AWAITING_CONFIRMATION",
  "priority": "HIGH",
  "payload": {
    "symptoms": ["Острая боль в груди", "Одышка"],
    "consciousness": "CLEAR",
    "breathing": "DIFFICULT"
  },
  "created_at": "2026-03-04T12:25:00Z",
  "current_assignment": {
    "id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",
    "crew_id": "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",
    "status": "AWAITING_CONFIRMATION",
    "expires_at": "2026-03-04T12:30:00Z"
  },
  "assignments_history": [
    {
      "id": "c31a9f6e-7c14-4d3f-bc9c-12f32acb4e22",
      "crew_id": "7b8e334f-9210-4f07-b8e1-0f9b8a12c4b2",
      "status": "REJECTED",
      "created_at": "2026-03-04T12:20:00Z",
      "resolved_at": "2026-03-04T12:22:00Z",
      "reject_reason": "TIMEOUT"
    }
  ],
  "version": 3,
  "updated_at": "2026-03-04T12:28:00Z"
}
```

## 4. Топики Kafka (обновленные)

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

### Архитектурные решения
1. Оркестровая Saga с Incident Service как оркестратором

2. Idempotency Keys для защиты от повторов

3. Outbox pattern для атомарности БД + Kafka

4. Optimistic Locking для защиты от race conditions

5. Partial Unique Index для гарантии одного активного назначения

6. Аудит с user_id + workstation_id

7. Scheduler для обработки таймаутов

8. Saga Timeout для зависших операций