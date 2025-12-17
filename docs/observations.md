# Revisión 1

## Requerimiento 1: Mejoras en el endpoint `/routes/planned/filter` microservicio LOCALIZATION

Hice la prueba con los valores 1, 2 y 3 para el filtro de `planned_route_ids`. En el segmento de `Params` en `POSTMAN` y la respuesta fue:

```json
[
    {
        "id": 1,
        "route_name": "La Paz: Inicio Tumusla",
        "route_code": "LPZ01",
        "description": "La Paz: Inicio Tumusla",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T08:45:55",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.49506246817429,
                "longitude": -68.14314472608758,
                "point_name": "Tumusla",
                "secuencial": 1,
                "reference_data": "Punto inicial",
                "id": 1,
                "created_at": "2025-12-01T08:45:55",
                "planned_route_id": 1
            },
            {
                "latitude": -16.49534603787516,
                "longitude": -68.14417522943486,
                "point_name": "Buenos Aires",
                "secuencial": 2,
                "reference_data": "Punto final",
                "id": 2,
                "created_at": "2025-12-01T08:45:55",
                "planned_route_id": 1
            }
        ]
    },
    {
        "id": 2,
        "route_name": "La Paz: Inicio Banco Económico (Central)",
        "route_code": "LPZ02",
        "description": "La Paz: Inicio Banco Económico (Central)",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T08:48:00",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.51243811093437,
                "longitude": -68.12255371501011,
                "point_name": "Banco Económico (Sucursal La Paz)",
                "secuencial": 1,
                "reference_data": "Punto inicial",
                "id": 3,
                "created_at": "2025-12-01T08:48:00",
                "planned_route_id": 2
            },
            {
                "latitude": -16.51188263585389,
                "longitude": -68.121813425322,
                "point_name": "Arce",
                "secuencial": 2,
                "reference_data": "Puntos libres",
                "id": 4,
                "created_at": "2025-12-01T08:48:00",
                "planned_route_id": 2
            }
        ]
    },
    {
        "id": 3,
        "route_name": "Cruce Villa Adela",
        "route_code": "LPZ03",
        "description": "Cruce Villa Adela",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T10:26:34",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.53509210393047,
                "longitude": -68.19052911444481,
                "point_name": "Cruce Villa Adela",
                "secuencial": 1,
                "reference_data": "Punto de partida",
                "id": 5,
                "created_at": "2025-12-01T10:26:34",
                "planned_route_id": 3
            },
            {
                "latitude": -16.52102421122305,
                "longitude": -68.17737579345703,
                "point_name": "Termianl de buses El Alto",
                "secuencial": 2,
                "reference_data": "Punto final",
                "id": 6,
                "created_at": "2025-12-01T10:26:34",
                "planned_route_id": 3
            }
        ]
    },
    {
        "id": 7,
        "route_name": "La Paz: Incio BM Group ",
        "route_code": "LPZ04",
        "description": "La Paz: Incio BM Group ",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T14:29:09",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.54010533200393,
                "longitude": -68.07923048466938,
                "point_name": "Oficina BM Group La Paz",
                "secuencial": 1,
                "reference_data": "Oficina La Paz",
                "id": 14,
                "created_at": "2025-12-01T14:29:09",
                "planned_route_id": 7
            },
            {
                "latitude": -16.54212086819628,
                "longitude": -68.09116851487751,
                "point_name": "Final Ruta",
                "secuencial": 2,
                "reference_data": "Oficina La Paz",
                "id": 15,
                "created_at": "2025-12-01T14:29:09",
                "planned_route_id": 7
            }
        ]
    },
    {
        "id": 8,
        "route_name": "La Paz: Inicio Agencia Tumusla",
        "route_code": "LPZ05",
        "description": "La Paz: Inicio Agencia Tumusla",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T14:39:59",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.49578442637703,
                "longitude": -68.1487966508369,
                "point_name": "Inicio Agencia Tumusla",
                "secuencial": 1,
                "reference_data": "Agencia Tumusla",
                "id": 16,
                "created_at": "2025-12-01T14:39:59",
                "planned_route_id": 8
            },
            {
                "latitude": -16.4957278458435,
                "longitude": -68.14605915693927,
                "point_name": "Tumusla",
                "secuencial": 2,
                "reference_data": "Agencia Tumusla",
                "id": 17,
                "created_at": "2025-12-01T14:39:59",
                "planned_route_id": 8
            }
        ]
    },
    {
        "id": 9,
        "route_name": "La Paz: Inicio Agencia Villa Fatima",
        "route_code": "LPZ06",
        "description": "La Paz: Inicio Agencia Villa Fatima",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T14:47:08",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.48064410493671,
                "longitude": -68.12147399214298,
                "point_name": "Inicio Agencia Villa Fatima",
                "secuencial": 1,
                "reference_data": "Inicio Agencia Villa Fatima",
                "id": 18,
                "created_at": "2025-12-01T14:47:09",
                "planned_route_id": 9
            },
            {
                "latitude": -16.48510861069127,
                "longitude": -68.12178397528913,
                "point_name": "Agencia Villa Fatima",
                "secuencial": 2,
                "reference_data": "Inicio Agencia Villa Fatima",
                "id": 19,
                "created_at": "2025-12-01T14:47:09",
                "planned_route_id": 9
            }
        ]
    },
    {
        "id": 10,
        "route_name": "La Paz: Inicio Agencia 16 de Julio",
        "route_code": "LPZ07",
        "description": "La Paz: Inicio Agencia 16 de Julio",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T15:03:06",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.49662837178251,
                "longitude": -68.17400962114334,
                "point_name": "Inicio Agencia 16 de Julio",
                "secuencial": 1,
                "reference_data": "Inicio Agencia 16 de Julio",
                "id": 20,
                "created_at": "2025-12-01T15:03:06",
                "planned_route_id": 10
            },
            {
                "latitude": -16.49971239716254,
                "longitude": -68.17492111043806,
                "point_name": "Agencia 16 de Julio",
                "secuencial": 2,
                "reference_data": "Inicio Agencia 16 de Julio",
                "id": 21,
                "created_at": "2025-12-01T15:03:06",
                "planned_route_id": 10
            }
        ]
    },
    {
        "id": 11,
        "route_name": "La Paz: BECO Rio Seco",
        "route_code": "LPZ08",
        "description": "La Paz: BECO Rio Seco",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T15:05:14",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.49107963424037,
                "longitude": -68.20378482341766,
                "point_name": "Inicio BECO Rio Seco",
                "secuencial": 1,
                "reference_data": "Inicio BECO Rio Seco",
                "id": 22,
                "created_at": "2025-12-01T15:05:14",
                "planned_route_id": 11
            },
            {
                "latitude": -16.49112837784801,
                "longitude": -68.20261727782821,
                "point_name": "BECO Rio Seco",
                "secuencial": 2,
                "reference_data": "Inicio BECO Rio Seco",
                "id": 23,
                "created_at": "2025-12-01T15:05:14",
                "planned_route_id": 11
            }
        ]
    },
    {
        "id": 12,
        "route_name": "La Paz: Incio BECO Av. Arce",
        "route_code": "LPZ09",
        "description": "La Paz: Incio BECO Av. Arce",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T15:08:32",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.51117035215469,
                "longitude": -68.12233382688505,
                "point_name": "Inicio BECO Av. Arce",
                "secuencial": 1,
                "reference_data": "Inicio BECO Av. Arce",
                "id": 24,
                "created_at": "2025-12-01T15:08:32",
                "planned_route_id": 12
            },
            {
                "latitude": -16.51071517694919,
                "longitude": -68.1229011140917,
                "point_name": "BECO Av. Arce",
                "secuencial": 2,
                "reference_data": "Inicio BECO Av. Arce",
                "id": 25,
                "created_at": "2025-12-01T15:08:32",
                "planned_route_id": 12
            }
        ]
    },
    {
        "id": 13,
        "route_name": "La Paz: Inicio Agencia San Miguel",
        "route_code": "LPZ10",
        "description": "La Paz: Inicio Agencia San Miguel",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-01T15:14:42",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.54509079948541,
                "longitude": -68.07815543987334,
                "point_name": "Inicio Agencia San Miguel",
                "secuencial": 1,
                "reference_data": "Inicio Agencia San Miguel",
                "id": 26,
                "created_at": "2025-12-01T15:14:42",
                "planned_route_id": 13
            },
            {
                "latitude": -16.54229201398165,
                "longitude": -68.07810844166096,
                "point_name": "Agencia San Miguel",
                "secuencial": 2,
                "reference_data": "Inicio Agencia San Miguel",
                "id": 27,
                "created_at": "2025-12-01T15:14:42",
                "planned_route_id": 13
            }
        ]
    },
    {
        "id": 14,
        "route_name": "La Paz: Inicio Agencia Miraflores",
        "route_code": "LPZ11",
        "description": "La Paz: Inicio Agencia Miraflores",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-02T16:06:28",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.49736776280069,
                "longitude": -68.11930730938911,
                "point_name": "Inicio Agencia Miraflores",
                "secuencial": 1,
                "reference_data": "Agencia Miraflores",
                "id": 28,
                "created_at": "2025-12-02T16:06:28",
                "planned_route_id": 14
            },
            {
                "latitude": -16.4981007731129,
                "longitude": -68.12105318670527,
                "point_name": "Final Agencia Miraflores",
                "secuencial": 2,
                "reference_data": "Agencia Miraflores",
                "id": 29,
                "created_at": "2025-12-02T16:06:28",
                "planned_route_id": 14
            }
        ]
    },
    {
        "id": 16,
        "route_name": "La Paz: Inicio Agencia Ceja",
        "route_code": "LPZ12",
        "description": "La Paz: Inicio Agencia Ceja",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-02T16:09:57",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.50757827847,
                "longitude": -68.1631417294115,
                "point_name": "Inicio Agencia Ceja",
                "secuencial": 1,
                "reference_data": "Inicio Agencia Ceja",
                "id": 32,
                "created_at": "2025-12-02T16:09:57",
                "planned_route_id": 16
            },
            {
                "latitude": -16.50457391814047,
                "longitude": -68.16290103988833,
                "point_name": "Final Agencia Ceja",
                "secuencial": 2,
                "reference_data": "Inicio Agencia Ceja",
                "id": 33,
                "created_at": "2025-12-02T16:09:57",
                "planned_route_id": 16
            }
        ]
    },
    {
        "id": 17,
        "route_name": "La Paz: Inicio Agencia Camacho",
        "route_code": "LPZ13",
        "description": "La Paz: Inicio Agencia Camacho",
        "company_id": 1,
        "app_id": 1,
        "city_id": 1,
        "created_at": "2025-12-02T16:12:48",
        "status": "ACTIVE",
        "points": [
            {
                "latitude": -16.4987796703206,
                "longitude": -68.13428074121475,
                "point_name": "Inicio Agencia Camacho",
                "secuencial": 1,
                "reference_data": "Inicio Agencia Camacho",
                "id": 34,
                "created_at": "2025-12-02T16:12:48",
                "planned_route_id": 17
            },
            {
                "latitude": -16.49939061860384,
                "longitude": -68.13323034762841,
                "point_name": "Final Agencia Camacho",
                "secuencial": 2,
                "reference_data": "Inicio Agencia Camacho",
                "id": 35,
                "created_at": "2025-12-02T16:12:48",
                "planned_route_id": 17
            }
        ]
    }
]
```

Adicionalmente usé otros filtros como `city_id` y `service_id` y me dió ese resultado y uno com ás registros cuando no utilizo esos valores lo que significa que el cambio no está funcionando correctamente.

En el lado de la terminal tenemos esta salida:

```shell

2025-12-16 20:14:25,527 - smartbear - INFO - User authenticated with email: psoto@binariaconsultores.com ------
2025-12-16 20:14:25,528 - smartbear - INFO - User: psoto@binariaconsultores.com. Received request to filter planned routes with parameters: planned_route_ids = None, route_code = None, route_name = None, status = None, company_id = 1
2025-12-16 20:14:25,528 - smartbear - INFO - Starting controller operation: filter planned routes
INFO:     127.0.0.1:59758 - "GET /localization/v1/localization/routes/planned/filter?company_id=1&city_id=1&planned_route_ids=1&planned_route_ids=2&planned_route_ids=3 HTTP/1.1" 200 OK
2025-12-16 20:14:31,006 - smartbear - INFO - Usage log sent successfully. Status: 201

```

# Revisión 2

## Requerimiento 2: Mejoras en el endpoint `/reports/contacts-by-route` microservicio FORMS

Para este requemiento me pide el cliente si se pued evisualizar el `planned_route_id` en cada registro.

Este es un pequeño ejemplo del objeto de salida:


```json
[
    {
        "form_id": 1,
        "user_id": 2928,
        "contact_id": 695,
        "status": "1",
        "rejection_reason": null,
        "affiliation_type": "AFILIACION",
        "company_id": 1,
        "affiliation_number": 600,
        "service_id": 1,
        "id": 695,
        "person_id": 618,
        "submission_date": "2025-12-05T10:23:02",
        "answers": [
            {
                "question_id": 1,
                "answer_value": "05/12/25",
                "id": 4793
            },
            {
                "question_id": 2,
                "answer_value": "BMLN01",
                "id": 4794
            },
            {
                "question_id": 3,
                "answer_value": "Mercadeo",
                "id": 4795
            },
            {
                "question_id": 4,
                "answer_value": "Caja de ahorros",
                "id": 4796
            },
            {
                "question_id": 5,
                "answer_value": "Negocio propio",
                "id": 4797
            },
            {
                "question_id": 6,
                "answer_value": "VENTAS POR MENOR",
                "id": 4798
            },
            {
                "question_id": 7,
                "answer_value": "La Paz",
                "id": 4799
            },
            {
                "question_id": 8,
                "answer_value": "JAIMES FREIRE",
                "id": 4800
            }
        ],
        "contact": {
            "latitude": -16.4934324,
            "longitude": -68.1392289,
            "start_datetime": "2025-12-05T10:20:51",
            "id": 695,
            "person": {
                "first_name": "ALEJANDRA",
                "paternal_last_name": "PAEZ",
                "maternal_last_name": "FERNANDEZ",
                "email": null,
                "phone_number": null,
                "phone_number_2": null,
                "birth_date": null,
                "identification_document_type": null,
                "identification_number": "13735857",
                "identification_expedition_place": null,
                "observations": null,
                "is_referred": false,
                "referred_note": null,
                "id": 618,
                "is_affiliated": true,
                "affiliation_date": "2025-12-05T10:24:09",
                "affiliation_user_id": 2928
            },
            "executed_route_point_id": 1983
        },
        "status_flow": []
    }
]

```

Es posible añadir el `planned_route_id` a cada registro?
