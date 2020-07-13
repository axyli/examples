#### Название
doc-warehouse.cell-audit-processing

#### Назначение
Инвентаризация ячеек

#### Тип микросервиса
Общий внутренний сервис

#### Интеграция

1. БД
2. REST на входе



##### Метод открытия ячейки
**post**
/v1/actioncell/{barcode}/open  
доп параметры для проверки, тк на открытие будут обращаться многие сервисы 

На вход от МП получает barcode  
Отправляет get запрос с баркодом в doc-warehouse.barcode-to-object-detector для определения типа штрихкода  
Если вернулся тип штрихкода - CELL, то:  
* Передает post запрос на открытие ячейки в doc-warehouse.cell (на вход передает barcode )
* В ответ получает код из запроса на открытие ячейки и uuid ячейки с набором данных  
    * uuid  
    * количество документов,  
    * номер(код) ячейки  
* Возвращает МП полученный набор данных
* Иначе, вернуть ошибку  

```json
 
    {
      "uuidCell": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "number": "004.17.05",
      "count": "25"
    }

```


##### Метод получения статуса документа
**get**
/v1/doc/{barcode}/checkdoc
* На вход от МП получает barcode
* Отправляет get запрос с баркодом в doc-warehouse.barcode-to-object-detector для определения типа штрихкода  
* Если вернулся тип штрихкода - DOCUMENT, то:
* Отправляет get запрос(/v1/doc/{barcode}/info) баркодом в сервис doc_warehouse.doc, в ответ получает: 
    * тип документа
    * uuid документа
    * cell_uuid	
* Cверяет равен ли полученный cell_uuid с cell_uuid переданным в запросе(/v1/doc/{cell_uuid}/checkdoc)
    * тип документа
    * uuid документа
    * uuid ячейки
    * признак доступности(available)

* Если равен, то вернуть МП объект с статусом avalible == true
* Если не равен, вернуть МП объект с статусом avalible == false

```json
    {
      "type": "накладная",
      "uuidDoc": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "uuidСell": "3fa85f64-5717-4562-b3fc-2c963f66afa6", 
      "available": "true"
    }
```

##### Метод закрытия ячейки
**post**
/v1/actioncell/{barcode}/close

на вход от МП получает barcode  

* Передает post запрос на закрытие ячейки в doc-warehouse.cell (на вход передает barcode )  
* Передает в ответ код из запроса на закрытие ячейки  
Иначе, вернуть ошибку

##### Метод сверки 
**post**
/v1/actioncell/{cell_uuid}/checkinv

* На вход от МП получает объект с  uuid ячейки, массивом uuid документов

 
 ```json
{
  "cellUuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "docsUUID": [
    "3fa85f64-5717-4562-b3fc-2c963f881afa4"
  ]
}
```

* Сравнивает с выборкой по текущей ячейке:
    * Выбирает по cell_uuid все документы находящиеся в этой ячейке(doc_warehouse.cell_objects.object_uuid)
    * по полученным от МП, но не найденным в ячейке UUID отправляет post запрос(/v1/doc/{uuid_doc}{cell_uuid}/move) в сервис перемещения документов(doc-warehouse.doc-resort-processing)
        * на вход передает {cell_uuid} == uuid инвентаризируемой ячейки и {uuid_doc}
        * в ответ от doc-warehouse.doc-resort-processing получает 200 при успешном внесении изменений
    * по найденным в БД, но не полученным от МП UUID отправляет post запрос(/v1/doc/{uuid_doc}{cell_uuid}/move) в сервис перемещения документов(doc-warehouse.doc-resort-processing)
        * на вход передает {cell_uuid} == uuid ячейки **розыск** и {uuid_doc}
        * в ответ от doc-warehouse.doc-resort-processing получает 200 при успешном внесении изменений
    * по всем UUID отправляет post (/v1/doc/{uuid_doc}{cell_uuid}/fixchange) запрос в сервис работы с ячейками(doc_warehouse.cell), для внесения изменений по статусам документов  
        * на вход передает uuid документа {uuid_doc} и uuid инвентаризируемой ячейки{cell_uuid} из списка выше
        * в ответ от doc_warehouse.cell получает 200 при успешном внесении изменений
        **переписать запрос и передавать {cell_uuid} как не обязательный параметр, тк запросом фиксации изменений будут пользоваться многие сервисы**                    
* Отправляет МП отчет
    * совпадающие UUID возвращаем в секции DocsOK
    * по полученным от МП, но не найденным в ячейке UUID возвращаем в секции DocsMove
    * по найденным в БД, но не полученным от МП UUID возвращаем в секции DocsNotFound           
 
 ```json
{
  "report": [
    {
      "cellUuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "docsOK": [
        
          "docsUuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        
      ],
      "docsMove": [
        
          "docsUuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        
      ],
      "docsNotFound": [
        
          "docsUuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        
      ]
    }
    ]
}
```
   


Сервисы для интеграции:  
[doc-warehouse.cell](https://BLABLA/documentation/analytics/tree/develop/microservices/doc-warehouse/doc-warehouse.cell)  
[doc-warehouse.doc-resort-processing](https://BLABLA/documentation/analytics/tree/develop/microservices/doc-warehouse/doc-warehouse.doc-resort-processing)  
[doc-warehouse.barcode-to-object-detector](https://BLABLA/documentation/analytics/blob/develop/microservices/doc-warehouse/doc-warehouse.barcode-to-object-detector/readme.md)  
[doc-warehouse.doc](https://BLABLA/documentation/analytics/tree/develop/microservices/doc-warehouse/doc-warehouse.doc)

БД  

[doc_warehouse.cell_objects](https://BLABLA/database-structure/blob/analytics/db/doc_warehouse/cell_objects.sql)  
[doc_warehouse.cell_actions](https://BLABLA/database-structure/blob/analytics/db/doc_warehouse/cell_actions.sql)  
[doc_warehouse.cell_errors](https://BLABLA/database-structure/blob/analytics/db/doc_warehouse/cell_errors.sql)  
[doc_warehouse.cells](https://BLABLA/database-structure/blob/analytics/db/doc_warehouse/cells.sql)  
[doc-warehouse.barcode-to-object-detector](https://BLABLA/documentation/analytics/blob/develop/microservices/doc-warehouse/doc-warehouse.barcode-to-object-detector/readme.md)  
