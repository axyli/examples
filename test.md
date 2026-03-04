# **1\. Физическая модель данных**

## **1.1 Incident Service**

### **Таблица: incident**

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор обращения |
| patient\_id | UUID | — | Идентификатор пациента |
| direction\_id | UUID | FK → directions.id | Направление обращения |
| status | VARCHAR(50) | FK → incident\_status\_dict.code | Статус обращения (NEW / ASSIGNED\_WAITING\_CONFIRMATION / IN\_PROGRESS / COMPLETED) |
| payload | JSONB | — | Детали обращения: симптомы, срочность, заметки диспетчера |
| version | BIGINT | — | Версия для Optimistic Locking |
| created\_at | TIMESTAMP | — | Дата создания |
| updated\_at | TIMESTAMP | — | Дата обновления |

**Индексы:** (direction\_id, status)

### **Таблица: incident\_assignment**

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор назначения |
| incident\_id | UUID | FK → incident.id | Связь с обращением |
| crew\_id | UUID | FK → crews.id | Назначенная бригада |
| status | VARCHAR(50) | FK → assignment\_status\_dict.code | Статус назначения (PENDING\_RESERVE / WAITING\_CONFIRMATION / ACCEPTED / REJECTED) |
| reject\_reason | VARCHAR(50) | FK → reject\_reason\_dict.code, NULL | Причина отказа |
| expires\_at | TIMESTAMP | — | Время истечения таймера (2 минуты) |
| assigned\_by | UUID | — | Диспетчер, создавший назначение |
| handled\_by | UUID | — | Врач, принявший назначение |
| workstation\_id | UUID | — | Рабочее место диспетчера |
| created\_at | TIMESTAMP | — | Дата создания |
| updated\_at | TIMESTAMP | — | Дата изменения |

**Ограничение:** UNIQUE(incident\_id) WHERE status IN ('PENDING\_RESERVE','WAITING\_CONFIRMATION','ACCEPTED')

---

### **Таблица: idempotency\_keys**

| Поле | Тип | Описание |
| ----- | ----- | ----- |
| key | VARCHAR | PK |
| user\_id | UUID | Пользователь, инициировавший запрос |
| request\_hash | VARCHAR | Хэш запроса |
| response\_payload | JSONB | Результат предыдущей операции |
| status | VARCHAR (IN\_PROGRESS / COMPLETED / FAILED) | Статус выполнения |
| created\_at | TIMESTAMP | Дата создания |

---

### **Таблица: audit\_log**

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Идентификатор записи |
| entity\_type | VARCHAR | — | Тип сущности: INCIDENT / ASSIGNMENT / CREW |
| entity\_id | UUID | — | ID сущности |
| action | VARCHAR | — | Тип действия |
| performed\_by | UUID | — | Пользователь (из токена) |
| workstation\_id | UUID | — | Рабочее место пользователя |
| payload | JSONB | — | Дополнительные данные |
| created\_at | TIMESTAMP | — | Время события |

---

### **Таблица: outbox\_events**

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Идентификатор события |
| aggregate\_id | UUID | — | ID агрегата (incident / assignment / crew) |
| aggregate\_type | VARCHAR | — | Тип агрегата |
| event\_type | VARCHAR | — | Тип события |
| payload | JSONB | — | Данные события |
| status | VARCHAR | NEW / SENT / FAILED |  |
| retry\_count | INT | Количество попыток |  |
| created\_at | TIMESTAMP | Дата создания |  |
| sent\_at | TIMESTAMP | Дата публикации |  |

---

## **1.2 Crew Service**

### **Таблица: crews**

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Уникальный идентификатор бригады |
| direction\_id | UUID | FK → directions.id | Направление бригады |
| status | VARCHAR | FK → crew\_status\_dict.code | Статус бригады (FREE / RESERVED / BUSY / OFFLINE) |
| version | BIGINT | — | Optimistic Locking |
| updated\_at | TIMESTAMP | — | Дата изменения |

## **1.3 Notification Service**

### **Таблица: notifications**

| Поле | Тип | PK/FK | Описание |
| ----- | ----- | ----- | ----- |
| id | UUID | PK | Идентификатор уведомления |
| user\_id | UUID | — | Получатель уведомления |
| type | VARCHAR | — | Тип события (REQUEST\_ASSIGN, REQUEST\_REJECTED, SYSTEM\_ALERT) |
| payload | JSONB | — | Данные уведомления |
| status | VARCHAR | NEW / SENT / ACKED / FAILED |  |
| retry\_count | INT | Попытки отправки |  |
| created\_at | TIMESTAMP | Дата создания |  |
| delivered\_at | TIMESTAMP | Дата доставки |  |
| acknowledged\_at | TIMESTAMP | Дата подтверждения получения |  |

## **1.4 Reference Data**

* directions: id, name, is\_active, created\_at

* crew\_status\_dict: code, description

* incident\_status\_dict: code, description

* assignment\_status\_dict: code, description

* reject\_reason\_dict: code, description

# **2\. Методы backend**

**Incident Service**

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| POST /incidents/{id}/assign | path: incident\_id, body: crew\_id, header: Authorization (JWT), Idempotency-Key | 201 Created \+ assignment\_id / 403 / 404 / 409 / 500 | Назначение обращения диспетчером через оркестрируемую Saga |
| POST /assignments/{id}/accept | path: assignment\_id, header: Authorization (JWT), Idempotency-Key | 200 OK / 403 / 404 / 409 / 500 | Подтверждение назначения врачем |
| POST /assignments/{id}/reject | path: assignment\_id, header: Authorization (JWT) | 200 OK / 403 / 404 / 409 / 500 | Отказ назначения |
| POST /incidents/{id}/complete | path: incident\_id, header: Authorization (JWT) | 200 OK / 403 / 404 / 500 | Завершение обращения |
| GET /incidents | query: filters | list of incidents | Список обращений |
| GET /incidents/{id} | path: incident\_id | incident detail | Детали обращения |
| GET /incidents/{id}/history | path: incident\_id | audit log | Аудит действий по обращению |

**Crew Service**

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| GET /crews?status=FREE | query: status | list of crews | Доступные бригады |
| internal ReserveCrew | internal | — | Команда для Saga, атомарное резервирование бригады |

**Notification Service**

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| GET /notifications | query: filters | list of notifications | Список уведомлений |
| WS ACK handler | payload: notification\_id | 200 OK | Подтверждение доставки |
| WS heartbeat | — | 200 OK | Поддержка сессии |

**Auth Service**

| Метод | Входные параметры | Выходные параметры | Описание |
| ----- | ----- | ----- | ----- |
| POST /login | body: username/password | JWT token | Авторизация |
| GET /me | header: Authorization (JWT) | user info | Информация о текущем пользователе |

---

# **3\. Подробная логика метода «Назначение обращения» с Saga**

**POST /v1/incidents/{incident\_id}/assign**

### **Логика работы**

На вход:

* incident\_id

* crew\_id

* header Authorization (JWT)

* header Idempotency-Key

---

## **1\. Проверка авторизации**

* Из JWT извлекаем user\_id, role, workstation\_id, direction\_id

* Токен невалиден → 401

* Роль ≠ DISPATCHER → 403

---

## **2\. Проверка идемпотентности**

* Таблица idempotency\_keys

* Статусы: IN\_PROGRESS / COMPLETED

* Если COMPLETED → вернуть сохранённый результат

* Если IN\_PROGRESS → 409 (обработка уже идёт)

* Если нет записи → создаём IN\_PROGRESS → продолжаем

---

## **3\. Проверка обращения**

* Таблица incident: id, status, direction\_id, version

* Проверяется:

    * Существует → иначе 404

    * Направление соответствует диспетчеру → иначе 403

    * Статус \= NEW → иначе 409

---

## **4\. Проверка бригады**

* Crew Service: id, status, direction\_id, version

* Проверяется:

    * Существует → 404

    * Направление совпадает → 403

    * Статус \= FREE → иначе 409

---

## **5\. Резервирование бригады (Saga step)**

* Отправляется команда ReserveCrewCommand в Crew Service

* Crew Service пытается атомарно обновить: FREE → RESERVED

* В случае успеха → CrewReserved

* В случае fail → CrewReserveFailed

---

## **6\. Создание назначения (assignment)**

* Таблица incident\_assignment:

    * id

    * incident\_id

    * crew\_id

    * status \= WAITING\_CONFIRMATION

    * expires\_at \= now \+ 2 мин

    * assigned\_by \= user\_id

    * workstation\_id

    * created\_at / updated\_at

* Ограничение уникальности активного назначения защищает от гонок

---

## **7\. Обновление обращения**

* Таблица incident: status \= ASSIGNED\_WAITING\_CONFIRMATION, version \+ 1, updated\_at

---

## **8\. Логирование**

* audit\_log: entity\_type \= INCIDENT, action \= INCIDENT\_ASSIGNED, payload \= crew\_id

---

## **9\. Outbox / Notification**

* outbox\_events: aggregate\_type \= ASSIGNMENT, event\_type \= IncidentAssigned

* После commit: Kafka → Notification Service → WebSocket врачу

---

## **10\. Завершение операции**

* Статус Idempotency-Key \= COMPLETED

---

### **Пример ответа**

{  
"assignment\_id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",  
"incident\_id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",  
"crew\_id": "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",  
"status": "WAITING\_CONFIRMATION",  
"expires\_at": "2026-03-04T12:30:00Z"  
}
---

## **Возможные ошибки**

* 401 — пользователь не авторизован

* 403 — недостаточно прав

* 404 — обращение или бригада не найдены

* 409 — обращение уже назначено

* 409 — бригада недоступна

* 409 — повторный Idempotency-Key

* 500 — внутренняя ошибка

---

# **4\. Подтверждение назначения врачом (Accept)**

**POST /v1/assignments/{assignment\_id}/accept**

Логика работы аналогична:

* Идемпотентность через Idempotency-Key

* Проверка таймаута: expires\_at \> now()

* Атомарное обновление статуса: WAITING\_CONFIRMATION → ACCEPTED

* Crew: RESERVED → BUSY

* Incident: ASSIGNED\_WAITING\_CONFIRMATION → IN\_PROGRESS

* Audit, Outbox, Notification

* Если timeout / отказ сработал параллельно → возвращаем 409

---

# **5\. Отказ или таймаут**

* Timeout / Reject → assignment → REJECTED, crew → FREE, incident → NEW

* Это отдельный шаг Saga с компенсацией

---

#  **Ключевые архитектурные моменты**

1. **Saga:** Incident Service — оркестратор, управление всеми шагами распределённого процесса

2. **Compensation:** Reject / Timeout → освобождение бригады, возврат обращения в NEW

3. **Idempotency:** ключи защищают от повторной обработки

4. **Concurrency:** conditional updates \+ partial unique index предотвращают гонки

5. **Outbox pattern:** атомарность записи событий и публикации в Kafka

6. **Асинхронность и eventual consistency:** конечное состояние всегда консистентно, промежуточные шаги могут быть временно несогласованными

7. **Audit:** все действия фиксируются с user\_id и workstation\_id
