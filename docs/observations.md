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


# Revisión 3

Tenemos el siguiente error a raiz del cambio que acabas de hacer:

```shell

2025-12-16 22:43:10,122 - smartbear - INFO - User authenticated with email: psoto@binariaconsultores.com ------
2025-12-16 22:43:21,102 - smartbear - ERROR - Database error in generate_contacts_by_route_report: (pymysql.err.OperationalError) (1054, "Unknown column 't_form_responses.planned_route_id' in 'field list'")
[SQL: SELECT t_form_responses.id AS t_form_responses_id, t_form_responses.form_id AS t_form_responses_form_id, t_form_responses.contact_id AS t_form_responses_contact_id, t_form_responses.person_id AS t_form_responses_person_id, t_form_responses.service_id AS t_form_responses_service_id, t_form_responses.submission_date AS t_form_responses_submission_date, t_form_responses.status AS t_form_responses_status, t_form_responses.user_id AS t_form_responses_user_id, t_form_responses.affiliation_number AS t_form_responses_affiliation_number, t_form_responses.company_id AS t_form_responses_company_id, t_form_responses.planned_route_id AS t_form_responses_planned_route_id, t_form_responses.rejection_reason AS t_form_responses_rejection_reason, t_form_responses.affiliation_type AS t_form_responses_affiliation_type, t_contacts_1.id AS t_contacts_1_id, t_contacts_1.person_id AS t_contacts_1_person_id, t_contacts_1.latitude AS t_contacts_1_latitude, t_contacts_1.longitude AS t_contacts_1_longitude, t_contacts_1.start_datetime AS t_contacts_1_start_datetime, t_contacts_1.executed_route_point_id AS t_contacts_1_executed_route_point_id, t_form_answers_1.id AS t_form_answers_1_id, t_form_answers_1.form_response_id AS t_form_answers_1_form_response_id, t_form_answers_1.question_id AS t_form_answers_1_question_id, t_form_answers_1.answer_value AS t_form_answers_1_answer_value, t_persons_1.id AS t_persons_1_id, t_persons_1.first_name AS t_persons_1_first_name, t_persons_1.paternal_last_name AS t_persons_1_paternal_last_name, t_persons_1.maternal_last_name AS t_persons_1_maternal_last_name, t_persons_1.email AS t_persons_1_email, t_persons_1.phone_number AS t_persons_1_phone_number, t_persons_1.phone_number_2 AS t_persons_1_phone_number_2, t_persons_1.birth_date AS t_persons_1_birth_date, t_persons_1.identification_document_type AS t_persons_1_identification_document_type, t_persons_1.identification_number AS t_persons_1_identification_number, t_persons_1.identification_expedition_place AS t_persons_1_identification_expedition_place, t_persons_1.observations AS t_persons_1_observations, t_persons_1.is_affiliated AS t_persons_1_is_affiliated, t_persons_1.affiliation_date AS t_persons_1_affiliation_date, t_persons_1.affiliation_user_id AS t_persons_1_affiliation_user_id, t_persons_1.is_referred AS t_persons_1_is_referred, t_persons_1.referred_note AS t_persons_1_referred_note 
FROM t_form_responses INNER JOIN t_contacts ON t_contacts.id = t_form_responses.contact_id INNER JOIN t_persons ON t_persons.id = t_form_responses.person_id LEFT OUTER JOIN t_form_answers ON t_form_responses.id = t_form_answers.form_response_id LEFT OUTER JOIN t_contacts AS t_contacts_1 ON t_contacts_1.id = t_form_responses.contact_id LEFT OUTER JOIN t_form_answers AS t_form_answers_1 ON t_form_responses.id = t_form_answers_1.form_response_id LEFT OUTER JOIN t_persons AS t_persons_1 ON t_persons_1.id = t_form_responses.person_id 
WHERE t_contacts.executed_route_point_id IN (%(executed_route_point_id_1_1)s, %(executed_route_point_id_1_2)s, %(executed_route_point_id_1_3)s, %(executed_route_point_id_1_4)s, %(executed_route_point_id_1_5)s, %(executed_route_point_id_1_6)s, %(executed_route_point_id_1_7)s, %(executed_route_point_id_1_8)s, %(executed_route_point_id_1_9)s, %(executed_route_point_id_1_10)s, %(executed_route_point_id_1_11)s, %(executed_route_point_id_1_12)s, %(executed_route_point_id_1_13)s, %(executed_route_point_id_1_14)s, %(executed_route_point_id_1_15)s, %(executed_route_point_id_1_16)s, %(executed_route_point_id_1_17)s, %(executed_route_point_id_1_18)s, %(executed_route_point_id_1_19)s, %(executed_route_point_id_1_20)s, %(executed_route_point_id_1_21)s, %(executed_route_point_id_1_22)s, %(executed_route_point_id_1_23)s, %(executed_route_point_id_1_24)s, %(executed_route_point_id_1_25)s, %(executed_route_point_id_1_26)s, %(executed_route_point_id_1_27)s, %(executed_route_point_id_1_28)s, %(executed_route_point_id_1_29)s, %(executed_route_point_id_1_30)s, %(executed_route_point_id_1_31)s, %(executed_route_point_id_1_32)s, %(executed_route_point_id_1_33)s, %(executed_route_point_id_1_34)s, %(executed_route_point_id_1_35)s, %(executed_route_point_id_1_36)s, %(executed_route_point_id_1_37)s, %(executed_route_point_id_1_38)s, %(executed_route_point_id_1_39)s, %(executed_route_point_id_1_40)s, %(executed_route_point_id_1_41)s, %(executed_route_point_id_1_42)s, %(executed_route_point_id_1_43)s, %(executed_route_point_id_1_44)s, %(executed_route_point_id_1_45)s, %(executed_route_point_id_1_46)s, %(executed_route_point_id_1_47)s, %(executed_route_point_id_1_48)s, %(executed_route_point_id_1_49)s, %(executed_route_point_id_1_50)s, %(executed_route_point_id_1_51)s, %(executed_route_point_id_1_52)s, %(executed_route_point_id_1_53)s, %(executed_route_point_id_1_54)s, %(executed_route_point_id_1_55)s, %(executed_route_point_id_1_56)s, %(executed_route_point_id_1_57)s, %(executed_route_point_id_1_58)s, %(executed_route_point_id_1_59)s, %(executed_route_point_id_1_60)s, %(executed_route_point_id_1_61)s, %(executed_route_point_id_1_62)s, %(executed_route_point_id_1_63)s, %(executed_route_point_id_1_64)s, %(executed_route_point_id_1_65)s, %(executed_route_point_id_1_66)s, %(executed_route_point_id_1_67)s, %(executed_route_point_id_1_68)s, %(executed_route_point_id_1_69)s, %(executed_route_point_id_1_70)s, %(executed_route_point_id_1_71)s, %(executed_route_point_id_1_72)s, %(executed_route_point_id_1_73)s, %(executed_route_point_id_1_74)s, %(executed_route_point_id_1_75)s, %(executed_route_point_id_1_76)s, %(executed_route_point_id_1_77)s, %(executed_route_point_id_1_78)s, %(executed_route_point_id_1_79)s, %(executed_route_point_id_1_80)s, %(executed_route_point_id_1_81)s, %(executed_route_point_id_1_82)s, %(executed_route_point_id_1_83)s, %(executed_route_point_id_1_84)s, %(executed_route_point_id_1_85)s, %(executed_route_point_id_1_86)s, %(executed_route_point_id_1_87)s, %(executed_route_point_id_1_88)s, %(executed_route_point_id_1_89)s, %(executed_route_point_id_1_90)s, %(executed_route_point_id_1_91)s, %(executed_route_point_id_1_92)s, %(executed_route_point_id_1_93)s, %(executed_route_point_id_1_94)s, %(executed_route_point_id_1_95)s, %(executed_route_point_id_1_96)s, %(executed_route_point_id_1_97)s, %(executed_route_point_id_1_98)s, %(executed_route_point_id_1_99)s, %(executed_route_point_id_1_100)s, %(executed_route_point_id_1_101)s, %(executed_route_point_id_1_102)s, %(executed_route_point_id_1_103)s, %(executed_route_point_id_1_104)s, %(executed_route_point_id_1_105)s, %(executed_route_point_id_1_106)s, %(executed_route_point_id_1_107)s, %(executed_route_point_id_1_108)s, %(executed_route_point_id_1_109)s, %(executed_route_point_id_1_110)s, %(executed_route_point_id_1_111)s, %(executed_route_point_id_1_112)s, %(executed_route_point_id_1_113)s, %(executed_route_point_id_1_114)s, %(executed_route_point_id_1_115)s, %(executed_route_point_id_1_116)s, %(executed_route_point_id_1_117)s, %(executed_route_point_id_1_118)s, %(executed_route_point_id_1_119)s, %(executed_route_point_id_1_120)s, %(executed_route_point_id_1_121)s, %(executed_route_point_id_1_122)s, %(executed_route_point_id_1_123)s, %(executed_route_point_id_1_124)s, %(executed_route_point_id_1_125)s, %(executed_route_point_id_1_126)s, %(executed_route_point_id_1_127)s, %(executed_route_point_id_1_128)s, %(executed_route_point_id_1_129)s, %(executed_route_point_id_1_130)s, %(executed_route_point_id_1_131)s, %(executed_route_point_id_1_132)s, %(executed_route_point_id_1_133)s, %(executed_route_point_id_1_134)s, %(executed_route_point_id_1_135)s, %(executed_route_point_id_1_136)s, %(executed_route_point_id_1_137)s, %(executed_route_point_id_1_138)s, %(executed_route_point_id_1_139)s, %(executed_route_point_id_1_140)s, %(executed_route_point_id_1_141)s, %(executed_route_point_id_1_142)s, %(executed_route_point_id_1_143)s, %(executed_route_point_id_1_144)s, %(executed_route_point_id_1_145)s, %(executed_route_point_id_1_146)s, %(executed_route_point_id_1_147)s, %(executed_route_point_id_1_148)s, %(executed_route_point_id_1_149)s, %(executed_route_point_id_1_150)s, %(executed_route_point_id_1_151)s, %(executed_route_point_id_1_152)s, %(executed_route_point_id_1_153)s, %(executed_route_point_id_1_154)s, %(executed_route_point_id_1_155)s, %(executed_route_point_id_1_156)s, %(executed_route_point_id_1_157)s, %(executed_route_point_id_1_158)s, %(executed_route_point_id_1_159)s, %(executed_route_point_id_1_160)s, %(executed_route_point_id_1_161)s, %(executed_route_point_id_1_162)s, %(executed_route_point_id_1_163)s, %(executed_route_point_id_1_164)s, %(executed_route_point_id_1_165)s, %(executed_route_point_id_1_166)s, %(executed_route_point_id_1_167)s, %(executed_route_point_id_1_168)s, %(executed_route_point_id_1_169)s, %(executed_route_point_id_1_170)s, %(executed_route_point_id_1_171)s, %(executed_route_point_id_1_172)s, %(executed_route_point_id_1_173)s, %(executed_route_point_id_1_174)s, %(executed_route_point_id_1_175)s, %(executed_route_point_id_1_176)s, %(executed_route_point_id_1_177)s, %(executed_route_point_id_1_178)s, %(executed_route_point_id_1_179)s, %(executed_route_point_id_1_180)s, %(executed_route_point_id_1_181)s, %(executed_route_point_id_1_182)s, %(executed_route_point_id_1_183)s, %(executed_route_point_id_1_184)s, %(executed_route_point_id_1_185)s, %(executed_route_point_id_1_186)s, %(executed_route_point_id_1_187)s, %(executed_route_point_id_1_188)s, %(executed_route_point_id_1_189)s, %(executed_route_point_id_1_190)s, %(executed_route_point_id_1_191)s, %(executed_route_point_id_1_192)s, %(executed_route_point_id_1_193)s, %(executed_route_point_id_1_194)s, %(executed_route_point_id_1_195)s, %(executed_route_point_id_1_196)s, %(executed_route_point_id_1_197)s, %(executed_route_point_id_1_198)s, %(executed_route_point_id_1_199)s, %(executed_route_point_id_1_200)s, %(executed_route_point_id_1_201)s, %(executed_route_point_id_1_202)s, %(executed_route_point_id_1_203)s, %(executed_route_point_id_1_204)s, %(executed_route_point_id_1_205)s, %(executed_route_point_id_1_206)s, %(executed_route_point_id_1_207)s, %(executed_route_point_id_1_208)s, %(executed_route_point_id_1_209)s, %(executed_route_point_id_1_210)s, %(executed_route_point_id_1_211)s, %(executed_route_point_id_1_212)s, %(executed_route_point_id_1_213)s, %(executed_route_point_id_1_214)s, %(executed_route_point_id_1_215)s, %(executed_route_point_id_1_216)s, %(executed_route_point_id_1_217)s, %(executed_route_point_id_1_218)s, %(executed_route_point_id_1_219)s, %(executed_route_point_id_1_220)s, %(executed_route_point_id_1_221)s, %(executed_route_point_id_1_222)s, %(executed_route_point_id_1_223)s, %(executed_route_point_id_1_224)s, %(executed_route_point_id_1_225)s, %(executed_route_point_id_1_226)s, %(executed_route_point_id_1_227)s, %(executed_route_point_id_1_228)s, %(executed_route_point_id_1_229)s, %(executed_route_point_id_1_230)s, %(executed_route_point_id_1_231)s, %(executed_route_point_id_1_232)s, %(executed_route_point_id_1_233)s, %(executed_route_point_id_1_234)s, %(executed_route_point_id_1_235)s, %(executed_route_point_id_1_236)s, %(executed_route_point_id_1_237)s, %(executed_route_point_id_1_238)s, %(executed_route_point_id_1_239)s, %(executed_route_point_id_1_240)s, %(executed_route_point_id_1_241)s, %(executed_route_point_id_1_242)s, %(executed_route_point_id_1_243)s, %(executed_route_point_id_1_244)s, %(executed_route_point_id_1_245)s, %(executed_route_point_id_1_246)s, %(executed_route_point_id_1_247)s, %(executed_route_point_id_1_248)s, %(executed_route_point_id_1_249)s, %(executed_route_point_id_1_250)s, %(executed_route_point_id_1_251)s, %(executed_route_point_id_1_252)s, %(executed_route_point_id_1_253)s, %(executed_route_point_id_1_254)s, %(executed_route_point_id_1_255)s, %(executed_route_point_id_1_256)s, %(executed_route_point_id_1_257)s, %(executed_route_point_id_1_258)s, %(executed_route_point_id_1_259)s, %(executed_route_point_id_1_260)s, %(executed_route_point_id_1_261)s, %(executed_route_point_id_1_262)s, %(executed_route_point_id_1_263)s, %(executed_route_point_id_1_264)s, %(executed_route_point_id_1_265)s, %(executed_route_point_id_1_266)s, %(executed_route_point_id_1_267)s, %(executed_route_point_id_1_268)s, %(executed_route_point_id_1_269)s, %(executed_route_point_id_1_270)s, %(executed_route_point_id_1_271)s, %(executed_route_point_id_1_272)s, %(executed_route_point_id_1_273)s, %(executed_route_point_id_1_274)s, %(executed_route_point_id_1_275)s, %(executed_route_point_id_1_276)s, %(executed_route_point_id_1_277)s, %(executed_route_point_id_1_278)s, %(executed_route_point_id_1_279)s, %(executed_route_point_id_1_280)s, %(executed_route_point_id_1_281)s, %(executed_route_point_id_1_282)s, %(executed_route_point_id_1_283)s, %(executed_route_point_id_1_284)s, %(executed_route_point_id_1_285)s, %(executed_route_point_id_1_286)s, %(executed_route_point_id_1_287)s, %(executed_route_point_id_1_288)s, %(executed_route_point_id_1_289)s, %(executed_route_point_id_1_290)s, %(executed_route_point_id_1_291)s, %(executed_route_point_id_1_292)s, %(executed_route_point_id_1_293)s, %(executed_route_point_id_1_294)s, %(executed_route_point_id_1_295)s, %(executed_route_point_id_1_296)s, %(executed_route_point_id_1_297)s, %(executed_route_point_id_1_298)s, %(executed_route_point_id_1_299)s, %(executed_route_point_id_1_300)s, %(executed_route_point_id_1_301)s, %(executed_route_point_id_1_302)s, %(executed_route_point_id_1_303)s, %(executed_route_point_id_1_304)s, %(executed_route_point_id_1_305)s, %(executed_route_point_id_1_306)s, %(executed_route_point_id_1_307)s, %(executed_route_point_id_1_308)s, %(executed_route_point_id_1_309)s, %(executed_route_point_id_1_310)s, %(executed_route_point_id_1_311)s, %(executed_route_point_id_1_312)s, %(executed_route_point_id_1_313)s, %(executed_route_point_id_1_314)s, %(executed_route_point_id_1_315)s, %(executed_route_point_id_1_316)s, %(executed_route_point_id_1_317)s, %(executed_route_point_id_1_318)s, %(executed_route_point_id_1_319)s, %(executed_route_point_id_1_320)s, %(executed_route_point_id_1_321)s, %(executed_route_point_id_1_322)s, %(executed_route_point_id_1_323)s, %(executed_route_point_id_1_324)s, %(executed_route_point_id_1_325)s, %(executed_route_point_id_1_326)s, %(executed_route_point_id_1_327)s, %(executed_route_point_id_1_328)s, %(executed_route_point_id_1_329)s, %(executed_route_point_id_1_330)s, %(executed_route_point_id_1_331)s, %(executed_route_point_id_1_332)s, %(executed_route_point_id_1_333)s, %(executed_route_point_id_1_334)s, %(executed_route_point_id_1_335)s, %(executed_route_point_id_1_336)s, %(executed_route_point_id_1_337)s, %(executed_route_point_id_1_338)s, %(executed_route_point_id_1_339)s, %(executed_route_point_id_1_340)s, %(executed_route_point_id_1_341)s, %(executed_route_point_id_1_342)s, %(executed_route_point_id_1_343)s, %(executed_route_point_id_1_344)s, %(executed_route_point_id_1_345)s, %(executed_route_point_id_1_346)s, %(executed_route_point_id_1_347)s, %(executed_route_point_id_1_348)s, %(executed_route_point_id_1_349)s, %(executed_route_point_id_1_350)s, %(executed_route_point_id_1_351)s, %(executed_route_point_id_1_352)s, %(executed_route_point_id_1_353)s, %(executed_route_point_id_1_354)s, %(executed_route_point_id_1_355)s, %(executed_route_point_id_1_356)s, %(executed_route_point_id_1_357)s, %(executed_route_point_id_1_358)s, %(executed_route_point_id_1_359)s, %(executed_route_point_id_1_360)s, %(executed_route_point_id_1_361)s, %(executed_route_point_id_1_362)s, %(executed_route_point_id_1_363)s, %(executed_route_point_id_1_364)s, %(executed_route_point_id_1_365)s, %(executed_route_point_id_1_366)s, %(executed_route_point_id_1_367)s, %(executed_route_point_id_1_368)s, %(executed_route_point_id_1_369)s, %(executed_route_point_id_1_370)s, %(executed_route_point_id_1_371)s, %(executed_route_point_id_1_372)s, %(executed_route_point_id_1_373)s, %(executed_route_point_id_1_374)s, %(executed_route_point_id_1_375)s, %(executed_route_point_id_1_376)s, %(executed_route_point_id_1_377)s, %(executed_route_point_id_1_378)s, %(executed_route_point_id_1_379)s, %(executed_route_point_id_1_380)s, %(executed_route_point_id_1_381)s, %(executed_route_point_id_1_382)s, %(executed_route_point_id_1_383)s, %(executed_route_point_id_1_384)s, %(executed_route_point_id_1_385)s, %(executed_route_point_id_1_386)s, %(executed_route_point_id_1_387)s, %(executed_route_point_id_1_388)s, %(executed_route_point_id_1_389)s, %(executed_route_point_id_1_390)s, %(executed_route_point_id_1_391)s, %(executed_route_point_id_1_392)s, %(executed_route_point_id_1_393)s, %(executed_route_point_id_1_394)s, %(executed_route_point_id_1_395)s, %(executed_route_point_id_1_396)s, %(executed_route_point_id_1_397)s, %(executed_route_point_id_1_398)s, %(executed_route_point_id_1_399)s, %(executed_route_point_id_1_400)s, %(executed_route_point_id_1_401)s, %(executed_route_point_id_1_402)s, %(executed_route_point_id_1_403)s, %(executed_route_point_id_1_404)s, %(executed_route_point_id_1_405)s, %(executed_route_point_id_1_406)s, %(executed_route_point_id_1_407)s, %(executed_route_point_id_1_408)s, %(executed_route_point_id_1_409)s, %(executed_route_point_id_1_410)s, %(executed_route_point_id_1_411)s, %(executed_route_point_id_1_412)s, %(executed_route_point_id_1_413)s, %(executed_route_point_id_1_414)s, %(executed_route_point_id_1_415)s, %(executed_route_point_id_1_416)s, %(executed_route_point_id_1_417)s, %(executed_route_point_id_1_418)s, %(executed_route_point_id_1_419)s, %(executed_route_point_id_1_420)s, %(executed_route_point_id_1_421)s, %(executed_route_point_id_1_422)s, %(executed_route_point_id_1_423)s, %(executed_route_point_id_1_424)s, %(executed_route_point_id_1_425)s, %(executed_route_point_id_1_426)s, %(executed_route_point_id_1_427)s, %(executed_route_point_id_1_428)s, %(executed_route_point_id_1_429)s, %(executed_route_point_id_1_430)s, %(executed_route_point_id_1_431)s, %(executed_route_point_id_1_432)s, %(executed_route_point_id_1_433)s, %(executed_route_point_id_1_434)s, %(executed_route_point_id_1_435)s, %(executed_route_point_id_1_436)s, %(executed_route_point_id_1_437)s, %(executed_route_point_id_1_438)s, %(executed_route_point_id_1_439)s, %(executed_route_point_id_1_440)s, %(executed_route_point_id_1_441)s, %(executed_route_point_id_1_442)s, %(executed_route_point_id_1_443)s, %(executed_route_point_id_1_444)s, %(executed_route_point_id_1_445)s, %(executed_route_point_id_1_446)s, %(executed_route_point_id_1_447)s, %(executed_route_point_id_1_448)s, %(executed_route_point_id_1_449)s, %(executed_route_point_id_1_450)s, %(executed_route_point_id_1_451)s, %(executed_route_point_id_1_452)s, %(executed_route_point_id_1_453)s, %(executed_route_point_id_1_454)s, %(executed_route_point_id_1_455)s, %(executed_route_point_id_1_456)s, %(executed_route_point_id_1_457)s, %(executed_route_point_id_1_458)s, %(executed_route_point_id_1_459)s, %(executed_route_point_id_1_460)s, %(executed_route_point_id_1_461)s, %(executed_route_point_id_1_462)s, %(executed_route_point_id_1_463)s, %(executed_route_point_id_1_464)s, %(executed_route_point_id_1_465)s, %(executed_route_point_id_1_466)s, %(executed_route_point_id_1_467)s, %(executed_route_point_id_1_468)s, %(executed_route_point_id_1_469)s, %(executed_route_point_id_1_470)s, %(executed_route_point_id_1_471)s, %(executed_route_point_id_1_472)s, %(executed_route_point_id_1_473)s, %(executed_route_point_id_1_474)s, %(executed_route_point_id_1_475)s, %(executed_route_point_id_1_476)s, %(executed_route_point_id_1_477)s, %(executed_route_point_id_1_478)s, %(executed_route_point_id_1_479)s, %(executed_route_point_id_1_480)s, %(executed_route_point_id_1_481)s, %(executed_route_point_id_1_482)s, %(executed_route_point_id_1_483)s, %(executed_route_point_id_1_484)s, %(executed_route_point_id_1_485)s, %(executed_route_point_id_1_486)s, %(executed_route_point_id_1_487)s, %(executed_route_point_id_1_488)s, %(executed_route_point_id_1_489)s, %(executed_route_point_id_1_490)s, %(executed_route_point_id_1_491)s, %(executed_route_point_id_1_492)s, %(executed_route_point_id_1_493)s, %(executed_route_point_id_1_494)s, %(executed_route_point_id_1_495)s, %(executed_route_point_id_1_496)s, %(executed_route_point_id_1_497)s, %(executed_route_point_id_1_498)s, %(executed_route_point_id_1_499)s, %(executed_route_point_id_1_500)s, %(executed_route_point_id_1_501)s, %(executed_route_point_id_1_502)s, %(executed_route_point_id_1_503)s, %(executed_route_point_id_1_504)s, %(executed_route_point_id_1_505)s, %(executed_route_point_id_1_506)s, %(executed_route_point_id_1_507)s, %(executed_route_point_id_1_508)s, %(executed_route_point_id_1_509)s, %(executed_route_point_id_1_510)s, %(executed_route_point_id_1_511)s, %(executed_route_point_id_1_512)s, %(executed_route_point_id_1_513)s, %(executed_route_point_id_1_514)s, %(executed_route_point_id_1_515)s, %(executed_route_point_id_1_516)s, %(executed_route_point_id_1_517)s, %(executed_route_point_id_1_518)s, %(executed_route_point_id_1_519)s, %(executed_route_point_id_1_520)s, %(executed_route_point_id_1_521)s, %(executed_route_point_id_1_522)s, %(executed_route_point_id_1_523)s, %(executed_route_point_id_1_524)s, %(executed_route_point_id_1_525)s, %(executed_route_point_id_1_526)s, %(executed_route_point_id_1_527)s, %(executed_route_point_id_1_528)s, %(executed_route_point_id_1_529)s, %(executed_route_point_id_1_530)s, %(executed_route_point_id_1_531)s, %(executed_route_point_id_1_532)s, %(executed_route_point_id_1_533)s, %(executed_route_point_id_1_534)s, %(executed_route_point_id_1_535)s, %(executed_route_point_id_1_536)s, %(executed_route_point_id_1_537)s, %(executed_route_point_id_1_538)s, %(executed_route_point_id_1_539)s, %(executed_route_point_id_1_540)s, %(executed_route_point_id_1_541)s, %(executed_route_point_id_1_542)s, %(executed_route_point_id_1_543)s) AND t_form_responses.submission_date BETWEEN %(submission_date_1)s AND %(submission_date_2)s AND t_form_responses.company_id = %(company_id_1)s AND t_form_responses.service_id = %(service_id_1)s]
[parameters: {'submission_date_1': datetime.date(2025, 12, 5), 'submission_date_2': datetime.date(2025, 12, 10), 'company_id_1': 1, 'service_id_1': 1, 'executed_route_point_id_1_1': 325, 'executed_route_point_id_1_2': 401, 'executed_route_point_id_1_3': 406, 'executed_route_point_id_1_4': 407, 'executed_route_point_id_1_5': 408, 'executed_route_point_id_1_6': 463, 'executed_route_point_id_1_7': 555, 'executed_route_point_id_1_8': 561, 'executed_route_point_id_1_9': 908, 'executed_route_point_id_1_10': 1014, 'executed_route_point_id_1_11': 1134, 'executed_route_point_id_1_12': 1191, 'executed_route_point_id_1_13': 1192, 'executed_route_point_id_1_14': 1260, 'executed_route_point_id_1_15': 1322, 'executed_route_point_id_1_16': 1323, 'executed_route_point_id_1_17': 1510, 'executed_route_point_id_1_18': 1517, 'executed_route_point_id_1_19': 1797, 'executed_route_point_id_1_20': 1857, 'executed_route_point_id_1_21': 1859, 'executed_route_point_id_1_22': 1939, 'executed_route_point_id_1_23': 1955, 'executed_route_point_id_1_24': 1956, 'executed_route_point_id_1_25': 1977, 'executed_route_point_id_1_26': 1978, 'executed_route_point_id_1_27': 1983, 'executed_route_point_id_1_28': 2143, 'executed_route_point_id_1_29': 2144, 'executed_route_point_id_1_30': 2145, 'executed_route_point_id_1_31': 2250, 'executed_route_point_id_1_32': 2402, 'executed_route_point_id_1_33': 2406, 'executed_route_point_id_1_34': 2407, 'executed_route_point_id_1_35': 2408, 'executed_route_point_id_1_36': 2409, 'executed_route_point_id_1_37': 2586, 'executed_route_point_id_1_38': 2587, 'executed_route_point_id_1_39': 2588, 'executed_route_point_id_1_40': 2589, 'executed_route_point_id_1_41': 2590, 'executed_route_point_id_1_42': 4680, 'executed_route_point_id_1_43': 4681, 'executed_route_point_id_1_44': 4682, 'executed_route_point_id_1_45': 4683, 'executed_route_point_id_1_46': 4684 ... 447 parameters truncated ... 'executed_route_point_id_1_494': 6457, 'executed_route_point_id_1_495': 6478, 'executed_route_point_id_1_496': 6482, 'executed_route_point_id_1_497': 6620, 'executed_route_point_id_1_498': 6720, 'executed_route_point_id_1_499': 6725, 'executed_route_point_id_1_500': 6872, 'executed_route_point_id_1_501': 6873, 'executed_route_point_id_1_502': 6874, 'executed_route_point_id_1_503': 6876, 'executed_route_point_id_1_504': 6877, 'executed_route_point_id_1_505': 6945, 'executed_route_point_id_1_506': 7068, 'executed_route_point_id_1_507': 7070, 'executed_route_point_id_1_508': 7098, 'executed_route_point_id_1_509': 7111, 'executed_route_point_id_1_510': 7145, 'executed_route_point_id_1_511': 7724, 'executed_route_point_id_1_512': 7794, 'executed_route_point_id_1_513': 7795, 'executed_route_point_id_1_514': 7796, 'executed_route_point_id_1_515': 7797, 'executed_route_point_id_1_516': 7799, 'executed_route_point_id_1_517': 7800, 'executed_route_point_id_1_518': 7812, 'executed_route_point_id_1_519': 7813, 'executed_route_point_id_1_520': 7814, 'executed_route_point_id_1_521': 7815, 'executed_route_point_id_1_522': 7816, 'executed_route_point_id_1_523': 7868, 'executed_route_point_id_1_524': 7870, 'executed_route_point_id_1_525': 7871, 'executed_route_point_id_1_526': 7990, 'executed_route_point_id_1_527': 7997, 'executed_route_point_id_1_528': 7998, 'executed_route_point_id_1_529': 8060, 'executed_route_point_id_1_530': 8080, 'executed_route_point_id_1_531': 8288, 'executed_route_point_id_1_532': 8290, 'executed_route_point_id_1_533': 8291, 'executed_route_point_id_1_534': 8298, 'executed_route_point_id_1_535': 8301, 'executed_route_point_id_1_536': 8338, 'executed_route_point_id_1_537': 8339, 'executed_route_point_id_1_538': 8340, 'executed_route_point_id_1_539': 8345, 'executed_route_point_id_1_540': 8347, 'executed_route_point_id_1_541': 8460, 'executed_route_point_id_1_542': 8464, 'executed_route_point_id_1_543': 8465}]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
Traceback (most recent call last):
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1964, in _exec_single_context
    self.dialect.do_execute(
    ~~~~~~~~~~~~~~~~~~~~~~~^
        cursor, str_statement, effective_parameters, context
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py", line 945, in do_execute
    cursor.execute(statement, parameters)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/cursors.py", line 153, in execute
    result = self._query(query)
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/cursors.py", line 322, in _query
    conn.query(q)
    ~~~~~~~~~~^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 563, in query
    self._affected_rows = self._read_query_result(unbuffered=unbuffered)
                          ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 825, in _read_query_result
    result.read()
    ~~~~~~~~~~~^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 1199, in read
    first_packet = self.connection._read_packet()
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 775, in _read_packet
    packet.raise_for_error()
    ~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/protocol.py", line 219, in raise_for_error
    err.raise_mysql_exception(self._data)
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/err.py", line 150, in raise_mysql_exception
    raise errorclass(errno, errval)
pymysql.err.OperationalError: (1054, "Unknown column 't_form_responses.planned_route_id' in 'field list'")

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/rafael/Work/projects/back/SmartBear/app/services/forms/services/utils.py", line 201, in wrapper
    result = await func(*args, **kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/app/services/forms/services/reports.py", line 587, in generate_contacts_by_route_report
    results = query.all()
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/orm/query.py", line 2704, in all
    return self._iter().all()  # type: ignore
           ~~~~~~~~~~^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/orm/query.py", line 2858, in _iter
    result: Union[ScalarResult[_T], Result[_T]] = self.session.execute(
                                                  ~~~~~~~~~~~~~~~~~~~~^
        statement,
        ^^^^^^^^^^
        params,
        ^^^^^^^
        execution_options={"_sa_orm_load_options": self.load_options},
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/orm/session.py", line 2365, in execute
    return self._execute_internal(
           ~~~~~~~~~~~~~~~~~~~~~~^
        statement,
        ^^^^^^^^^^
    ...<4 lines>...
        _add_event=_add_event,
        ^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/orm/session.py", line 2251, in _execute_internal
    result: Result[Any] = compile_state_cls.orm_execute_statement(
                          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        self,
        ^^^^^
    ...<4 lines>...
        conn,
        ^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/orm/context.py", line 306, in orm_execute_statement
    result = conn.execute(
        statement, params or {}, execution_options=execution_options
    )
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1416, in execute
    return meth(
        self,
        distilled_parameters,
        execution_options or NO_OPTIONS,
    )
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/sql/elements.py", line 523, in _execute_on_connection
    return connection._execute_clauseelement(
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        self, distilled_params, execution_options
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1638, in _execute_clauseelement
    ret = self._execute_context(
        dialect,
    ...<8 lines>...
        cache_hit=cache_hit,
    )
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1843, in _execute_context
    return self._exec_single_context(
           ~~~~~~~~~~~~~~~~~~~~~~~~~^
        dialect, context, statement, parameters
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1983, in _exec_single_context
    self._handle_dbapi_exception(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        e, str_statement, effective_parameters, cursor, context
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 2352, in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1964, in _exec_single_context
    self.dialect.do_execute(
    ~~~~~~~~~~~~~~~~~~~~~~~^
        cursor, str_statement, effective_parameters, context
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py", line 945, in do_execute
    cursor.execute(statement, parameters)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/cursors.py", line 153, in execute
    result = self._query(query)
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/cursors.py", line 322, in _query
    conn.query(q)
    ~~~~~~~~~~^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 563, in query
    self._affected_rows = self._read_query_result(unbuffered=unbuffered)
                          ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 825, in _read_query_result
    result.read()
    ~~~~~~~~~~~^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 1199, in read
    first_packet = self.connection._read_packet()
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/connections.py", line 775, in _read_packet
    packet.raise_for_error()
    ~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/protocol.py", line 219, in raise_for_error
    err.raise_mysql_exception(self._data)
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/rafael/Work/projects/back/SmartBear/.venv/lib/python3.13/site-packages/pymysql/err.py", line 150, in raise_mysql_exception
    raise errorclass(errno, errval)
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (1054, "Unknown column 't_form_responses.planned_route_id' in 'field list'")
[SQL: SELECT t_form_responses.id AS t_form_responses_id, t_form_responses.form_id AS t_form_responses_form_id, t_form_responses.contact_id AS t_form_responses_contact_id, t_form_responses.person_id AS t_form_responses_person_id, t_form_responses.service_id AS t_form_responses_service_id, t_form_responses.submission_date AS t_form_responses_submission_date, t_form_responses.status AS t_form_responses_status, t_form_responses.user_id AS t_form_responses_user_id, t_form_responses.affiliation_number AS t_form_responses_affiliation_number, t_form_responses.company_id AS t_form_responses_company_id, t_form_responses.planned_route_id AS t_form_responses_planned_route_id, t_form_responses.rejection_reason AS t_form_responses_rejection_reason, t_form_responses.affiliation_type AS t_form_responses_affiliation_type, t_contacts_1.id AS t_contacts_1_id, t_contacts_1.person_id AS t_contacts_1_person_id, t_contacts_1.latitude AS t_contacts_1_latitude, t_contacts_1.longitude AS t_contacts_1_longitude, t_contacts_1.start_datetime AS t_contacts_1_start_datetime, t_contacts_1.executed_route_point_id AS t_contacts_1_executed_route_point_id, t_form_answers_1.id AS t_form_answers_1_id, t_form_answers_1.form_response_id AS t_form_answers_1_form_response_id, t_form_answers_1.question_id AS t_form_answers_1_question_id, t_form_answers_1.answer_value AS t_form_answers_1_answer_value, t_persons_1.id AS t_persons_1_id, t_persons_1.first_name AS t_persons_1_first_name, t_persons_1.paternal_last_name AS t_persons_1_paternal_last_name, t_persons_1.maternal_last_name AS t_persons_1_maternal_last_name, t_persons_1.email AS t_persons_1_email, t_persons_1.phone_number AS t_persons_1_phone_number, t_persons_1.phone_number_2 AS t_persons_1_phone_number_2, t_persons_1.birth_date AS t_persons_1_birth_date, t_persons_1.identification_document_type AS t_persons_1_identification_document_type, t_persons_1.identification_number AS t_persons_1_identification_number, t_persons_1.identification_expedition_place AS t_persons_1_identification_expedition_place, t_persons_1.observations AS t_persons_1_observations, t_persons_1.is_affiliated AS t_persons_1_is_affiliated, t_persons_1.affiliation_date AS t_persons_1_affiliation_date, t_persons_1.affiliation_user_id AS t_persons_1_affiliation_user_id, t_persons_1.is_referred AS t_persons_1_is_referred, t_persons_1.referred_note AS t_persons_1_referred_note 
FROM t_form_responses INNER JOIN t_contacts ON t_contacts.id = t_form_responses.contact_id INNER JOIN t_persons ON t_persons.id = t_form_responses.person_id LEFT OUTER JOIN t_form_answers ON t_form_responses.id = t_form_answers.form_response_id LEFT OUTER JOIN t_contacts AS t_contacts_1 ON t_contacts_1.id = t_form_responses.contact_id LEFT OUTER JOIN t_form_answers AS t_form_answers_1 ON t_form_responses.id = t_form_answers_1.form_response_id LEFT OUTER JOIN t_persons AS t_persons_1 ON t_persons_1.id = t_form_responses.person_id 
WHERE t_contacts.executed_route_point_id IN (%(executed_route_point_id_1_1)s, %(executed_route_point_id_1_2)s, %(executed_route_point_id_1_3)s, %(executed_route_point_id_1_4)s, %(executed_route_point_id_1_5)s, %(executed_route_point_id_1_6)s, %(executed_route_point_id_1_7)s, %(executed_route_point_id_1_8)s, %(executed_route_point_id_1_9)s, %(executed_route_point_id_1_10)s, %(executed_route_point_id_1_11)s, %(executed_route_point_id_1_12)s, %(executed_route_point_id_1_13)s, %(executed_route_point_id_1_14)s, %(executed_route_point_id_1_15)s, %(executed_route_point_id_1_16)s, %(executed_route_point_id_1_17)s, %(executed_route_point_id_1_18)s, %(executed_route_point_id_1_19)s, %(executed_route_point_id_1_20)s, %(executed_route_point_id_1_21)s, %(executed_route_point_id_1_22)s, %(executed_route_point_id_1_23)s, %(executed_route_point_id_1_24)s, %(executed_route_point_id_1_25)s, %(executed_route_point_id_1_26)s, %(executed_route_point_id_1_27)s, %(executed_route_point_id_1_28)s, %(executed_route_point_id_1_29)s, %(executed_route_point_id_1_30)s, %(executed_route_point_id_1_31)s, %(executed_route_point_id_1_32)s, %(executed_route_point_id_1_33)s, %(executed_route_point_id_1_34)s, %(executed_route_point_id_1_35)s, %(executed_route_point_id_1_36)s, %(executed_route_point_id_1_37)s, %(executed_route_point_id_1_38)s, %(executed_route_point_id_1_39)s, %(executed_route_point_id_1_40)s, %(executed_route_point_id_1_41)s, %(executed_route_point_id_1_42)s, %(executed_route_point_id_1_43)s, %(executed_route_point_id_1_44)s, %(executed_route_point_id_1_45)s, %(executed_route_point_id_1_46)s, %(executed_route_point_id_1_47)s, %(executed_route_point_id_1_48)s, %(executed_route_point_id_1_49)s, %(executed_route_point_id_1_50)s, %(executed_route_point_id_1_51)s, %(executed_route_point_id_1_52)s, %(executed_route_point_id_1_53)s, %(executed_route_point_id_1_54)s, %(executed_route_point_id_1_55)s, %(executed_route_point_id_1_56)s, %(executed_route_point_id_1_57)s, %(executed_route_point_id_1_58)s, %(executed_route_point_id_1_59)s, %(executed_route_point_id_1_60)s, %(executed_route_point_id_1_61)s, %(executed_route_point_id_1_62)s, %(executed_route_point_id_1_63)s, %(executed_route_point_id_1_64)s, %(executed_route_point_id_1_65)s, %(executed_route_point_id_1_66)s, %(executed_route_point_id_1_67)s, %(executed_route_point_id_1_68)s, %(executed_route_point_id_1_69)s, %(executed_route_point_id_1_70)s, %(executed_route_point_id_1_71)s, %(executed_route_point_id_1_72)s, %(executed_route_point_id_1_73)s, %(executed_route_point_id_1_74)s, %(executed_route_point_id_1_75)s, %(executed_route_point_id_1_76)s, %(executed_route_point_id_1_77)s, %(executed_route_point_id_1_78)s, %(executed_route_point_id_1_79)s, %(executed_route_point_id_1_80)s, %(executed_route_point_id_1_81)s, %(executed_route_point_id_1_82)s, %(executed_route_point_id_1_83)s, %(executed_route_point_id_1_84)s, %(executed_route_point_id_1_85)s, %(executed_route_point_id_1_86)s, %(executed_route_point_id_1_87)s, %(executed_route_point_id_1_88)s, %(executed_route_point_id_1_89)s, %(executed_route_point_id_1_90)s, %(executed_route_point_id_1_91)s, %(executed_route_point_id_1_92)s, %(executed_route_point_id_1_93)s, %(executed_route_point_id_1_94)s, %(executed_route_point_id_1_95)s, %(executed_route_point_id_1_96)s, %(executed_route_point_id_1_97)s, %(executed_route_point_id_1_98)s, %(executed_route_point_id_1_99)s, %(executed_route_point_id_1_100)s, %(executed_route_point_id_1_101)s, %(executed_route_point_id_1_102)s, %(executed_route_point_id_1_103)s, %(executed_route_point_id_1_104)s, %(executed_route_point_id_1_105)s, %(executed_route_point_id_1_106)s, %(executed_route_point_id_1_107)s, %(executed_route_point_id_1_108)s, %(executed_route_point_id_1_109)s, %(executed_route_point_id_1_110)s, %(executed_route_point_id_1_111)s, %(executed_route_point_id_1_112)s, %(executed_route_point_id_1_113)s, %(executed_route_point_id_1_114)s, %(executed_route_point_id_1_115)s, %(executed_route_point_id_1_116)s, %(executed_route_point_id_1_117)s, %(executed_route_point_id_1_118)s, %(executed_route_point_id_1_119)s, %(executed_route_point_id_1_120)s, %(executed_route_point_id_1_121)s, %(executed_route_point_id_1_122)s, %(executed_route_point_id_1_123)s, %(executed_route_point_id_1_124)s, %(executed_route_point_id_1_125)s, %(executed_route_point_id_1_126)s, %(executed_route_point_id_1_127)s, %(executed_route_point_id_1_128)s, %(executed_route_point_id_1_129)s, %(executed_route_point_id_1_130)s, %(executed_route_point_id_1_131)s, %(executed_route_point_id_1_132)s, %(executed_route_point_id_1_133)s, %(executed_route_point_id_1_134)s, %(executed_route_point_id_1_135)s, %(executed_route_point_id_1_136)s, %(executed_route_point_id_1_137)s, %(executed_route_point_id_1_138)s, %(executed_route_point_id_1_139)s, %(executed_route_point_id_1_140)s, %(executed_route_point_id_1_141)s, %(executed_route_point_id_1_142)s, %(executed_route_point_id_1_143)s, %(executed_route_point_id_1_144)s, %(executed_route_point_id_1_145)s, %(executed_route_point_id_1_146)s, %(executed_route_point_id_1_147)s, %(executed_route_point_id_1_148)s, %(executed_route_point_id_1_149)s, %(executed_route_point_id_1_150)s, %(executed_route_point_id_1_151)s, %(executed_route_point_id_1_152)s, %(executed_route_point_id_1_153)s, %(executed_route_point_id_1_154)s, %(executed_route_point_id_1_155)s, %(executed_route_point_id_1_156)s, %(executed_route_point_id_1_157)s, %(executed_route_point_id_1_158)s, %(executed_route_point_id_1_159)s, %(executed_route_point_id_1_160)s, %(executed_route_point_id_1_161)s, %(executed_route_point_id_1_162)s, %(executed_route_point_id_1_163)s, %(executed_route_point_id_1_164)s, %(executed_route_point_id_1_165)s, %(executed_route_point_id_1_166)s, %(executed_route_point_id_1_167)s, %(executed_route_point_id_1_168)s, %(executed_route_point_id_1_169)s, %(executed_route_point_id_1_170)s, %(executed_route_point_id_1_171)s, %(executed_route_point_id_1_172)s, %(executed_route_point_id_1_173)s, %(executed_route_point_id_1_174)s, %(executed_route_point_id_1_175)s, %(executed_route_point_id_1_176)s, %(executed_route_point_id_1_177)s, %(executed_route_point_id_1_178)s, %(executed_route_point_id_1_179)s, %(executed_route_point_id_1_180)s, %(executed_route_point_id_1_181)s, %(executed_route_point_id_1_182)s, %(executed_route_point_id_1_183)s, %(executed_route_point_id_1_184)s, %(executed_route_point_id_1_185)s, %(executed_route_point_id_1_186)s, %(executed_route_point_id_1_187)s, %(executed_route_point_id_1_188)s, %(executed_route_point_id_1_189)s, %(executed_route_point_id_1_190)s, %(executed_route_point_id_1_191)s, %(executed_route_point_id_1_192)s, %(executed_route_point_id_1_193)s, %(executed_route_point_id_1_194)s, %(executed_route_point_id_1_195)s, %(executed_route_point_id_1_196)s, %(executed_route_point_id_1_197)s, %(executed_route_point_id_1_198)s, %(executed_route_point_id_1_199)s, %(executed_route_point_id_1_200)s, %(executed_route_point_id_1_201)s, %(executed_route_point_id_1_202)s, %(executed_route_point_id_1_203)s, %(executed_route_point_id_1_204)s, %(executed_route_point_id_1_205)s, %(executed_route_point_id_1_206)s, %(executed_route_point_id_1_207)s, %(executed_route_point_id_1_208)s, %(executed_route_point_id_1_209)s, %(executed_route_point_id_1_210)s, %(executed_route_point_id_1_211)s, %(executed_route_point_id_1_212)s, %(executed_route_point_id_1_213)s, %(executed_route_point_id_1_214)s, %(executed_route_point_id_1_215)s, %(executed_route_point_id_1_216)s, %(executed_route_point_id_1_217)s, %(executed_route_point_id_1_218)s, %(executed_route_point_id_1_219)s, %(executed_route_point_id_1_220)s, %(executed_route_point_id_1_221)s, %(executed_route_point_id_1_222)s, %(executed_route_point_id_1_223)s, %(executed_route_point_id_1_224)s, %(executed_route_point_id_1_225)s, %(executed_route_point_id_1_226)s, %(executed_route_point_id_1_227)s, %(executed_route_point_id_1_228)s, %(executed_route_point_id_1_229)s, %(executed_route_point_id_1_230)s, %(executed_route_point_id_1_231)s, %(executed_route_point_id_1_232)s, %(executed_route_point_id_1_233)s, %(executed_route_point_id_1_234)s, %(executed_route_point_id_1_235)s, %(executed_route_point_id_1_236)s, %(executed_route_point_id_1_237)s, %(executed_route_point_id_1_238)s, %(executed_route_point_id_1_239)s, %(executed_route_point_id_1_240)s, %(executed_route_point_id_1_241)s, %(executed_route_point_id_1_242)s, %(executed_route_point_id_1_243)s, %(executed_route_point_id_1_244)s, %(executed_route_point_id_1_245)s, %(executed_route_point_id_1_246)s, %(executed_route_point_id_1_247)s, %(executed_route_point_id_1_248)s, %(executed_route_point_id_1_249)s, %(executed_route_point_id_1_250)s, %(executed_route_point_id_1_251)s, %(executed_route_point_id_1_252)s, %(executed_route_point_id_1_253)s, %(executed_route_point_id_1_254)s, %(executed_route_point_id_1_255)s, %(executed_route_point_id_1_256)s, %(executed_route_point_id_1_257)s, %(executed_route_point_id_1_258)s, %(executed_route_point_id_1_259)s, %(executed_route_point_id_1_260)s, %(executed_route_point_id_1_261)s, %(executed_route_point_id_1_262)s, %(executed_route_point_id_1_263)s, %(executed_route_point_id_1_264)s, %(executed_route_point_id_1_265)s, %(executed_route_point_id_1_266)s, %(executed_route_point_id_1_267)s, %(executed_route_point_id_1_268)s, %(executed_route_point_id_1_269)s, %(executed_route_point_id_1_270)s, %(executed_route_point_id_1_271)s, %(executed_route_point_id_1_272)s, %(executed_route_point_id_1_273)s, %(executed_route_point_id_1_274)s, %(executed_route_point_id_1_275)s, %(executed_route_point_id_1_276)s, %(executed_route_point_id_1_277)s, %(executed_route_point_id_1_278)s, %(executed_route_point_id_1_279)s, %(executed_route_point_id_1_280)s, %(executed_route_point_id_1_281)s, %(executed_route_point_id_1_282)s, %(executed_route_point_id_1_283)s, %(executed_route_point_id_1_284)s, %(executed_route_point_id_1_285)s, %(executed_route_point_id_1_286)s, %(executed_route_point_id_1_287)s, %(executed_route_point_id_1_288)s, %(executed_route_point_id_1_289)s, %(executed_route_point_id_1_290)s, %(executed_route_point_id_1_291)s, %(executed_route_point_id_1_292)s, %(executed_route_point_id_1_293)s, %(executed_route_point_id_1_294)s, %(executed_route_point_id_1_295)s, %(executed_route_point_id_1_296)s, %(executed_route_point_id_1_297)s, %(executed_route_point_id_1_298)s, %(executed_route_point_id_1_299)s, %(executed_route_point_id_1_300)s, %(executed_route_point_id_1_301)s, %(executed_route_point_id_1_302)s, %(executed_route_point_id_1_303)s, %(executed_route_point_id_1_304)s, %(executed_route_point_id_1_305)s, %(executed_route_point_id_1_306)s, %(executed_route_point_id_1_307)s, %(executed_route_point_id_1_308)s, %(executed_route_point_id_1_309)s, %(executed_route_point_id_1_310)s, %(executed_route_point_id_1_311)s, %(executed_route_point_id_1_312)s, %(executed_route_point_id_1_313)s, %(executed_route_point_id_1_314)s, %(executed_route_point_id_1_315)s, %(executed_route_point_id_1_316)s, %(executed_route_point_id_1_317)s, %(executed_route_point_id_1_318)s, %(executed_route_point_id_1_319)s, %(executed_route_point_id_1_320)s, %(executed_route_point_id_1_321)s, %(executed_route_point_id_1_322)s, %(executed_route_point_id_1_323)s, %(executed_route_point_id_1_324)s, %(executed_route_point_id_1_325)s, %(executed_route_point_id_1_326)s, %(executed_route_point_id_1_327)s, %(executed_route_point_id_1_328)s, %(executed_route_point_id_1_329)s, %(executed_route_point_id_1_330)s, %(executed_route_point_id_1_331)s, %(executed_route_point_id_1_332)s, %(executed_route_point_id_1_333)s, %(executed_route_point_id_1_334)s, %(executed_route_point_id_1_335)s, %(executed_route_point_id_1_336)s, %(executed_route_point_id_1_337)s, %(executed_route_point_id_1_338)s, %(executed_route_point_id_1_339)s, %(executed_route_point_id_1_340)s, %(executed_route_point_id_1_341)s, %(executed_route_point_id_1_342)s, %(executed_route_point_id_1_343)s, %(executed_route_point_id_1_344)s, %(executed_route_point_id_1_345)s, %(executed_route_point_id_1_346)s, %(executed_route_point_id_1_347)s, %(executed_route_point_id_1_348)s, %(executed_route_point_id_1_349)s, %(executed_route_point_id_1_350)s, %(executed_route_point_id_1_351)s, %(executed_route_point_id_1_352)s, %(executed_route_point_id_1_353)s, %(executed_route_point_id_1_354)s, %(executed_route_point_id_1_355)s, %(executed_route_point_id_1_356)s, %(executed_route_point_id_1_357)s, %(executed_route_point_id_1_358)s, %(executed_route_point_id_1_359)s, %(executed_route_point_id_1_360)s, %(executed_route_point_id_1_361)s, %(executed_route_point_id_1_362)s, %(executed_route_point_id_1_363)s, %(executed_route_point_id_1_364)s, %(executed_route_point_id_1_365)s, %(executed_route_point_id_1_366)s, %(executed_route_point_id_1_367)s, %(executed_route_point_id_1_368)s, %(executed_route_point_id_1_369)s, %(executed_route_point_id_1_370)s, %(executed_route_point_id_1_371)s, %(executed_route_point_id_1_372)s, %(executed_route_point_id_1_373)s, %(executed_route_point_id_1_374)s, %(executed_route_point_id_1_375)s, %(executed_route_point_id_1_376)s, %(executed_route_point_id_1_377)s, %(executed_route_point_id_1_378)s, %(executed_route_point_id_1_379)s, %(executed_route_point_id_1_380)s, %(executed_route_point_id_1_381)s, %(executed_route_point_id_1_382)s, %(executed_route_point_id_1_383)s, %(executed_route_point_id_1_384)s, %(executed_route_point_id_1_385)s, %(executed_route_point_id_1_386)s, %(executed_route_point_id_1_387)s, %(executed_route_point_id_1_388)s, %(executed_route_point_id_1_389)s, %(executed_route_point_id_1_390)s, %(executed_route_point_id_1_391)s, %(executed_route_point_id_1_392)s, %(executed_route_point_id_1_393)s, %(executed_route_point_id_1_394)s, %(executed_route_point_id_1_395)s, %(executed_route_point_id_1_396)s, %(executed_route_point_id_1_397)s, %(executed_route_point_id_1_398)s, %(executed_route_point_id_1_399)s, %(executed_route_point_id_1_400)s, %(executed_route_point_id_1_401)s, %(executed_route_point_id_1_402)s, %(executed_route_point_id_1_403)s, %(executed_route_point_id_1_404)s, %(executed_route_point_id_1_405)s, %(executed_route_point_id_1_406)s, %(executed_route_point_id_1_407)s, %(executed_route_point_id_1_408)s, %(executed_route_point_id_1_409)s, %(executed_route_point_id_1_410)s, %(executed_route_point_id_1_411)s, %(executed_route_point_id_1_412)s, %(executed_route_point_id_1_413)s, %(executed_route_point_id_1_414)s, %(executed_route_point_id_1_415)s, %(executed_route_point_id_1_416)s, %(executed_route_point_id_1_417)s, %(executed_route_point_id_1_418)s, %(executed_route_point_id_1_419)s, %(executed_route_point_id_1_420)s, %(executed_route_point_id_1_421)s, %(executed_route_point_id_1_422)s, %(executed_route_point_id_1_423)s, %(executed_route_point_id_1_424)s, %(executed_route_point_id_1_425)s, %(executed_route_point_id_1_426)s, %(executed_route_point_id_1_427)s, %(executed_route_point_id_1_428)s, %(executed_route_point_id_1_429)s, %(executed_route_point_id_1_430)s, %(executed_route_point_id_1_431)s, %(executed_route_point_id_1_432)s, %(executed_route_point_id_1_433)s, %(executed_route_point_id_1_434)s, %(executed_route_point_id_1_435)s, %(executed_route_point_id_1_436)s, %(executed_route_point_id_1_437)s, %(executed_route_point_id_1_438)s, %(executed_route_point_id_1_439)s, %(executed_route_point_id_1_440)s, %(executed_route_point_id_1_441)s, %(executed_route_point_id_1_442)s, %(executed_route_point_id_1_443)s, %(executed_route_point_id_1_444)s, %(executed_route_point_id_1_445)s, %(executed_route_point_id_1_446)s, %(executed_route_point_id_1_447)s, %(executed_route_point_id_1_448)s, %(executed_route_point_id_1_449)s, %(executed_route_point_id_1_450)s, %(executed_route_point_id_1_451)s, %(executed_route_point_id_1_452)s, %(executed_route_point_id_1_453)s, %(executed_route_point_id_1_454)s, %(executed_route_point_id_1_455)s, %(executed_route_point_id_1_456)s, %(executed_route_point_id_1_457)s, %(executed_route_point_id_1_458)s, %(executed_route_point_id_1_459)s, %(executed_route_point_id_1_460)s, %(executed_route_point_id_1_461)s, %(executed_route_point_id_1_462)s, %(executed_route_point_id_1_463)s, %(executed_route_point_id_1_464)s, %(executed_route_point_id_1_465)s, %(executed_route_point_id_1_466)s, %(executed_route_point_id_1_467)s, %(executed_route_point_id_1_468)s, %(executed_route_point_id_1_469)s, %(executed_route_point_id_1_470)s, %(executed_route_point_id_1_471)s, %(executed_route_point_id_1_472)s, %(executed_route_point_id_1_473)s, %(executed_route_point_id_1_474)s, %(executed_route_point_id_1_475)s, %(executed_route_point_id_1_476)s, %(executed_route_point_id_1_477)s, %(executed_route_point_id_1_478)s, %(executed_route_point_id_1_479)s, %(executed_route_point_id_1_480)s, %(executed_route_point_id_1_481)s, %(executed_route_point_id_1_482)s, %(executed_route_point_id_1_483)s, %(executed_route_point_id_1_484)s, %(executed_route_point_id_1_485)s, %(executed_route_point_id_1_486)s, %(executed_route_point_id_1_487)s, %(executed_route_point_id_1_488)s, %(executed_route_point_id_1_489)s, %(executed_route_point_id_1_490)s, %(executed_route_point_id_1_491)s, %(executed_route_point_id_1_492)s, %(executed_route_point_id_1_493)s, %(executed_route_point_id_1_494)s, %(executed_route_point_id_1_495)s, %(executed_route_point_id_1_496)s, %(executed_route_point_id_1_497)s, %(executed_route_point_id_1_498)s, %(executed_route_point_id_1_499)s, %(executed_route_point_id_1_500)s, %(executed_route_point_id_1_501)s, %(executed_route_point_id_1_502)s, %(executed_route_point_id_1_503)s, %(executed_route_point_id_1_504)s, %(executed_route_point_id_1_505)s, %(executed_route_point_id_1_506)s, %(executed_route_point_id_1_507)s, %(executed_route_point_id_1_508)s, %(executed_route_point_id_1_509)s, %(executed_route_point_id_1_510)s, %(executed_route_point_id_1_511)s, %(executed_route_point_id_1_512)s, %(executed_route_point_id_1_513)s, %(executed_route_point_id_1_514)s, %(executed_route_point_id_1_515)s, %(executed_route_point_id_1_516)s, %(executed_route_point_id_1_517)s, %(executed_route_point_id_1_518)s, %(executed_route_point_id_1_519)s, %(executed_route_point_id_1_520)s, %(executed_route_point_id_1_521)s, %(executed_route_point_id_1_522)s, %(executed_route_point_id_1_523)s, %(executed_route_point_id_1_524)s, %(executed_route_point_id_1_525)s, %(executed_route_point_id_1_526)s, %(executed_route_point_id_1_527)s, %(executed_route_point_id_1_528)s, %(executed_route_point_id_1_529)s, %(executed_route_point_id_1_530)s, %(executed_route_point_id_1_531)s, %(executed_route_point_id_1_532)s, %(executed_route_point_id_1_533)s, %(executed_route_point_id_1_534)s, %(executed_route_point_id_1_535)s, %(executed_route_point_id_1_536)s, %(executed_route_point_id_1_537)s, %(executed_route_point_id_1_538)s, %(executed_route_point_id_1_539)s, %(executed_route_point_id_1_540)s, %(executed_route_point_id_1_541)s, %(executed_route_point_id_1_542)s, %(executed_route_point_id_1_543)s) AND t_form_responses.submission_date BETWEEN %(submission_date_1)s AND %(submission_date_2)s AND t_form_responses.company_id = %(company_id_1)s AND t_form_responses.service_id = %(service_id_1)s]
[parameters: {'submission_date_1': datetime.date(2025, 12, 5), 'submission_date_2': datetime.date(2025, 12, 10), 'company_id_1': 1, 'service_id_1': 1, 'executed_route_point_id_1_1': 325, 'executed_route_point_id_1_2': 401, 'executed_route_point_id_1_3': 406, 'executed_route_point_id_1_4': 407, 'executed_route_point_id_1_5': 408, 'executed_route_point_id_1_6': 463, 'executed_route_point_id_1_7': 555, 'executed_route_point_id_1_8': 561, 'executed_route_point_id_1_9': 908, 'executed_route_point_id_1_10': 1014, 'executed_route_point_id_1_11': 1134, 'executed_route_point_id_1_12': 1191, 'executed_route_point_id_1_13': 1192, 'executed_route_point_id_1_14': 1260, 'executed_route_point_id_1_15': 1322, 'executed_route_point_id_1_16': 1323, 'executed_route_point_id_1_17': 1510, 'executed_route_point_id_1_18': 1517, 'executed_route_point_id_1_19': 1797, 'executed_route_point_id_1_20': 1857, 'executed_route_point_id_1_21': 1859, 'executed_route_point_id_1_22': 1939, 'executed_route_point_id_1_23': 1955, 'executed_route_point_id_1_24': 1956, 'executed_route_point_id_1_25': 1977, 'executed_route_point_id_1_26': 1978, 'executed_route_point_id_1_27': 1983, 'executed_route_point_id_1_28': 2143, 'executed_route_point_id_1_29': 2144, 'executed_route_point_id_1_30': 2145, 'executed_route_point_id_1_31': 2250, 'executed_route_point_id_1_32': 2402, 'executed_route_point_id_1_33': 2406, 'executed_route_point_id_1_34': 2407, 'executed_route_point_id_1_35': 2408, 'executed_route_point_id_1_36': 2409, 'executed_route_point_id_1_37': 2586, 'executed_route_point_id_1_38': 2587, 'executed_route_point_id_1_39': 2588, 'executed_route_point_id_1_40': 2589, 'executed_route_point_id_1_41': 2590, 'executed_route_point_id_1_42': 4680, 'executed_route_point_id_1_43': 4681, 'executed_route_point_id_1_44': 4682, 'executed_route_point_id_1_45': 4683, 'executed_route_point_id_1_46': 4684 ... 447 parameters truncated ... 'executed_route_point_id_1_494': 6457, 'executed_route_point_id_1_495': 6478, 'executed_route_point_id_1_496': 6482, 'executed_route_point_id_1_497': 6620, 'executed_route_point_id_1_498': 6720, 'executed_route_point_id_1_499': 6725, 'executed_route_point_id_1_500': 6872, 'executed_route_point_id_1_501': 6873, 'executed_route_point_id_1_502': 6874, 'executed_route_point_id_1_503': 6876, 'executed_route_point_id_1_504': 6877, 'executed_route_point_id_1_505': 6945, 'executed_route_point_id_1_506': 7068, 'executed_route_point_id_1_507': 7070, 'executed_route_point_id_1_508': 7098, 'executed_route_point_id_1_509': 7111, 'executed_route_point_id_1_510': 7145, 'executed_route_point_id_1_511': 7724, 'executed_route_point_id_1_512': 7794, 'executed_route_point_id_1_513': 7795, 'executed_route_point_id_1_514': 7796, 'executed_route_point_id_1_515': 7797, 'executed_route_point_id_1_516': 7799, 'executed_route_point_id_1_517': 7800, 'executed_route_point_id_1_518': 7812, 'executed_route_point_id_1_519': 7813, 'executed_route_point_id_1_520': 7814, 'executed_route_point_id_1_521': 7815, 'executed_route_point_id_1_522': 7816, 'executed_route_point_id_1_523': 7868, 'executed_route_point_id_1_524': 7870, 'executed_route_point_id_1_525': 7871, 'executed_route_point_id_1_526': 7990, 'executed_route_point_id_1_527': 7997, 'executed_route_point_id_1_528': 7998, 'executed_route_point_id_1_529': 8060, 'executed_route_point_id_1_530': 8080, 'executed_route_point_id_1_531': 8288, 'executed_route_point_id_1_532': 8290, 'executed_route_point_id_1_533': 8291, 'executed_route_point_id_1_534': 8298, 'executed_route_point_id_1_535': 8301, 'executed_route_point_id_1_536': 8338, 'executed_route_point_id_1_537': 8339, 'executed_route_point_id_1_538': 8340, 'executed_route_point_id_1_539': 8345, 'executed_route_point_id_1_540': 8347, 'executed_route_point_id_1_541': 8460, 'executed_route_point_id_1_542': 8464, 'executed_route_point_id_1_543': 8465}]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
INFO:     127.0.0.1:64843 - "POST /forms/v1/reports/contacts-by-route HTTP/1.1" 500 Internal Server Error
2025-12-16 22:43:23,911 - smartbear - INFO - Usage log sent successfully. Status: 201

```
