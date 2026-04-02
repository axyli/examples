# docflow.recognition-docs-crud

## Назначение
Сервис ведения распознавания документов

## Тип микросервиса
Общий внутренний сервис

## Интеграция
- БД
- REST на входе
- REST на выходе
- на выход журнал Scans сообщение remove_pages

## Логика работы
### Установка блокировки и разблокировки документа (POST /v1/docs/{uuid}/lock)
1. сервис получает идентификатор документа и признак блокировки
2. в таблице docflow.doc_locks проверяется последняя запись по документу
3. если значение поля is_locked совпадает с полученным lock, то никаких действий не выполняется
4. если записей не найдено или значения не совпадают, то добавляется запись в таблицу doc_locks
* uuid        генерируется новый уникальный идентификатор
* domain_uuid указывается домен документа
* doc_uuid    идентификатор документа из входных данных
* worker_uuid идентификатор пользователя из токена
* is_locked   входящее значение lock

Пример запроса:  
`/v1/docs/bbea9b8d-5c0a-44e1-a38f-67028fad33e9/lock`

Пример тела запроса:  
```
{
  "lockBoolean": true
}
```

### Установка признака документа "Валидный" (POST /v1/docs/{uuid}/validate)
1. сервис получает идентификатор документа  
2. в таблице docflow.docs проверяется статус status  
3. если статус разрешает валидацию (равен ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, INVALID) то  
3.1. создать запись в таблице doc_actions. Заполнение полей  
* uuid - сформировать уникальный uuid  
* domain_uuid - домен документа  
* doc_uuid - полученный идентификатор документа  
* action - константа MANUAL_VALIDATED  
* worker_uuid - идентификатор пользователя из токена  
* comment - текст "Смена статуса с <docflow.docs.status> на MANUAL_VALIDATED"  
3.2. установить статус VALID  
4. иначе значение не меняет  

Пример запроса:  
`/v1/docs/bbea9b8d-5c0a-44e1-a38f-67028fad33e9/validate`

### Установка признака документа "Невалидный" и отмена установки признака (POST /v1/docs/{uuid}/invalidate)
1. сервис получает идентификатор документа, причину и комментарий  
2. в таблице docflow.docs проверяется статус status  
3. если статус разрешает установку невалидный (равен ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, VALID, AUTO_VERIFIED_WITH_ERRORS) то  
3.1. сохраняет историю в таблице doc_actions. Заполнение полей  
* uuid - сформировать уникальный uuid  
* domain_uuid - домен документа  
* doc_uuid - полученный идентификатор документа  
* action - константа INVALIDATED  
* worker_uuid - идентификатор пользователя из токена  
* comment - текст "Смена статуса с <docflow.docs.status> на INVALIDATED. Причина <docflow.invalidation_reasons.title>. Комментарий comment"    
3.2. в поле docflow.docs.invalidation_reason_uuid записать причину невалидности reason_uuid    
  3.3. установить статус INVALID  
  3.4. если по заказу получен trips.client_uuid, то  
    3.4.1 выбрать значения trips.contractor_uuid, trips.uuid, docs.type_uuid  
    3.4.2 в журнал notification.in передать сообщение doc-client-invalidate  
4. иначе значение не меняет  

Пример запроса:  
`/v1/docs/bbea9b8d-5c0a-44e1-a38f-67028fad33e9/invalidate`  

Пример тела запроса: 
```
{
  "reason_uuid": "44f5f38a-3f28-449f-b9a4-69c485602bc7",
  "comment": "Отсутствует штрихкод"
}
```


### Сохранение типа документа в парсере документа (POST /v1/docs/{uuid}/type)  
1. сервис получает идентификатор документа и тип документа  
2. в таблице docflow.docs проверяется значение поля type_uuid  
3. если type_uuid не равен типу документа в параметрах, то   
  3.1. выгружает набор полей для указанного типа документа из таблицы docflow.doc_field_settings  
  3.2. сохраняет историю в таблицу doc_contents. Заполнение полей  
    uuid - сформировать уникальный uuid  
    domain_uuid - домен документа  
    doc_uuid - полученный идентификатор документа  
    status - константа MANUAL_CORRECTED  
    updater_type - константа WORKER  
    worker_uuid - идентификатор пользователя из токена  
    content - копируется предыдущий контент, дополняется перечнем полей из doc_field_settings, и заполняется тип документа (uuid)  
    search_content - аналогично content  
  3.3. is_active - константа true. Если есть другие записи с true по этому же документу, их перевести в false  
  3.4. в таблице docflow.docs устанавливает type_uuid равным полученному значению  
4. иначе значение не меняет  

Пример запроса:
`/v1/docs/44f5f38a-3f28-449f-b9a4-69c485602bc7/type`

Пример тела запроса:
```
{
  "type_uuid": "44f5f38a-3f28-449f-b9a4-69c485602bc7"
}
```


### Удаление документа и отмена удаления (DELETE /v1/docs/{uuid})
1. сервис получает идентификатор документа  
2. в таблицах docflow.scanned_docs и docflow.docs проверяется значение поля is_deleted  
3. если is_deleted = null, то устанавливает значение в true  
4. иначе значение не меняет  

Примечание для фронта  
  Запрос передается с фронта на бэк в следующих случаях  
  * через определенное количество секунд  
  * после нажатия какой-либо кнопки в интерфейсе  
  * при закрытии окна  

Пример запроса:
`/v1/docs/44f5f38a-3f28-449f-b9a4-69c485602bc7`

### Сохранение статуса "Отложить" по документу (POST /v1/docs/{uuid}/postpone)
1. сервис получает идентификатор документа и массив значений полей документа  
2. в таблице docflow.scanned_docs находится запись по uuid и проверяется значение поля status  
3. если status допускает переход в отложено (значения AUTO_VERIFIED_WITH_ERRORS или ON_MANUAL_VERIFICATION)  
  3.1. обновляет значение статуса (status) в ON_MANUAL_VERIFICATION_POSTPONED  
  3.2. сохраняет в таблицу doc_contents. Заполнение полей  
    uuid - сформировать уникальный uuid  
    domain_uuid - домен документа  
    doc_uuid - полученный идентификатор документа doc_uuid  
    status - константа MANUAL_CORRECTED  
    updater_type - константа WORKER  
    worker_uuid - идентификатор пользователя из токена  
    content - сохраняется полученный массив DocContent  
    search_content - аналогично content  
  3.3. is_active - константа true. Если есть другие записи с true по этому же документу, их перевести в false  
4. иначе значение не меняется  
Примечание для фронта  
  После нажатия кнопки "Отложить" вначале выполняется сохранение параметров документа (PUT /v1/additional_data/<uuid>) и потом запускается текущий запрос  

Пример запроса:
`/v1/docs/44f5f38a-3f28-449f-b9a4-69c485602bc7/postpone`

Пример тела запроса:
```
{
  "docContent": [
    {
      "uuid": "81d1a6a6-dd48-4248-bfa9-62d3462ef6bf",
      "value": "ООО Ромашка",
      "check": true
    }
  ]
}
```

### Сохранение номера заказа в парсере документа (POST /v1/trip_number/{uuid})
1. сервис получает идентификатор документа, номер заказа поставщика и массив значений полей документа  
2. в таблице docflow.docs находит значение по uuid и проверяется значение поля trip_uuid  
3. если trip_uuid в таблице не равно полученному значению  
  3.1. сохраняет в таблицу doc_contents. Заполнение полей  
    uuid - сформировать уникальный uuid  
    domain_uuid - домен документа  
    doc_uuid - полученный идентификатор документа doc_uuid  
    status - константа MANUAL_CORRECTED  
    updater_type - константа WORKER  
    worker_uuid - идентификатор пользователя из токена  
    content - сохраняется полученный массив DocContent  
    search_content - аналогично content  
  3.2. is_active - константа true. Если есть другие записи с true по этому же документу, их перевести в false  
  3.3. записывает в таблицу docs полученный trip_uuid
4. если trip_uuid равно полученному значению, то никаких действий не выполняется  

Пример запроса:
`/v1/trip_number/41576fb6-380c-4da2-8178-4e2441b69063`

Пример тела запроса:
```
{
  "trip_uuid": "44f5f38a-3f28-449f-b9a4-69c485602bc7",
  "docContent": [
    {
      "uuid": "81d1a6a6-dd48-4248-bfa9-62d3462ef6bf",
      "value": "ООО Ромашка",
      "check": true
    }
  ]
}
```

### Сохранение вручную измененных данных полей в парсере документа (POST /v1/additional_data)
1. сервис получает массив значений полей документа  
2. сохраняет в таблицу doc_contents. Заполнение полей  
    uuid - сформировать уникальный uuid  
    domain_uuid - домен документа  
    doc_uuid - полученный идентификатор документа doc_uuid  
    status - константа MANUAL_CORRECTED  
    updater_type - константа WORKER  
    worker_uuid - идентификатор пользователя из токена  
    content - сохраняется полученный массив Content  
    search_content - аналогично content  

Пример запроса:
`/v1/additional_data`

Пример тела запроса:
```
{
  "doc_uuid": "44f5f38a-3f28-449f-b9a4-69c485602bc7",
  "docContent": [
    {
      "uuid": "81d1a6a6-dd48-4248-bfa9-62d3462ef6bf",
      "value": "ООО Ромашка",
      "check": true
    }
  ]
}
```

### Получение дополнительных полей документа из парсера по идентификатору документа (GET /v1/additional_data/{uuid})
1. сервис получает идентификатор документа  
2. выполняет запрос формирования эталонных значений полей документа (docflow.etalon-doc-viewer). На вход передает идентификатор документа  
4. запрос возвращает идентификатор поля, наименование, значение из заказа  
5. выполняет поиск самой ранней записи в таблице doc_contents по идентификатору документа (recognize)  
6. выполняет поиск активной записи в таблице doc_contents по идентификатору документа (modified)  
7. объединяет полученные данные эталонных значений и recognize.content(value), modified.content(value), modified.content(check). Перечень полей устанавливается на основе самой ранней версии распознования: recognize. Если в заказе присутствуют дополнительные поля - они игнорируются. Если по части полей отсутствует информация в заказе - то указывается пустое значение.
8. возвращает данные в массиве  
Фронт на основании полученного ответа выполняет признак сверки. Если установлен признак сверки (check), то считает что поле подтверждено пользователем и не блокирует признание документа валидным/невалидным.  
Фронт исключает поля "Штрих-код" и "Вид документа" из списка отражения, так как внесение изменений в данные поля возможно только в заголовке и подразумевает запуски отдельных запросов  

Пример ответа:
```
[
  {
    "uuid": "5d06bedd-0236-439b-be20-e4f67c1eca79",
    "title": "Госномер",
    "fieldOrder": "В658АС716",
    "fieldRecognize": "В688АС716",
    "fieldModified": "В658АС716",
    "check": "true"
  }
]
```

### Получение основных данных документа из парсера по идентификатору документа (GET /v1/main_data/{uuid})
1. сервис получает идентификатор документа  
2. из таблицы docs выбирает штрих-код (barcode), дата сканирования (created_at), тип документа (doc_types.title), номер заказа  
3. возвращает данные  

Пример ответа:
```
{
  "barcode": "23423432",
  "created": "2016-11-21T08:00:00.000Z",
  "docType": "BUYER",
  "orderNumber": "PO19 092 8761"
}
```


### Получение заказов для документа с фильтрацией (POST /odata/v1/listOrders?$filter={parameter_filter}&$orderby={parameter_order}&$top={parameter_top}&$skip={parameter_skip})
1. Передать объект Order в запрос по поиску заказов (микросервис docflow.order) и параметры смещения и общего количества записей  
2. Полученный ответ передать в объект ListOrders  
3. Вернуть ListOrders в ответ  

Запрос работает с форматом oData

Пример запроса:
`odata/v1/listOrders?$filter=type%20eq%20%27BUYER%27&$orderby=pickup_date_plan%20desc&$top=100&$skip=10`

Пример ответа:
```
[
  {
    "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "type": "BUYER",
    "number": "PO19 092 8761",
    "status": "EXECUTED",
    "created": "2016-11-21T08:00:00.000Z",
    "from": "Беларусь, г.Минск",
    "to": "Беларусь, г.Пушкино",
    "pickup_date_plan": "2016-11-21T08:00:00.000Z",
    "pickup_date_actual": "2016-11-21T08:00:00.000Z",
    "internal_number": "09287618",
    "executor": "ООО “Ромашка”",
    "logist": "Ковалев П.А.",
    "customer_title": "ООО”Марс”"
  }
]
```


### Сохранение изъятия страниц из документа и отмена (PUT /v1/page_remove/{doc_uuid})
1. Запрос получает на вход идентификатор документа и перечень страниц для удаления  
2. Формируется сообщение remove_pages в журнал docflow.scans. Сообщение содержит идентификатор документа и список страниц

Запрос передается с фронта на бэк в следующих случаях  
    через определенное количество секунд  
    после нажатия какой-либо кнопки в интерфейсе  
    при закрытии окна  

Пример запроса:
`/v1/page_remove/df974953-b7c9-41dd-8577-8565b6efd866`

Пример тела запроса:
```
[
  {
    "number": 3
  }
]
```


### Получение консолидированных данных по отклонениям (GET /v1/rejection)
1. Из токена выбрать uuid пользователя и по нему определить домен (выбрать users.contractor_uuid и по uuid найти в таблице домен domains.participant_domain_records.domain_uuid)  
2. Собрать данные по отклонениям с учетом видимости по домену (domain_uuid в таблицах docs и scanned_docs равен входящему домену)  
•	Отсутствующие (absent_count)  
посчитать количество записей в таблице docflow.docs, где запись не удалена (is_deleted = false) и статус утерян (status = ABSENT)  
•	ШК невалиден (bad_barcode_count)  
посчитать количество записей в таблице docflow.scanned_docs со статусом штрих-код не распознан (status = BAD_BARCODE) и запись не удалена (is_deleted = false)  
•	Типизация (absent_type_count)    
посчитать количество записей в таблице docflow.scanned_docs, где запись не удалена (is_deleted = false), статус на ручном распозновании (status in ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, AUTO_VERIFIED_WITH_ERRORS) и поле docs.type_uuid пустое. Таблицы scanned_docs и docs содержат одинаковый uuid  
•	Определение заказа (absent_trip_count)  
посчитать количество записей в таблице docflow.scanned_docs, где запись не удалена (is_deleted = false), статус на ручном распозновании (status in ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, AUTO_VERIFIED_WITH_ERRORS), поле docs.type_uuid не пустое и поле docs.trip_uuid пустое. Таблицы scanned_docs и docs содержат одинаковый uuid  
•	Ручная проверка (manual_count)  
посчитать количество записей в таблице docflow.scanned_docs, где запись не удалена (is_deleted = false), статус на ручном распозновании (status in ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, AUTO_VERIFIED_WITH_ERRORS), поле docs.type_uuid не пустое и поле docs.trip_uuid не пустое. Таблицы scanned_docs и docs содержат одинаковый uuid  
3. Вернуть количество документов в ответ  

Пример тела ответа:
```
{
  "absent_count": 13,
  "bad_barcode_count": 17,
  "absent_type_count": 17,
  "absent_trip_count": 17,
  "manual_count": 17
}
```


### Получение списка документов по конкретному отклонению (GET /v1/docs_list_rejected/{reject_type}/{offset}/{limit})
1. Из токена выбрать uuid пользователя и по нему определить домен (выбрать users.contractor_uuid и по uuid найти в таблице домен domains.participant_domain_records.domain_uuid)  
2. Анализ типа отклонения (reject_type) - должен быть один из (absent, bad_barcode, absent_type, absent_trip, manual). Иначе вернуть ошибку  
3. В зависимости от типа отклонения (reject_type) сформировать список документов (doc_uuid) с учетом ограничений offset, limit и домен  
    absent (Отсутствующие)  
        вернуть список uuid из таблицы docflow.docs, где запись не удалена (is_deleted = false) и статус утерян (status = ABSENT)  
    bad_barcode (ШК невалиден)  
        вернуть список uuid из таблицы docflow.scanned_docs со статусом штрих-код не распознан (status = BAD_BARCODE) и запись не удалена (is_deleted = false)  
    absent_type (Типизация)  
        вернуть список uuid из таблицы docflow.scanned_docs, где запись не удалена (is_deleted = false), статус на ручном распозновании (status in ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, AUTO_VERIFIED_WITH_ERRORS, AUTO_RECOGNIZED_WITH_ERRORS) и поле docs.type_uuid пустое. Таблицы scanned_docs и docs содержат одинаковый uuid  
    absent_trip (Определение заказа)  
        вернуть список uuid из таблицы docflow.scanned_docs, где запись не удалена (is_deleted = false), статус на ручном распозновании (status in ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, AUTO_VERIFIED_WITH_ERRORS, AUTO_RECOGNIZED_WITH_ERRORS), поле docs.type_uuid не пустое и поле docs.trip_uuid пустое. Таблицы scanned_docs и docs содержат одинаковый uuid  
    manual (Ручная проверка)  
        вернуть список uuid из таблицы docflow.scanned_docs, где запись не удалена (is_deleted = false), статус на ручном распозновании (status in ON_MANUAL_VERIFICATION, ON_MANUAL_VERIFICATION_POSTPONED, AUTO_VERIFIED_WITH_ERRORS, AUTO_RECOGNIZED_WITH_ERRORS), поле docs.type_uuid не пустое и поле docs.trip_uuid не пустое. Таблицы scanned_docs и docs содержат одинаковый uuid  
4. Выбрать данные для ответа. Основная таблица docflow.docs. В ЛЮБОЙ друрой таблице данных может быть не найдено  
    Идентификатор документа (uuid) - docs.uuid  
    ШК/ № документа (barcode) - docs.barcode  
    Тип документа (doc_type) - doc_types.title (связаны по type_uuid)  
    № PO (po_number) - trips.po_number (связаны по trip_uuid)  
    Автор (fio_action) - из первой записи в таблице doc_actions по данному документу выбрать worker_uuid и вернуть ФИО из представления docflow.users   
    Кем отложено (fio_postponed) - если статус отложено (scanned_docs.status = ON_MANUAL_VERIFICATION_POSTPONED), то указать ФИО из представления docflow.users. Идентификатор пользователя worker_uuid из таблицы doc_contents, где запись активна по документу.  
    Дата и время выявления отклонения (reject_time) - в зависимости от типа отклонения (reject_type) определить время отклонения  
        absent (Отсутствующие)  
            последняя запись по документу в таблице docflow.doc_actions где action = LOSTED  
        bad_barcode (ШК невалиден)  
            последняя запись по документу в таблице docflow.doc_actions где action = AUTO_INVALIDATED  
        absent_type (Типизация)  
            последняя запись по документу в таблице docflow.doc_actions где action = AUTO_INVALIDATED  
        absent_trip (Определение заказа)  
            последняя запись по документу в таблице docflow.doc_actions где action = AUTO_INVALIDATED  
        manual (Ручная проверка)  
            последняя запись по документу в таблице docflow.doc_actions где action = AUTO_INVALIDATED  
    Когда открыт (lock_time) - из таблицы docflow.doc_locks (запись активна и не удалена) выбрать время created_at  
    Кем открыт (fio_lock)- по таблице docflow.doc_locks (запись активна и не удалена) найти пользователя worker_uuid и вернуть ФИО из представления docflow.users   
    Ячейка (cell_code) - по таблице doc_warehouse.cell_objects найти ячейку и вернуть код doc_warehouse.cells.code   
5. Вернуть DocsListRejected в ответ  

Пример запроса:
`/v1/docs_list_rejected/bad_barcode/1/100`

Пример ответа:
```
[
  {
    "uuid": "0b5db68b-db8c-45ab-9ba5-a77eea29db90",
    "barcode": "34095734097580",
    "doc_type": "Счёт",
    "po_number": "1237532-238",
    "fio_action": "Петренко А.В.",
    "fio_postponed": "Сидоров А.А.",
    "reject_time": "2016-11-21T08:00:00.000Z",
    "lock_time": "2016-11-21T08:00:00.000Z",
    "fio_lock": "Тимофеев В.Н.",
    "cell_code": "124.55.22"
  }
]
```

## Таблицы PostgreSQL
* [docflow.doc_types](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/doc_types.sql)
* [docflow.doc_contents](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/doc_contents.sql)
* [docflow.scanned_docs](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/scanned_docs.sql)
* [docflow.doc_locks](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/doc_locks.sql)
* [docflow.docs](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/docs.sql)
* [docflow.doc_actions](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/doc_actions.sql)
* [docflow.invalidation_reasons](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/invalidation_reasons.sql)
* [docflow.doc_field_settings](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/doc_field_settings.sql)
* [docflow.users](https://gitlab.blalala.com/blablabla/database-structure/blob/analytics/db/docflow/views/users.sql)
* [docflow.etalon-doc-viewer](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/etalon-doc-viewer.sql)
* [docflow.scanned_doc_field_settings](https://gitlab.blalala.com/blablabla/database-structure/blob/feature-541/db/docflow/scanned_doc_field_settings.sql)
* [domains.participant_domain_records](https://gitlab.blalala.com/blablabla/database-structure/blob/analytics/db/domains/views/participant_domain_records.sql)