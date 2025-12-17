# Requerimiento 1: Mejoras en el endpoint `/routes/planned/filter` microservicio LOCALIZATION

En el archivo `services/localization/routes/localization.py` tenemos la función `get_or_filter_planned_routes_endpoint` cuyo objeto que recibimos mediante el `query string` es:


## Request:

```Python
class PlannedRouteFilterSchema(BaseModel):
    '''
        Schema to filter planned routes based on various criteria.
    '''
    route_code: Optional[str] = Query(None, description = 'Unique code of the planned route.')
    route_name: Optional[str] = Query(None, description = 'Name of the planned route.')
    route_status: Optional[PlannedRouteStatusEnum] = Query(None,
                            description = 'Status of the planned route.')
    company_id: Optional[int] = Query(None, description = 'ID of the company who owns the route.')
    city_id: Optional[int] = Query(None,
                            description = 'ID of the city associated with the planned route.')

    class Config:# pylint: disable=too-few-public-methods
        '''
            This setting allows the class to be instantiated without arguments in
            the @router.get() decorator.
        '''
        arbitrary_types_allowed = True

```

El cliente ha solicitado que en la lista de opciones de filtro puedan recibir una lista de `IDs` de `RUTA PLANIFICADA` al menos un valor en la lista y que se mantenga la respuesta que se tiene actualmente que es:


## Response (lista):

```Python
class PlannedRouteListResponseSchema(LocalizationBaseSchema):
    '''
        Response schema for a list of planned routes. This is the missing class
        used by the list and filter endpoints.
    '''
    id: int
    route_name: str
    route_code: str
    description: Optional[str]
    company_id: int
    app_id: int
    city_id: int
    created_at: datetime
    status: PlannedRouteStatusEnum
    points: List[PlannedPointResponseSchema]

```

La diferencia cconsistiría en que si recibimos los `IDs` de las `RUTAS PLANIFICADAS` en la lista similar a esta `[1, 2, 3]` la repsuesta debería de incluir todos los atributos descritos en el `RESPONSE` de ejemplo para todos esos `IDs`. Queda todo claro? Tienes alguna duda?


# Requerimiento 2: Mejoras en el endpoint `/reports/contacts-by-route` microservicio FORMS

En el archivo `services/forms/routes/reports.py` tenemos la función `get_contacts_by_route_report` que es un método `POST`, el objeto que recibimos mediante el `raw body` es el siguiente:


## Request:

```Python
class ContactsByRouteReportRequestSchema(BaseModel):
    '''
        Schema to handle the request payload for the "Forms by Points and Contact" report.
        Includes all required and optional filtering variables.
    '''
    # --- Required Filtering Variables ---
    company_id: Optional[int] = Field(None,
            description = 'ID of the company to filter the report.')
    service_id:  Optional[int] = Field(None,
            description = 'ID of the service to filter the report.')

    # --- Date Filter (Required) ---
    submission_date_from: date = Field(...,
            description = 'Start date for the form submission date range.')
    submission_date_to: date = Field(...,
            description = 'End date for the form submission date range.')

    # --- Optional Filtering Variables ---
    team_id: Optional[int] = Field(None,
            description = 'Team ID to include.')
    user_id: Optional[int] = Field(None,
            description = 'User ID (affiliator) to include.')
    city_id: Optional[int] = Field(None,
            description = 'City ID to include.')
    planned_route_id: Optional[int] = Field(None,
            description = 'Planned route ID to include.')

    class Config: # pylint: disable=too-few-public-methods
        '''
            Pydantic config for the schema.
        '''
        from_attributes = True
```

El cliente ha solicitado que en la lista de opciones de filtro puedan recibir una lista de `IDs` de `RUTA PLANIFICADA` en lugar del valor `planned_route_id` que ahora es un único valor sea una lista que deba tener al menos un valor en la lista y que se mantenga la respuesta que se tiene actualmente que es:


## Response (lista):

```Python
class FormResponseDetailResponse(FormResponseBase):
    '''
        Response schema for a detailed completed form response.
        Includes ID, submission_date, and nested answers.
    '''
    id: int
    person_id: int = Field(..., description = 'ID of the person associated with this response.')
    submission_date: datetime = Field(...,
        description = 'Timestamp when the form response was submitted.')
    answers: List[FormAnswerResponse] = []
    contact: ContactResponse
    status_flow: List[FormResponseFlowResponse] = []

    class Config:# pylint: disable=too-few-public-methods
        '''
            FormResponseDetailResponse - Config Class - To get form attributes
        '''
        from_attributes = True

```

La diferencia cconsistiría en que es una lista de listasya que  si recibimos los `IDs` de las `RUTAS PLANIFICADAS` en la lista similar a esta `[1, 2, 3]` la repsuesta debería de incluir todos los atributos descritos en el `RESPONSE` de ejemplo para todos esos `IDs`. Queda todo claro? Tienes alguna duda?


# Datos adicionales

- Respeta todo lo descrito en el documento `GEMINI.md`

- Debes actualizar el archivo `README.md` si es que existen cambios que deban reflejarse ahí

- Crea o modifica el archivo tipo `md` con el nombre del microservicio que debe estar en la raíz de la carpeta del micro servicio que refleje la documentación necesaria que describa todo el microservicio que sea en inglés y que le permita a otro desarrollador entender todo lo necesario al respecto

- Los microservicios ya están en producción y necesitan estos cambios en los endpoints para mejorar sus reportes 

- Cualquier duda que tengas pregunta para que pueda darte más contexto de ser necesario

- Puedes hacer un commit con los cambios hechos y una descripción acorde al trabajo realizado

<!-- api.binaria.app -->