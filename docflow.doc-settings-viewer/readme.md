# docflow.doc-settings-viewer

## Назначение
Сервис просмотра допустимых значений полей

## Тип микросервиса
Общий внутренний сервис

## Интеграция
- БД
- REST на входе

## Методы REST API

### Получение списка всех типов документов (GET /v1/doc_type)

Логика работы:  
1. Из токена выбрать uuid пользователя и по нему определить домен (выбрать users.contractor_uuid и по uuid найти в таблице домен domains.participant_domain_records.domain_uuid)  
2. Выполняет поиск в таблице docflow.doc_types  
    запись не удалена  
    домен соответствует найденому или пусто  
3. Формирует массив ListItems  
4. Вернуть ListItems в ответ  

Пример ответа:  
```
[
  {
    "uuid": "8c8c654e-325f-43d2-be6b-cfbaadd431de",
    "title": "Значение"
  }
]
```

  

### Получение списка причин невалидности (GET /v1/invalidation_reason)

Логика работы:  
1. Из токена выбрать uuid пользователя и по нему определить домен (выбрать users.contractor_uuid и по uuid найти в таблице домен domains.participant_domain_records.domain_uuid)  
2. Выполняет поиск в таблице docflow.invalidation_reasons   
    запись не удалена  
    домен соответствует найденому или пусто  
3. Формирует массив ListItems  
4. Вернуть ListItems в ответ  

Пример ответа:  
```
[
  {
    "uuid": "8c8c654e-325f-43d2-be6b-cfbaadd431de",
    "title": "Значение"
  }
]
```


### Получение расположения полей документа на скане по идентификатору документа (GET /v1/fields_position/{doc_uuid})

Логика работы:  
1. На вход запрос получает идентификатор документа  
2. Выбирает значения идентификатор поля, номер страницы, координаты из таблицы docflow.scanned_doc_field_settings   
    идентификатор поля - field_uuid  
    номер страницы - page_number   
    координаты - coordinates  
3. Формирует массив ListFieldsPosition  
4. Вернуть ListFieldsPosition в ответ  

Пример ответа:  
```
[
  {
    "uuid": "8c8c654e-325f-43d2-be6b-cfbaadd431de",
    "page": 2,
    "coordinate": "10,10,70,30"
  }
]
```


## Таблицы PostgreSQL
* [docflow.doc_types](https://BLABLABLA/database-structure/blob/feature-541/db/docflow/doc_types.sql)
* [docflow.invalidation_reasons](https://BLABLABLA/database-structure/blob/analytics/db/docflow/invalidation_reasons.sql)
* [docflow.users](https://BLABLABLA/database-structure/blob/analytics/db/docflow/views/users.sql)
* [domains.participant_domain_records](https://BLABLABLA/database-structure/blob/analytics/db/domains/views/participant_domain_records.sql)
* [docflow.doc_field_settings](https://BLABLABLA/database-structure/blob/feature-541/db/docflow/doc_field_settings.sql)
* [docflow.scanned_doc_field_settings](https://BLABLABLA/database-structure/blob/analytics/db/docflow/scanned_doc_field_settings.sql)