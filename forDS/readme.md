## 1. Физическая модель данных

### 1.1 Incident Service

#### Таблица: incident

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

#### Таблица: incident_assignment

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

#### Таблица: idempotency_keys

| Поле | Тип | Описание |
| ----- | ----- | ----- |
| key | VARCHAR | PK |
| user_id | UUID | Пользователь, инициировавший запрос |
| request_hash | VARCHAR | Хэш запроса |
| response_payload | JSONB | Результат предыдущей операции |
| status | VARCHAR (IN_PROGRESS / COMPLETED / FAILED) | Статус выполнения |
| created_at | TIMESTAMP | Дата создания |

#### Таблица: audit_log

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

#### Таблица: outbox_events

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

### 1.2 Crew Service

#### Таблица: crews

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор бригады |
| direction_id | UUID | FK → directions.id | Направление бригады |
| status | VARCHAR | FK → crew_status_dict.code | Статус бригады (FREE / RESERVED / BUSY / OFFLINE) |
| version | BIGINT | — | Optimistic Locking |
| updated_at | TIMESTAMP | — | Дата изменения |

### 1.3 Notification Service

#### Таблица: notifications

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

### 1.4 Reference Data

* **directions:** id, name, is_active, created_at
* **crew_status_dict:** code, description
* **incident_status_dict:** code, description
* **assignment_status_dict:** code, description
* **reject_reason_dict:** code, description

---

## 2. Методы backend

### Incident Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| POST /incidents/{id}/assign | path: incident_id, body: crew_id, header: Authorization (JWT), Idempotency-Key | 201 Created + assignment_id / 403 / 404 / 409 / 500 | Назначение обращения диспетчером через оркестрируемую Saga |
| POST /assignments/{id}/accept | path: assignment_id, header: Authorization (JWT), Idempotency-Key | 200 OK / 403 / 404 / 409 / 500 | Подтверждение назначения врачем |
| POST /assignments/{id}/reject | path: assignment_id, header: Authorization (JWT) | 200 OK / 403 / 404 / 409 / 500 | Отказ назначения |
| POST /incidents/{id}/complete | path: incident_id, header: Authorization (JWT) | 200 OK / 403 / 404 / 500 | Завершение обращения |
| GET /incidents | query: filters | list of incidents | Список обращений |
| GET /incidents/{id} | path: incident_id | incident detail | Детали обращения |
| GET /incidents/{id}/history | path: incident_id | audit log | Аудит действий по обращению |

### Crew Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| GET /crews?status=FREE | query: status | list of crews | Доступные бригады |
| internal ReserveCrew | internal | — | Команда для Saga, атомарное резервирование бригады |

### Notification Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| GET /notifications | query: filters | list of notifications | Список уведомлений |
| WS ACK handler | payload: notification_id | 200 OK | Подтверждение доставки |
| WS heartbeat | — | 200 OK | Поддержка сессии |

### Auth Service

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| POST /login | body: username/password | JWT token | Авторизация |
| GET /me | header: Authorization (JWT) | user info | Информация о текущем пользователе |

---

## 3. Подробная логика метода «Назначение обращения» с Saga (Event-Driven)

**POST /v1/incidents/{incident_id}/assign**

---

### Логика работы (overview)

Incident Service выступает **оркестратором Saga**:

1. Проверяет права и статус обращения (синхронно, гарантированный ответ)
2. Публикует событие `IncidentAssignmentRequested` (асинхронно через Kafka)
3. Crew Service подписан на событие → обновляет статус бригады в своей БД
4. Crew Service публикует результат (`CrewReserved` или `CrewReservationFailed`)
5. Incident Service реагирует на событие и завершает создание `incident_assignment`

---

## 1. Проверка авторизации (синхронно)

* Из JWT извлекает: `user_id`, `role`, `workstation_id`, `direction_id`
* Токен невалиден → **401**
* Роль != DISPATCHER → **403**

**Комментарий:** нужна гарантированная проверка до публикации событий, иначе возможна неверная обработка.

---

## 2. Проверка идемпотентности (синхронно)

* Таблица `idempotency_keys`
* Статусы: `IN_PROGRESS` / `COMPLETED`
* Если `COMPLETED` → вернуть сохранённый результат
* Если `IN_PROGRESS` → **409**
* Если нет записи → создаём `IN_PROGRESS`

**Комментарий:** критично гарантированное сохранение Idempotency-Key перед публикацией события, иначе возможны дубли.

---

## 3. Проверка обращения (синхронно)

* Таблица `incident`: `id`, `status`, `direction_id`, `version`
* Проверяется:
    * Существует → иначе **404**
    * Направление соответствует диспетчеру → иначе **403**
    * Статус = NEW → иначе **409**

**Комментарий:** синхронно, чтобы предотвратить гонки до публикации события.

---

## 4. Публикация события назначения (асинхронно)

* Incident Service публикует `IncidentAssignmentRequested` в Kafka:
    * `incident_id`, `crew_id`, `requested_by`, `expires_at`
* После публикации **не ждём ответа от Crew Service**

**Комментарий:** асинхронно → Incident Service не блокируется, нет ожидания REST-ответа.

---

## 5. Обработка события в Crew Service (асинхронно)

* Подписка на `IncidentAssignmentRequested`
* Crew Service проверяет:
    * Бригада существует (`id`)
    * Статус = `FREE`
    * Направление совпадает
* Если всё ок → обновляет `status = RESERVED` в своей БД и публикует `CrewReserved`
* Если проверка не пройдена → публикует `CrewReservationFailed`

**Комментарий:** гарантированная доставка Kafka нужна, чтобы Incident Service точно получил результат.

---

## 6. Реакция Incident Service на результат (асинхронно)

* Подписка на события `CrewReserved` / `CrewReservationFailed`
* `CrewReserved` →
    * Создаёт `incident_assignment` в своей БД
    * Обновляет `incident.status = ASSIGNED_WAITING_CONFIRMATION`
    * Добавляет запись в `audit_log`
    * Публикует `IncidentAssigned` в Kafka для Notification Service
* `CrewReservationFailed` →
    * Отмечает Idempotency-Key как FAILED
    * Возвращает клиенту **409**

**Комментарий:** Event-driven → конечная обработка может быть немного отложена (eventually consistent), но клиент получает ответ только после результата резервирования.

---

## 7. Outbox / Notification (асинхронно)

* Все события фиксируются в `outbox_events` атомарно с изменениями своей БД
* После commit Outbox-процесс публикует события в Kafka → Notification Service и фронт получают обновления

**Комментарий:** полностью асинхронно, фронт и Notification Service могут получить данные с небольшой задержкой, согласованность eventual.

---

### Пример ответа клиенту (после получения `CrewReserved`)

```json
{
  "assignment_id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",
  "incident_id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",
  "crew_id": "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",
  "status": "WAITING_CONFIRMATION",
  "expires_at": "2026-03-04T12:30:00Z"
}
```

### Возможные ошибки

* **401** — пользователь не авторизован
* **403** — недостаточно прав
* **404** — обращение или бригада не найдены
* **409** — обращение уже назначено
* **409** — бригада недоступна
* **409** — повторный Idempotency-Key
* **500** — внутренняя ошибка

---

## 4. Подтверждение назначения врачом (Accept)

**POST /v1/assignments/{assignment_id}/accept**

### Логика работы аналогична

* Идемпотентность через `Idempotency-Key`
* Проверка таймаута: `expires_at > now()`
* Атомарное обновление статуса: `WAITING_CONFIRMATION → ACCEPTED`
* Crew: `RESERVED → BUSY`
* Incident: `ASSIGNED_WAITING_CONFIRMATION → IN_PROGRESS`
* Audit, Outbox, Notification
* Если timeout / отказ сработал параллельно → возвращаем **409**

---

## 5. Отказ или таймаут

* Timeout / Reject → `assignment → REJECTED`, `crew → FREE`, `incident → NEW`
* Это отдельный шаг Saga с компенсацией

---

## 6. Ключевые архитектурные моменты

1. **Saga:** Incident Service — оркестратор, управление всеми шагами распределённого процесса
2. **Compensation:** Reject / Timeout → освобождение бригады, возврат обращения в NEW
3. **Idempotency:** ключи защищают от повторной обработки
4. **Concurrency:** conditional updates + partial unique index предотвращают гонки
5. **Outbox pattern:** атомарность записи событий и публикации в Kafka
6. **Асинхронность и eventual consistency:** конечное состояние всегда консистентно, промежуточные шаги могут быть временно несогласованными
7. **Audit:** все действия фиксируются с `user_id` и `workstation_id`  