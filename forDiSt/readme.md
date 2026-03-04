Отличная задача! Проведу полный рефакторинг OpenAPI спецификации в соответствии с нашей доработанной архитектурой.

## 1. Обновленная OpenAPI спецификация (openapi.yaml)

```yaml
openapi: 3.0.3
info:
  title: Incident Management API
  version: 2.0.0
  description: |
    API для управления назначением обращений на бригады скорой помощи.
    
    Ключевые архитектурные решения:
    - Оркестровая Saga (Incident Service — оркестратор)
    - Идемпотентность через Idempotency-Key
    - Асинхронное взаимодействие через Kafka (Outbox pattern)
    - Оптимистичные блокировки для защиты от race conditions
    - Аудит всех действий с привязкой к пользователю и рабочему месту
    
    Жизненный цикл обращения:
    PENDING_ASSIGNMENT → AWAITING_CONFIRMATION → IN_PROGRESS → COMPLETED

servers:
  - url: https://api.example.com/v1
    description: Production server
  - url: https://staging-api.example.com/v1
    description: Staging server

tags:
  - name: Incidents
    description: Управление обращениями
  - name: Assignments
    description: Управление назначениями
  - name: Crews
    description: Информация о бригадах
  - name: Notifications
    description: Уведомления

paths:

  # ==================== INCIDENTS ====================

  /incidents/{incident_id}/assign:
    post:
      tags: [Incidents]
      summary: Назначение обращения на бригаду
      description: |
        Инициируется диспетчером. Запускает оркестровую сагу:
        1. Проверка прав и идемпотентности
        2. Публикация IncidentAssignmentRequested
        3. Crew Service резервирует бригаду (FREE → RESERVED)
        4. Создание assignment со статусом AWAITING_CONFIRMATION
        5. Запуск таймера на 2 минуты
        
        Бригада получает уведомление через WebSocket.
      operationId: assignIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          description: UUID обращения
          schema:
            type: string
            format: uuid
            example: "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901"
        
        - name: Idempotency-Key
          in: header
          required: true
          description: |
            Уникальный ключ идемпотентности. 
            Должен быть уникальным для каждого пользователя и операции.
            При повторном запросе с тем же ключом возвращается сохраненный ответ.
          schema:
            type: string
            format: uuid
            example: "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11"
        
        - name: X-Workstation-ID
          in: header
          required: true
          description: Идентификатор рабочего места диспетчера (для аудита)
          schema:
            type: string
            format: uuid
            example: "3a7e334f-9210-4f07-b8e1-0f9b8a12c4a1"

      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssignRequest'
            example:
              crew_id: "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1"

      responses:
        '202':
          description: |
            Назначение инициировано, ожидает подтверждения от бригады.
            Статус обращения изменен на AWAITING_CONFIRMATION.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssignmentResponse'
              example:
                assignment_id: "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11"
                incident_id: "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901"
                crew_id: "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1"
                status: "AWAITING_CONFIRMATION"
                expires_at: "2026-03-04T12:30:00Z"
                created_at: "2026-03-04T12:28:00Z"

        '400':
          description: Ошибка валидации запроса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: VALIDATION_ERROR
                message: "Invalid crew_id format"

        '401':
          description: JWT отсутствует или невалиден
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: UNAUTHORIZED
                message: "Authentication required"

        '403':
          description: |
            Роль пользователя не DISPATCHER 
            или направление бригады не совпадает с направлением обращения
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              examples:
                wrongRole:
                  value:
                    code: FORBIDDEN_ROLE
                    message: "User is not a dispatcher"
                directionMismatch:
                  value:
                    code: DIRECTION_MISMATCH
                    message: "Crew direction does not match incident direction"

        '404':
          description: Обращение или бригада не найдены
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              examples:
                incidentNotFound:
                  value:
                    code: INCIDENT_NOT_FOUND
                    message: "Incident not found"
                crewNotFound:
                  value:
                    code: CREW_NOT_FOUND
                    message: "Crew not found"

        '409':
          description: Бизнес-конфликт
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              examples:
                alreadyAssigned:
                  value:
                    code: INCIDENT_ALREADY_ASSIGNED
                    message: "Incident already has an active assignment"
                crewUnavailable:
                  value:
                    code: CREW_NOT_AVAILABLE
                    message: "Crew is not in FREE state"
                idempotencyInProgress:
                  value:
                    code: IDEMPOTENCY_IN_PROGRESS
                    message: "Request with this key is already being processed"
                idempotencyConflict:
                  value:
                    code: IDEMPOTENCY_CONFLICT
                    message: "Idempotency key already used with different request"

        '429':
          description: Слишком много запросов
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: TOO_MANY_REQUESTS
                message: "Rate limit exceeded"

        '500':
          description: Внутренняя ошибка сервиса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: INTERNAL_ERROR
                message: "An unexpected error occurred"

  /incidents/{incident_id}:
    get:
      tags: [Incidents]
      summary: Получение детальной информации об обращении
      description: Возвращает полную информацию об обращении с историей назначений
      operationId: getIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Информация об обращении
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/IncidentDetailResponse'
        '401':
          description: Пользователь не авторизован
        '403':
          description: Нет прав на просмотр обращения
        '404':
          description: Обращение не найдено
        '500':
          description: Внутренняя ошибка

  /incidents:
    get:
      tags: [Incidents]
      summary: Список обращений с фильтрацией
      description: Возвращает список обращений с поддержкой пагинации и фильтров
      operationId: listIncidents
      parameters:
        - name: status
          in: query
          description: Фильтр по статусу
          schema:
            type: string
            enum: [PENDING_ASSIGNMENT, AWAITING_CONFIRMATION, IN_PROGRESS, COMPLETED]
        - name: direction_id
          in: query
          description: Фильтр по направлению
          schema:
            type: string
            format: uuid
        - name: created_from
          in: query
          description: Дата создания от (включительно)
          schema:
            type: string
            format: date-time
        - name: created_to
          in: query
          description: Дата создания до (включительно)
          schema:
            type: string
            format: date-time
        - name: limit
          in: query
          description: Максимальное количество записей
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 50
        - name: offset
          in: query
          description: Смещение для пагинации
          schema:
            type: integer
            minimum: 0
            default: 0
      responses:
        '200':
          description: Список обращений
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/IncidentSummaryResponse'
                  total:
                    type: integer
                    description: Общее количество записей (без учета пагинации)
                  limit:
                    type: integer
                  offset:
                    type: integer
        '401':
          description: Пользователь не авторизован
        '500':
          description: Внутренняя ошибка

  /incidents/{incident_id}/history:
    get:
      tags: [Incidents]
      summary: История действий по обращению
      description: Возвращает аудит-лог всех действий, связанных с обращением
      operationId: getIncidentHistory
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        '200':
          description: История действий
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/AuditLogEntry'
                  total:
                    type: integer
        '401':
          description: Пользователь не авторизован
        '403':
          description: Нет прав на просмотр истории
        '404':
          description: Обращение не найдено
        '500':
          description: Внутренняя ошибка

  /incidents/{incident_id}/complete:
    post:
      tags: [Incidents]
      summary: Завершение обращения
      description: |
        Завершает обращение. Доступно только для врача бригады, 
        выполняющей обращение.
      operationId: completeIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: X-Workstation-ID
          in: header
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Обращение успешно завершено
          content:
            application/json:
              schema:
                type: object
                properties:
                  incident_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [COMPLETED]
                  completed_at:
                    type: string
                    format: date-time
        '401':
          description: Пользователь не авторизован
        '403':
          description: |
            Пользователь не является членом бригады, 
            выполняющей это обращение
        '404':
          description: Обращение не найдено
        '409':
          description: Обращение не в статусе IN_PROGRESS
        '500':
          description: Внутренняя ошибка

  # ==================== ASSIGNMENTS ====================

  /assignments/{assignment_id}/confirm:
    post:
      tags: [Assignments]
      summary: Подтверждение назначения врачом
      description: |
        Подтверждение назначения врачом бригады.
        
        Критически важный метод с защитой от race condition:
        - Используется оптимистичная блокировка (version)
        - Проверяется, что назначение еще не истекло (expires_at > now())
        - Только первый запрос успешно меняет статус
        
        При успехе:
        - Статус назначения: AWAITING_CONFIRMATION → CONFIRMED
        - Статус бригады: RESERVED → BUSY (через событие)
        - Статус обращения: AWAITING_CONFIRMATION → IN_PROGRESS
      operationId: confirmAssignment
      parameters:
        - name: assignment_id
          in: path
          required: true
          description: UUID назначения
          schema:
            type: string
            format: uuid
            example: "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11"
        
        - name: Idempotency-Key
          in: header
          required: true
          schema:
            type: string
            format: uuid
        
        - name: X-Workstation-ID
          in: header
          required: true
          description: Идентификатор рабочего места (планшета)
          schema:
            type: string
            format: uuid

      responses:
        '200':
          description: Назначение успешно подтверждено
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConfirmResponse'
              example:
                assignment_id: "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11"
                incident_id: "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901"
                status: "CONFIRMED"
                confirmed_at: "2026-03-04T12:29:30Z"

        '400':
          description: Ошибка валидации
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ASSIGNMENT_EXPIRED
                message: "Assignment confirmation window has expired"

        '401':
          description: Пользователь не авторизован
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

        '403':
          description: |
            Пользователь не является членом данной бригады
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: FORBIDDEN_OPERATION
                message: "User is not a member of the assigned crew"

        '404':
          description: Назначение не найдено
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ASSIGNMENT_NOT_FOUND
                message: "Assignment not found"

        '409':
          description: |
            Конфликт состояния назначения.
            Возникает при race condition между подтверждением и таймаутом.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              examples:
                alreadyProcessed:
                  value:
                    code: ASSIGNMENT_ALREADY_PROCESSED
                    message: "Assignment has already been confirmed or rejected"
                versionMismatch:
                  value:
                    code: CONCURRENT_MODIFICATION
                    message: "Assignment was modified by another request"
                idempotencyConflict:
                  value:
                    code: IDEMPOTENCY_CONFLICT
                    message: "Duplicate request detected"

        '500':
          description: Внутренняя ошибка сервиса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /assignments/{assignment_id}/reject:
    post:
      tags: [Assignments]
      summary: Отказ от назначения врачом
      description: |
        Отказ врача от принятия назначения.
        
        Также вызывается автоматически при истечении таймера (2 минуты).
        Запускает компенсирующие транзакции Saga:
        - Статус назначения: REJECTED
        - Бригада: RESERVED → FREE
        - Обращение: AWAITING_CONFIRMATION → PENDING_ASSIGNMENT
      operationId: rejectAssignment
      parameters:
        - name: assignment_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
        
        - name: X-Workstation-ID
          in: header
          required: true
          schema:
            type: string
            format: uuid

      requestBody:
        required: false
        content:
          application/json:
            schema:
              type: object
              properties:
                reason:
                  type: string
                  enum: [CREW_REJECTED, TIMEOUT, CREW_UNAVAILABLE]
                  default: CREW_REJECTED
                comment:
                  type: string
                  maxLength: 500
                  description: Комментарий к отказу (опционально)

      responses:
        '200':
          description: Отказ зарегистрирован
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RejectResponse'
              example:
                assignment_id: "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11"
                incident_id: "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901"
                status: "REJECTED"
                reason: "CREW_REJECTED"
                rejected_at: "2026-03-04T12:31:00Z"

        '401':
          description: Пользователь не авторизован
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

        '403':
          description: |
            Нет прав на отклонение назначения
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

        '404':
          description: Назначение не найдено
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

        '409':
          description: Назначение уже обработано
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: ASSIGNMENT_ALREADY_PROCESSED
                message: "Assignment already confirmed or rejected"

        '500':
          description: Внутренняя ошибка сервиса
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  # ==================== CREWS ====================

  /crews:
    get:
      tags: [Crews]
      summary: Список бригад с фильтрацией
      description: Возвращает список бригад, доступных для назначения
      operationId: listCrews
      parameters:
        - name: status
          in: query
          description: Фильтр по статусу бригады
          schema:
            type: string
            enum: [FREE, RESERVED, BUSY, OFFLINE]
        - name: direction_id
          in: query
          description: Фильтр по направлению
          schema:
            type: string
            format: uuid
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        '200':
          description: Список бригад
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/CrewResponse'
                  total:
                    type: integer
        '401':
          description: Пользователь не авторизован
        '500':
          description: Внутренняя ошибка

  # ==================== NOTIFICATIONS ====================

  /notifications:
    get:
      tags: [Notifications]
      summary: Список уведомлений пользователя
      description: Возвращает историю уведомлений для текущего пользователя
      operationId: listNotifications
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [NEW, SENT, ACKED, FAILED]
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        '200':
          description: Список уведомлений
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/NotificationResponse'
                  total:
                    type: integer
        '401':
          description: Пользователь не авторизован
        '500':
          description: Внутренняя ошибка

  /notifications/ack:
    post:
      tags: [Notifications]
      summary: Подтверждение получения уведомления
      description: |
        WebSocket endpoint для подтверждения доставки уведомления.
        Реализует механизм exactly-once delivery.
      operationId: ackNotification
      parameters:
        - name: X-WebSocket-Session-ID
          in: header
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - notification_id
              properties:
                notification_id:
                  type: string
                  format: uuid
                acked_at:
                  type: string
                  format: date-time
      responses:
        '200':
          description: Подтверждение принято
        '401':
          description: Невалидная WebSocket сессия
        '404':
          description: Уведомление не найдено
        '500':
          description: Внутренняя ошибка

  /notifications/heartbeat:
    post:
      tags: [Notifications]
      summary: Heartbeat для поддержания WebSocket сессии
      description: Периодически вызывается клиентом для подтверждения активности
      operationId: heartbeat
      parameters:
        - name: X-WebSocket-Session-ID
          in: header
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Heartbeat принят
        '401':
          description: Сессия не найдена или истекла
        '500':
          description: Внутренняя ошибка

components:

  schemas:

    # ========== REQUEST SCHEMAS ==========

    AssignRequest:
      type: object
      description: Запрос на назначение обращения бригаде
      required:
        - crew_id
      properties:
        crew_id:
          type: string
          format: uuid
          description: Идентификатор бригады
          example: "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1"
        comment:
          type: string
          maxLength: 500
          description: Комментарий диспетчера (опционально)
          example: "Срочный вызов, пациент в тяжелом состоянии"

    # ========== RESPONSE SCHEMAS ==========

    AssignmentResponse:
      type: object
      description: Ответ на успешное создание назначения
      required:
        - assignment_id
        - incident_id
        - crew_id
        - status
        - expires_at
        - created_at
      properties:
        assignment_id:
          type: string
          format: uuid
          description: Уникальный идентификатор назначения
        incident_id:
          type: string
          format: uuid
          description: Идентификатор обращения
        crew_id:
          type: string
          format: uuid
          description: Идентификатор назначенной бригады
        status:
          type: string
          enum: [AWAITING_CONFIRMATION]
          description: Статус назначения
        expires_at:
          type: string
          format: date-time
          description: Время истечения таймера подтверждения (через 2 минуты)
        created_at:
          type: string
          format: date-time
          description: Время создания назначения

    ConfirmResponse:
      type: object
      description: Ответ на успешное подтверждение назначения
      required:
        - assignment_id
        - incident_id
        - status
        - confirmed_at
      properties:
        assignment_id:
          type: string
          format: uuid
        incident_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [CONFIRMED]
        confirmed_at:
          type: string
          format: date-time
        confirmed_by:
          type: string
          format: uuid
          description: Идентификатор подтвердившего врача

    RejectResponse:
      type: object
      description: Ответ на отклонение назначения
      required:
        - assignment_id
        - incident_id
        - status
        - reason
        - rejected_at
      properties:
        assignment_id:
          type: string
          format: uuid
        incident_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [REJECTED]
        reason:
          type: string
          enum: [CREW_REJECTED, TIMEOUT, CREW_UNAVAILABLE]
        rejected_at:
          type: string
          format: date-time
        comment:
          type: string
          description: Комментарий к отказу (если был)

    IncidentSummaryResponse:
      type: object
      description: Краткая информация об обращении (для списка)
      required:
        - id
        - patient_id
        - direction_id
        - status
        - created_at
      properties:
        id:
          type: string
          format: uuid
        patient_id:
          type: string
          format: uuid
        direction_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [PENDING_ASSIGNMENT, AWAITING_CONFIRMATION, IN_PROGRESS, COMPLETED]
        priority:
          type: string
          enum: [LOW, MEDIUM, HIGH, CRITICAL]
          description: Срочность обращения
        created_at:
          type: string
          format: date-time
        current_assignment:
          type: object
          nullable: true
          properties:
            id:
              type: string
              format: uuid
            crew_id:
              type: string
              format: uuid
            status:
              type: string
              enum: [AWAITING_CONFIRMATION, CONFIRMED, REJECTED]
            expires_at:
              type: string
              format: date-time
              nullable: true

    IncidentDetailResponse:
      allOf:
        - $ref: '#/components/schemas/IncidentSummaryResponse'
        - type: object
          properties:
            payload:
              type: object
              description: Детальная информация об обращении (симптомы, заметки и т.д.)
              example:
                symptoms: ["Острая боль в груди", "Одышка"]
                consciousness: "CLEAR"
                breathing: "DIFFICULT"
            assignments_history:
              type: array
              description: История всех попыток назначения
              items:
                type: object
                properties:
                  id:
                    type: string
                    format: uuid
                  crew_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [AWAITING_CONFIRMATION, CONFIRMED, REJECTED]
                  created_at:
                    type: string
                    format: date-time
                  resolved_at:
                    type: string
                    format: date-time
                    nullable: true
                  reject_reason:
                    type: string
                    enum: [CREW_REJECTED, TIMEOUT, CREW_UNAVAILABLE]
                    nullable: true
            updated_at:
              type: string
              format: date-time
            version:
              type: integer
              description: Версия для оптимистичной блокировки

    CrewResponse:
      type: object
      description: Информация о бригаде
      required:
        - id
        - direction_id
        - status
        - members_count
      properties:
        id:
          type: string
          format: uuid
        direction_id:
          type: string
          format: uuid
        name:
          type: string
          description: Название/номер бригады
        status:
          type: string
          enum: [FREE, RESERVED, BUSY, OFFLINE]
        members_count:
          type: integer
          description: Количество сотрудников в бригаде
        current_incident_id:
          type: string
          format: uuid
          nullable: true
          description: Текущее обращение (если статус BUSY)
        updated_at:
          type: string
          format: date-time
        version:
          type: integer
          description: Версия для оптимистичной блокировки

    NotificationResponse:
      type: object
      description: Уведомление пользователя
      required:
        - id
        - type
        - payload
        - status
        - created_at
      properties:
        id:
          type: string
          format: uuid
        type:
          type: string
          enum: [ASSIGNMENT_REQUESTED, ASSIGNMENT_CONFIRMED, ASSIGNMENT_REJECTED, SYSTEM_ALERT]
        payload:
          type: object
          description: Данные уведомления
          example:
            assignment_id: "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11"
            incident_id: "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901"
            expires_at: "2026-03-04T12:30:00Z"
        status:
          type: string
          enum: [NEW, SENT, ACKED, FAILED]
        created_at:
          type: string
          format: date-time
        delivered_at:
          type: string
          format: date-time
          nullable: true
        acknowledged_at:
          type: string
          format: date-time
          nullable: true

    AuditLogEntry:
      type: object
      description: Запись аудита
      required:
        - id
        - entity_type
        - entity_id
        - action
        - performed_by
        - workstation_id
        - created_at
      properties:
        id:
          type: string
          format: uuid
        entity_type:
          type: string
          enum: [INCIDENT, ASSIGNMENT, CREW]
        entity_id:
          type: string
          format: uuid
        action:
          type: string
          enum: [CREATED, ASSIGNED, CONFIRMED, REJECTED, COMPLETED, STATUS_CHANGED]
        performed_by:
          type: string
          format: uuid
          description: Идентификатор пользователя
        workstation_id:
          type: string
          format: uuid
          description: Идентификатор рабочего места
        idempotency_key:
          type: string
          format: uuid
          description: Ключ идемпотентности запроса (для трассировки)
        payload:
          type: object
          description: Дополнительные данные действия
        created_at:
          type: string
          format: date-time

    # ========== ERROR SCHEMAS ==========

    ErrorResponse:
      type: object
      description: Стандартный формат ошибки
      required:
        - code
        - message
      properties:
        code:
          type: string
          enum:
            # Authentication & Authorization
            - UNAUTHORIZED
            - FORBIDDEN_ROLE
            - DIRECTION_MISMATCH
            - FORBIDDEN_OPERATION
            
            # Not Found
            - INCIDENT_NOT_FOUND
            - ASSIGNMENT_NOT_FOUND
            - CREW_NOT_FOUND
            - NOTIFICATION_NOT_FOUND
            
            # Business Logic Conflicts
            - INCIDENT_ALREADY_ASSIGNED
            - INCIDENT_INVALID_STATUS
            - CREW_NOT_AVAILABLE
            - ASSIGNMENT_EXPIRED
            - ASSIGNMENT_ALREADY_PROCESSED
            
            # Concurrency & Idempotency
            - IDEMPOTENCY_IN_PROGRESS
            - IDEMPOTENCY_CONFLICT
            - CONCURRENT_MODIFICATION
            
            # Validation
            - VALIDATION_ERROR
            
            # Rate Limiting
            - TOO_MANY_REQUESTS
            
            # System
            - INTERNAL_ERROR
            - SERVICE_UNAVAILABLE
        message:
          type: string
          description: Человекочитаемое описание ошибки
        details:
          type: object
          description: Дополнительная информация (опционально)
          example:
            field: "crew_id"
            reason: "Crew is already BUSY"
        request_id:
          type: string
          format: uuid
          description: Идентификатор запроса для поддержки
        timestamp:
          type: string
          format: date-time
          description: Время возникновения ошибки

  # ========== SECURITY SCHEMES ==========

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: |
        JWT токен, полученный при авторизации.
        Содержит информацию о пользователе, его роли и направлении.

security:
  - bearerAuth: []
```

## 2. Ключевые изменения в OpenAPI спецификации

### Что добавлено/улучшено:

| Компонент | Изменения | Обоснование |
|-----------|-----------|-------------|
| **Статусы** | `WAITING_CONFIRMATION` → `AWAITING_CONFIRMATION`<br>`ACCEPTED` → `CONFIRMED` | Устранение дублирования и семантическая точность |
| **HTTP статусы** | `201` → `202` для `/assign` | Более корректно, т.к. операция асинхронная |
| **X-Workstation-ID** | Добавлен во все методы | Требование аудита с привязкой к рабочему месту |
| **ErrorResponse** | Расширен набор кодов ошибок | Конкретные ошибки для каждого бизнес-сценария |
| **Детальные схемы** | `IncidentDetailResponse`, `AuditLogEntry` | Полная информация для клиентов |
| **WebSocket** | Добавлены `/notifications/ack` и `/heartbeat` | Exactly-once delivery и поддержка сессий |
| **Idempotency** | Явное описание поведения в 409 ошибках | Понятно клиентам, что делать |

## 3. Обновленный README.md (с учетом всех изменений)

```markdown
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
```sql
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
```sql
-- Фоновый процесс для очистки зависших idempotency ключей
UPDATE idempotency_keys
SET status = 'FAILED'
WHERE status = 'IN_PROGRESS' 
  AND saga_timeout < NOW();

-- Для каждого такого ключа отправляем компенсирующее событие
-- (если бригада была зарезервирована, но мы не получили CrewReserved)
```

### 3.3 Примеры ответов

#### Успешное назначение (202 Accepted)
```json
{
  "assignment_id": "b21a9f6e-7c14-4d3f-bc9c-12f32acb4e11",
  "incident_id": "9f83d9b1-1b62-4c4f-8e4e-6bfc84f1d901",
  "crew_id": "6a7e334f-9210-4f07-b8e1-0f9b8a12c4a1",
  "status": "AWAITING_CONFIRMATION",
  "expires_at": "2026-03-04T12:30:00Z",
  "created_at": "2026-03-04T12:28:00Z"
}
```

#### Ошибка Race Condition (409 Conflict)
```json
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
```

#### Детали обращения с историей
```json
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

---

## 4. Топики Kafka (обновленные)

| Топик | Тип события | Продюсер | Консьюмеры | Описание |
|-------|-------------|----------|------------|----------|
| **incident.assignments.requested** | `IncidentAssignmentRequested` | Incident Service | Crew Service | Запрос на резервирование бригады |
| **crew.reservation.events** | `CrewReserved` / `CrewReservationFailed` | Crew Service | Incident Service | Результат резервирования |
| **incident.assignments.lifecycle** | `IncidentAwaitingConfirmation` / `IncidentInProgress` / `IncidentPendingAssignment` | Incident Service | Notification Service | Изменения статуса обращения |
| **assignment.confirmed** | `AssignmentConfirmed` | Incident Service | Crew Service | Врач подтвердил назначение |
| **assignment.rejected** | `AssignmentRejected` | Incident Service | Crew Service | Отказ или таймаут |
| **crew.status.updated** | `CrewBecameBusy` / `CrewBecameFree` | Crew Service | Incident Service | Изменения статуса бригады |
| **notification.events** | Все события для уведомлений | Все сервисы | Notification Service | События, требующие уведомлений |

---

