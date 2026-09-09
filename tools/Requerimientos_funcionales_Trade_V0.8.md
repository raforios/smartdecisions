Great – Módulo de Trade Marketing
Especificación de requerimientos
funcionales
Versión: 0.8
Fecha: 10/07/2025 – 10/10/2025

Great –Trade Marketing
Especificación de requerimientos funcionales

HISTORIAL DEL DOCUMENTO

|                         | Autor  |     | Fecha       | Versión  |
| ----------------------- | ------ | --- | ----------- | -------- |
| Paula Soto Montpellier  |        |     | 10/07/2025  | 0.1      |
Estructura general de Trade.
Parámetros y catálogos de Afiliaciones.
| Paula Soto Montpellier  |     |     | 31/07/2025  | 0.2  |
| ----------------------- | --- | --- | ----------- | ---- |
Funcionalidades para Afiliaciones (hasta “Registrar afiliación”).
| Paula Soto Montpellier  |     |     | 12/08/2025  | 0.3  |
| ----------------------- | --- | --- | ----------- | ---- |
Correcciones y mejoras a transacciones anteriores.
| Paula Soto Montpellier  |     |     | 14/08/2025  | 0.4  |
| ----------------------- | --- | --- | ----------- | ---- |
Funcionalidades para Afiliaciones (hasta “Consultar afiliaciones”).
| Paula Soto Montpellier  |     |     | 21/08/2025  | 0.5  |
| ----------------------- | --- | --- | ----------- | ---- |
Funcionalidades para Afiliaciones; nuevo “Monitor de afiliaciones”.
| Paula Soto Montpellier  |     |     | 26/08/2025  | 0.6  |
| ----------------------- | --- | --- | ----------- | ---- |
Reporte de Afiliaciones.
| Paula Soto Montpellier  |     |     | 16/09/2025  | 0.7  |
| ----------------------- | --- | --- | ----------- | ---- |
Parámetros, catálogos, transacciones de Impulsos (excepto bandeo y
puntos promocionales).
Ajustes en inicio y fin de ruta de Afiliaciones.
| Paula Soto Montpellier  |     |     | 10/10/2025  | 0.8  |
| ----------------------- | --- | --- | ----------- | ---- |
Transacciones finales de Impulsos. Transacciones de Reposiciones.

| Revisado por  | Fecha  | Motivo  |     | Versión  |
| ------------- | ------ | ------- | --- | -------- |
Equipo de proyecto  03/09/2025  Revisión de avance del desarrollo de  0.6
Afiliaciones contrastado con los
requerimientos.
Paula Soto  17/09/2025  Revisión de monitor y de reportes de  0.7
Rafael Ríos  Afiliaciones previa al desarrollo.
Revisión de Impulsos previa al desarrollo.
|     |     |     |     |     |
| --- | --- | --- | --- | --- |

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
Versión 0.8  Estrictamente privado y confidencial  Página 2 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
CONTENIDO
1 Estructura interna ................................................................................................ 6
1.1 General ........................................................................................................ 6
1.2 Seguridad .................................................................................................... 6
1.3 Trade ........................................................................................................... 6
1.3.1 Afiliaciones ............................................................................................ 7
1.3.2 Reposiciones e Impulsos .......................................................................... 7
2 Definiciones generales para este documento ........................................................... 9
2.1 Notación ...................................................................................................... 9
2.2 Definiciones de datos para este documento ...................................................... 9
3 Definiciones generales para el sistema .................................................................. 10
3.1 Opciones generales para los parámetros ........................................................ 10
3.2 Opciones generales para los catálogos ........................................................... 10
3.3 Estándares para el ingreso y almacenamiento de datos en el sistema ................ 11
3.4 Estándares para el uso de datos en el sistema ................................................ 11
3.5 Otras características generales...................................................................... 11
4 Parámetros ....................................................................................................... 12
4.1 Parámetros generales .................................................................................. 12
4.1.1 Zonas ................................................................................................. 12
4.1.2 Unidades de medida.............................................................................. 12
4.1.3 Equivalencias internas de unidades de medida ......................................... 13
4.2 Parámetros de compañía .............................................................................. 13
4.2.1 Objetos internos ................................................................................... 13
4.2.2 Regionales ........................................................................................... 14
4.3 Parámetros de Seguridad ............................................................................. 14
4.3.1 Asignación de grupos de empleados a usuarios ........................................ 14
4.3.2 Asignación de estados de servicios a roles ............................................... 15
4.4 Parámetros de Afiliaciones ............................................................................ 15
4.4.1 Formularios ......................................................................................... 15
4.4.2 Servicios ............................................................................................. 17
4.5 Parámetros de Trade ................................................................................... 19
4.5.1 Tipos de puntos de venta ....................................................................... 19
4.5.2 Canales ............................................................................................... 20
4.5.3 Categorías ........................................................................................... 20
4.5.4 Valores de categorías ............................................................................ 21
5 Catálogos de Trade ............................................................................................ 22
5.1 Equipos de trabajo ...................................................................................... 22
5.2 Puntos de venta .......................................................................................... 23
5.3 Productos ................................................................................................... 24
5.4 Equivalencias de códigos de productos ........................................................... 28
6 Afiliaciones ........................................................................................................ 29
6.1 Catálogos de Afiliaciones .............................................................................. 29
6.1.1 Rutas de afiliación ................................................................................ 29
6.2 Transacciones ............................................................................................. 30
6.2.1 Planificación ......................................................................................... 31
6.2.1.1 Habilitar periodo de afiliaciones ....................................................... 31
6.2.1.2 Planificación de afiliaciones ............................................................. 32
Versión 0.8 Estrictamente privado y confidencial Página 3 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6.2.2 Ejecución de ruta .................................................................................. 35
6.2.2.1 Iniciar ruta de afiliaciones ............................................................... 35
6.2.2.2 Registrar contacto .......................................................................... 37
6.2.2.3 Registrar afiliación ......................................................................... 39
6.2.2.4 Registrar referido ........................................................................... 46
6.2.2.5 Finalizar ruta de afiliaciones ............................................................ 47
6.2.3 Revisar afiliaciones ............................................................................... 49
6.2.3.1 Validar afiliación ............................................................................ 49
6.2.3.2 Consultar afiliaciones ...................................................................... 51
6.3 Monitor de afiliaciones ................................................................................. 53
6.3.1 Panel de control ................................................................................... 53
6.3.2 Seguimiento de rutas ............................................................................ 61
6.4 Reportes .................................................................................................... 63
6.4.1 Agenda de campo ................................................................................. 63
6.4.2 Listado de personas .............................................................................. 66
6.4.3 Listado de afiliaciones ........................................................................... 66
6.4.4 Listado de referidos .............................................................................. 66
7 Trade ............................................................................................................... 67
7.1 Catálogos específicos ................................................................................... 67
7.1.1 Rutas .................................................................................................. 67
7.2 Planificación ............................................................................................... 68
7.2.1 Asignar productos por PDV .................................................................... 68
7.2.2 Preparar bandeos ................................................................................. 71
7.2.3 Planificación semanal ............................................................................ 73
7.3 Actividades de ruta ...................................................................................... 77
7.3.1 Ingresar a PDV ..................................................................................... 78
7.3.2 Actividades de impulsos ........................................................................ 79
7.3.2.1 Inventario inicial de productos ......................................................... 79
7.3.2.2 Registrar venta .............................................................................. 81
7.3.2.3 Inventario final de productos ........................................................... 83
7.3.3 Actividades de reposición ....................................................................... 85
7.3.3.1 Registrar reposición ........................................................................ 85
7.3.3.2 Inventario de productos .................................................................. 86
7.3.3.3 Recepción de productos del proveedor .............................................. 89
7.3.4 Actividades complementarias ................................................................. 92
7.3.4.1 Registrar bandeo ........................................................................... 92
7.3.4.2 Registrar punto promocional ............................................................ 95
7.3.4.3 Registrar información de la competencia ........................................... 96
7.3.5 Salir de PDV ......................................................................................... 97
7.4 Monitor de Trade ......................................................................................... 99
7.4.1 Panel de control de Afiliaciones .............................................................. 99
7.4.2 Panel de control de Impulsos ............................................................... 107
7.4.3 Panel de control de Reposiciones .......................................................... 108
7.4.4 Seguimiento de rutas de Trade ............................................................. 117
7.5 Reportes .................................................................................................. 121
7.5.1 Planificación ....................................................................................... 121
7.5.1.1 Agenda de campo ........................................................................ 121
7.5.2 Impulsos ........................................................................................... 121
7.5.2.1 Reporte fotográfico de impulsos ..................................................... 121
7.5.2.2 Inventario ................................................................................... 121
Versión 0.8 Estrictamente privado y confidencial Página 4 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.5.2.3 Reporte de ventas ........................................................................ 121
7.5.2.4 Reporte fotográfico de ventas ........................................................ 122
7.5.3 Reposiciones ...................................................................................... 122
7.5.3.1 Reporte gráfico de reposiciones ..................................................... 122
7.5.3.2 Inventario por PDV ....................................................................... 122
7.5.3.3 Reporte de fecha corta ................................................................. 122
7.5.3.4 Reporte de quiebre de stock .......................................................... 122
7.5.4 Otros reportes .................................................................................... 122
7.5.4.1 Tiempos por PDV ......................................................................... 122
7.5.4.2 Reporte de bandeos ..................................................................... 122
7.5.4.3 Reporte de puntos promocionales .................................................. 122
Versión 0.8 Estrictamente privado y confidencial Página 5 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
1 Estructura interna
1.1 General
1.2 Seguridad
1.3 Trade
Nota funcional: Para el funcionamiento del módulo de “Trade”, cada cliente corporativo debe
ser creado como una compañía externa, de modo que pueda tener sus propios usuarios
externos y roles de acceso a la información de la compañía que corresponda. En
consecuencia, los parámetros de Trade se definen por compañía.
Versión 0.8 Estrictamente privado y confidencial Página 6 de 122
E n c u e s t a s A f i l i a c i o n
P
e
a
s
r á m e
R
t
e
r
S
o
p
e
s
o
g
s
u
i c
r i
i
d
o n
C
a d
e
a
s
t á l o g o
I m
s
p u l s o s

Great –Trade Marketing
Especificación de requerimientos funcionales
1.3.1 Afiliaciones
1.3.2 Reposiciones e Impulsos
Versión 0.8 Estrictamente privado y confidencial Página 7 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Versión 0.8 Estrictamente privado y confidencial Página 8 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
2 Definiciones generales para este documento
2.1 Notación
En el presente documento se remarcan partes con diferentes colores, cuyo significado es el
siguiente:
Verde Dato de tipo SI/NO o lista fija de valores, que se define como fija dado que es muy
probable que no cambie en el tiempo; no requiere parámetro.
Amarillo Tema que aun requiere revisión. No deben quedar temas amarillos para el desarrollo
del requerimiento.
Rojo Tema que se diseñó en versiones anteriores pero que ya no se utilizará (a partir de la
presente versión). No debe incluirse en los planes de desarrollo del módulo.
Magenta Temas nuevos o que cambiaron en este documento respecto de versiones anteriores.
2.2 Definiciones de datos para este documento
En este documento se hará referencia a los siguientes tipos de datos:
 Texto corto: significa un campo de tipo texto, de longitud máxima de 50 caracteres.
 Texto mediano: significa un campo de tipo texto, de longitud máxima de 100 caracteres.
 Texto largo: significa un campo de tipo texto, de longitud máxima de 250 caracteres.
 Texto ilimitado: significa un campo de tipo texto, de longitud ilimitada de caracteres.
Se definen también algunos detalles de formato para ciertos tipos de datos.
 Para todas las fechas del sistema:
• El formato de presentación debe ser DD/MM/AAAA.
• Se requiere que se use un control de calendario para el ingreso de todas las fechas.
• Sin embargo, las fechas también deben poderse ingresar manualmente.
• Se debe controlar que las fechas ingresadas, por control o manualmente, sean
fechas válidas.
 Para los textos inextensos (ilimitados), se debe usar un control tipo “editor de texto”.
 Para las listas de selección única se usará un control tipo “lista desplegable (combo
box)”.
 Para las listas de selección múltiple se usará un control tipo “lista múltiple”.
 Las tablas de datos en pantalla se deben poder ordenar y filtrar por cualquiera de sus
columnas. Se deben paginar en bloques de a 10 registros. La carga de datos en pantalla
se debe hacer de 1 página (10 registros) a la vez (no cargar todos los registros en una
sola llamada).
Versión 0.8 Estrictamente privado y confidencial Página 9 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
3 Definiciones generales para el sistema
3.1 Opciones generales para los parámetros
Todos los parámetros deben incluir el dato “Estado” con los valores “Activo (si) / Inactivo
(no)”. Sólo los registros “Activos” se pueden ver y utilizar en otras funcionalidades del
sistema. Un registro “Inactivo” no debe aparecer en otras pantallas del sistema – no se
usará más; este estado se usa para registros que dejan de necesitarse, pero que no pueden
ser eliminados por integridad de la base de datos (ya se usaron en referencias anteriores).
Todos los parámetros del sistema deben contar con las siguientes opciones:
 Crear,
 Visualizar,
 Editar, y
 Eliminar.
La opción “Eliminar” debe permitirse si y sólo si el/los registro/s seleccionado/s para
eliminarse no se referencia/n en otros registros del sistema (control de integridad
referencial).
Si algún parámetro necesita opciones diferentes a las anteriores lo especificará
explícitamente es su definición.
3.2 Opciones generales para los catálogos
Todos los parámetros deben incluir el dato “Estado” con los valores “Activo (si) / Inactivo
(no)”. Sólo los registros activos se pueden ver y utilizar en otras funcionalidades del
sistema.
Todos los catálogos del sistema deben contar con las siguientes opciones:
 Crear,
 Visualizar,
 Editar,
 Copiar,
 Eliminar,
 Importar, y
 Exportar.
La opción “Eliminar” debe permitirse si y sólo si el/los registro/s seleccionado/s para
eliminarse no se referencia/n en otros registros del sistema (control de integridad
referencial).
Si algún catálogo necesita opciones diferentes a las anteriores lo especificará explícitamente
es su definición.
Versión 0.8 Estrictamente privado y confidencial Página 10 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
3.3 Estándares para el ingreso y almacenamiento de datos en el
sistema
 Toda la información del sistema debe grabarse en las tablas en letras mayúsculas,
minúsculas, con acentos y con caracteres especiales, tal cual sea ingresada.
 Toda importación de datos al sistema debe leer datos de un archivo de texto separado
por pipes “|” codificado UTF-8, y guardarlos en la tabla/s que corresponda.
 Toda exportación de datos desde el sistema debe generar un archivo de datos que
contenga los registros seleccionados, en formato de texto separado por pipes “|”
codificado UTF-8.
 Las exportaciones de datos se llevarán a la bandeja de descargas del usuario que
exporta, en todos los casos.
3.4 Estándares para el uso de datos en el sistema
 Cuando una transacción del sistema utilice un parámetro lo hará a través de un combo
box. No se introducirán códigos de parámetros manualmente.
 Cuando una transacción del sistema utilice un catálogo lo hará a través de una lista con
opción de búsqueda, o de un botón de búsqueda de registros en catálogos, el cual
llamará a un diálogo de tipo modal para búsqueda del valor. Se usará el más
conveniente y simple, según la complejidad del catálogo lo requiera.
3.5 Otras características generales
 El sistema debe ser multi idioma. Para esto:
• Todas las etiquetas de pantallas, reportes u otras funcionalidades, deben mostrarse
al usuario en su idioma seleccionado (de una lista fija).
• Todo usuario tendrá un idioma definido en sus opciones.
• El sistema tendrá un archivo “diccionario”, donde se realice la traducción de todas
las etiquetas a N idiomas.
• El idioma debe poderse cambiar en la pantalla de ingreso al sistema y/o una vez
logeado. Cada cambio debe guardarse como opción del usuario.
• Para la primera versión del sistema se preparará el idioma español.
• El idioma no aplica a los datos de la base de datos.
 Cada vez que el sistema realice una búsqueda de registros deberá presentar los
resultados en una lista. Las listas deben incluir columnas para los datos más
importantes de sus registros, que permitan identificar cada registro con claridad. Deben
ser listas paginadas, con 10 registros a la vez (definir la cantidad en alguna variable que
pueda ser modificada).
 Toda opción de impresión del sistema debe generar un pdf, que podrá ser guardado
como archivo o impreso una vez que se visualice en pantalla, con opciones estándar de
este tipo de archivos.
Versión 0.8 Estrictamente privado y confidencial Página 11 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
4 Parámetros
4.1 Parámetros generales
4.1.1 Zonas
Definición
Parámetro para crear “Zonas” (barrios, distritos u otro sinónimo) dentro de una ciudad en el
sistema.
Datos
Los datos requeridos para este parámetro son al menos la siguiente:
Dato Condición Descripción
País Obligatorio Código de país, del parámetro “Países”.
Ciudad Obligatorio Código de ciudad, para el país seleccionado.
Código Obligatorio Código de Zona.
Nombre Obligatorio Texto mediano. Nombre o descripción de la zona.
Estado Obligatorio Activo / Inactivo, estándar.
4.1.2 Unidades de medida
Definición
Parámetro para definir las unidades de los diferentes productos en el sistema, siendo que
cada producto podrá utilizar varias unidades de medida en función de la actividad en la que
se usarán.
Datos
Los datos requeridos para este parámetro son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía.
Código Obligatorio Código de unidad de medida. Alfanumérico de hasta 3
caracteres.
Nombre Obligatorio Texto corto. Nombre de la unidad de medida.
Estado Obligatorio Activo / Inactivo, estándar.
Versión 0.8 Estrictamente privado y confidencial Página 12 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

4.1.3 Equivalencias internas de unidades de medida

Definición
Parámetro para definir las equivalencias que se pueden manejar entre diferentes unidades
de medida, para fines de actividades específicas con diferentes productos.

Datos
Los datos requeridos para este parámetro son al menos los siguientes:

|           | Dato  |     | Condición    |                      | Descripción  |
| --------- | ----- | --- | ------------ | -------------------- | ------------ |
| Compañía  |       |     | Obligatorio  | Código de compañía.  |              |

Unidad de medida  Obligatorio  Código  de  una  unidad  de  medida,  de  la  compañía
seleccionada.

| Cantidad  |     |     | Obligatorio  | Número entero mayor o igual a 1.  |     |
| --------- | --- | --- | ------------ | --------------------------------- | --- |

Unidad de medida  Obligatorio  Código  de  una  segunda  unidad  de  medida,  de  la
| equivalente  |     |     |     | compañía seleccionada.  |     |
| ------------ | --- | --- | --- | ----------------------- | --- |

| Cantidad  |     |     | Obligatorio  | Número entero mayor o igual a 1.  |     |
| --------- | --- | --- | ------------ | --------------------------------- | --- |
|           |     |     |              |                                   |     |
| Estado    |     |     | Obligatorio  | Activo / Inactivo, estándar.      |     |

Ejemplo
| Producto:                |     |     | Crema de manos  |     |     |
| ------------------------ | --- | --- | --------------- | --- | --- |
| Unidad de compra:        |     |     | Pallet          |     |     |
| Unidad de distribución:  |     |     | Caja            |     |     |
| Unidad de venta:         |     |     | Unidad          |     |     |

Equivalencias:
| Unidad  |     | Q   |   Unidad equivalente  |     | Q   |
| ------- | --- | --- | --------------------- | --- | --- |
| Pallet  |     | 1   | =  Cajas              |     | 12  |
| Caja    |     | 1   | =  Unidad             |     | 24  |

4.2  Parámetros de compañía

4.2.1 Objetos internos

Agregar a la lista los siguientes objetos internos:
•  AFILIACION, para las transacciones de “Afiliaciones” en el módulo de Trade. No requiere
definición  de  documentos  de  respaldo.  Se  usará  este  objeto  para  asignaciones  de
seguridad del módulo “Afiliaciones”.

•  IMPULSO, para las transacciones de “Impulsos” en el módulo de Trade. No requiere
definición  de  documentos  de  respaldo.  Se  usará  este  objeto  para  asignaciones  de
seguridad del módulo “Impulsos”.
Versión 0.8  Estrictamente privado y confidencial  Página 13 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
4.2.2 Regionales
Definición
Parámetro para definir las “Regionales” que se gestionan por compañía (cliente), donde una
regional es un conjunto de ciudades dentro de un país.
Datos
Los datos requeridos para este parámetro son al menos la siguiente:
Dato Condición Descripción
Compañía Obligatorio Código de compañía.
País Obligatorio Código de país, del parámetro “Países”.
Código Obligatorio Código de regional.
Nombre Obligatorio Texto mediano. Nombre o descripción de la regional.
Estado Obligatorio Activo / Inactivo, estándar.
Ciudades (N)
Ciudades Obligatorio Código de ciudad que se asocia a la regional, del país
seleccionado.
4.3 Parámetros de Seguridad
4.3.1 Asignación de grupos de empleados a usuarios
Modificación
Este parámetro, ya existente en el sistema, requiere la modificación del campo denominado
“Funcionalidad”; debe ser reemplazado por el siguiente:
Dato Condición Descripción
Objeto interno Obligatorio Código del objeto interno al que corresponde la asignación de
seguridad, del parámetro “Objetos internos” para la compañía
seleccionada.
Los registros de este parámetro previos a los módulos de Trade, deben editarse con estos
valores:
• Si “Funcionalidad = BOLETASPAGO”, se actualizan con el objeto interno “BOLETAPAGO”
de cada compañía.
• Si “Funcionalidad = AUSENCIA”, se actualizan con el objeto interno “AUSENCIA” de cada
compañía.
Versión 0.8 Estrictamente privado y confidencial Página 14 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Es necesario revisarlas funciones de “Boletas y Ausencias” cuya seguridad depende de este
parámetro, para que utilicen sólo asignaciones de grupos que correspondan a los objetos
internos de ese módulo.
Las asignaciones de seguridad para el módulo de “Afiliaciones” usarán el objeto interno
”AFILIACION” (definición predeterminada).
Las asignaciones de seguridad para el módulo de “Impulsos” usarán el objeto interno
”IMPULSO” (definición predeterminada).
4.3.2 Asignación de estados de servicios a roles
Definición
Parámetro para definir la asignación de estados de cada servicio a los roles de acceso que
correspondan según la compañía.
• Los roles de una compañía interna pueden acceder a servicios de compañías internas o
externas.
• Los roles de una compañía externa pueden acceder a servicios de la misma compañía
únicamente.
Datos
Los datos requeridos para este parámetro son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de la compañía para la cual se definen las asignaciones.
Servicio Obligatorio Código de un servicio de la compañía seleccionada, sea como
“compañía” (que ejecuta el servicio) o como “compañía cliente”
en la definición de servicios.
Rol Obligatorio Código de un rol de acceso, de la compañía seleccionada.
Estado del Obligatorio Código de un estado del servicio seleccionado.
servicio
Estado Obligatorio Activo / Inactivo, estándar.
4.4 Parámetros de Afiliaciones
4.4.1 Formularios
Definición
Parámetro para definir los formularios con los que se realizarán los servicios de Trade en el
sistema.
Un formulario es un conjunto de preguntas con las siguientes características:
• Respuestas posibles
Versión 0.8 Estrictamente privado y confidencial Página 15 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
o Verdadero / Falso
o Opción múltiple
o Numérica
o Literal / Abierta (texto)
o Carga de imagen
• Secuencia de preguntas (flujo de preguntas en función a las respuestas a preguntas
anteriores)
Como parte de la configuración, un formulario se define en este parámetro y se asocia luego
a un servicio para una compañía. Posteriormente, en el momento transaccional de registro
de respuestas, es decir, cuando se ejecuta el servicio, en el sistema se registrarán un
número R ilimitado de respuestas para cada formulario (por servicio y compañía).
Datos
Los datos requeridos para este parámetro son al menos los siguientes:
Dato Condición Descripción
Código Obligatorio Código de formulario. Dato alfanumérico de hasta 10 caracteres,
sin duplicados.
Nombre Obligatorio Texto mediano. Nombre o descripción del formulario.
Estado Obligatorio Activo / Inactivo, estándar.
Preguntas (N)
Número de Obligatorio Número (entero) de pregunta para el formulario (NP).
pregunta Define el orden, de menor a mayor, en el que se presentarán las
preguntas en el momento de registro de respuestas.
Contenido de Obligatorio Texto largo. Texto de la pregunta.
pregunta
Tipo de Obligatorio Tipo de respuesta esperada para la pregunta, que puede ser:
respuesta • Verdadero / Falso (V/F): La respuesta esperada será Si o
esperada No.
• Opción múltiple (OM): La respuesta esperada tiene varias
(M) opciones de respuesta, que se definen en las “Opciones
de respuesta”.
• Numérica: La respuesta esperada será un número.
• Literal: La respuesta esperada será un texto largo.
• Carga de archivo: La respuesta esperada será la carga de
una imagen o archivo guardado en el dispositivo del usuario
(extensión y tamaño permitidos), o una fotografía que se
tome en el momento de la respuesta, desde el dispositivo
del usuario. Para este tipo de respuesta se asume que la
carga del archivo será obligatoria (en el momento de
registro de respuestas).
Secuencia Obligatorio Si / No
condicionada • Si: Significa que la respuesta a la pregunta condicionará la
pregunta siguiente (en el flujo de preguntas). Se permite
“Si” sólo para preguntas de tipo V/F Y OM.
• No: Valor por defecto. Significa que la pregunta siguiente es
la que continue en el orden normal de las preguntas.
Opciones de respuestas (M para cada N)
Número de Obligatorio Número de la pregunta, de tipo OM, para la que se definen
Versión 0.8 Estrictamente privado y confidencial Página 16 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
pregunta opciones de respuesta.
Número de Obligatorio Número de opción de respuesta.
opción
Contenido de Obligatorio Texto mediano. Texto de la posible respuesta para la pregunta.
respuesta
Pregunta siguiente (P posibilidades)
Número de Obligatorio Número de la pregunta (NP), de tipo V/F u OM, para la cual
pregunta “Secuencia condicionada = Si”, para la cual se define la pregunta
siguiente.
Respuesta Obligatorio Valor esperado como respuesta a la pregunta NP:
esperada • Para preguntas de tipo V/F hay dos posibles respuestas
esperadas: V (Verdadero), o F (Falso).
• Para preguntas de tipo OM hay M opciones posibles como
respuesta esperada, identificadas con el número de opción.
Para determinar la siguiente pregunta a mostrar a un usuario (en
el momento de registro de respuestas), el sistema aplicará:
• Si “Respuesta ingresada = Valor de respuesta esperado”
entonces “Siguiente pregunta (a desplegar) = Número de
pregunta siguiente”.
• Si una pregunta está definida como “Secuencia condicionada
= Si”, pero en el momento de registro de respuestas no se
tiene un valor esperado que defina el número de pregunta
siguiente, entonces la pregunta siguiente será NP + 1.
Número de Obligatorio Número de la pregunta siguiente (de las N definidas para el
pregunta formulario).
siguiente
Características especiales
Se requiere la opción “Copiar” formulario.
4.4.2 Servicios
Definición
Parámetro para definir cada servicio de Afiliaciones o de Encuestas que se brindará a cada
cliente, con todas sus características.
Datos
Los datos requeridos para este parámetro son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de la compañía que ejecutará el servicio. Proviene del
parámetro “Compañías” para “Tipo de compañía = Interna”.
Compañía Obligatorio Código de la compañía que recibirá el servicio. Proviene del
cliente parámetro “Compañías” para “Tipo de compañía = Externa”.
Código Obligatorio Código del servicio. Dato alfanumérico de hasta 10 caracteres,
sin duplicados.
Nombre Obligatorio Texto mediano. Nombre o descripción del servicio.
Versión 0.8 Estrictamente privado y confidencial Página 17 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Tipo de servicio Obligatorio Lista fija de valores. Pueden ser:
• AFILIACION
• ENCUESTA
Código de Obligatorio Código del formulario asignado al servicio.
formulario
Distancia Obligatorio Número entero, mayor o igual a 0, que define la distancia
máxima de máxima en metros que se acepta (diferencia permitida) para el
marca registro de marcas de inicio y fin de ruta para el servicio.
Estado Obligatorio Activo / Inactivo, estándar.
Estados (N)
Código Obligatorio Código de estado.
Nombre Obligatorio Texto corto. Nombre del estado.
Siguiente Opcional Código del estado siguiente por “Aceptar” (en flujo de estados),
positivo de los N definidos para el servicio.
Siguiente Opcional Código del estado siguiente por “Rechazar” (en el flujo de
negativo estados), de los N definidos para el servicio.
Motivos de rechazo (M)
Código Obligatorio Código del motivo de rechazo del servicio (para registros de
resultados del servicio).
Descripción Obligatorio Texto mediano. Descripción del motivo de rechazo.
Características especiales
• Se debe definir al menos 1 estado para cada servicio.
• Los estados se usarán, en el momento transaccional, en la transacción del “Cambio de
estado” a los registros de respuesta de cada formulario.
Cada estado puede tener sólo un estado siguiente por positivo y uno por negativo.
El siguiente es un ejemplo de configuración de estados:
Versión 0.8 Estrictamente privado y confidencial Página 18 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
El primer estado debe ser “Nueva” (primer registro de la lista de M estados).
Los últimos estados posibles son “Aprobada” y “Anulada”; ambos no definen salidas.
• Para los cambios de estado se deberá configurar qué roles (de seguridad) acceden a
cuáles estados de cada servicio (ver en Seguridad).
• Se debe definir al menos 1 motivo de rechazo para cada servicio.
4.5 Parámetros de Trade
4.5.1 Tipos de puntos de venta
Definición
Parámetro para clasificar los puntos de venta (PDV) a ser registrados en el sistema, en
función de su naturaleza o movilidad.
Datos
Los datos requeridos para este parámetro son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía.
Código Obligatorio Código del clasificador.
Nombre Obligatorio Texto mediano. Nombre del clasificador.
Versión 0.8 Estrictamente privado y confidencial Página 19 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Notas conceptuales:
Punto de En los procesos de negocio, el punto de venta se utiliza para:
venta • Gestión de ventas: Punto donde se registran las ventas de la empresa.
• Procesamiento de pagos: Asocia múltiples métodos de pago aceptados en
las ventas.
• Gestión de clientes: Almacena información clave de clientes.
• Control de inventarios: Mantiene actualizado el inventario en tiempo real.
Almacena información relevante para la gestión de stocks.
Tipo de Clasificador de PDV que podría definir características como:
punto de • Fijo (establecimiento),
venta • Móvil (carro de comida),
• En línea,
• Temporal (ferias).
4.5.2 Canales
Definición
Parámetro para clasificar los puntos de venta (PDV) a ser registrados en el sistema, en
función de su forma de llevar productos al cliente.
Datos
Los datos requeridos para este parámetro son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía a la que pertenece el canal.
Código Obligatorio Código del canal.
Nombre Obligatorio Texto mediano. Nombre del canal.
Notas conceptuales:
Canal Camino que seguirá un producto o servicio, desde la empresa que lo produce
hasta el cliente que lo consume.
Ejemplo de definición de canales:
• Mayorista / Minorista;
• Vertical / Horizontal;
• Cadena de… / Pequeños comercios.
4.5.3 Categorías
Definición
Parámetro para definir las “Categorías” con las que clasificarán los productos.
Versión 0.8 Estrictamente privado y confidencial Página 20 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

Datos
Los datos requeridos para este parámetro son al menos los siguientes:

| Dato      | Condición    |                      | Descripción  |     |     |     |
| --------- | ------------ | -------------------- | ------------ | --- | --- | --- |
| Compañía  | Obligatorio  | Código de compañía.  |              |     |     |     |

Código  Obligatorio  Código  de  categoría.  Alfanumérico  de  hasta  2
caracteres.

| Nombre  | Obligatorio  | Texto corto. Nombre de categoría.  |     |     |     |     |
| ------- | ------------ | ---------------------------------- | --- | --- | --- | --- |

Categoría superior  Opcional  Código  de  una  categoría  prexistente,  de  la  misma
compañía, de la cual depende la categoría nueva.
Si queda vacío se considera categoría independiente.

Compone SKU  Obligatorio  Dato “Si / No” que define si la categoría será parte del
código de producto (SKU) o no.
|     |     | Se  permite  | un  máximo  | de  4  categorías  | que  | “Si”  |
| --- | --- | ------------ | ----------- | ------------------ | ---- | ----- |
componen el SKU.

| Estado  | Obligatorio  | Activo / Inactivo, estándar.  |     |     |     |     |
| ------- | ------------ | ----------------------------- | --- | --- | --- | --- |

4.5.4 Valores de categorías

Definición
Parámetro para definir los valores posibles de cada una de las categorías configuradas en el
parámetro anterior, para uso en la clasificación de productos.

Datos
Los datos requeridos para este parámetro son al menos los siguientes:

| Dato      | Condición    |                      | Descripción  |     |     |     |
| --------- | ------------ | -------------------- | ------------ | --- | --- | --- |
| Compañía  | Obligatorio  | Código de compañía.  |              |     |     |     |

Categoría  Obligatorio  Código de categoría, de la compañía seleccionada.

Valor superior  Opcional /  Para  la  categoría  seleccionada,  verificar  si  tiene
|     | Obligatorio  | definida una “Categoría superior”:  |                   |               |             |     |
| --- | ------------ | ----------------------------------- | ----------------- | ------------- | ----------- | --- |
|     |              | •  Si  NO                           | la  tiene,  este  | campo  queda  | vacío  (no  | se  |
requiere).
•  SI la tiene, este campo es obligatorio; debe permitir
|     |     | seleccionar  | uno  de  | los  valores  prexistentes  |     | de  la  |
| --- | --- | ------------ | -------- | --------------------------- | --- | ------- |
categoría superior.

Código  Obligatorio  Código de valor. Alfanumérico de 3 caracteres.

| Nombre  | Obligatorio  | Texto mediano. Descripción del valor.  |     |     |     |     |
| ------- | ------------ | -------------------------------------- | --- | --- | --- | --- |

| Estado  | Obligatorio  | Activo / Inactivo, estándar.  |     |     |     |     |
| ------- | ------------ | ----------------------------- | --- | --- | --- | --- |

|     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- |
Versión 0.8  Estrictamente privado y confidencial  Página 21 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
5 Catálogos de Trade
5.1 Equipos de trabajo
Definición
Catálogo para definir los diferentes equipos de trabajo para ejecutar servicios de Trade en el
sistema. Se usarán en los módulos de Afiliaciones, Encuestas, Reposiciones e Impulsos.
Un equipo de trabajo se compone de un conjunto de empleados, más un líder de grupo y un
supervisor.
• Los empleados de una compañía interna pueden asignarse a equipos de trabajo de
compañías internas o externas.
• Los empleados de una compañía externa pueden asignarse a equipos de trabajo de la
misma compañía únicamente.
Datos
Los datos requeridos para este catálogo son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía a la que pertenece el equipo de trabajo.
Tipo de equipo Obligatorio Objeto interno, que puede ser:
• AFILIACION,
• ENCUESTA,
• REPOSICION,
• IMPULSO.
Servicio Obligatorio Es obligatorio para equipos de tipo AFILIACION o ENCUESTA; en
/ No los otros casos no se requiere.
requerido Código de un servicio de la compañía seleccionada (donde la
compañía seleccionada puede ser sólo la que ejecuta el servicio),
para el mismo tipo de grupo seleccionado.
Código Obligatorio Código del equipo de trabajo.
Nombre Obligatorio Texto mediano. Nombre o descripción del equipo de trabajo.
Supervisor Obligatorio Código del empleado supervisor del equipo de trabajo, de la
compañía seleccionada.
Líder Obligatorio Código del empleado líder (a cargo) del equipo de trabajo, de la
compañía seleccionada.
Ciudad Obligatorio Código de la ciudad a la que se asigna al equipo de trabajo, de la
compañía seleccionada. Para buscar la ciudad se debería presentar
“Países” como filtro.
Estado Obligatorio Activo / Inactivo, estándar.
Miembros del equipo (N)
Empleado Obligatorio Código del empleado asignado al equipo de trabajo, de la compañía
seleccionada.
Versión 0.8 Estrictamente privado y confidencial Página 22 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
5.2 Puntos de venta
Definición
Catálogo para registrar los diferentes puntos de venta (PDV) de una compañía.
Se usarán en los módulos de Reposiciones y de Impulsos.
Datos
Los datos requeridos para este catálogo son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía a la que pertenece el PDV.
Código Obligatorio Código del PDV.
Nombre Obligatorio Texto mediano. Nombre del PDV.
Descripción Opcional Texto largo que describe el PDV.
País Obligatorio Código del país donde se encuentra el PDV.
Por defecto proponer el país de la compañía.
Ciudad Obligatorio Código de ciudad, para el país seleccionado.
Dirección Obligatorio Texto largo para registrar la dirección del PDV (calle, avenida,
número, edificio, departamento, otros).
Zona Obligatorio Código de zona, para la ciudad seleccionada.
Latitud Obligatorio Latitud de la ubicación geográfica, a ser capturada en un mapa.
Longitud Obligatorio Longitud de la ubicación geográfica, a ser capturada en un mapa.
Referencia Opcional Texto largo para registrar referencias de la dirección dada.
Horario de Obligatorio Horas “Desde – Hasta” en las que atiende el PDV.
atención
Persona de Opcional Texto mediano. Nombre completo de la persona de contacto en el
contacto punto de venta.
Cargo Opcional Texto mediano. Cargo de la persona de contacto.
Teléfono de Opcional Texto corto. Número de teléfono de la persona de contacto.
contacto
Tipo de PDV Obligatorio Código de tipo de PDV, de la compañía seleccionada.
Canal Obligatorio Código de canal, de la compañía seleccionada.
Distancia Obligatorio Número entero mayor o igual a 0, que establece la distancia en
máxima de metros que se aceptará como máxima, para permitir el registro
marca de un ingreso o una salida de usuario al PDV (impulsadores o
reponedores).
Versión 0.8 Estrictamente privado y confidencial Página 23 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Fotografía Opcional Fotografía (imagen) del punto de venta.
Estado Obligatorio En creación / Activo / Inactivo.
(gestión de en la sección “Características especiales”).
Características especiales
Estados de un PDV:
• Todo PDV nuevo tendrá el estado “En creación”.
• Alta rápida: Se permite la creación de PDV sin datos obligatorios, registrando sólo los
datos disponibles de un PDV.
• En el estado “En creación” el PDV no puede ser usado en las transacciones del sistema,
hasta que se active.
• La función “Activar PDV” realiza el cambio de su estado a “Activo”. Para que se permita
el sistema debe verificar que todos los datos obligatorios del PDV han sido ingresados.
• Sólo los PDV activos se usan en transacciones del sistema.
• Un PDV se puede activar o inactivar (cambio al estado “Inactivo”) pero no retorna al
estado “En creación”.
5.3 Productos
Definición
Catálogo para definir los productos o ítems de inventario de cada compañía.
Al código de un producto se denominará SKU (de Stock Keeping Unit), nombre estándar en
procesos de gestión de materiales.
Cada SKU debe ser único en su compañía. Debe identificar a un producto específico,
incluyendo a las características que lo distinguen para fines de gestión. No cambia en el
tiempo.
Los productos se utilizarán en Reposiciones y en Impulsos.
Datos
Los datos requeridos para este catálogo son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía a la que pertenece el producto.
SKU Automático Código de producto compuesto automáticamente por el sistema,
para la compañía seleccionada.
Alfanumérico de 15 caracteres, inicialmente vacío.
Este código debe componerlo el sistema concatenando los códigos
de las categorías asignadas al producto, marcadas con “Compone
SKU = Si” (máximo 4), más un número secuencial:
• Cada categoría tiene un código alfanumérico de 3 caracteres.
Versión 0.8 Estrictamente privado y confidencial Página 24 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
• Los primeros 12 caracteres del SKU corresponden a los
valores de las categorías seleccionadas (siempre en el orden
de creación de las categorías).
• Los últimos 3 caracteres del SKU son un número secuencial,
para cada combinación de valores de categorías, empezando
en 001.
• Por tanto, el SKU tendrá 15 caracteres.
• Si para un producto no se utilizan las 4 categorías posibles,
los 3 caracteres que corresponden a cada categoría no
definida se rellenan con ceros (000).
Mostrar este dato resaltado en pantalla.
No es editable por el usuario.
Nombre Obligatorio Texto mediano. Nombre del producto.
Descripción Opcional Texto largo. Descripción del producto.
Tipo de producto Obligatorio Dos posibles valores: Venta / Promocional.
Diferenciará los productos de cliente, que se utilizan en campañas
de impulsos o en inventarios, de aquellos que sólo se utilizan para
ofertas comerciales pero no se venden de forma individual(como
los bandeos).
Estado Obligatorio En creación / Activo / Inactivo.
(gestión de en la sección “Características especiales”).
Categorías (N; 1 obligatoria; de 1 a 4 componen el SKU)
Categoría (*1) Obligatorio Código de categoría, para la compañía seleccionada.
Valor Obligatorio Código de valor, para la categoría seleccionada.
Categoría 2 (*1) Opcional Código 2 de categoría, para la compañía seleccionada.
Valor 2 Opcional Código de valor 2, para la categoría seleccionada, diferente de las
categorías anteriores.
Categoría 3 (*1) Opcional Código 3 de categoría, para la compañía seleccionada, diferente
de las categorías anteriores.
Valor 3 Opcional Código de valor 3, para la categoría seleccionada.
Categoría 4 (*1) Opcional Código 4 de categoría, para la compañía seleccionada, diferente
de las categorías anteriores.
Valor 4 Opcional Código de valor 4, para la categoría seleccionada.
…
Categoría N (*1) Opcional Código N de categoría, para la compañía seleccionada, diferente
de las categorías anteriores.
Valor N Opcional Código de valor N, para la categoría seleccionada.
Versión 0.8 Estrictamente privado y confidencial Página 25 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Unidades de medida (UM)
UM stock Obligatorio Código del a unidad de medida (UM) principal para el producto,
que se usa para su control de stock.
Esta será la UN que se utilice en las transacciones centrales del
sistema. Será la base para los cálculos que se requieran para
equivalencias en otras unidades de medida.
UM reposición Obligatorio UM para solicitar reposición del producto a su proveedor.
UM compra Opcional UM para realizar la compra del producto.
UM venta Opcional UM para realizar la venta del producto.
Control de stock
Margen de fecha Obligatorio Número entero que define la cantidad de días, previos a la fecha
corta de vencimiento del producto, en los que se consideran prontos a
vencer.
Stock mínimo Obligatorio Número entero que define la cantidad mínima de unidades del
producto que se requieren en stock, expresado en UM principal.
Precios
Valor de stock Opcional Número con dos decimales (moneda).
Precio unitario del producto en inventario (stock), por UM stock.
Precio de compra Opcional Número con dos decimales (moneda).
Último precio de compra del producto, por UM de compra.
Precio de venta Opcional Número con dos decimales (moneda).
Último precio de venta del producto, por UM de venta.
Moneda Opcional Código de moneda en la que se expresan los precios anteriores,
del parámetro “Monedas”.
Otros datos del producto
Fabricante Opcional Texto mediano. Nombre del fabricante del producto.
País de origen Opcional Código de país.
País de procedencia (origen) del producto
Instrucciones de Opcional Texto largo. Indicaciones específicas para el movimiento y
manejo almacenamiento del producto.
Condiciones de Opcional Texto largo. Requisitos como temperatura, humedad o exposición
almacenamiento a la luz.
Cuidados Opcional Texto largo. Datos sobre si es un producto inflamable, tóxico, o
especiales requiere precauciones especiales.
Fotografía (1 foto)
Fotografía Opcional Fotografía del producto.
Archivo de imagen:
• Extensiones permitidas (definición técnica).
Versión 0.8 Estrictamente privado y confidencial Página 26 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
• Tamaño máximo permitido (definición técnica).
(*1) Notas a las categorías:
• La etiqueta de cada categoría en pantalla debe ser el “Nombre” de la categoría.
• Una categoría se puede seleccionar una sola vez por producto, por lo que cada categoría
N debe ser diferente de las anteriores ya seleccionadas.
• Si una categoría N seleccionada tiene una “Categoría superior” S configurada (en el
parámetro “Categorías”), en los valores de categoría N se muestran sólo los valores que
corresponden a los de la categoría superior S.
• Con la selección de cada categoría y su valor, el sistema debe componer el SKU y
actualizarlo en pantalla.
• Las categorías 1 a 4 no se podrán editar una vez que sea guardado un nuevo producto.
Nota: Si bien se requiere mostrar las categorías en pantalla y permitir su uso, para facilitar
la selección de sus correspondientes valores, no significa que sea obligatorio persistir los
códigos de categoría por producto dado que pueden determinarse a partir de sus valores (el
parámetro “Valores” es dependiente del parámetro “Categorías”).
Características especiales
Estados de un producto:
• Todo producto nuevo tendrá el estado “En creación”.
• Alta rápida: Se permite la creación de producto sin datos obligatorios, registrando sólo
los datos disponibles del producto.
• En el estado “En creación” el producto no puede ser usado en las transacciones del
sistema, hasta que se active.
• La función “Activar producto” realiza el cambio de su estado a “Activo”. Para que se
permita el sistema debe verificar que todos los datos obligatorios del producto han sido
ingresados.
• Sólo los producto activos se usan en transacciones del sistema.
• Un producto se puede activar o inactivar (cambio al estado “Inactivo”) pero no retorna
al estado “En creación”.
Características especiales
• Se requiere la funcionalidad de importación de productos.
El SKU no se importa; debe ser asignado en el proceso de importación, siguiendo la
misma lógica definida en el requerimiento.
• Se requiere la funcionalidad de exportación de productos.
Debe ser posible realizar una exportación usando los códigos de producto de una la
compañía cliente. Si este es el caso, se deben usar las equivalencias de códigos de
productos definidos en la sección siguiente.
Versión 0.8 Estrictamente privado y confidencial Página 27 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
5.4 Equivalencias de códigos de productos
Definición
Catálogo para registrar las equivalencias códigos de un mismo producto, entre el código
definido en el sistema y el o los códigos que pueda tener definidos en sistemas externos
usados por el mismo cliente (compañía).
Datos
Los datos requeridos para este catálogo son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de la compañía a la que pertenece el producto, del
parámetro “Compañías”.
SKU Obligatorio SKU o código de producto, del catálogo de productos de la
compañía seleccionada.
Sistema Obligatorio Código del sistema externo con el que se creará la equivalencia,
externo del parámetro “Sistemas externos” para la compañía
seleccionada.
Código en el Obligatorio Texto de hasta 20 caracteres. Código del producto en el sistema
sistema externo seleccionado.
externo
Estado Obligatorio Activo / Inactivo, estándar.
Funcionalidades requeridas
En este catálogo se requieren las siguientes funciones especiales.
• La importación de equivalencias, con códigos de producto en el sistema y en el o los
sistemas externos que corresponda.
• La exportación de equivalencias con todos sus datos, con la opción de especificar el o los
sistemas externos cuyas equivalencias se requiere exportar.
Versión 0.8 Estrictamente privado y confidencial Página 28 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6 Afiliaciones
6.1 Catálogos de Afiliaciones
6.1.1 Rutas de afiliación
Definición
Catálogo para definir las diferentes rutas plan en las que se realizarán servicios de
afiliaciones (rutas planificadas para ejecutar un servicio).
Una ruta de afiliación planificada es un conjunto de puntos geográficos que determinan un
inicio y un fin de la ruta, y N puntos geográficos intermedios que componen la ruta.
Datos
Los datos requeridos para este catálogo son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía a la que pertenece la ruta.
Código Obligatorio Código de la ruta.
Nombre Obligatorio Texto mediano. Nombre o descripción de a ruta.
País Obligatorio País donde se ejecuta la ruta.
Ciudad Obligatorio Ciudad donde se ejecuta la ruta, del país seleccionado.
Estado Obligatorio En creación / Activo / Inactivo.
Gestión de estados en “Características especiales”.
Puntos de la ruta (N, mínimo 2 – Inicio y Fin)
Latitud Obligatorio Latitud del punto geográfico.
Longitud Obligatorio Longitud del punto geográfico.
Tipo de punto Obligatorio Tipo de punto geográfico, que puede ser:
• Inicio (un solo punto),
• Intermedio (N puntos),
• Fin (un solo punto).
Características especiales
• Una ruta de afiliación debe tener al menos 2 puntos geográficos, uno de tipo “Inicio” y
otro de tipo “Fin” (sólo uno de cada tipo mencionado).
• Una ruta puede tener N puntos intermedios, entre el Inicio y el Fin.
• Las rutas deben definirse por el usuario sobre un mapa de Google Maps (crear /
visualizar / editar).
• El usuario debe marcar los puntos de la ruta en orden, desde el punto Inicio, pasando
por los N puntos intermedios, hasta punto Fin. Cada punto se define con un clic sobre el
mapa.
Versión 0.8 Estrictamente privado y confidencial Página 29 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Cada punto se debe mostrar visualmente sobre el mapa con un ícono (por ejemplo, una
bandera). Se debe trazar una línea delgada que muestre la ruta completa, uniendo sus
puntos.
• En las rutas plan, los puntos de la ruta y su línea de unión se deben visualizar en azul.
Estados de una ruta de afiliaciones:
• Toda ruta nueva tendrá el estado “En creación”.
• Una ruta “En creación” puede ser editada; no puede ser usada en las transacciones del
sistema, hasta que se active.
• La función “Activar ruta” realiza el cambio de su estado a “Activo”; sólo las rutas activas
se usan en transacciones del sistema.
• Una ruta se puede activar o inactivar (cambio al estado “Inactivo”) pero no retorna al
estado “En creación”.
6.2 Transacciones
El siguiente diagrama esquematiza el flujo posible de pasos entre las transacciones centrales
de Afiliaciones:
Versión 0.8 Estrictamente privado y confidencial Página 30 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6.2.1 Planificación
6.2.1.1 Habilitar periodo de afiliaciones
Definición
En esta transacción se llevará el control de los periodos de tiempo habilitados para la
realización de diferentes servicios por compañía.
Un periodo de control de servicios se define habitualmente en meses.
Funcionalidades requeridas
Al inicio de la transacción se requiere los siguientes datos:
Dato Condición Descripción
Compañía Obligatorio Código de la compañía a la cual pertenece o tiene acceso el
usuario. Proviene de los parámetros “Compañías” y “Asignación
de compañías por usuario”.
Servicio Obligatorio Código de servicio para la compañía seleccionada (compañía
que ejecuta el servicio).
Gestión Obligatorio Gestión para la cual se habilitará un periodo de servicios.
Proviene del parámetro “Gestiones” para la compañía
seleccionada; sólo se permiten seleccionar gestiones con el
valor “Procesamiento = Abierta”.
Periodo Obligatorio Es un valor entero, del 1 al 12, que representa a los meses de
una gestión (no necesariamente son los meses calendario, pues
una compañía puede iniciar gestión fiscal en enero mientras que
otra lo hace en julio; en ambos casos el primer periodo de una
gestión es 1).
El primer periodo en el sistema no tendrá control especial
(depende de cuándo una compañía empiece a usar el sistema);
pero, del segundo periodo en adelante, deben ser correlativos,
es decir, que para agregar el periodo “N” debe estar registrado
el periodo “N-1”.
Se debe controlar que el periodo para cada servicio sea único
por compañía y gestión.
Mes Obligatorio Mes calendario, de enero a diciembre, para la gestión
seleccionada.
Será una lista fija de valores con los meses del año.
Estado objetivo Obligatorio Estado, del servicio seleccionado, que define los objetivos de
cumplimiento del mes.
Afiliaciones Obligatorio Número entero mayor o igual a cero.
objetivo Cantidad de afiliaciones en el estado objetivo, que se define
como meta por afiliador para el periodo.
Días de trabajo Obligatorio Número entero mayor o igual a cero.
Cantidad de días de trabajo hábiles que tendrá el periodo.
Procesamiento Obligatorio Estado de procesamiento del tipo de planilla para el periodo
seleccionado. Puede ser:
• Abierto, cuando se permiten registros de ausencias para el
periodo, o
• Cerrado, cuando no son permitidos nuevos registros de
ausencias para el periodo.
El valor inicial debe ser “Abierto”.
Versión 0.8 Estrictamente privado y confidencial Página 31 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6.2.1.2 Planificación de afiliaciones
Definición
Transacción para planificar las rutas de afiliación a recorrerse semanalmente, por compañía
y servicio.
Registro del plan de afiliaciones = Compañía + Servicio + Ruta + Equipo de trabajo + Fecha
(día de trabajo de afiliaciones).
El formato base de la transacción debe ser una agenda, con periodicidad semanal por
defecto. Debe contar con un filtro según los datos más relevantes.
Seguridad especial
Para acceder y utilizar esta transacción, un usuario requiere:
• Tener asignado el rol que incluye la transacción;
• Tener asignada la compañía de la cual requiere información;
• En esta transacción se permite a un usuario gestionar (registrar / visualizar / editar /
eliminar) la planificación para los grupos de trabajo de los cuales es “Supervisor”.
Funcionalidades requeridas
1. Al inicio de la transacción el sistema debe presentar un filtro para la gestión de la
planificación, con al menos los siguientes datos:
Dato Condición Descripción
Compañía Obligatorio Compañía (una) cuya planificación se requiere gestionar
(compañías que ejecutan servicios).
Por defecto debe estar seleccionada la compañía de sesión.
Servicio Opcional Servicios (N) cuya planificación se requiere gestionar, de la
compañía seleccionada (compañía que ejecuta el servicio).
Ruta Opcional Ruta (N) cuya planificación se requiere visualizar, de la
compañía seleccionada.
Equipo de Opcional Equipo de trabajo (N) cuya planificación se requiere
trabajo registrar, de la compañía seleccionada.
Se incluyen en la lista y permiten seleccionar los equipos de
trabajo:
• Del objeto interno “AFILIACION”;
• En los que el usuario de sesión se encuentra asignado
como “Supervisor”.
Las fechas no forman parte del filtro, son las que se ven en el calendario.
Por defecto los campos del filtro deben estar vacíos (se lee como “todos” los valores),
excepto la compañía.
Este filtro debe ubicarse dentro de un panel abierto que se pueda cerrar:
Versión 0.8 Estrictamente privado y confidencial Página 32 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Inmediatamente debajo del filtro, debe presentar un calendario vacío, en configuración
“Semanal”, ejemplo:
Para la vista semanal, la semana es de 7 días, empieza en lunes. Por tanto, debe
mostrar de lunes a domingo.
Las horas de trabajo por defecto son las estándar, de 8:30 a 17:00.
2. Debajo del calendario (pie de la pantalla) debe ubicarse un segundo panel (abierto, que
se pueda cerrar) con el código de colores usado para mostrar los diferentes registros
del plan. Se debe asignar un color a cada combinación servicio + ruta.
Los colores son:
SERVICIO1/ RUTA1 Amarillo claro (RGB: 255, 242, 204)
SERVICIO1/ RUTA2 Amarillo oscuro (RGB: 255, 192, 0)
SERVICIO2/ RUTA1 Verde (RGB: 146, 208, 80)
SERVICIO2/ RUTA2 Azul claro (RGB: 157, 195, 230)
Etc.
3. Las opciones del sistema para esta transacción son las siguientes:
• “Buscar”, paso 4;
• “Agregar”, paso 5;
• “Importar”, paso 6;
• “Imprimir”, paso 7; y
• “Salir”, que vuelve a la pantalla principal del sistema.
4. La opción “Buscar” debe mostrar en el calendario los registros de la planificación que
cumpla con los criterios de búsqueda del filtro, que se encuentren en el periodo de
tiempo que muestra el calendario.
Versión 0.8 Estrictamente privado y confidencial Página 33 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Registro del plan = Compañía + Servicio + Ruta + Grupo de trabajo + Fecha
(encabezado) (calendario)
Los registros del plan en pantalla pueden seleccionarse para visualización, en cuyo caso
el sistema abrirá un cuadro de datos de la ausencia seleccionada:
• Clic en un registro: desplegar un cuadro con información del registro:
o Fecha,
o Compañía,
o Servicio,
o Ruta,
o Grupo de trabajo.
• Doble clic en un registro: no se requiere.
Ejemplo:
En este cuadro se debe permitir la edición de los datos del registro seleccionado,
excepto compañía, para todo registro donde “Fecha >= Fecha de sesión” (no se permite
la edición de planificación de fechas pasadas).
Las opciones de este cuadro son:
• “Guardar”: graba los cambios de datos que se hayan hecho y cierra el cuadro;
• “Cerrar”: cierra el cuadro sin grabar cambios de datos.
En el calendario, se debe poder cambiar a las vistas mensual y diaria. En cualquier
vista, debe salir marcado el día de sesión en azul (como en el ejemplo).
Se deben mantener los demás controles estándares del componente “Calendario” como
avanzar o retroceder fechas, y otros.
5. La opción “Agregar” debe permitir añadir un nuevo registro a la planificación de
afiliaciones. Para esto, debe abrir una pantalla (cuadro de diálogo) para el ingreso de los
siguientes datos:
Dato Condición
Fecha Obligatorio
Por defecto = Fecha de sesión
>= Fecha de sesión (no se permite la planificación de fechas pasadas)
Versión 0.8 Estrictamente privado y confidencial Página 34 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición
Compañía Obligatorio
Por defecto = Compañía de sesión
Servicio Obligatorio
Ruta Obligatorio
Grupo de trabajo Obligatorio
Los datos que se incluyen en cada lista y que se permiten seleccionar dependen de la
seguridad del usuario de sesión, igual que en el filtro de entrada.
Las opciones de este cuadro son:
• “Guardar”: graba el nuevo registro de planificación y cierra el cuadro; debe
actualizar el calendario en pantalla.
• “Cerrar”: cierra el cuadro sin grabar los nuevos datos.
6. La opción “Importar” debe permitir cargar N registros de la planificación a partir de un
archivo plano de datos (funciones estándar del sistema para importación).
El archivo plano (extensión .csv, separado por pipes “|”, codificación UTF-8) debe tener
una fila de encabezado y N filas de datos; cada fila representa un registro nuevo para la
planificación de afiliaciones.
Los datos de cada registro son los mismos detallados en la opción “Agregar”. Para
importar (persistir) esos datos en la base de datos, se deben aplicar los mismos
controles por usuario definidos para la función “Agregar”.
Si se genera algún error en la validación de datos, se debe dar el mensaje de error
incluyendo el detalle de los registros procesados con error. La importación no se realiza.
Cuando todos los registros del archivo se validan, la importación se completa. Al
finalizar se debe dar al usuario un mensaje de éxito, incluyendo la cantidad de registros
importados.
Al salir de la función de importación se debe actualizar el calendario en pantalla.
7. La agenda que se visualiza en pantalla se debe poder imprimir, tal como se esté
visualizando, en un archivo pdf.
6.2.2 Ejecución de ruta
6.2.2.1 Iniciar ruta de afiliaciones
Definición
Transacción para marcar el inicio de trabajo en una ruta de afiliaciones, en un día laboral.
Versión 0.8 Estrictamente privado y confidencial Página 35 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Seguridad especial
En esta transacción el sistema presenta únicamente la ruta asignada al usuario de sesión (si
tiene una), para la fecha de sesión.
Funcionalidades requeridas
1. Al ingresar a la transacción el sistema debe presentar una pantalla con un mapa donde
se visualice la ruta de afiliaciones plan asignada al usuario de sesión para el día de sesión.
Para esto se sugiere buscar:
• Compañía = Compañía de sesión
• Usuario de sesión -> Empleado de sesión (desde el catálogo de empleados)
• Empleado de sesión -> Grupo de trabajo (desde el catálogo de grupos de trabajo de
afiliaciones)
• En la planificación de afiliaciones buscar:
Registro de afiliación: Compañía + Fecha de sesión + Grupo de trabajo
Obtener: Servicio, Ruta plan.
Con la ruta plan para el usuario, se deben mostrar los datos de encabezado:
• Compañía cliente (se obtiene del servicio),
• Código y nombre del servicio,
• Código y nombre de la ruta,
• Hora de inicio de ruta (si está marcada),
• Hora de salida de ruta (si está marcada).
A continuación, en el mapa en pantalla, se debe mostrar la ruta plan incluyendo todos
sus puntos geográficos unidos por una línea en color azul.
El sistema debe verificar si la ruta seleccionada ha sido o no iniciada en el día. Si la ruta
fue iniciada:
• Agregar al mapa la ruta real recorrida hasta el momento, en verde.
• Mostrar el cuadro “Avance de ruta” al pie del mapa, que incluye los siguientes datos
para el día:
o Número de contactos marcados,
o Número de afiliaciones registradas,
o Número de afiliaciones rechazadas,
o Número de referidos registrados.
Se requieren las siguientes opciones en pantalla:
• “Marcar inicio”:
o Si la ruta no está iniciada, opción habilitada– Paso 2;
o Si la ruta está iniciada, opción deshabilita;
• “Salir”, que retorna a la pantalla inicial del sistema.
2. La opción “Marcar inicio” debe:
• Obtener la ubicación geográfica (UG) del usuario (de su dispositivo móvil).
Versión 0.8 Estrictamente privado y confidencial Página 36 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Calcular “DI = Distancia Inicial” en metros, entre la UG del usuario y el “Punto inicial”
de la ruta plan asignada al usuario.
• Si la “DI <= Distancia máxima de marca” para el “Servicio” asignado (en el
parámetro “Servicios”), se acepta el “Inicio de ruta”:
o Se registra el “Punto inicial” de la ruta real recorrida por el usuario, con la fecha,
hora y UG de la marca.
o Se actualiza la “Hora de inicio de ruta” en pantalla.
o Se inhabilita la opción “Marcar inicio”.
• Si la “DI > Distancia máxima de marca” para el “Servicio” asignado (en el parámetro
“Servicios”), se rechaza el “Inicio de ruta”:
o Mostrar mensaje al usuario que indica “No es posible marcar el inicio de la ruta
dado que aún se encuentra lejos del punto inicial planificado”.
o No se realizan cambios en pantalla.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente una ruta
(ruta en curso), utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente
responsiva para adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
6.2.2.2 Registrar contacto
Definición
Transacción para registrar, de forma simple y rápida, un nuevo contacto en la ruta real de
afiliaciones.
Contacto (datos básicos) = Fecha + Hora + Ubicación Geográfica (Latitud + Longitud)
Seguridad especial
En esta transacción el sistema permite únicamente registrar contactos para la ruta asignada
al empleado de sesión que se encuentra “Iniciada” (en curso), para la fecha de sesión.
Funcionalidades requeridas
1. Las opciones al inicio de la transacción son:
• “Salir” (estándar), retorna a la pantalla principal del sistema.
• Opción especial “Marcar contacto”, según se detalla a continuación.
Debe ser un botón diferente a los de la barra de opciones (mayor tamaño, color
llamativo) ubicado debajo de dicha barra.
Versión 0.8 Estrictamente privado y confidencial Página 37 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Contacto habilitado Contacto inhabilitado
Para habilitar el botón “Marcar contacto”, se debe validar:
a) Si el usuario ha marcado el inicio (pero no el final) de su ruta asignada en el día:
a. Ruta en curso: Mostrar código y nombre de la ruta iniciada.
b. Contactos marcados: Mostrar la cantidad de contactos registrados en la
ruta del día (contador de contactos registrados).
c. Botón “Marcar contacto” habilitado; permite avanzar al paso 2.
b) Si el usuario NO ha marcado el inicio ni el final de su ruta asignada en el día:
a. Ruta no iniciada: Datos vacíos; mensaje para el usuario “Aun no ha
registrado el inicio de la ruta que tiene asignada para hoy”.
b. Contactos marcados: 0 (cero)
c. Botón “Registrar contacto” inhabilitado.
c) Si el usuario ha marcado el inicio y el final de su ruta asignada en el día:
a. Ruta finalizada: Código y nombre de la “Ruta de afiliaciones del día”.
b. Hora de inicio: de la ruta.
c. Hora de fin: de la ruta.
d. Contactos marcados: Cantidad total de contactos registrados en la ruta del
día.
e. Botón de “Registrar contacto” inhabilitado.
2. Cuando el botón “Marcar contacto” está habilitado y el usuario lo presiona, el sistema
debe:
a) Obtener la ubicación geográfica (UG) del usuario (de su dispositivo móvil).
b) Agregar un registro de contacto a la ruta real del usuario (guardar en la base de
datos), donde:
Contacto = Fecha + Hora + UG
c) Incrementar el contador de contactos de la ruta en curso.
d) Actualizar el dato “Contactos marcados” en pantalla.
e) Abrir un cuadro de diálogo preguntando al usuario: “Procede el registro de
afiliación?”
Con las opciones “Si / No”:
a. Si llama inmediatamente a la transacción “Registrar afiliación”.
b. No cierra en cuadro de diálogo; el sistema se mantiene en la pantalla
actualizada de la transacción “Registrar contacto” (se repite el paso 2 N veces);
el botón “Marcar contacto” continua habilitado.
Versión 0.8 Estrictamente privado y confidencial Página 38 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente una ruta
(ruta en curso), utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente
responsiva para adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
6.2.2.3 Registrar afiliación
Definición
Transacción para registrar una nueva afiliación al servicio, durante la ruta de afiliaciones en
curso.
Una afiliación consta de dos partes:
1. Persona: Datos de identificación de la persona que se registra como afiliada;
2. Respuestas: Respuestas al formulario de afiliación (formulario asociado al servicio en
curso).
Es posible el registro de datos de persona sin respuestas al formulario. Sin embargo, no se
permite el registro de respuestas sin persona previamente registrada.
Seguridad especial
En esta transacción el sistema permite al usuario registrar únicamente afiliaciones para su
ruta “Iniciada” (en curso), en la fecha de sesión.
Funcionalidades requeridas
1. La pantalla de inicio de esta transacción es similar a la siguiente:
Versión 0.8 Estrictamente privado y confidencial Página 39 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Las opciones al inicio son:
• “Registrar”, para registrar una nueva afiliación en el sistema.
o Si el registro de afiliación es entrada directa desde el menú (o código de
transacción), ejecutar el paso 2 (contacto automático).
o Si el registro de afiliación fue llamado desde ”Registrar contacto”, ejecutar el
paso 3 (persona).
• “Rechazar”, para guardar la persona de una afiliación pero no avanzar a su detalle,
según se explica más adelante.
• “Referido”, para avanzar a la transacción “Registrar referido”, según se detalla en
el paso 5.
• “Salir”, retorna a la pantalla principal del sistema; no guarda datos que se hayan
ingresado.
2. Si el registro de la afiliación es entrada directa desde el menú (o código de
transacción), se debe verificar que el usuario de sesión tenga una ruta iniciada:
• Si ha marcado el inicio de su ruta del día pero no el final, puede continuar. En este
caso, se debe realizar el registro automático del contacto:
o Obtener la ubicación geográfica (UG) del usuario (de su dispositivo móvil).
o Agregar un registro de contacto a la ruta real del usuario (guardar en la base de
datos), donde: Contacto = Fecha + Hora + UG
o Incrementar el contador de contactos de la ruta en curso.
o “Registrar” habilitado.
o “Rechazar” habilitado.
o Avanzar al paso 3.
• Si NO ha marcado el inicio de ruta, se debe dar un mensaje al usuario para que lo
haga para que sea posible registrar una afiliación.
o “Registrar” inhabilitado.
o “Rechazar” inhabilitado.
• Si el usuario ha marcado también el final de su ruta del día ya no es posible
registrar nuevas afiliaciones para esa ruta en el día. Para hacerlo debe iniciar una
nueva ruta que tenga asignada.
o “Registrar” inhabilitado.
o “Rechazar” inhabilitado.
3. Los datos de identificación de la persona para la afiliación son al menos los siguientes:
Dato Condición Descripción
Contacto Automático ID del contacto para el cual se registran datos de la persona (a
(no mostrar la que corresponde la afiliación).
en pantalla)
Número de Automático Es un número único de documento interno, entero, que inicia en
afiliación (no mostrar uno (1), correlativo por compañía.
en pantalla) Inicialmente está vacío. Debe ser asignado automáticamente
por el sistema cuando se “Registra” (graba o persiste) la
afiliación.
Versión 0.8 Estrictamente privado y confidencial Página 40 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

| Dato  | Condición  |     | Descripción  |
| ----- | ---------- | --- | ------------ |
Servicio  Automático  Código del servicio al que corresponde la afiliación (de la ruta en
curso).

Fecha de  Automático  Fecha de solicitud que se registra en el sistema.
| afiliación  | (no mostrar   | Es la fecha de sesión.    |     |
| ----------- | ------------- | ------------------------- | --- |
|             | en pantalla)  |                           |     |
| Tipo de     | Obligatorio   | Valor fijo “AFILIACION”.  |     |
| afiliación  | (no mostrar   |                           |     |
en pantalla)
Nombres  Obligatorio  Texto mediano. Nombres de la persona contactada.

Primer apellido  Obligatorio  Texto mediano. Primer apellido de la persona contactada.

Segundo  Opcional  Texto mediano. Segundo apellido de la persona contactada.
apellido
Fecha de  Opcional  Fecha de nacimiento de la persona contactada.
nacimiento  Formato: DD/MM/AAAA, a ingresar manualmente o con control
calendario.
Validación: Anterior a la fecha de sesión, entre 18 y 100 años.

Tipo de  Opcional  Código.  Del  parámetro  “Tipos  de  documentos  de  identidad”,
| documento de  |     | para el país de la compañía de sesión.  |     |
| ------------- | --- | --------------------------------------- | --- |
identidad
Número de  Obligatorio  Texto corto; número de documento de identidad.
| documento de  | (si ingresó     |     |     |
| ------------- | --------------- | --- | --- |
| identidad     | tipo de DocId)  |     |     |
Lugar de  Opcional /  Código. Del parámetro “Lugares de expedición de documentos
expedición de  Obligatorio  de identidad”, para el tipo de documento seleccionado.
| documento de  | (según tipo de  |               |     |
| ------------- | --------------- | ------------- | --- |
| identidad     | DocId)          |               |     |
| Teléfono 1    | Opcional        | Texto corto.  |     |

| Teléfono 2  | Opcional  | Texto corto.  |     |
| ----------- | --------- | ------------- | --- |

Observaciones  Opcional  Texto largo. El usuario puede ingresar una nota u observación a
tener en cuenta en relación a la afiliación.

Estado  Automático  Estado  inicial  de  la  afiliación:  Código  del  primer  estado
definido en el parámetro “Servicios”, para el servicio que se
registra (se asume como estado “INICIAL”).

Fecha interna  Automático  Fecha  y  hora  internas  del  sistema,  que  se  graban
de afiliación  (no mostrar)  automáticamente cuando se crea la afiliación. Estos datos no
pueden ser modificados.

Usuario de  Automático  Usuario  de  sesión  que  registra  la  afiliación.  No  puede  ser
| afiliación  | (no mostrar)  | modificado.  |     |
| ----------- | ------------- | ------------ | --- |

Una vez ingresados los datos el usuario continuará con la opción “Registrar”; con esta
opción se guardan los datos de persona y se avanza al paso 4.

Versión 0.8  Estrictamente privado y confidencial  Página 41 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
El botón “Registrar” debe estar disponible en la barra de botones (estándar) pero
también el pie del formulario de datos de persona.
Si en algún punto de este paso el usuario presiona “Rechazar”, el sistema debe:
• Solicitar al usuario el motivo de rechazo, obligatorio, de los motivos definidos en el
parámetro “Servicios” para la ruta en curso.
• El estado de la afiliación cambia al último estado definido en el Servicio, el cual se
asume equivalente a afiliación “RECHAZADA”.
• Guardar los datos que hayan sido ingresados en pantalla.
• Volver directamente a la transacción “Registrar contacto”.
Si durante el ingreso de los datos de persona el usuario presiona “Referido”, pasar al
paso 5.b).
Si el usuario ingresó datos de la persona, pero presiona “Salir” antes de registrarla, el
sistema vuelve a la pantalla principal y los datos ingresados no se guardan (se cancela
el registro).
4. La siguiente etapa del registro de una afiliación consiste en registrar las respuestas al
formulario de afiliación.
Cada servicio (parámetro “Servicios”) tiene asociado un “Formulario”. Cada Formulario
(parámetro “Formularios”) tiene definidas N preguntas con sus tipos de respuestas.
Es este paso se deben solicitar al usuario respuestas para cada una de las preguntas del
formulario, una por una, siguiendo la secuencia de preguntas configurada en el
formulario.
La pantalla para usar en cada pregunta depende del tipo de pregunta (una pantalla
estándar por tipo de pregunta).
Tipo: Verdadero / falso
Versión 0.8 Estrictamente privado y confidencial Página 42 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Tipo: Opción múltiple
Tipo: Numeral
Versión 0.8 Estrictamente privado y confidencial Página 43 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Tipo: Literal
Tipo: Carga de archivo
Para todas las preguntas la respuesta es obligatoria. Sin respuesta no se permite
avanzar a la siguiente pregunta.
Las respuestas se deben guardar de forma temporal (memoria cache) hasta llegar a la
última pregunta. Las respuestas se guardarán en la base de datos cuando estén
completas (todas las respuestas requeridas).
Se permite retroceder a preguntas anteriores para editarlas. Para avanzar o volver a
una pregunta siguiente se deben controlar la secuencia de preguntas según la
configuración del formulario.
El “Estado” de la afiliación (dato de encabezado) no varía mientras se responde y
guarda el formulario, se mantiene con el estado inicial asignado al registrar el
encabezado.
En este paso, las opciones de la transacción se comportan de la siguiente manera:
• “Registrar”: Verifica que todas las respuestas requeridas al formulario estén
completas y las guarda en la base de datos.
Las respuestas requeridas dependen de la configuración del formulario; es posible
que haya preguntas que no se mostraron al usuario siguiendo la secuencia lógica
definida en el parámetro; esas respuestas no son obligatorias.
Deben guardarse todas las respuestas ingresadas; no se aceptan formularios
incompletos.
Una vez guardado el formulario, el sistema debe retornar a la pantalla principal.
Versión 0.8 Estrictamente privado y confidencial Página 44 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• “Rechazar”: Si en algún momento del formulario el usuario presiona esta opción, el
sistema debe:
o Solicitar al usuario el motivo de rechazo, definidos en el parámetro “Servicios”
para la ruta en curso.
o El estado de la afiliación cambia al último estado definido en el Servicio, el cual
se asume equivalente a afiliación “RECHAZADA”
o Las respuestas ingresadas hasta el momento se pierden.
o Volver directamente a la transacción “Registrar contacto”.
• “Referido”: Si durante el ingreso del encabezado el usuario presiona esta opción
pasar al paso 5.c).
• “Salir”: Similar a “Rechazar”.
5. Registrar “Referido”
Esta opción depende del momento en el que se use.
a) Antes del registro de la persona (inicio de la transacción):
• Pasar directamente a la transacción “Registrar referido”, asociando el ID del
contacto ya guardado (aún no hay persona).
b) Durante el registro de la persona:
• Solicitar al usuario el motivo de rechazo, definidos en el parámetro “Servicios”
para la ruta en curso.
• El estado de la afiliación cambia al último estado definido en el Servicio, el cual
se asume equivalente a afiliación “RECHAZADA”
• Guardar los datos que hayan sido ingresados en pantalla.
• Pasar directamente a la transacción “Registrar referido”, asociando el ID del
afiliado (persona) ya guardado.
c) Durante el registro de las respuestas:
• Solicitar al usuario el motivo de rechazo, definidos en el parámetro “Servicios”
para la ruta en curso.
• El estado de la afiliación cambia al último estado definido en el Servicio, el cual
se asume equivalente a afiliación “RECHAZADA”
• Las respuestas ingresadas hasta el momento se pierden.
• Pasar directamente a la transacción “Registrar referido”, asociando el ID del
afiliado (persona) ya guardado.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente una ruta
(ruta en curso), utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente
responsiva para adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
Versión 0.8 Estrictamente privado y confidencial Página 45 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6.2.2.4 Registrar referido
Definición
Transacción para registrar un nuevo contacto referido para un servicio, a lo largo de una
ruta de afiliaciones.
Un referido es un registro de datos de identificación de una persona, dados por la misma
persona o por una tercera, para realizar un contacto posterior para sugerirle su afiliación a
un servicio.
Seguridad especial
En esta transacción el sistema permite registrar referidos para el servicio correspondiente a
la ruta en curso del usuario de sesión.
Funcionalidades requeridas
1. La pantalla de inicio de esta transacción debe permitir ingresar los datos de
identificación de la persona referida que se encuentren disponibles, que son al menos:
Dato Condición Descripción
Afiliado Automático / ID del afiliado que brinda los datos del referido, cuando está
Opcional disponible (un registro directo de referido no tendrá este dato).
Servicio Automático Código del servicio (de la ruta en curso) para el cual se registra
al referido.
Nombres Obligatorio Texto mediano. Nombres del referido.
Primer apellido Obligatorio Texto mediano. Primer apellido del referido.
Segundo Opcional Texto mediano. Segundo apellido del referido.
apellido
Fecha de Opcional Fecha de nacimiento de la persona contactada.
nacimiento Formato: DD/MM/AAAA, a ingresar manualmente o con control
calendario.
Validación: Anterior a la fecha de sesión, entre 18 y 100 años.
Tipo de Opcional Código. Del parámetro “Tipos de documentos de identidad”,
documento de para el país de la compañía de sesión.
identidad
Número de Obligatorio Texto corto; número de documento de identidad.
documento de (si ingresó
identidad tipo de DocId)
Lugar de Opcional / Código. Del parámetro “Lugares de expedición de documentos
expedición de Obligatorio de identidad”, para el tipo de documento seleccionado.
documento de (según tipo de
identidad DocId)
Teléfono 1 Opcional Texto corto.
Teléfono 2 Opcional Texto corto.
Versión 0.8 Estrictamente privado y confidencial Página 46 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Observaciones Opcional Texto largo. El usuario puede ingresar una nota u observación a
tener en cuenta para contactar al referido.
Fecha interna Automático Fecha y hora internas del sistema, que se graban
de registro (no mostrar) automáticamente cuando se crea al referido. Estos datos no
pueden ser modificados.
Usuario de Automático Usuario de sesión que registra al referido. No puede ser
registro (no mostrar) modificado.
Las opciones requeridas son:
• “Registrar”, guarda los datos del nuevo referido y retorna a la pantalla principal del
sistema.
• “Salir”, retorna a la pantalla principal del sistema; no guarda datos que se hayan
ingresado.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente una ruta
(ruta en curso), utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente
responsiva para adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
6.2.2.5 Finalizar ruta de afiliaciones
Definición
Transacción para marcar el final del trabajo en una ruta de afiliaciones, en un día laboral.
Seguridad especial
En esta transacción el sistema presenta únicamente la ruta asignada al usuario de sesión (si
tiene una), para la fecha de sesión.
Funcionalidades requeridas
1. Al ingresar a la transacción el sistema debe determinar la ruta de afiliaciones asignada al
usuario en el día de sesión. Con los datos de la ruta, debe presentar en pantalla:
Los datos de encabezado:
• Compañía cliente (se obtiene del servicio),
• Código y nombre del servicio,
• Código y nombre de la ruta,
• Hora de inicio de ruta (si está marcada),
• Hora de salida de ruta (si está marcada).
A continuación, en el mapa en pantalla, se debe mostrar la ruta plan incluyendo todos
sus puntos geográficos unidos por una línea en color azul.
Versión 0.8 Estrictamente privado y confidencial Página 47 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
El sistema debe verificar si la ruta seleccionada ha sido o no iniciada en el día. Si la ruta
fue iniciada:
• Mostrar en el mapa la ruta real recorrida hasta el momento, en verde.
• Mostrar el cuadro “Avance de ruta” al pie del mapa, que incluye los siguientes datos
para el día:
o Número de contactos marcados,
o Número de afiliaciones registradas,
o Número de afiliaciones rechazadas,
o Número de referidos registrados.
Se requieren las siguientes opciones en pantalla:
• “Marcar final”:
o Si la ruta no está iniciada, opción inhabilitada;
o Si la ruta está iniciada, opción habilita – Paso 2;
• “Salir”, que retorna a la pantalla inicial del sistema.
2. La opción “Marcar final” debe:
• Obtener la ubicación geográfica (UG) del usuario (de su dispositivo móvil).
• Calcular “DS = Distancia de Salida” en metros, entre la UG del usuario y el “Punto
inicial” de la ruta plan asignada al usuario.
• Si la “DS <= Distancia máxima de marca” para el “Servicio” asignado (en el
parámetro “Servicios”), se acepta el “Final de ruta”:
o Se registra el “Punto final” de la ruta real recorrida por el usuario, con la fecha,
hora y UG de la marca.
o Se actualiza la “Hora de salida de ruta” en pantalla.
o Se inhabilita la opción “Marcar salida”.
• Si la “DI > Distancia máxima de marca” para el “Servicio” asignado (en el parámetro
“Servicios”), se rechaza el “Inicio de ruta”:
o Mostrar mensaje al usuario que indica “No es posible marcar el inicio de la ruta
dado que aún se encuentra lejos del punto inicial planificado”.
o No se realizan cambios en pantalla.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente una ruta
(ruta en curso), utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente
responsiva para adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
Versión 0.8 Estrictamente privado y confidencial Página 48 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6.2.3 Revisar afiliaciones
6.2.3.1 Validar afiliación
Definición
Transacción para revisar una afiliación previamente registrada en el sistema y cambiar su
estado.
Esta transacción será ejecutada por usuarios de las diferentes compañías, tanto internos (de
una compañía interna ejecutora de un servicio) como externos (de una compañía externa,
cliente o beneficiaria de un servicio).
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En cuanto a las afiliaciones a acceder:
• El usuario de sesión debe estar asignado al menos a un “Grupo de trabajo” de
Afiliaciones, sea como “Supervisor”, como “Líder” o como empleado miembro del grupo
o “Afiliador”.
• Si es “Supervisor” o “Líder”, tiene acceso a todas las afiliaciones registradas por los
empleados asignados a sus grupos de trabajo.
• Si es “Afiliador” tiene acceso únicamente a sus propias afiliaciones.
Funcionalidades requeridas
Esta funcionalidad utiliza dos configuraciones previas:
• Los N estados definidos por servicio, en el catálogo de servicios, donde tienen un orden
y una secuencia posible dada por el estado “Siguiente positivo” y “Siguiente negativo”.
• La configuración definida en el parámetro “Asignación de estados de servicios a roles”,
donde un rol puede tener asignados N estados de cada servicio.
En esta transacción se seleccionan solamente los servicios donde “Tipo de servicio =
AFILIACION”.
Las funcionalidades de esta transacción son:
1. Al ingresar a la transacción, el sistema debe presentar un filtro de entrada para buscar
afiliaciones por validar, al menos con los siguientes campos:
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenecen las afiliaciones buscadas.
Por defecto debe estar seleccionada la compañía de sesión.
Otras compañías listadas según la seguridad.
Versión 0.8 Estrictamente privado y confidencial Página 49 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Servicio Obligatorio Código del servicio para buscar afiliaciones, de la compañía
seleccionada. Incluir servicios asociados a la compañía
seleccionada, sea principal (ejecutora) o cliente para el
servicio.
Número de Opcional Rango de números de afiliación desde – hasta.
afiliación • Se puede buscar sólo por “Desde”.
Desde / Hasta • “Hasta” debe ser igual o mayor a “Desde”.
Fecha de Opcional Rango de fechas desde – hasta del registro de afiliaciones.
registro • Se puede buscar sólo por “Fecha desde”.
Desde / Hasta • “Fecha hasta” debe ser mayor o igual a “Fecha desde”.
Estado Opcional Estado de las afiliaciones a validar. La lista incluye los
estados que cumplen:
• Corresponden al servicio seleccionado.
• Están definidos en el parámetro “Asignación de estados
de servicios a roles” para al menos un rol del usuario de
sesión.
Grupo de Opcional Grupo de trabajo que corresponda al servicio seleccionado.
trabajo
Afiliador Opcional Empleado:
• Si se seleccionó un grupo de trabajo, puede ser un
empleado asignado a ese grupo;
• Si no se seleccionó un grupo de trabajo, puede ser un
empleado que pertenezca a cualquier grupo de trabajo
relacionado con el servicio seleccionado.
Las opciones en este paso son:
• “Buscar”, que avanza al paso 2.
• “Salir”, que vuelve a la pantalla principal del sistema.
2. “Buscar” debe presentar una lista con las afiliaciones que cumplan con los criterios de
búsqueda.
Las opciones en este paso son:
• El número de afiliación debe ser el vínculo para ver el detalle de una afiliación,
paso 3.
• “Volver”, retorna al paso 1 (filtro).
• “Salir”, que vuelve a la pantalla principal del sistema.
3. Al presionar un número de afiliación el sistema debe presentar una pantalla con toda la
información registrada de la afiliación. Debe incluir:
• Estado de la afiliación, remarcado, al inicio de la página;
• Datos del contacto relacionado;
• Datos de la persona relacionada;
• Respuestas al formulario de la afiliación (todas secuenciales, no paginadas).
• El historial de estados de la afiliación, incluyendo para cada estado: fecha y hora de
asignación, usuario que lo asignó y observación registrada en el cambio.
Versión 0.8 Estrictamente privado y confidencial Página 50 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Las opciones en este paso son:
• “Validar”,
• “Observar”,
• “Rechazar”,
• “Volver”, retorna al listado del paso 2 (lista).
Opción “Validar”:
• Solicitar una observación (texto), opcional;
• Cambiar el estado de la afiliación al “Siguiente positivo”;
• Guardar el cambio, junto con el usuario, fecha y hora del cambio;
• Volver al paso 2 (listado).
Opción “Observar”:
• Solicitar una observación (texto), obligatoria;
• Cambiar el estado de la afiliación al “Siguiente negativo”;
• Guardar el cambio, junto con el usuario, fecha y hora del cambio;
• Volver al paso 2 (listado).
Opción “Rechazar”:
• Solicitar un motivo de rechazo, de los motivos definidos en el Servicio, obligatorio;
• Solicitar una observación (texto), opcional;
• Dar un mensaje al usuario indicando que el rechazo de la afiliación no se puede
revertir, con opción a “Cancelar” (volver a la afiliación) o “Confirmar” (seguir);
• Cambiar el estado de la afiliación al último estado definido en el Servicio, el cual se
asume equivalente a afiliación “RECHAZADA”;
• Guardar el cambio, junto con el usuario, fecha y hora del cambio;
• Volver al paso 2 (listado).
6.2.3.2 Consultar afiliaciones
Definición
Transacción para buscar y visualizar afiliaciones previamente registradas en el sistema.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En cuanto a las afiliaciones: El usuario puede acceder a todas las afiliaciones registradas en
el sistema por empleados incluidos en los “Grupos de empleados” asignados al usuario de
sesión (parámetro “Asignación de grupos de empleados a usuarios”), para el objeto interno
“AFILIACION”.
Funcionalidades requeridas
1. Al ingresar a la transacción, el sistema debe presentar un filtro de entrada para buscar
afiliaciones, al menos con los siguientes campos:
Versión 0.8 Estrictamente privado y confidencial Página 51 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenecen las afiliaciones buscadas.
Por defecto debe estar seleccionada la compañía de sesión.
Otras compañías listadas según la seguridad.
Servicio Obligatorio Código del servicio para buscar afiliaciones, de la compañía
seleccionada. La lista debe incluir servicios asociados a la
compañía sea definida como compañía principal (ejecutora)
o como compañía cliente (en servicios).
Ruta Opcional Ruta de afiliaciones, del servicio seleccionado.
Número de Opcional Rango de números de afiliación desde – hasta.
afiliación • Se puede buscar sólo por “Desde”.
Desde / Hasta • “Hasta” debe ser igual o mayor a “Desde”.
Fecha de Opcional Rango de fechas desde – hasta del registro de afiliaciones.
registro • Se puede buscar sólo por “Fecha desde”.
Desde / Hasta • “Fecha hasta” debe ser mayor o igual a “Fecha desde”.
Estado Opcional Estado de las afiliaciones buscadas. Pueden ser N, según el
servicio seleccionado.
Grupo de Opcional Grupo de trabajo correspondiente al servicio seleccionado.
trabajo
Afiliador Opcional Empleado:
• Si se seleccionó un grupo de trabajo, puede ser un
empleado asignado a ese grupo;
• Si no se seleccionó un grupo de trabajo, puede ser un
empleado que pertenezca a cualquier grupo de trabajo
relacionado con el servicio seleccionado.
Las opciones en este paso son:
• “Buscar”, que avanza al paso 2.
• “Salir”, que vuelve a la pantalla principal del sistema.
2. “Buscar” debe presentar una lista con las afiliaciones que cumplan con los criterios de
búsqueda.
Las opciones en este paso son:
• El número de afiliación debe ser el vínculo para ver el detalle de una afiliación,
paso 3.
• “Exportar”, según el paso 4.
• “Volver”, retorna al paso 1 (filtro).
• “Salir”, que vuelve a la pantalla principal del sistema.
3. Al presionar un número de afiliación el sistema debe presentar una pantalla con toda la
información registrada de la afiliación. Debe incluir:
• Estado de la afiliación, remarcado, al inicio de la página;
Versión 0.8 Estrictamente privado y confidencial Página 52 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Datos del contacto relacionado;
• Datos de la persona relacionada;
• Respuestas al formulario de la afiliación (todas secuenciales, no paginadas; incluir
los archivos que se hayan cargado en las respuestas de ese tipo);
• El historial de estados de la afiliación, incluyendo para cada estado: fecha y hora de
asignación, usuario que lo asignó y observación registrada en el cambio.
Las opciones en este paso son:
• “Imprimir” la afiliación que se genera en un archivo pdf, y
• “Volver”, retorna al listado del paso 2 (lista).
4. La opción “Exportar” debe llevar todas las afiliaciones incluidas en el listado a un
archivo plano de datos. Para cada afiliación, debe incluir la información del contacto, de
la persona y de todas las respuestas registradas.
Este archivo debe tener un formato que facilite el análisis externo de datos, como
herramientas como Tablas dinámicas de Excel u otras. Para ello, podría incluir tantas
filas como respuestas tenga cada afiliación, repitiendo los datos de contacto y de
persona en cada fila.
La exportación no incluye:
• El historial de cambios de estado.
• Archivos adjuntos a respuestas de tipo “carga de archivo”. En esos casos sólo
debería indicar si la respuesta si/no tiene archivo cargado en el sistema.
La opción “Exportar” requiere un permiso adicional en la seguridad.
6.3 Monitor de afiliaciones
6.3.1 Panel de control
Definición
Transacción para mostrar, en una pantalla, el avance e indicadores más relevantes de las
afiliaciones que se realizan en campo.
Calcula los indicadores para diferentes cruces de variables y valores seleccionados por el
usuario. Incluye una vista de datos detallados (planilla) para el periodo de análisis.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
Versión 0.8 Estrictamente privado y confidencial Página 53 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
En cuanto a las afiliaciones: En los resultados de cada búsqueda para la actualización de
estadísticas, se incluirán únicamente registros ingresados por afiliadores (empleados)
pertenecientes al grupo de empleados asignado al usuario de sesión, para el objeto interno
“AFILIACION”.
Funcionalidades requeridas
1. Panel de control
La pantalla inicial del panel requiere de una barra de variables de análisis (ver 2) y de
un área de datos (ver 3) donde se desplieguen diversas estadísticas a ser calculadas
según dichas variables.
Esquema ejemplo:
2. Las variables de análisis requeridas son:
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenecen las afiliaciones a incluir.
Por defecto debe estar seleccionada la compañía de sesión.
Otras compañías listadas según la seguridad.
Se permite selección única.
Versión 0.8 Estrictamente privado y confidencial Página 54 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Servicio Obligatorio Servicio para las afiliaciones a incluir, de la compañía
seleccionada.
Incluir servicios asociados a la compañía seleccionada, sea
principal (ejecutora) o cliente para el servicio.
Se permite selección única.
Gestión Obligatorio Gestión o año en el que se registraron afiliaciones, de la
transacción “Habilitar periodo de afiliaciones”, para la
compañía y servicio seleccionados.
Por defecto la gestión y periodo más reciente disponible en
la transacción, tomados cuando se selecciona el servicio.
Se permite selección única.
Periodo Obligatorio Periodo en el que se registraron afiliaciones, de la gestión
seleccionada (no se requiere tomar en cuenta los estados
de los periodos).
Por defecto la gestión y periodo más reciente disponible en
la transacción, tomados cuando se selecciona el servicio.
Se permite selección única.
Fecha de Opcional Rango de fechas desde – hasta del registro de afiliaciones a
registro incluir.
Desde / Hasta • El rango de fechas permitido debe estar dentro del
periodo seleccionado.
• Se puede buscar sólo por “Fecha desde”.
• “Fecha hasta” debe ser mayor o igual a “Fecha desde”.
Ruta Opcional Ruta(s) para las afiliaciones a incluir, del servicio
seleccionado.
Se permite selección múltiple.
Número de Opcional Rango de números de afiliaciones a incluir.
afiliación • Se puede buscar sólo por “Desde”.
Desde / Hasta • “Hasta” debe ser igual o mayor a “Desde”.
Estado Opcional Estado de las afiliaciones a incluir, tomados del servicio
seleccionado.
Se permite selección múltiple.
Equipo de Opcional Equipo de trabajo cuyos empleados registraron las
trabajo afiliaciones a incluir; para la compañía seleccionada.
Se permite selección múltiple.
Afiliador Opcional Afiliador (empleado) que registró las afiliaciones a incluir,
de la compañía se.
Si se marcó equipo de trabajo, los afiliadores posibles
deben pertenecer a los equipos marcados.
Se permite selección múltiple.
País Opcional País para incluir afiliaciones.
Se permite selección múltiple.
Versión 0.8 Estrictamente privado y confidencial Página 55 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Regional Opcional Regional para incluir afiliaciones, del país seleccionado.
Si no se marcó país, no se permite seleccionar regional.
Se permite selección múltiple.
Ciudad Opcional Ciudad para incluir afiliaciones, del país y de la regional (si
se marcó) seleccionados.
Si no se marcó país, no se permite seleccionar ciudad.
Se permite selección múltiple.
Inicialmente, las variables que no tienen valores por defecto se presentan vacías (sin
valor marcado), por lo que el área de datos no muestra estadísticas calculadas.
Para el cálculo de las estadísticas, si el usuario no marca valores en las variables
opcionales significa “todos los valores”.
Una vez marcados valores para “Compañía” y “Servicio”, se deben calcular las
estadísticas y actualizar el área de datos.
Cada cambio en la marca de valores de una variable debe recalcular las estadísticas y
actualizar el área de datos.
3. Las Estadísticas requeridas para el área de datos, que se deben calcular en función a
las variables de análisis seleccionadas; las estadísticas se describen a continuación.
Datos que se usan en los cálculos:
Dato Descripción
Estado objetivo Es el estado de una afiliación, definido por compañía,
servicio y periodo, en la transacción “Habilitar periodo de
afiliaciones”.
Q afiliaciones objetivo Es la cantidad de afiliaciones, en el “Estado objetivo”, que
se define como meta a ser lograda en un periodo por cada
afiliador. Valor definido por compañía, servicio y periodo,
en la transacción “Habilitar periodo de afiliaciones”.
Días de trabajo Es la cantidad de días de registro de afiliaciones que se
tendrá en un periodo. Valor definido por compañía, servicio
y periodo, en la transacción “Habilitar periodo de
afiliaciones”.
Versión 0.8 Estrictamente privado y confidencial Página 56 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Cuadro de “Registros”:
Indicador Descripción
Q contactos marcados Cantidad de contactos que hayan sido registrados (creados)
en el periodo de análisis, que cumplan con las demás
variables seleccionadas.
Q personas registradas Cantidad de personas que hayan sido registradas (creadas)
en el periodo de análisis, que cumplan con las demás
variables seleccionadas.
Q afiliaciones registradas Cantidad de afiliaciones registradas (formularios
respondidos) en el periodo de análisis, que cumplan con las
demás variables seleccionadas. No toma en cuenta el
estado de las afiliaciones.
Q afiliaciones aprobadas Q afiliaciones registradas que tengan el “Estado objetivo”.
% afiliaciones aprobadas Q afiliaciones aprobadas / Q afiliaciones registradas * 100
(porcentual)
Q referidos registrados Cantidad de referidos que hayan sido registradas (creadas)
en el periodo de análisis, que cumplan con las demás
variables seleccionadas.
Cuadro de “Objetivos”:
Indicador Descripción
Días laborables del periodo Días de trabajo
Objetivo del periodo Q afiliaciones objetivo * Q afiliadores
Donde, dado que “Q afiliaciones objetivo” se define por
periodo para un afiliador, para este indicador se debe
calcular:
Q afiliadores = Cantidad de afiliadores presentes en el set
de datos de resultados
Objetivo diario Objetivo del periodo / Días laborables del periodo
Cuadro de “Indicadores”:
Indicador Descripción
Ratio Promedio de afiliaciones registradas por día, durante los
días transcurridos en el periodo seleccionado, en el “Estado
objetivo”.
Ratio individual Ratio / Q afiliadores
Necesidad diaria (Objetivo del periodo – Q afiliaciones aprobadas) / Días
hábiles del periodo
Versión 0.8 Estrictamente privado y confidencial Página 57 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráficos (un cuadro para cada gráfico):
Gráfico Descripción
Avance del periodo Q afiliaciones aprobadas / Objetivo del periodo *100
(porcentual)
Tipo de gráfico: Doughnut
Se consigue el efecto del ejemplo
con una serie de 3 datos:
Dato 1 = Avance porcentual
Dato 2 = 100 – Avance
Dato 3 = 100
Formato:
Etiqueta de valor, sólo para el dato
1
Dato 3 sin borde ni relleno
- E
l
a
v
a
n
c
e
Gráfico Descripción
Afiliaciones por estado Q afiliaciones por estado (incluye todos los estados)
(porcentual)
Tipo de gráfico: Pie
- E
l
a
v
a
n
c
e
Versión 0.8 Estrictamente privado y confidencial Página 58 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráfico Descripción
Logrado en el periodo Q afiliaciones aprobadas por día / Q objetivo por día
Tipo de gráfico: Line (custom)
- E
l
a
v
a
n
c
e
Gráfico Descripción
Comparativo acumulado del Q afiliaciones aprobadas acumuladas por día / Q objetivo
periodo acumuladas por día
Tipo de gráfico: Line (custom)
- E
l
a
v
a
n
c
e
Ideas de controles de PrimeFaces para armar el panel de control:
Barra flotante para variables
https://showcase.primefaces.org/ui/misc/sticky.xhtml?jfwid=56205
Paneles móviles para las estadísticas
https://showcase.primefaces.org/ui/panel/dashboard.xhtml?jfwid=56205
Bloques de estadísticas
https://www.primefaces.org/primeblocks-jsf/free.xhtml
Versión 0.8 Estrictamente privado y confidencial Página 59 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráficos de diversos tipos:
https://showcase.primefaces.org/ui/chart/bar.xhtml?jfwid=56205
4. Las opciones requeridas en esta pantalla son:
• “Planilla” de indicadores, como se detalla en el punto 5;
• “Salir”, que retorna a la pantalla inicial del sistema.
5. La opción “Planilla” debe mostrar en pantalla, en formato de tabla, las cantidades de
registros e indicadores individuales que respaldan los datos calculados y mostrados en el
panel. Este archivo debe incluir las siguientes columnas:
Dato Observación
Compañía
Servicio
Gestión
Periodo
Regional
Ciudad
Afiliador Una fila por afiliador.
Este nivel de detalle hace que los indicadores calculados sean
“individuales”.
Objetivo del periodo
Ratio
Ratio individual
Necesidad diaria
Avance
Días del mes Van de 1 a N, una columna por día.
Las opciones requeridas en esta pantalla son:
• “Exportar”, que genera un archivo plano con los datos que se muestran en
pantalla;
• “Volver”, que retorna al panel de control;
• “Salir”, que retorna a la pantalla inicial del sistema.
Ver datos de ejemplo en el archivo “RF Ejemplo planilla de indicadores.xlsx”.
Q rechazos
Motivos de rechazo
Versión 0.8 Estrictamente privado y confidencial Página 60 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6.3.2 Seguimiento de rutas
Definición
Transacción para mostrar, en un mapa en pantalla, la ejecución de una ruta en campo.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En cuanto a las afiliaciones: En los resultados de cada búsqueda para la actualización del
mapa de seguimiento, se incluirán únicamente registros ingresados por afiliadores
(empleados) pertenecientes al grupo de empleados asignado al usuario de sesión, para el
objeto interno “AFILIACION”.
Funcionalidades requeridas
1. Mapa de seguimiento
La pantalla inicial de esta función requiere de una barra de variables de análisis (ver
2) y de un área de mapa (ver 3) donde se desplieguen las rutas seleccionadas en las
variables.
Versión 0.8 Estrictamente privado y confidencial Página 61 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
2. Las variables de análisis requeridas son:
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenece la ruta a revisar.
Por defecto debe estar seleccionada la compañía de sesión.
Otras compañías listadas según la seguridad.
Se permite selección única.
Servicio Obligatorio Servicio cuya ruta se requiere revisar, de la compañía
seleccionada.
Incluir servicios asociados a la compañía seleccionada, sea
principal (ejecutora) o cliente para el servicio.
Se permite selección única.
Ruta Obligatorio Ruta a revisar, del servicio seleccionado.
Se permite selección única.
Fecha Obligatorio Fecha para la cual se requiere revisar la ruta.
Por defecto es la fecha de sesión.
Equipo de Opcional Equipo de trabajo cuyos datos se requieren mostrar en el
trabajo mapa, para la compañía y ruta seleccionadas.
Se permite selección múltiple.
Afiliador Opcional Afiliador (empleado) cuyos datos se requieren mostrar en
el mapa, para la compañía, ruta y equipo seleccionados.
Se permite selección múltiple.
Ver personas Opcional Marca Si / No que indica se muestran o no los pines de
puntos de registro de personas en el mapa. Por defecto
“Si”.
Ver Opcional Marca Si / No que indica se muestran o no los pines de
afiliaciones puntos de registro de afiliaciones en el mapa. Por defecto
“Si”.
Ver referidos Opcional Marca Si / No que indica se muestran o no los pines de
puntos de registro de referidos en el mapa. Por defecto
“Si”.
Inicialmente, las variables que no tienen valores por defecto se presentan vacías (sin
valor marcado), por lo que el mapa no muestra ninguna ruta.
Para las variables opcionales, si el usuario no marca valores significa “todos los valores”.
Una vez marcados valores para “Compañía”, “Servicio”, y “Ruta”, se debe mostrar la
ruta seleccionada en el mapa, como se detalla en el punto 3.
Cada cambio en la marca de valores de una variable debe actualizar la información en el
mapa.
Versión 0.8 Estrictamente privado y confidencial Página 62 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
3. El mapa de seguimiento debe:
Cada vez que se actualice el mapa de seguimiento, este debe mostrar lo siguiente:
Mostrar la ruta seleccionada:
• Planificada, en azul;
• Ejecutada (secuencia de puntos de contacto), en rojo, para la fecha seleccionada.
Sobre la ruta ejecutada, se requiere:
• Mostrar todos los puntos de contacto;
• Poner un pin especial en los puntos donde se registraron personas;
• Poner un pin especial diferenciado, en los puntos donde se registraron afiliaciones.
• Poner un pin especial diferenciado, en los puntos donde se registraron referidos.
Un clic sobre un pin especial de afiliación debe desplegar un cuadro emergente con
información de la afiliación:
• Número de afiliación,
• Hora de registro,
• Estado,
• Afiliador que la registró.
6.4 Reportes
6.4.1 Agenda de campo
Definición
Transacción para visualizar, en formato de reporte y con opción de impresión, la agenda de
actividades que tienen planificadas en campo los afiliadores.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En cuanto a las afiliaciones: En los resultados de cada búsqueda de registros para este
reporte, se incluirán únicamente afiliaciones registradas por afiliadores (empleados)
pertenecientes al grupo de empleados asignado al usuario de sesión, para el objeto interno
“AFILIACION”.
Descripción
1. Al inicio de esta función el sistema debe presentar un filtro de entrada, al menos con los
siguientes datos:
Versión 0.8 Estrictamente privado y confidencial Página 63 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenecen las afiliaciones buscadas.
Por defecto debe estar seleccionada la compañía de sesión.
Otras compañías según la seguridad, para el usuario de
sesión.
Servicio Obligatorio Código del servicio para buscar la planificación, de la
compañía seleccionada. La lista debe incluir servicios
asociados a la compañía seleccionada, sea definida como
compañía principal (ejecutora) o como compañía cliente (en
servicios).
País Opcional País para selección de rutas.
Regional Opcional Regional para selección de rutas, del país seleccionado (si
se marcó alguno).
Ciudad Opcional Ciudad para selección de rutas, del país y regional
seleccionados (si se marcó alguno).
Ruta Opcional Ruta de afiliaciones planificada, del servicio seleccionado,
para el país / regional / ciudad seleccionados.
Fecha de Obligatorio / Rango de fechas desde – hasta para la búsqueda de
trabajo Opcional planificación.
Desde / Hasta • La “Fecha desde” por defecto será la fecha de sesión.
• Se puede buscar sólo por “Fecha desde” (obligatorio).
• “Fecha hasta” (opcional) debe ser mayor o igual a
“Fecha desde”.
Equipo de Opcional Equipo de trabajo correspondiente al servicio seleccionado.
trabajo • Validar seguridad especial por grupos de empleados.
Afiliador Opcional Empleado:
(N) • Si se seleccionó un equipo de trabajo, pueden ser
empleados asignado al equipo seleccionado.
• Si no se seleccionó un equipo de trabajo, puede ser un
empleado que pertenezca a cualquier equipo de trabajo
relacionado con el servicio seleccionado.
• Validar seguridad especial por grupos de empleados.
Agrupar por Obligatorio Campo principal para agrupar el reporte, uno de los
siguientes valores:
• Fecha: Se agrupa por fecha, los afiliadores se llevan en
el detalle.
• Afiliador: Se agrupa por afiliador, las fechas se llevan al
detalle.
Las opciones en este paso son:
• “Buscar”, que avanza al paso 2.
• “Salir”, que vuelve a la pantalla principal del sistema.
Versión 0.8 Estrictamente privado y confidencial Página 64 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
2. El sistema debe “Buscar” todos los registros que cumplan con los criterios de búsqueda
y preparar la agenda de campo solicitada, siguiendo el formato del archivo anexo
“Agenda de campo - Afiliaciones.xlsx”, con las consideraciones a continuación:
Encabezado:
(a) Título, fijo.
(b) Logotipo de la compañía de sesión, del parámetro “Compañías”.
Sección:
(c) Nombre de la compañía cliente, definida en el servicio seleccionado.
(d) Nombre del servicio seleccionado.
(e) Código y nombre de la ruta seleccionada. El reporte debe repetir esta sección
(incluyendo subsecciones) por cada ruta seleccionada.
(f) Nombres de país, ciudad y regional a los que pertenece la ruta.
La sección se repite para cada ruta seleccionada en el filtro de entrada.
Se incluye un salto de página al final de cada ruta.
Sub sección:
(g) Fechas “Desde” y “Hasta” para las que se emite el reporte.
Si la fecha “Hasta” en el filtro de entrada estuvo vacío, se repite la fecha “Desde”.
Se incluye esta fila sólo si en el filtro de entrada se marcó “Agrupar por fecha”.
En este caso la subsección no se repite.
(h) Nombre completo del afiliador.
Se incluye esta fila sólo si en el filtro de entrada se marcó “Agrupar por afiliador”.
En este caso, la sub sección (incluyendo el detalle) se repite para cada afiliador
seleccionado en el filtro de entrada.
Versión 0.8 Estrictamente privado y confidencial Página 65 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Detalle:
(i) Fecha del periodo “Desde – Hasta” de la planificación.
Se incluye esta columna sólo si en el filtro de entrada se marcó “Agrupar por
afiliador”.
(j) Afiliador de la planificación.
Se incluye esta columna sólo si en el filtro de entrada se marcó “Agrupar por fecha”.
(k) Puntos a recorrer
Nombre de cada punto a recorrer, de la ruta planificada seleccionada, para cada
fecha / afiliador incluidos en el detalle.
6.4.2 Listado de personas
Definición
Reporte de las personas registradas en el módulo de Afiliaciones, para diferentes compañías,
servicios, rutas, fechas y/o equipos de afiliación.
6.4.3 Listado de afiliaciones
Definición
Reporte de las afiliaciones (formularios) registradas en el módulo de Afiliaciones, para
diferentes compañías, servicios, rutas, fechas y/o equipos de afiliación.
6.4.4 Listado de referidos
Definición
Reporte de las personas referidas registradas en el módulo de Afiliaciones, para diferentes
compañías, servicios, rutas, fechas y/o equipos de afiliación.
Versión 0.8 Estrictamente privado y confidencial Página 66 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7 Trade
7.1 Catálogos específicos
7.1.1 Rutas de trade
Definición
Catálogo para definir las diferentes rutas en las que se ejecutarán las actividades tanto de
impulsos como de reposición de productos.
Una ruta es, en este módulo, un conjunto ordenado de puntos de venta (PDV) que
pertenecen a una misma compañía; incluye como mínimo un (1) PDV.
Datos
Los datos requeridos para este catálogo son al menos los siguientes:
Dato Condición Descripción
Compañía Obligatorio Código de compañía que ejecutará la ruta (a la que pertenece la
ruta).
Compañía Obligatorio Código de compañía cliente, que será beneficiaria de los servicios
cliente de trade. Es la dueña de los PDV a ser asignados a la ruta.
Código Obligatorio Código de la ruta.
Tipo de ruta Obligatorio Objeto interno para la compañía seleccionada.
Puede ser:
• IMPULSO, para rutas de impulsos, o
• REPOSICION, para rutas de reposiciones.
En esta transacción no se permiten otros valores.
Nombre Obligatorio Texto mediano. Nombre o descripción de a ruta.
País Obligatorio País donde se ejecuta la ruta.
Ciudad Obligatorio Ciudad donde se ejecuta la ruta, del país seleccionado.
Estado Obligatorio En creación / Activo / Inactivo.
Gestión del estado en “Características especiales”.
Puntos de venta (N, mínimo 1)
Código Obligatorio Código del PDV. Los PDV en una ruta pertenecen a la compañía
cliente antes seleccionada. El botón de búsqueda de PDV debe
incluir compañía en el filtro.
Secuencia Obligatorio Número entero, a partir de 1, que define el orden de visita a los
PDV en la ruta.
Hora ingreso Obligatorio Hora de ingreso al PDV.
Para el punto N+1 la hora de ingreso debe ser posterior a la
definida para el punto N.
Versión 0.8 Estrictamente privado y confidencial Página 67 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Tiempo Obligatorio Tiempo estimado en horas y minutos que tomarán las actividades a
estimado realizarse en el PDV.
Observación Opcional Texto mediano.
Observación al PDV en la ruta.
Características especiales
• Una ruta debe tener al menos un PDV asignado.
• Los PDV de una ruta deben pertenecer a la misma compañía (compañía cliente del
servicio).
• Estas rutas se deben poder visualizar sobre un mapa de Google Maps, usando la
ubicación geográfica registrada en cada PDV.
• Cada PDV se debe mostrar visualmente en el mapa con un ícono (por ejemplo, un pin).
Se debe trazar una línea azul que muestre la ruta completa, uniendo los PDV según su
secuencia (orden) establecida.
Estados de una ruta:
• Toda nueva ruta tendrá el estado “En creación”.
• Una ruta “En creación” puede ser editada; no puede ser usada en las transacciones del
sistema, hasta que se active.
• La función “Activar ruta” realiza el cambio de su estado a “Activo”; sólo las rutas activas
se usan en transacciones del sistema.
• Una ruta se puede activar o inactivar (cambio al estado “Inactivo”) pero no retorna al
estado “En creación”.
7.2 Planificación
7.2.1 Asignar productos por PDV
Definición
Transacción para asignar los productos con los que se realizarán las actividades, tanto de
impulsos como de reposiciones, en cada punto de venta de cada cliente (compañía externa).
Seguridad especial
Para acceder y utilizar esta transacción, un usuario requiere:
• Tener asignado el rol que incluye la transacción;
• Tener asignada la compañía de la cual gestionará información.
Funcionalidades requeridas
1. Al inicio de la transacción el sistema debe presentar un filtro para la gestión de las
asignaciones, con al menos los siguientes datos:
Dato Condición Descripción
Compañía Obligatorio Compañía externa (entidad cliente; una) cuya planificación
cliente de impulsos se requiere gestionar.
Versión 0.8 Estrictamente privado y confidencial Página 68 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

| Dato  | Condición  |                                              | Descripción  |
| ----- | ---------- | -------------------------------------------- | ------------ |
| País  | Opcional   | País para la selección de ciudades y PDVs.   |              |
Por defecto el país de la compañía seleccionada.

| Ciudad  | Opcional  | Ciudad, del país seleccionado.  |     |
| ------- | --------- | ------------------------------- | --- |

| PDV  | Opcional  | PDV, de la compañía y ciudad seleccionadas.  |     |
| ---- | --------- | -------------------------------------------- | --- |

Por defecto los campos del filtro deben estar vacíos (se lee como “todos” los valores).

Las opciones del sistema para esta transacción son las siguientes:
•  “Buscar”, paso 2;
•  “Salir”, que vuelve a la pantalla principal del sistema.

2.  El sistema debe presentar el listado de registros que cumplen con los criterios de
búsqueda, con estos datos:

Encabezado:

Compañía cliente  La del filtro de entrada, fija (no se puede cambiar en este paso).
País  El del filtro de entrada, si se seleccionó. Se permite cambiar.
Ciudad  El del filtro de entrada, si se seleccionó. Se permite cambiar (actualiza
el listado).

Listado (detalle):

| Columna  |                                                | Condición  |     |
| -------- | ---------------------------------------------- | ---------- | --- |
| PDV      | Código del PDV (de la compañía cliente).       |            |     |
| Nombre   | Nombre del PDV.                                |            |     |
| SKU      | Código del producto (de la compañía cliente).  |            |     |
| Nombre   | Nombre del producto.                           |            |     |
Fecha corta  Margen de fecha corta del SKU en el PDV (en días).
Stock mínimo  Cantidad mínima de unidades del SKU en el PDV (en UM stock).
| UM stock       | Unidad de medida de stock del SKU.         |     |     |
| -------------- | ------------------------------------------ | --- | --- |
| Estado         | Estado (de la asignación del SKU al PDV).  |     |     |
| Observaciones  | Observación del registro.                  |     |     |
| Eliminar       | Campo para marcar registros a eliminar.    |     |     |

Todas las columnas deben permitir filtrar los registros por sus valores.

Con las siguientes opciones:
•  “Agregar”, paso 3;
•  “Visualizar”, vínculo a partir del SKU al al detalle del registro, paso 4;
•  “Importar”, paso 5;
•  “Exportar”, paso 6;
•  “Eliminar”, que elimina los registros marcados; y
•  “Volver”, retorna al paso 1.

Versión 0.8  Estrictamente privado y confidencial  Página 69 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
3. Opción para agregar un registro de asignación de productos por PDV, con al menos los
siguientes datos:
Dato Condición Descripción
Compañía Obligatorio Fija. La del filtro de entrada.
cliente
PDV Obligatorio Código del PDV, de la compañía seleccionada.
En el botón de búsqueda (…) incluir país, ciudad, tipo de
PDV y canal.
SKU Obligatorio Código del producto, de la compañía seleccionada.
En el botón de búsqueda (…) incluir las 4 categorías que
definen la codificación (valores).
Margen de Obligatorio Margen de fecha corta del SKU en el PDV.
fecha corta Por defecto poner el margen de fecha corta del catálogo del
SKU; se permite modificar.
Stock mínimo Obligatorio Cantidad mínima de unidades del SKU en el PDV,
expresada en UM stock.
Por defecto poner el stock mínimo del catálogo del SKU; se
permite modificar.
Estado Obligatorio Activo / Inactivo.
Estado de la asignación del SKU al PDV.
Por defecto será “Activo”; se permite el cambio a “Inactivo”
para registros previos.
Observaciones Opcional Texto largo. Observación que pueda tener el usuario a la
asignación realizada.
Las opciones requeridas son:
• “Guardar”: graba el nuevo registro y retorna al listado (paso 2);
• “Cancelar”: retorna al listado (paso 2) sin grabar los datos ingresados.
4. Opción para visualizar un registro previo, con los mismos datos / pantalla del paso 3.
Las opciones requeridas son:
• “Editar”: permite modificar algunos datos del registro (fecha corta, stock mínimo,
estado y observaciones), con las opciones:
o “Guardar” la modificación, se mantiene en la visualización del registro;
o “Volver” a la visualización del registro sin guardar los cambios.
• “Volver”: retorna al listado (paso 2).
5. La opción “Importar” debe permitir importar registros desde un archivo de texto, con
los mismos datos del ingreso manual.
Se permite importar datos de una sola compañía a la vez.
Versión 0.8 Estrictamente privado y confidencial Página 70 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
6. La opción “Exportar” debe permitir exportar los registros seleccionados a un archivo de
texto. En la exportación se aplican los mismos filtros ingresados para la transacción (una
sola compañía por exportación).
7.2.2 Preparar bandeos
Definición
Transacción para preparar el bandeo de productos a ser realizado en un PDV.
Se entiende como “bandeo” a la unión de dos o más productos para ser vendidos como uno
solo en una promoción comercial.
Seguridad especial
Para acceder y utilizar esta transacción, un usuario requiere:
• Tener asignado el rol que incluye la transacción;
• Tener asignada la compañía de la cual gestionará información.
Funcionalidades requeridas
1. Al inicio de la transacción el sistema debe presentar un filtro para la preparación del
bandeo, con al menos los siguientes datos:
Dato Condición Descripción
Compañía Obligatorio Compañía externa (entidad cliente; una) cuya planificación
cliente de impulsos se requiere gestionar.
País Opcional País para la selección de ciudades y PDVs.
Por defecto el país de la compañía seleccionada.
Ciudad Opcional Ciudad, del país seleccionado.
PDV Opcional PDV, de la compañía y ciudad seleccionadas.
Por defecto los campos del filtro deben estar vacíos (se entiende como “todos” los
valores).
Las opciones del sistema para esta transacción son las siguientes:
• “Buscar”, paso 2;
• “Salir”, que vuelve a la pantalla principal del sistema.
2. El sistema debe presentar el listado de registros previos de bandeos que cumplen con
los criterios de búsqueda, con estos datos:
Versión 0.8 Estrictamente privado y confidencial Página 71 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Encabezado:
Compañía cliente La del filtro de entrada, fija (no se puede cambiar en este paso).
Listado (detalle):
Columna Contenido
PDV Código del PDV.
Nombre Nombre del PDV.
Bandeo Código del bandeo.
Descripción Descripción del bandeo.
Estado Estado del bandeo: Activo / Inactivo (estándar).
Eliminar Campo para marcar registros a eliminar.
Todas las columnas deben permitir filtrar los registros por sus valores.
Con las siguientes opciones:
• “Agregar”, paso 3;
• “Visualizar”, a partir del código de bandeo que será un vínculo al detalle del
registro, paso 4;
• “Copiar” un bandeo marcado, permitiendo su edición;
• “Eliminar”, que elimina los registros marcados; y
• “Volver”, retorna al paso 1.
3. Opción para agregar un registro de bandeo para el PDV, con al menos los siguientes
datos:
Dato Condición Descripción
Compañía Obligatorio Compañía seleccionada en el filtro de entrada.
PDV Obligatorio Lista de selección. Código de un PDV, de la compañía
seleccionada.
Nombre del Lectura Nombre del PDV seleccionado.
PDV
Código Obligatorio Texto corto. Código del bandeo (único por compañía).
Descripción Obligatorio Texto mediano. Descripción del bandeo.
Observaciones Opcional Texto largo. Notas a tener en cuenta al momento de armar el
bandeo.
Fotografía Opcional Carga de una fotografía de cómo debería quedar el bandeo.
Estado Obligatorio Estado del bandeo: Activo / Inactivo. Estándar.
Productos incluidos (pueden ser N)
SKU Obligatorio Código del producto a incluirse en el bandeo, de los productos
asignados al PDV seleccionado.
El SKU se busca con un “Botón de búsqueda” (botón “…”), que
abre un diálogo para buscar un SKU por diferentes criterios:
Versión 0.8 Estrictamente privado y confidencial Página 72 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
• Código,
• Nombre o parte del nombre,
• Categorías principales (valores de las 4 categorías que
componen el código).
Nombre Lectura Nombre del producto seleccionado. Se muestra al seleccionar el
código.
Cantidad en Obligatorio Número entero mayor a 0. Cantidad del producto, en la UM a
bandeo ser escogida, que se incluye en un bandeo (un paquete).
UM Obligatorio Unidad de medida del producto seleccionado que se usará para
el bandeo, del catálogo del producto; se permite escoger la “UM
stock” o la “UM venta”.
Ejemplo: Se requiere bandear botellas de refresco; para cada bandeo se necesita:
SKU Nombre Q paquete UM
100210BOT000001 … Refresco de limón envase retornable 1 UI
de 2 lt
100210VAS000001 … Vaso de plástico de 200 ml para 1 UI
promociones
999100PRO000001 … Cinta de ofertas para bandeo 50 CM
En este punto se requieren las siguientes opciones:
• “Visualizar SKU”, vínculo en el SKU a todos sus datos (catálogo), desde donde se
debe volver a este paso;
• “Guardar”, guarda los datos del bandeo y retorna al paso 2;
• “Volver”, retorna al paso 2 sin guardar los datos ingresados.
4. Opción para visualizar un registro previo de bandeo, con los mismos datos / pantalla
del paso 3.
Las opciones requeridas son:
• “Editar”: permite modificar los datos del bandeo:
o “Guardar” la modificación, se mantiene en la visualización del registro;
o “Volver” a la visualización del registro sin guardar los cambios.
• “Volver”: retorna al listado (paso 3).
7.2.3 Planificación semanal
Definición
Transacción para planificar las rutas a recorrerse semanalmente, por los equipos de trabajo
de cada compañía (ejecutora del servicio), para realizar actividades de impulsos y/o de
reposiciones.
Versión 0.8 Estrictamente privado y confidencial Página 73 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Registro del plan semanal: Compañía + Ruta + Empleado + Fecha (día de trabajo).
En cada registro del plan, se deben incluir también los bandeos a realizarse en cada PDV.
El formato base de la transacción debe ser una agenda, con periodicidad semanal por
defecto. Debe contar con un filtro según los datos más relevantes.
Seguridad especial
Para acceder y utilizar esta transacción, un usuario requiere:
• Tener asignado el rol que incluye la transacción;
• Tener asignada la compañía de la cual gestionará información;
• En esta transacción se permite a un usuario gestionar (registrar / visualizar / editar /
eliminar) la planificación para los grupos de trabajo de los cuales es “Supervisor”.
Funcionalidades requeridas
1. Al inicio de la transacción el sistema debe presentar un filtro para la gestión de la
planificación, con al menos los siguientes datos:
Dato Condición Descripción
Compañía Obligatorio Compañía (una) cuya planificación se requiere gestionar
(compañías que ejecutan servicios, internas).
Por defecto debe estar seleccionada la compañía de sesión.
Ruta Opcional Ruta cuya planificación se requiere visualizar, de la
compañía seleccionada.
• De los objetos internos “IMPULSO” o “REPOSICION”.
Equipo de Opcional Equipo de trabajo cuya planificación se requiere gestionar,
trabajo de la compañía seleccionada (para uso en el filtro).
Se incluyen en la lista y permiten seleccionar los equipos de
trabajo:
• De los objetos internos “IMPULSO” o “REPOSICION”;
• En los que el usuario de sesión se encuentra asignado
como “Supervisor”.
Empleado Opcional Uno de los empleados que forman parte del equipo de
trabajo seleccionado.
Las fechas no forman parte del filtro de entrada, son las que se ven en el calendario.
Por defecto los campos del filtro deben estar vacíos (se lee como “todos” los valores),
excepto la compañía.
Este filtro debe ubicarse dentro de un panel abierto que se pueda cerrar:
Versión 0.8 Estrictamente privado y confidencial Página 74 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Inmediatamente debajo del filtro, debe presentar un calendario vacío, en configuración
“Semanal”, ejemplo:
Para la vista semanal, la semana es de 7 días, empieza en lunes. Por tanto, debe
mostrar de lunes a domingo.
Las horas de trabajo por defecto son estándar, de 9:00 a 17:00.
Debajo del calendario (pie de la pantalla) debe ubicarse un segundo panel (abierto, que
se pueda cerrar) con el código de colores usado para mostrar los diferentes registros
del plan. Se debe asignar el mismo color a todos los registros de cada ruta.
Los colores son:
RUTA1 Amarillo oscuro (RGB: 255, 192, 0)
RUTA2 Verde (RGB: 146, 208, 80)
RUTA3 Azul claro (RGB: 157, 195, 230)
Etc.
Las opciones del sistema para esta transacción son las siguientes:
• “Buscar”, paso 2;
• “Importar”, paso 5;
• “Exportar”, paso 6;
• “Salir”, que vuelve a la pantalla principal del sistema.
2. La opción “Buscar” debe mostrar en el calendario los registros de la planificación que
cumpla con los criterios de búsqueda del filtro, que se encuentren en el periodo de
tiempo que muestra el calendario.
Registro del plan = Compañía + Ruta + Empleado + Fecha
(encabezado) (calendario)
Versión 0.8 Estrictamente privado y confidencial Página 75 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Se pueden agregar registros en la agenda y/o seleccionar registros existentes para su
edición y/o para agregarles bandeos, según:
• Clic en un punto de la agenda: agregar o editar, con un cuadro emergente del
registro de planificación, según se detalla en el paso 3.
• Doble clic en un registro existente: agregar o editar bandeos al registro de
planificación seleccionado, según se detalla en el paso 4.
En el calendario, se debe poder cambiar a las vistas mensual y diaria. En cualquier
vista, debe salir marcado el día de sesión en azul (como en el ejemplo).
Se deben mantener los demás controles estándares del componente “Calendario” como
avanzar o retroceder fechas, y otros.
3. Un clic en la agenda permite agregar un registro de planificación (clic en una fecha /
hora sin registro) o editar un registro seleccionado.
Para un registro nuevo el sistema debe abrir un cuadro de diálogo para el ingreso de los
siguientes datos:
Dato Condición Descripción
Fecha y hora Obligatorio Por defecto: Fecha marcada en el calendario
de inicio Control: >= Fecha de sesión (no se permite la planificación
de fechas pasadas)
Ruta Obligatorio Ruta de reposiciones cuya planificación se requiere
visualizar, de la compañía seleccionada.
Empleado Obligatorio Empleado de la compañía seleccionada y del equipo de
trabajo del filtro (si hay uno seleccionado).
Los empleados que se permite seleccionar sólo pueden ser
miembros de los equipos de trabajo de la compañía, donde
el usuario de sesión es supervisor.
Los datos que se incluyen en cada lista y que se permiten seleccionar dependen de la
seguridad del usuario de sesión, igual que en el filtro de entrada.
Las opciones de este cuadro son:
• “Guardar”: graba el nuevo registro de planificación y cierra el cuadro; debe
actualizar el calendario en pantalla.
• “Eliminar” un registro existente en la planificación con la verificación de fechas;
debe actualizar el calendario en pantalla.
• “Cancelar”: cierra el cuadro sin grabar los nuevos datos.
4. Un doble clic en la agenda, sobre un registro de planificación existente, permite
agregar o editar bandeos correspondientes al registro.
Versión 0.8 Estrictamente privado y confidencial Página 76 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
En este caso el sistema debe desplegar un cuadro emergente con la siguiente lista:
Dato Condición
PDV Predefinido.
Incluir todos los PDV pertenecientes a la ruta del registro de
planificación seleccionado.
Bandeo Predefinido.
Incluir todos los bandeos activos que se encuentren asignados a cada
PDV.
Q bandeo Obligatorio. Número entero >= 0.
Es la cantidad de paquetes de cada bandeo que se planifica armar en el
PDV.
En este cuadro se permite:
• “Guardar” las cantidades planificadas de bandeos por PDV (nuevas o editadas); se
debe controlar que “Fecha >= Fecha de sesión” (no se permite la planificación de
fechas pasadas).
• “Cancelar” que cierra el cuadro sin grabar los cambios de datos.
5. La opción “Importar” debe permitir cargar N registros de la planificación a partir de un
archivo plano de datos, incluyendo datos de bandeo (funciones estándar del sistema
para importación, desde archivo csv).
Sólo se permite importar registros para una compañía a la vez (una compañía por
archivo). Se deben aplicar las mismas validaciones a los datos que se realizan al agregar
registros de planificación nuevos.
Si se genera algún error en la validación de datos, se debe dar el mensaje de error
incluyendo el detalle de los registros procesados con error. La importación no se realiza.
Cuando todos los registros del archivo se validan, la importación se completa. Al
finalizar se debe dar al usuario un mensaje de éxito, incluyendo la cantidad de registros
importados.
Al salir de la función de importación se debe actualizar el calendario en pantalla.
6. La opción “Exportar” debe permitir llevar los registros de la planificación que cumplen
con el filtro de búsqueda ingresado, a un archivo plano de datos (archivo csv),
incluyendo los datos de bandeo (funciones estándar del sistema para exportación).
7.3 Actividades de ruta
Notas del proceso de reposiciones:
Cuando un reponedor llega a un PDV debe marcar su ingreso.
Versión 0.8 Estrictamente privado y confidencial Página 77 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
A continuación, debe realizar actividades de reposición externas al sistema como limpieza de
góndolas, limpieza de productos, organización de productos en exposición, y otras. Si es
necesario, realiza también la reposición de productos de almacén a sala. Cuando concluye
estas actividades, el reponedor debe tomar y enviar las fotografías de éxito de su trabajo.
En sus actividades el reponedor podría realizar la recepción de productos a su proveedor, e
ingresarlos al PDV.
Finalmente, el reponedor debe realizar la toma de inventario en el PDV, que incluye el
control de fechas cortas y quiebres de stock.
Si es necesario (depende de productos en fecha corta y de planes de promoción), el
reponedor puede preparar bandeos, de cuyo resultado debe enviar fotografías de éxito.
Al finalizar todas las actividades, el reponedor debe marcar su salida del PDV.
Casos especiales a considerar:
• Puede ir un reponedor solo
• Cambio de reponedor (emergencia)
• Visita especial por pedido de cliente
7.3.1 Ingresar a PDV
Definición
Transacción para marcar la llegada a un PDV, dentro de la ruta del día laboral asignada al
usuario de sesión.
Seguridad especial
En esta transacción el sistema presenta únicamente la ruta asignada al usuario de sesión (si
tiene una), para la fecha de sesión.
Funcionalidades requeridas
1. Al ingresar a la transacción el sistema debe buscar la ruta de trabajo planificada para el
usuario en la fecha de sesión. Se sugiere:
• Usuario de sesión -> Empleado de sesión (desde el catálogo de empleados)
• En la planificación buscar:
Registro: Compañía de sesión + Fecha de sesión + Empleado de sesión
Obtener: Ruta a ejecutar
Una vez encontrada la ruta, se requiere mostrarla en el mapa de pantalla, en azul. Los
PDV de la ruta se muestran en colores:
• PDV pendiente en rojo (no tiene registro de ingreso ni de salida);
• PDV abierto en amarillo (tiene registro de ingreso pero no de salida);
• PDV cerrado en verde (tiene registro de ingreso y de salida).
Se requieren las siguientes opciones en pantalla:
Versión 0.8 Estrictamente privado y confidencial Página 78 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• “Marcar ingreso”:
o Si no hay un PDV abierto habilitada – paso 2;
o Si hay un PDV abierto inhabilitada.
• “Salir”, que retorna a la pantalla inicial del sistema.
2. La opción “Marcar ingreso” debe:
• Obtener la ubicación geográfica (UG) del usuario.
• Calcular “DI = Distancia de Ingreso” en metros, entre la UG del usuario y la UG del
PDV.
• Si la “DI <= Distancia máxima de marca” para el PDV se acepta el “Ingreso a PDV”:
o Se registra la UG, fecha, hora y distancia de ingreso al PDV en el sistema.
o Se “abre” el PDV para el usuario, con lo cual se le permiten las transacciones de
Impulsos en el PDV.
o Se muestra el PDV en el mapa, en color amarillo (PDV abierto).
o Se muestran los datos de ingreso al PDV en pantalla.
o Se inhabilita la opción “Marcar ingreso”.
• Si la “DI > Distancia máxima de marca” para el PDV se rechaza el “Ingreso a PDV”:
o Mostrar mensaje al usuario que indica “No es posible marcar el ingreso al PDV
dado que aún se encuentra lejos del mismo”.
o No se realizan cambios en pantalla.
o No se permiten transacciones de Impulsos en el PDV para el usuario de sesión.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.2 Actividades de impulsos
7.3.2.1 Inventario inicial de productos
Definición
Transacción para registrar el inventario inicial de productos existentes en un PDV abierto.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta de impulsos asignada para el día de
sesión:
Versión 0.8 Estrictamente privado y confidencial Página 79 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Si tiene un PDV abierto, el registro de inventario corresponderá a ese PDV; avanza
al paso 2.
• Si no tiene un PDV abierto, no se permite el registro inventario; se debe dar un
mensaje que indique que debe registrar el ingreso al PDV antes de registrar su
inventario. Todos los botones se deshabilitan excepto “Salir”.
2. Para el PDV abierto, el sistema debe mostrar en pantalla:
Encabezado:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV (de la planificación, previamente abierto)
Nombre Nombre del PDV
Fecha de último La fecha del inventario de impulsos más reciente que se haya
inventario registrado para el PDV.
Listado (detalle):
Columna Condición
SKU Código del producto. Lectura.
Se deben incluir en la lista todos los SKU que fueron asignados al PDV
(asignación activa en la planificación).
Nombre Nombre del producto. Lectura.
Cantidad inicial Campo abierto / de lectura (*1), obligatorio.
Número entero igual o mayor a 0.
Valor por defecto = 0.
El usuario ingresará la cantidad del producto que encuentre en stock
inicial en el PDV.
UN stock Unidad de medida “UM stock” del producto. Lectura.
Stock mínimo Stock mínimo del producto en el PDV (tomado de la asignación del SKU
al PDV).
Quiebre de stock Indicador calculado (Si / No):
Si Cantidad total < Stock mínimo, entonces Quiebre de stock = Si
(pintar el indicador de rojo)
Si Cantidad total >= Stock mínimo, entonces Quiebre de stock = No
(pintar el indicador de verde)
Observaciones Campo abierto, opcional. Texto largo.
El usuario ingresará una nota al producto, si lo considera necesario.
Nota (*1):
Sólo se permite registrar el inventario inicial para el PDV una vez. Por tanto:
• Si no se tiene registro de inventario inicial del día, el campo “Cantidad existente”
admite ingreso de dato.
Versión 0.8 Estrictamente privado y confidencial Página 80 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Si ya se tiene registro de inventario inicial del día, el campo “Cantidad existente”
muestra el dato previo pero no permite edición (esto permitirá al usuario visualizar
el inventario inicial en cualquier momento de las actividades del impulso).
• En ambos casos se permite editar el campo “Observaciones”.
Todas las columnas deben permitir filtrar los registros por sus valores.
Se requieren las siguientes opciones:
• “Guardar” los datos ingresados y salir a la pantalla principal del sistema;
• “Salir”, retorna a la pantalla principal del sistema; no guarda los datos ingresados.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.2.2 Registrar venta
Definición
Transacción para registrar cada venta de productos impulsados que se realiza en un PDV
abierto.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar:
• Si el usuario de sesión tiene un PDV abierto (registró su ingreso al PDV), en la ruta
de impulsos asignada para el día de sesión;
• Si se registró inventario inicial para el PDV.
Si se cumplen las condiciones, el registro de venta es permitido para el PDV; avanza al
paso 2.
Si no se cumplen las condiciones, no se permite el registro de ventas; se debe dar un
mensaje al usuario que indique los pasos previos no realizados. Todos los botones se
deshabilitan excepto “Salir”.
2. Para el PDV abierto y con inventario, el sistema debe mostrar en pantalla:
Encabezado:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV (de la planificación, previamente abierto)
Nombre Nombre del PDV
Listado (detalle) donde se permite agregar una fila por cada producto vendido:
Versión 0.8 Estrictamente privado y confidencial Página 81 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
SKU Código del producto. Lista para selección (incluir código y nombre).
Obligatorio.
Se deben incluir en la lista todos los SKU de la compañía cliente que
fueron asignados al PDV (asignación activa en la planificación).
Búsqueda Botón de búsqueda de SKU (botón “…”), que abra un diálogo para
buscar un SKU por diferentes criterios:
• Código
• Nombre o parte del nombre
• Categorías principales (valores de las 4 categorías que componen el
código)
Esta búsqueda incluye sólo SKUs de la compañía cliente asignados al
PDV.
Nombre Nombre del producto. Lectura.
Se actualiza al seleccionar un SKU.
Cantidad Campo abierto, obligatorio.
Número entero igual o mayor a 0.
Valor por defecto = 1.
El usuario ingresará la cantidad del producto que se haya vendido.
Cantidad (de la venta) <= Cantidad inicial (del inventario inicial).
UN stock Unidad de medida “UM venta” del producto. Lectura (dato del catálogo
de SKU).
Comprobantes de venta (pueden ser N):
Columna Condición
Archivos Carga de N archivos gráficos (fotografías) que comprueban la venta
(factura). Obligatorio cargar un archivo (mínimo 1).
Los archivos cargados se deben visualizar en pantalla.
Sin comprobante Dato Si / No. Por defecto “No”.
El usuario marcará “Sin comprobante = Si” sólo cuando no se puede
obtener una fotografía comprobante de la venta. En este caso, el
archivo no se carga, pero las observaciones son obligatorias.
Observaciones Campo abierto, opcional / obligatorio. Texto largo.
El usuario ingresará una nota al producto, si lo considera necesario.
Es opcional si tiene el archivo cargado, pero es obligatorio si no se
tiene archivo y se marca “Sin comprobante = Si”.
Se requieren las siguientes opciones:
• “Guardar” los datos ingresados y salir a la pantalla principal del sistema;
• “Salir”, retorna a la pantalla principal del sistema; no guarda los datos ingresados.
Versión 0.8 Estrictamente privado y confidencial Página 82 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.2.3 Inventario final de productos
Definición
Transacción para registrar el inventario final (inventario de cierre) de productos restantes en
un PDV abierto.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta de impulsos asignada para el día de
sesión y con inventario inicial registrado:
• Si se cumplen las condiciones, el registro de inventario de cierre corresponderá a
ese PDV; avanza al paso 2.
• Si no tiene un PDV abierto y/o lo tiene uno pero sin inventario inicial, no se permite
el registro de inventario de cierre; se debe dar un mensaje que indique los
incidentes encontrados (debe registrar el ingreso al PDV, y/o debe registrar el
inventario inicial antes de registrar inventario de cierre). Todos los botones se
deshabilitan excepto “Salir”.
2. Para el PDV abierto, con inventario inicial, el sistema debe mostrar en pantalla:
Encabezado:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV (de la planificación, previamente abierto)
Nombre Nombre del PDV
Fecha de Fecha del inventario inicial registrado para el PDV.
inventario inicial
Hora de Hora del inventario inicial registrado para el PDV.
inventario inicial
Listado (detalle):
Columna Condición
SKU Código del producto. Lectura.
Se deben incluir en la lista todos los SKU que fueron asignados al PDV
(asignación activa en la planificación).
Nombre Nombre del producto. Lectura.
Cantidad inicial Cantidad del producto registrada en el inventario inicial. Lectura.
Versión 0.8 Estrictamente privado y confidencial Página 83 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
Cantidad final Campo de lectura (*2), obligatorio.
Número entero igual o mayor a 0.
Valor por defecto = 0.
El usuario ingresará la cantidad del producto que encuentre en stock
en el PDV.
Control: Cantidad final <= Cantidad inicial
UN stock Unidad de medida “UM stock” del producto. Lectura.
Stock mínimo Stock mínimo del producto en el PDV (tomado de la asignación del SKU
al PDV).
Quiebre de stock Indicador calculado (Si / No):
Si Cantidad total < Stock mínimo, entonces Quiebre de stock = Si
(pintar el indicador de rojo)
Si Cantidad total >= Stock mínimo, entonces Quiebre de stock = No
(pintar el indicador de verde)
Observaciones Campo abierto, opcional. Texto largo.
Se muestra la observación registrada al inicio, si hay una; el usuario
puede modificar y/o complementar esa observación al producto, si lo
considera necesario.
Nota (*2):
Sólo se permite registrar el inventario de cierre para el PDV una vez. Por tanto:
• Si no se tiene registro de inventario de cierre del día, el campo “Cantidad al cierre”
admite ingreso de dato.
• Si ya se tiene registro de inventario de cierre del día, el campo “Cantidad existente”
muestra el dato previo pero no permite edición (esto permitirá al usuario visualizar
el inventario de cierre después de registrarlo).
• En ambos casos se permite editar el campo “Observaciones”.
Se deben guardar la fecha y hora del inventario final.
Todas las columnas deben permitir filtrar los registros por sus valores.
Se requieren las siguientes opciones:
• “Guardar” los datos ingresados y salir a la pantalla principal del sistema;
• “Salir”, retorna a la pantalla principal del sistema; no guarda los datos ingresados.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
Versión 0.8 Estrictamente privado y confidencial Página 84 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.3.3 Actividades de reposición
7.3.3.1 Registrar reposición
Definición
Transacción para registrar el resultado de las actividades de reposición realizadas en un PDV
abierto.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta de reposiciones asignada para el día de
sesión:
• Si tiene un PDV abierto, el registro de inventario corresponderá a ese PDV; avanza
al paso 2.
• Si no tiene un PDV abierto, no se permite el registro de la reposición; se debe dar
un mensaje que indique que debe registrar el ingreso al PDV antes de registrar sus
actividades. Todos los botones se deshabilitan excepto “Salir”.
2. Para el PDV abierto, el sistema debe mostrar en pantalla los datos del PDV y listar todos
los productos que tiene asignados.
Encabezado:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV (de la planificación, previamente abierto)
Nombre Nombre del PDV
Fecha de Fecha de registro de la reposición. Automático: fecha de sesión.
reposición
Productos (listado):
Columna Condición
SKU Código del producto. Lectura.
Se deben incluir en la lista todos los SKU que fueron asignados al PDV
(estado de asignación activa en la planificación).
Nombre Nombre del producto. Lectura.
UM stock Unidad de medida “UM stock” del producto. Lectura.
Revisado Dato de tipo “Si / No”, obligatorio.
Indica si el reponedor revisó o no el producto en el PDV.
Por defecto “No”.
Fotografías (listado):
Columna Condición
Versión 0.8 Estrictamente privado y confidencial Página 85 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
Archivo El sistema debe permitir la carga de N fotografías del resultado de la
reposición, siendo obligatoria 1.
Se requieren las siguientes opciones:
• “Guardar” los datos ingresados y salir a la pantalla principal del sistema;
• “Salir”, retorna a la pantalla principal del sistema; no guarda los datos ingresados.
Si el usuario realizó el registro de la reposición y vuelve a entrar a esta pantalla, se
muestran los datos antes registrados y se permite su edición, mientras el PDV esté
abierto. Una vez que el PDV fue cerrado, no se permite la edición de estos datos.
7.3.3.2 Inventario de productos
Definición
Transacción para registrar el inventario de productos existentes en un PDV abierto.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta de reposiciones asignada para el día de
sesión:
• Si tiene un PDV abierto, el registro de inventario corresponderá a ese PDV; avanza
al paso 2.
• Si no tiene un PDV abierto, no se permite el registro inventario; se debe dar un
mensaje que indique que debe registrar el ingreso al PDV antes de registrar su
inventario. Todos los botones se deshabilitan excepto “Salir”.
2. Registro de inventario
Para el PDV abierto, el sistema debe verificar si el inventario del PDV está abierto o
cerrado:
• Esta abierto tenga o no datos registrados, mientras el usuario NO usó la opción
”Cerrar inventario” (más adelante). En este caso se muestran los datos registrados
y se permite su edición.
• Está cerrado tenga o no datos registrados, cuando el usuario SI usó la opción
”Cerrar inventario” (más adelante). En este caso se muestran los datos registrados
pero no se permite su edición.
Para el inventario, el sistema debe mostrar en pantalla los datos del PDV y listar
automáticamente todos los productos que tenga asignados (en la planificación), junto
con las cantidades de los productos registradas en el inventario anterior (si se tiene uno
registrado).
Requiere los siguientes datos.
Datos del PDV:
Versión 0.8 Estrictamente privado y confidencial Página 86 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV (de la planificación, previamente abierto)
Nombre Nombre del PDV
Fecha de Fecha del inventario inmediato anterior realizado en el PDV
inventario anterior
Existencias (tabla, una fila por producto):
Columna Condición
SKU Código del producto. Lectura.
Se deben incluir en la lista todos los SKU que fueron asignados al PDV
(asignación activa en la planificación).
Nombre Nombre del producto. Lectura.
Cantidad anterior Cantidad del producto en sala registrado en el inventario anterior.
en sala Lectura.
Cantidad en sala Cantidad del producto encontrada en sala. Obligatorio.
Valor por defecto: 0
Control: Número entero igual o mayor a 0.
El usuario ingresará la cantidad del producto que encuentre en
exposición en el PDV, en UM stock.
Cantidad anterior Cantidad del producto en almacén registrado en el inventario anterior.
en almacén Lectura.
Cantidad en Cantidad del producto encontrada en almacén. Obligatorio.
almacén Valor por defecto: 0
Control: Número entero igual o mayor a 0.
El usuario ingresará la cantidad del producto que encuentre en el
almacén del PDV, en UM stock.
Vencimientos Botón para registro de fechas de vencimiento del stock en sala o
almacén (paso 3).
Cantidad total Cantidad total del producto registrado en el inventario anterior.
anterior Cantidad total anterior = Cantidad anterior en sala + Cantidad anterior
en almacén
Lectura.
Cantidad total Calculado por el sistema automáticamente.
Cantidad total = Cantidad en sala + Cantidad en almacén
Se debe actualizar cuando el usuario ingresa alguna de las cantidades
del producto (en sala o en almacén).
UM stock Unidad de medida “UM stock” del producto (de su catálogo). Lectura.
Stock mínimo Stock mínimo del producto en el PDV (tomado de la asignación del SKU
al PDV).
Versión 0.8 Estrictamente privado y confidencial Página 87 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
Quiebre de stock Indicador calculado (Si / No):
Si Cantidad total < Stock mínimo, entonces Quiebre de stock = Si
(pintar el indicador de rojo)
Si Cantidad total >= Stock mínimo, entonces Quiebre de stock = No
(pintar el indicador de verde)
Observaciones Campo abierto, opcional. Texto largo.
El usuario ingresará una nota al producto, si lo considera necesario.
Todas las columnas deben permitir filtrar los registros por sus valores.
El botón “Vencimientos” se usará para registrar el lote y fecha de vencimiento de cada
unidad en existencia de cada producto, sea que se encuentre en sala o en almacén.
Cuando se presione este botón, el sistema debe avanzar al paso 3.
En esta función se requieren las siguientes opciones:
• “Guardar” los datos ingresados (existencias y vencimientos) y mantenerse en la
pantalla de inventario; se permite la edición de los datos ingresados en pantalla; el
sistema se mantiene en la misma pantalla.
• “Cerrar inventario” guarda todos los datos ingresados pero ya no se permitirá
editarlos, por lo que debe dar un mensaje de advertencia al usuario (Confirmar /
Cancelar); retorna a la pantalla principal del sistema.
• “Salir”, retorna a la pantalla principal del sistema; no guarda los datos ingresados.
3. Registro de vencimientos
El sistema debe agregar registros en la tabla de vencimientos, ubicada debajo de la
tabla de existencias, incluyendo automáticamente tantos registros como cantidad total
de ítems se haya ingresado en las existencias. Adicionalmente, el sistema debe copiar el
número de lote y la fecha de vencimiento del último registro de vencimientos, a todos
los nuevos registros de vencimientos, para cada producto.
Requiere los siguientes datos:
Datos del SKU:
SKU Código del SKU
Nombre Nombre del SKU
Margen de fecha Número en días, tomado de la asignación del SKU al PDV
corta (planificación)
Vencimientos (tabla, una fila por unidad):
Columna Condición
Versión 0.8 Estrictamente privado y confidencial Página 88 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
Ubicación Sala / Almacén. Automático (se agrega un registro por unidad).
El sistema deberá asignar “Sala” para los ítems 1 a QS ubicados en
sala, o “Almacén” para los ítems QS+1 a QT ubicados en almacén.
Donde:
QS = Cantidad de productos en sala
QT = Cantidad total de productos
(QA = Cantidad total de productos en almacén = QT – QS)
Número Número de ítem (entero), de 1 hasta QT. Automático.
Lote Número de lote de la unidad. Obligatorio.
Alfanumérico de hasta 20 caracteres.
Por defecto: Copia del número de lote del último registro de
vencimientos del inventario anterior.
Fecha de Fecha de vencimiento de la unidad (DD/MM/AAAA). Obligatorio.
vencimiento Dato tipo fecha.
Por defecto: La fecha de vencimiento del último registro de
vencimientos del inventario anterior.
Días restantes Dato calculado, número entero:
Días restantes = Fecha de vencimiento – Fecha de sesión
Fecha corta Indicador calculado (Si / No):
Si Días restantes <= Días para fecha corta, entonces Fecha corta = Si
(pintar el indicador de rojo)
Si Días restantes > Días para fecha corta, entonces Fecha corta = No
(pintar el indicador de verde)
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.3.3 Recepción de productos del proveedor
Definición
Transacción para registrar la recepción de productos en un PDV abierto, entregados por su
proveedor (externo al PDV).
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta de reposiciones asignada para el día de
sesión:
Versión 0.8 Estrictamente privado y confidencial Página 89 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Si tiene un PDV abierto, el registro de inventario corresponderá a ese PDV; avanza
al paso 2.
• Si no tiene un PDV abierto, no se permite el registro inventario; se debe dar un
mensaje que indique que debe registrar el ingreso al PDV antes de registrar su
inventario. Todos los botones se deshabilitan excepto “Salir”.
2. Registro de productos recibidos
Para registrar productos recibidos, el sistema debe mostrar en pantalla los datos del
PDV y listar automáticamente todos los productos que tenga asignados (en la
planificación):
Datos del PDV:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV (de la planificación, previamente abierto)
Nombre Nombre del PDV
Productos (tabla, una fila por producto):
Columna Condición
Ubicación Por defecto “Almacén”. Automático (toda recepción de productos se
asignará automáticamente al almacén del PDV).
SKU Código del producto. Lectura.
Se deben incluir en la lista todos los SKU que fueron asignados al PDV
(asignación activa en la planificación).
Nombre Nombre del producto. Lectura.
Cantidad Cantidad recibida del producto. Obligatorio.
Valor por defecto: 0
Control: Número entero igual o mayor a 0.
El usuario ingresará la cantidad del producto que haya recibido para el
PDV, en UM stock.
Vencimientos Botón para registro de fechas de vencimiento del stock recibido (paso
3).
UM stock Unidad de medida “UM stock” del producto (de su catálogo). Lectura.
Observaciones Campo abierto, opcional. Texto largo.
El usuario ingresará una nota al producto, si lo considera necesario.
Todas las columnas deben permitir filtrar los registros por sus valores.
El botón “Vencimientos” se usará para registrar el lote y fecha de vencimiento de cada
unidad de cada producto recibido. Cuando se presione este botón, el sistema debe
avanzar al paso 3.
En esta función se requieren las siguientes opciones:
Versión 0.8 Estrictamente privado y confidencial Página 90 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• “Recibir” para guardar todos los datos ingresados; no podrán editarse, por lo que
debe dar un mensaje de advertencia al usuario (Confirmar / Cancelar); retorna a la
pantalla principal del sistema.
• “Salir”, retorna a la pantalla principal del sistema; no guarda los datos ingresados.
3. Registro de vencimientos
El sistema agregar registros en la tabla de vencimientos, ubicada debajo de la tabla de
productos, incluyendo automáticamente tantos registros como cantidad total de ítems se
haya ingresado; requiere los siguientes datos:
Datos del SKU:
SKU Código del SKU
Nombre Nombre del SKU
Vencimientos (tabla, una fila por unidad):
Columna Condición
Número Número de ítem (entero), de 1 hasta Q. Automático.
Fecha de ingreso Fecha de ingreso del artículo al almacén. Automático: fecha de sesión.
Lote Número de lote de la unidad. Obligatorio.
Alfanumérico de hasta 20 caracteres.
Operativamente, es probable que todas las unidades de un mismo
producto recibido sean del mismo lote. Por tanto, cuando el usuario
ingrese el número de lote a la primera unidad (primera fila de la lista),
ese número debe copiarse a todas las unidades siguientes de la lista
(todas las filas). Se permite su edición en todas las filas.
Fecha de Fecha de vencimiento de la unidad (DD/MM/AAAA). Obligatorio.
vencimiento Dato tipo fecha.
De la misma forma, cuando el usuario ingrese la fecha de vencimiento
a la primera unidad (primera fila de la lista), ese número debe copiarse
a todas las unidades siguientes de la lista (todas las filas). Se permite
su edición en todas las filas.
Días restantes Dato calculado, número entero:
Días restantes = Fecha de vencimiento – Fecha de sesión
Fecha corta Indicador calculado (Si / No):
Si Días restantes <= Días para fecha corta, entonces Fecha corta = Si
(pintar el indicador de rojo)
Si Días restantes > Días para fecha corta, entonces Fecha corta = No
(pintar el indicador de verde)
Notas al proceso
• Sugerencia: Realizar la recepción de productos antes del inventario, de modo que el
inventario incluya los productos recibidos.
Versión 0.8 Estrictamente privado y confidencial Página 91 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Sugerencia: Si se realiza un inventario antes de la recepción, pero se espera una
recepción, no “Cerrar el inventario” hasta después de la recepción, de modo que sea
posible editar las cantidades del inventario.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.4 Actividades complementarias
7.3.4.1 Registrar bandeo
Definición
Transacción para registrar los bandeos que se realizan en cada PDV abierto.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta que tiene asignada para el día de
sesión:
• Si se cumple la condición, avanza al paso 2 para el PDV.
• Si no tiene un PDV abierto, no se permite el registro de bandeo; se debe dar un
mensaje que indique el incidente encontrado (debe registrar el ingreso al PDV.
Todos los botones se deshabilitan excepto “Salir”.
2. Para el PDV abierto:
• Si no se recibieron los productos del bandeo:
“Recibir” habilitado;
“Devolver” y “Fotografías” inhabilitado.
Continua el paso 2.
• Si ya se recibieron los productos:
“Recibir” inhabilitado;
“Devolver” y “Fotografías” habilitado.
Mostrar datos en pantalla y seguir con el paso 3.
El sistema debe mostrar los datos de los bandeos que tiene planificados para el PDV y
permitir registrar las cantidades de productos recibidos:
Encabezado:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV abierto (de la planificación)
Nombre Nombre del PDV
Versión 0.8 Estrictamente privado y confidencial Página 92 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Listado de bandeos (pueden ser varios) y sus productos (detalle):
Columna Condición
Bandeo Código del bandeo, tomado de la planificación del PDV.
Lectura. Incluir todos los bandeos planificados.
Nombre Nombre del bandeo, tomado de la planificación del PDV.
Lectura.
Q bandeo Cantidad planificada de bandeos para el PDV.
Lectura.
Productos del bandeo (N asignados a cada bandeo)
SKU Código del producto que forma parte del bandeo.
Automático (incluir todos los planificados), lectura.
Nombre Nombre del producto.
Lectura.
Q plan Cantidad del producto incluida en el bandeo, según la planificación.
Lectura.
Q recibida Cantidad recibida del producto.
Número entero igual o mayor a cero. Obligatorio.
Por defecto: Q recibida = Q bandeo * Q plan
UM Unidad de medida del producto que se usa en el bandeo, tomada de la
planificación. Lectura.
En este punto se requieren las siguientes opciones:
• “Recibir” guarda las cantidades de los productos recibidos para el bandeo.
Esta opción debe:
o Guardar las cantidades ingresadas, las cuales ya no se podrán editar;
o Inhabilitar “Recibir”;
o Mostrar las columnas de datos “Q utilizada” y “Q devuelta”;
o Habilitar “Devolver” y “Fotografías”.
• “Devolver” los productos no utilizados; habilitado sólo cuando ya se marcó
“Recibir”; paso 3;
• “Fotografías” del bandeo realizado; habilitado sólo cuando ya se marcó “Recibir”;
paso 4;
• “Salir”, retorna a la pantalla principal del sistema sin guardar los datos que se
hayan ingresado.
3. Con los productos recibidos, el impulsador armará los bandeos (actividad externa al
sistema). Una vez armados, el usuario deberá “Devolver” los productos sobrantes, lo
cual se registra en el sistema.
La devolución se registra en la misma pantalla del paso 2:
Columna Condición
Bandeo Código del bandeo, tomado de la planificación del PDV.
Lectura. Incluir todos los bandeos planificados.
Nombre Nombre del bandeo, tomado de la planificación del PDV.
Lectura.
Q bandeo Cantidad planificada de bandeos para el PDV.
Lectura.
Versión 0.8 Estrictamente privado y confidencial Página 93 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
Productos del bandeo (N asignados a cada bandeo)
SKU Código del producto que forma parte del bandeo.
Lectura.
Nombre Nombre del producto.
Lectura.
Q plan Cantidad del producto incluida en el bandeo, según la planificación.
Lectura.
Q recibida Cantidad recibida del producto, previamente registrada.
Lectura.
Q utilizada Cantidad utilizada del producto.
Número entero. Obligatorio.
Por defecto: Q utilizada = Q recibida
Control: Q utilizada <= Q recibida
El usuario puede modificar el valor de Q utilizada antes de guardar sus
datos.
Q devuelta Cantidad devuelta del producto.
Número entero. Obligatorio.
Por defecto: Q devuelta = Q recibida - Q utilizada
Control: Q devuelta <= Q recibida
El usuario puede modificar este valor antes de guardar; si lo modifica,
es obligatorio que ingrese una observación al registro.
UM Unidad de medida del producto que se usa en el bandeo, tomada de la
planificación. Lectura.
Observación Texto mediano. Observación al registro de un producto.
Opcional / Obligatorio si se modificó la Q devuelta calculada por el
sistema.
Se tienen habilitadas las opciones:
• “Devolver” la cual debe:
o Guardar los datos ingresados que ya no se podrán editar;
o Avanzar a la pantalla de carga “Fotografías”; paso 4;
o Dar un mensaje al usuario solicitando la carga de al menos 1 fotografía del
bandeo.
• “Salir” retorna a la pantalla principal del sistema sin guardar los datos que se hayan
ingresado. Debe validar que se haya cargado al menos 1 fotografía del bandeo.
4. El usuario deberá cargar al menos una fotografía del bandeo realizado. Para esto, al
“Recibir” los productos, se habilita la opción “Fotografías”.
Esta opción permite cargar N archivos de imágenes correspondientes a su bandeo, 1
obligatorio. La carga se realiza según el estándar del sistema.
Las imágenes cargadas se deben poder visualizar en pantalla.
La opción que se habilita en este punto es:
• “Volver” que retorna a la pantalla del paso 3. Debe validar que se haya cargado al
menos 1 fotografía del bandeo.
Versión 0.8 Estrictamente privado y confidencial Página 94 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.4.2 Registrar punto promocional
Definición
Transacción para registrar la instalación de un punto de promoción de productos que se
realiza en un PDV abierto.
Un “punto promocional” puede ser una mesa, pequeño quiosco, estand u otro similar que se
instala para realizar la promoción y oferta especial de los productos del cliente.
Ocasionalmente se entregan productos promocionales y/o productos bandeados a los
clientes finales.
Funcionalidades requeridas
1. Al inicio de esta transacción el sistema debe verificar si el usuario de sesión tiene un
PDV abierto (registró ingreso al PDV), en la ruta de impulsos asignada para el día de
sesión:
• Si se cumple la condición, avanza al paso 2 para el PDV.
• Si no tiene un PDV abierto, no se permite el registro de punto de promoción; se
debe dar un mensaje que indique el incidente encontrado (debe registrar el ingreso
al PDV. Todos los botones se deshabilitan excepto “Salir”.
2. Para el PDV abierto, el sistema debe habilitar el registro de datos y fotografías del punto
promocional.
Encabezado:
Compañía cliente La planificada para el usuario de sesión
PDV Código del PDV abierto (de la planificación)
Nombre Nombre del PDV
Datos del punto de promoción (detalle):
Columna Condición
Fecha Fecha de instalación del punto promocional.
Fecha de sesión, lectura.
Hora apertura Hora de inicio de atención del punto.
Obligatorio.
Hora de cierre Hora de fin de atención del punto.
Obligatorio.
Versión 0.8 Estrictamente privado y confidencial Página 95 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Columna Condición
Descripción Texto inextenso para que el usuario (responsable del punto) ingrese la
descripción del punto promocional, materiales utilizados, y toda
observación adicional que considere necesaria.
Obligatorio.
Fotografías (N)
Archivo Carga de N archivos de imagen (fotografías) correspondientes al punto
promocional.
El mínimo de 1 fotografía es obligatorio.
En este punto se requieren las siguientes opciones:
• “Guardar”, guarda los datos que hayan sido ingresados; la transacción se mantiene
en la misma pantalla;
• “Salir”, retorna a la pantalla principal del sistema.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.4.3 Registrar información de la competencia
Definición
Transacción para registrar información de la competencia observada en un PDV.
La información a registrar puede incluir productos y precios, bandeos y/o puntos
promocionales. Se denomina “Punto de Competencia” (PC).
Funcionalidades requeridas
1. Un usuario puede requerir registrar información de la competencia en cualquier PDV
donde se encuentre. El sistema debe habilitar el registro de los datos y fotografías que
se detallan a continuación.
Encabezado:
Compañía Compañía de sesión (automático, lectura).
Fecha y hora Fecha y hora de sesión (automático, lectura).
PDV Código del PDV donde se encuentra el usuario, si está en uno abierto
(automático, lectura).
Nombre Nombre del PDV (automático, lectura)
Versión 0.8 Estrictamente privado y confidencial Página 96 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Ubicación del PC El sistema debe capturar la ubicación geográfica del usuario
(automático), que se usará como ubicación del PC.
Descripción del Texto largo. Opcional si hay un PDV abierto; si no lo hay es obligatorio.
lugar Dirección. Espacio para que el usuario describa el PC donde se
encuentra.
Datos de la competencia (N registros, detalle):
Columna Condición
Número Número de registro (1 en adelante), automático.
Tipo Valor fijo, obligatorio. Puede ser:
• Producto,
• Bandeo,
• Actividad promocional.
Descripción Texto largo, obligatorio.
Descripción del ítem.
Precio Número con 2 decimales. Opcional.
Fotografía Carga de 1 archivo de imagen (fotografía) correspondientes al PC.
Opcional.
En este punto se requieren las siguientes opciones:
• “Guardar”, guarda los datos que hayan sido ingresados; retorna a la pantalla
principal del sistema;
• “Salir”, retorna a la pantalla principal del sistema.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
7.3.5 Salir de PDV
Definición
Transacción para marcar la salida de un PDV, dentro de la ruta de reposiciones del día
laboral asignada al usuario de sesión.
Seguridad especial
En esta transacción el sistema presenta únicamente la ruta asignada al usuario de sesión (si
tiene una), para la fecha de sesión.
Versión 0.8 Estrictamente privado y confidencial Página 97 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Funcionalidades requeridas
1. Al ingresar a la transacción el sistema debe buscar la ruta de trabajo planificada para el
usuario. Se sugiere:
• Usuario de sesión -> Empleado de sesión (desde el catálogo de empleados)
• En la planificación de impulsos buscar:
Registro: Compañía de sesión + Fecha de sesión + Empleado de sesión (reponedor)
Obtener: Ruta de reposiciones.
Una vez encontrada la ruta, se requiere mostrarla en el mapa de pantalla, en azul. Los
PDV de la ruta se muestran en colores:
• PDV pendiente en rojo (no tiene registro de ingreso ni de salida);
• PDV abierto en amarillo (tiene registro de ingreso pero no de salida);
• PDV cerrado en verde (tiene registro de ingreso y de salida
Se requieren las siguientes opciones en pantalla:
• “Marcar salida”:
o Si no hay un PDV abierto inhabilitada;
o Si hay un PDV abierto habilitada – paso 2.
• “Salir”, que retorna a la pantalla inicial del sistema.
2. La opción “Marcar salida” debe:
• Obtener la ubicación geográfica (UG) del usuario.
• Calcular “DS = Distancia de Salida” en metros, entre la UG del usuario y la UG del
PDV.
• Si la “DS <= Distancia máxima de marca” para el PDV se acepta la “Salida de PDV”:
o Se registra la UG, fecha, hora y distancia de salida del PDV en el sistema.
o Se “cierra” el PDV para el usuario, por lo cual ya no se le permite ejecutar
transacciones de reposición en el PDV.
o Se muestra el PDV en el mapa, en color verde (PDV cerrado).
o Se muestran los datos de ingreso y de salida del PDV en pantalla.
o Se inhabilita la opción “Marcar salida”.
• Si la “DS > Distancia máxima de marca” para el PDV se rechaza la “Salida de PDV”:
o Mostrar mensaje al usuario que indica “No es posible marcar la salida del PDV
dado que se encuentra lejos del mismo”.
o No se realizan cambios en pantalla.
o Se permiten transacciones de Impulsos en el PDV para el usuario de sesión.
Características especiales
Esta transacción se utilizará en campo, por los usuarios que recorren físicamente los PDV en
ruta, utilizando dispositivos móviles. Por tanto, debe ser cuidadosamente responsiva para
adaptarse a dispositivos móviles.
Transacción candidata para desarrollo en aplicación móvil.
Versión 0.8 Estrictamente privado y confidencial Página 98 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.4 Monitor de Trade
7.4.1 Panel de control de Afiliaciones
Definición
Transacción para mostrar, en una pantalla, el estado y los indicadores más relevantes de los
impulsos que se realizan en campo.
Calcula los indicadores para diferentes cruces de variables y valores seleccionados por el
usuario. Incluye una vista de datos detallados (planilla) para el periodo de análisis.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En cuanto a los impulsos: En los resultados de cada búsqueda para la actualización de
estadísticas, se incluirán únicamente registros ingresados por empleados (usuarios)
pertenecientes al grupo de empleados asignado al usuario de sesión, para el objeto interno
“IMPULSO”.
Funcionalidades requeridas
1. Panel de control
La pantalla inicial del panel requiere de una barra de variables de análisis (ver 2) y de
un área de datos (ver 3) donde se desplieguen diversas estadísticas a ser calculadas
según dichas variables. Esquema ejemplo:
Versión 0.8 Estrictamente privado y confidencial Página 99 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
2. Las variables de análisis requeridas son:
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenecen los datos de impulsos a
incluir.
Por defecto: compañía de sesión.
La lista incluye las compañías asignadas al usuario
(seguridad).
Selección única.
Fecha de Obligatorio Rango de fechas desde – hasta del registro de impulsos a
registro incluir.
Desde / Hasta • Por defecto: “Fecha desde” = Fecha de sesión.
• Se puede buscar sólo por “Fecha desde” (un día).
• “Fecha hasta” debe ser mayor o igual a “Fecha desde”.
País Opcional País para buscar ciudades y PDV.
Por defecto el país de la compañía seleccionada.
Selección única.
Regional Opcional Regional para buscar ciudades y PDV, del país
seleccionado.
Selección única.
Ciudad Opcional Ciudad para buscar PDV, del país / regional seleccionados.
Selección única.
Ruta Opcional Ruta(s) para incluir PDV, de la compañía y ciudad
seleccionada.
Se permite selección múltiple.
Versión 0.8 Estrictamente privado y confidencial Página 100 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Tipo de PDV Opcional Tipos de PDV, de la compañía seleccionada.
Selección única.
Canal Opcional Canales (de PDV), de la compañía seleccionada.
Selección única.
PDV Opcional PDV de la compañía seleccionada, y de las otras variables si
se marcaron valores.
Se permite selección múltiple.
Categoría 1 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Categoría 2 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Categoría 3 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Categoría 4 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Producto Opcional Productos cuyos datos se deben incluir, de la compañía
seleccionada.
Se permite selección múltiple.
Equipo de Opcional Equipo de trabajo cuyos empleados registraron los datos a
campo incluir (del objeto interno “IMPULSO”); para la compañía
seleccionada.
Se permite selección múltiple.
Impulsadora Opcional Impulsadora (empleado) que registró los datos a incluir, de
la compañía / equipo de campo seleccionados.
Se permite selección múltiple.
Inicialmente, las variables que no tienen valores por defecto se presentan vacías (sin
valor marcado), por lo que el área de datos no muestra estadísticas calculadas.
Para el cálculo de las estadísticas, si el usuario no marca valores en las variables
opcionales significa “todos los valores”.
Una vez marcado al menos el valor para “Compañía”, se deben calcular las estadísticas
y actualizar el área de datos.
Cada cambio en la marca de valores de una variable debe recalcular las estadísticas y
actualizar el área de datos.
3. Las Estadísticas requeridas para el área de datos, que se deben calcular en función a
las variables de análisis seleccionadas; las estadísticas se describen a continuación.
Versión 0.8 Estrictamente privado y confidencial Página 101 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Cuadro de “Indicadores generales”:
Indicador Descripción
PDV impulsados Cantidad de PDV impulsados (visitados) en el periodo
(fechas desde / hasta)
X visitas a un mismo PDV cuentan como 1 (suma por PDV).
Impulsos realizados Cantidad impulsos realizados en el periodo (fechas desde /
hasta)
Impulso = Visita (ingreso – salida) a 1 PVD.
Impulsos por PDV Impulsos / PDV impulsado
Productos promocionados Suma de productos incluidos en los impulsos realizados
(productos asignados a los PDV, consolidados)
Productos por impulso Productos promocionados / Impulsos
Tiempo promedio por PDV Tiempo por PDV = Hora de salida del PDV – Hora de
ingreso al PDV (en horas y minutos)
Luego, se promedian los tiempos de todos los PDV
seleccionados.
Cuadro de “Indicadores de ruta”:
Se calculan cuando hay al menos una ruta seleccionada
Indicador Descripción
PDV por ruta Promedio de PDV asignados a cada ruta
Tiempo promedio por ruta Tiempo por ruta = Hora de salida del último PDV de la ruta
– Hora de ingreso al primer PDV de la ruta (en horas y
minutos)
Luego, se promedian los tiempos de todas las rutas
seleccionadas.
Tiempo promedio por PDV Tiempo por PDV = Hora de salida del PDV – Hora de
ingreso al PDV (en horas y minutos)
Luego, se promedian los tiempos de todos los PDV
seleccionados.
Tiempo promedio entre PDVs Tiempo entre PDVs (del N-1 al N) = Hora de ingreso al
PDV(N) – Hora de salida del PDV(N-1)
Se puede calcular sólo para rutas que tienen al menos 2
PDV.
Si la ruta tiene N PDV asignados, se calcula N-1 tiempos
entre PDV.
Luego, se calcula el promedio de los N-1 tiempos
calculados por ruta, y los tiempos promedio entre las rutas
seleccionadas.
Versión 0.8 Estrictamente privado y confidencial Página 102 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráficos (un cuadro para cada gráfico):
Gráfico Descripción
PDV por ciudad Q PDV por ciudad
(porcentual)
Tipo de gráfico: Pie
a. E
l
a
v
a
n
c
e
Gráfico Descripción
Impulsos por ciudad Q impulsos realizados por ciudad
(porcentual)
Tipo de gráfico: Pie
b. E
l
a
v
a
n
c
e
Versión 0.8 Estrictamente privado y confidencial Página 103 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

| Gráfico  |     |     |     | Descripción  |
| -------- | --- | --- | --- | ------------ |
Impulsos por día  Q de impulsos realizados por día (en el tiempo)
|                                 |     |     |     |     |
| ------------------------------- | --- | --- | --- | --- |
| Tipo de gráfico: Line (custom)  |     |     |     |     |

|     |     |     |     | c.  E |
| --- | --- | --- | --- | ----- |
l

a
v
a
n
c
e

Cuadro de “Datos de inventario”:
Tabla de datos a mostrarse en un cuadro del panel, sumando el inventario del día al
momento de análisis, existente en todos los PDV que cumplan con las variables de
selección; incluirlas columnas a continuación.

| Fecha  | Día (de análisis)  |         |       |     |
| ------ | ------------------ | ------- | ----- | --- |
| SKU    |                    | Nombre  | Q en  | UM  |
stock
|     |     |     |     |     |
| --- | --- | --- | --- | --- |
|     |     |     |     |     |

Donde:
| Q en stock  | ->  |     |     |     |
| ----------- | --- | --- | --- | --- |
Para un PDV, en un día:     Q stock = Q inicial(día) – Q ventas(día)
Para todos los PDV seleccionados:   Q stock = Suma(Q stock) de todos los PDV

UM    ->  Unidad de medida de venta del producto en el PDV.

Cuadro de “Datos de ventas”:
Tabla de datos a mostrarse en un cuadro del panel, sumando las ventas del periodo, de
todos  los  PDV  que  cumplan  con  las  variables  de  selección;  incluirlas  columnas  a
continuación.

| SKU            |     | Nombre  | Q venta  | UM  |
| -------------- | --- | ------- | -------- | --- |
|                |     |         |          |     |
| Total por SKU  |     |         |          |     |
|                |     |         |          |     |
|                |     |         |          |     |
| Total por SKU  |     |         |          |     |

Versión 0.8  Estrictamente privado y confidencial  Página 104 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Donde:
Q venta -> Suma de Q vendida en todos los PDV seleccionados
UM -> Unidad de medida de venta del producto en el PDV.
Gráficos de “Ventas”:
Gráfico Descripción
Ventas por día Q ventas realizadas por día, por SKU
Tipo de gráfico: Line (custom)
Una línea separada por SKU
d. E
l
a
v
a
n
c
e
Gráfico Descripción
Ventas por ciudad Q ventas por ciudad, por SKU
(porcentual)
Tipo de gráfico: Pie
Sólo se puede mostrar el gráfico
de 1 SKU a la vez. Se tendría que
poner una lista de SKU en el
cuadro (incluye los seleccionados),
para selección única.
e.
f. E
l
a
v
a
n
c
e
Versión 0.8 Estrictamente privado y confidencial Página 105 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
4. Las opciones requeridas en esta pantalla son:
• “Planilla” de datos, como se detalla en el punto 5;
• “Salir”, que retorna a la pantalla inicial del sistema.
5. La opción “Planilla” debe mostrar en pantalla, en formato de tabla, todos los registros
que respaldan los datos calculados y mostrados en el panel. Este archivo debe incluir las
siguientes columnas:
Dato Observación
Compañía
Fecha y hora de ingreso Fecha y hora de ingreso al PDV
Fecha y hora de salida Fecha y hora de salida del PDV
País Nombre del país
Regional Nombre de la regional
Ciudad Nombre de la ciudad
Ruta Código de la ruta
Nombre de la ruta
Tipo de PDV Nombre del tipo de PDV
Canal Nombre del canal
PDV Código del PDV
Nombre del PDV
Categoría 1 (nombre) Nombre del valor de Categoría 1 del producto
Categoría 2 (nombre) Nombre del valor de Categoría 2 del producto
Categoría 3 (nombre) Nombre del valor de Categoría 3 del producto
Categoría 4 (nombre) Nombre del valor de Categoría 4 del producto
SKU Código del producto
Nombre del producto
Q inicial Q del inventario de inicio del producto
Q vendida Q total vendida del producto en la fecha
Q final Q del inventario de fin del producto
UM venta Unidad de medida de venta del producto
Equipo de campo Código del equipo de campo
Nombre del equipo de campo
Impulsadora Nombre completo de la impulsadora
Usuario Usuario que guardó el registro
Las opciones requeridas en esta pantalla son:
• “Exportar”, que genera un archivo plano con los datos que se muestran en
pantalla;
• “Volver”, que retorna al panel de control;
• “Salir”, que retorna a la pantalla inicial del sistema.
Inventario en línea
Ventas en línea
Tiempos
• En PDV
• Entre PDV
Versión 0.8 Estrictamente privado y confidencial Página 106 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.4.2 Panel de control de Impulsos
Versión 0.8 Estrictamente privado y confidencial Página 107 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.4.3 Panel de control de Reposiciones
Definición
Transacción para mostrar, en una pantalla, el estado y los indicadores más relevantes de las
reposiciones que se realizan en campo.
Calcula los indicadores para diferentes cruces de variables y valores seleccionados por el
usuario. Incluye una vista de datos detallados (planilla) para el periodo de análisis.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En cuanto a las reposiciones: En los resultados de cada búsqueda para la actualización de
estadísticas, se incluirán únicamente registros ingresados por empleados (usuarios)
pertenecientes al grupo de empleados asignado al usuario de sesión, para el objeto interno
“REPOSICION”.
Funcionalidades requeridas
1. Panel de control
La pantalla inicial del panel requiere de una barra de variables de análisis y de un
área de datos donde se desplieguen diversas estadísticas a ser calculadas según dichas
variables.
Esquema ejemplo:
Versión 0.8 Estrictamente privado y confidencial Página 108 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Las variables de análisis requeridas son:
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenecen los datos de reposiciones a
incluir.
Por defecto: compañía de sesión.
La lista incluye las compañías asignadas al usuario
(seguridad).
Selección única.
Compañía Opcional Compañía cliente para la cual se realizaron las
cliente reposiciones. Es la compañía dueña de los PDV visitados.
Fecha de Obligatorio Rango de fechas desde – hasta del registro de reposiciones
registro a incluir.
Desde / Hasta • Por defecto: “Fecha desde” = Fecha de sesión.
• Se puede buscar sólo por “Fecha desde” (un día).
• “Fecha hasta” debe ser mayor o igual a “Fecha desde”.
País Opcional País para buscar ciudades y PDV.
Por defecto el país de la compañía seleccionada.
Selección única.
Regional Opcional Regional para buscar ciudades y PDV, del país
seleccionado.
Selección única.
Ciudad Opcional Ciudad para buscar PDV, del país / regional seleccionados.
Selección única.
Ruta Opcional Ruta(s) para incluir PDV, de la compañía y ciudad
seleccionada.
Se permite selección múltiple (del objeto interno
“REPOSICION”).
Tipo de PDV Opcional Tipos de PDV. Si se seleccionó compañía cliente, incluir sólo
datos de esa compañía.
Selección única.
Canal Opcional Canales (de PDV). Si se seleccionó compañía cliente, incluir
sólo datos de esa compañía.
Selección única.
PDV Opcional PDV. Si se seleccionó compañía cliente, incluir sólo datos
de esa compañía. Filtrar también por valores de las otras
variables que se hayan seleccionado.
Se permite selección múltiple.
Categoría 1 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Versión 0.8 Estrictamente privado y confidencial Página 109 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Categoría 2 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Categoría 3 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Categoría 4 Opcional Valores de la categoría 1 para selección de productos.
(nombre) Se permite selección múltiple.
Producto Opcional Productos cuyos datos se deben incluir, de la compañía
seleccionada.
Se permite selección múltiple.
Equipo de Opcional Equipo de trabajo cuyos empleados registraron los datos a
campo incluir (del objeto interno “REPOSICION”); para la
compañía seleccionada.
Se permite selección múltiple.
Empleado Opcional Empleado que registró los datos a incluir, de la compañía /
equipo de campo seleccionados.
Se permite selección múltiple.
Inicialmente, las variables que no tienen valores por defecto se presentan vacías (sin
valor marcado), por lo que el área de datos no muestra estadísticas calculadas.
Para el cálculo de las estadísticas, si el usuario no marca valores en las variables
opcionales significa “todos los valores”.
Una vez marcado al menos el valor para “Compañía”, se deben calcular las estadísticas
y actualizar el área de datos.
Cada cambio en la marca de valores de una variable debe recalcular las estadísticas y
actualizar el área de datos.
• Las Estadísticas requeridas para el área de datos, que se deben calcular en función a
las variables de análisis seleccionadas; las estadísticas se describen a continuación.
Cuadro de “Indicadores generales”:
Indicador Descripción
PDV Cantidad de PDV visitados en el periodo (fechas desde /
hasta)
X visitas a un mismo PDV cuentan como 1 (suma por PDV).
Reposiciones realizadas Cantidad de reposiciones realizados en el periodo (fechas
desde / hasta)
Reposición = Visita (ingreso – salida) a 1 PVD.
Reposiciones por PDV Reposiciones / PDV visitados
Versión 0.8 Estrictamente privado y confidencial Página 110 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Indicador Descripción
Productos gestionados Suma de productos gestionados (productos asignados a los
PDV, consolidados)
Productos por reposición Productos gestionados / Reposiciones realizadas
Tiempo promedio por PDV Tiempo por PDV = Hora de salida del PDV – Hora de
ingreso al PDV (en horas y minutos)
Luego, se promedian los tiempos de todos los PDV
seleccionados.
Cuadro de “Indicadores de ruta”:
Se calculan cuando hay al menos una ruta seleccionada
Indicador Descripción
PDV por ruta Promedio de PDV asignados a cada ruta seleccionada
Tiempo promedio por ruta Tiempo por ruta = Hora de salida del último PDV de la ruta
– Hora de ingreso al primer PDV de la ruta (en horas y
minutos)
Luego, se promedian los tiempos de todas las rutas
seleccionadas.
Tiempo promedio por PDV Tiempo por PDV = Hora de salida del PDV – Hora de
ingreso al PDV (en horas y minutos)
Luego, se promedian los tiempos de todos los PDV
seleccionados.
Tiempo promedio entre PDVs Tiempo entre PDVs (del N-1 al N) = Hora de ingreso al
PDV(N) – Hora de salida del PDV(N-1)
Se puede calcular sólo para rutas que tienen al menos 2
PDV.
Si la ruta tiene N PDV asignados, se calcula N-1 tiempos
entre PDV.
Luego, se calcula el promedio de los N-1 tiempos
calculados por ruta, y los tiempos promedio entre las rutas
seleccionadas.
Gráficos (un cuadro para cada gráfico):
Gráfico Descripción
PDV por ciudad Q PDV por ciudad
(porcentual)
Versión 0.8 Estrictamente privado y confidencial Página 111 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráfico Descripción
Tipo de gráfico: Pie
g. E
l
a
v
a
n
c
e
Gráfico Descripción
Reposiciones por ciudad Q reposiciones realizados por ciudad
(porcentual)
Versión 0.8 Estrictamente privado y confidencial Página 112 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráfico Descripción
Tipo de gráfico: Pie
h. E
l
a
v
a
n
c
e
Gráfico Descripción
Reposiciones por día Q de reposiciones realizados por día (en el tiempo)
Tipo de gráfico: Line (custom)
i. E
l
a
v
a
n
c
e
Cuadro de “Datos de inventario”:
Versión 0.8 Estrictamente privado y confidencial Página 113 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

Tabla de datos a mostrarse en un cuadro del panel, sumando el inventario del día al
momento de análisis, existente en todos los PDV que cumplan con las variables de
selección; incluirlas columnas a continuación.

| SKU  | Nombre  | Q sala  Q almacén  | Q total  Q min  | UM  | Quiebre  |
| ---- | ------- | ------------------ | --------------- | --- | -------- |
|      |         |                    |                 |     |          |
|      |         |                    |                 |     |          |

Donde:
Q sala  ->  Suma de cantidad del producto en sala, de los PDV seleccionados
Q almacén->  Suma de cantidad del producto en almacén, de los PDV seleccionados
| Q total  ->  | Q sala + Q almacén  |     |     |     |     |
| ------------ | ------------------- | --- | --- | --- | --- |
Q min   ->  Suma de Q mínima del producto en stock en cada PVD, de los PDV
seleccionados
| UM  ->  | Unidad de medida de stock de cada producto.  |     |     |     |     |
| ------- | -------------------------------------------- | --- | --- | --- | --- |
Quiebre ->  Indicador: Si Qtotal >= Qmin ent. SI; Si Qtotal < Qmin ent. NO
Quiebre de stock SI – rojo / NO – verde

AQUI
Cuadro de “Datos de vencimientos”:
Tabla de datos a mostrarse en un cuadro del panel, con el detalle de unidades del
inventario del día al momento de análisis, que se encuentra en todos los PDV que
cumplan con las variables de selección; incluirlas columnas a continuación.

Unidad  SKU  Nombre  Ubicación  Lote  Vencimiento  Días  Fecha
|                         |     |     |     | restantes  | corta  |
| ----------------------- | --- | --- | --- | ---------- | ------ |
|                         |     |     |     |            |        |
| Total unidades por SKU  |     |     |     |            |        |
|                         |     |     |     |            |        |
|                         |     |     |     |            |        |
| Total unidades por SKU  |     |     |     |            |        |

Q Fecha corta / Q stock (%)

Quiebres de stock por producto por PDV, en el tiempo

|     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- |
Versión 0.8  Estrictamente privado y confidencial  Página 114 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Gráficos de “Inventarios”:
Gráfico Descripción
Inventario por ciudad Q total por ciudad, por SKU
(porcentual)
Tipo de gráfico: Pie
Sólo se puede mostrar el gráfico
de 1 SKU a la vez. Se tendría que
poner una lista de SKU en el
cuadro (incluye los seleccionados),
para selección única.
j.
k. E
l
a
v
a
n
c
e
Gráfico Descripción
Inventario por día Q total por día (en el tiempo)
Tipo de gráfico: Line (custom)
Una línea en el gráfico por SKU.
Siempre medido en UM stock.
a. E
l
a
v
a
n
c
e
Q Fecha corta / Q stock %
Versión 0.8 Estrictamente privado y confidencial Página 115 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Las opciones requeridas en esta pantalla son:
• “Planilla” de datos, como se detalla en el punto 5;
• “Salir”, que retorna a la pantalla inicial del sistema.
• La opción “Planilla” debe mostrar en pantalla, en formato de tabla, todos los registros
que respaldan los datos calculados y mostrados en el panel. Este archivo debe incluir las
siguientes columnas:
Dato Observación
Compañía
Fecha y hora de ingreso Fecha y hora de ingreso al PDV
Fecha y hora de salida Fecha y hora de salida del PDV
País Nombre del país
Regional Nombre de la regional
Ciudad Nombre de la ciudad
Ruta Código de la ruta
Nombre de la ruta
Tipo de PDV Nombre del tipo de PDV
Canal Nombre del canal
PDV Código del PDV
Nombre del PDV
Categoría 1 (nombre) Nombre del valor de Categoría 1 del producto
Categoría 2 (nombre) Nombre del valor de Categoría 2 del producto
Categoría 3 (nombre) Nombre del valor de Categoría 3 del producto
Categoría 4 (nombre) Nombre del valor de Categoría 4 del producto
SKU Código del producto
Nombre del producto
Q inicial Q del inventario de inicio del producto
Q vendida Q total vendida del producto en la fecha
Q final Q del inventario de fin del producto
UM venta Unidad de medida de venta del producto
Equipo de campo Código del equipo de campo
Nombre del equipo de campo
Impulsadora Nombre completo de la impulsadora
Usuario Usuario que guardó el registro
Las opciones requeridas en esta pantalla son:
• “Exportar”, que genera un archivo plano con los datos que se muestran en
pantalla;
• “Volver”, que retorna al panel de control;
• “Salir”, que retorna a la pantalla inicial del sistema.
Inventario en línea
Ventas en línea
Tiempos
• En PDV
• Entre PDV
Versión 0.8 Estrictamente privado y confidencial Página 116 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.4.4 Seguimiento de rutas de Trade
Definición
Transacción para mostrar, en un mapa en pantalla, la ejecución de una ruta en campo, sea
de impulsos o de reposiciones.
Seguridad especial
En cuanto a las compañías:
• Si el usuario es interno, puede seleccionar compañías que tenga asignadas en el
parámetro “Asignación de compañías a usuarios internos”.
• Si el usuario es externo sólo puede seleccionar afiliaciones de su propia compañía.
En los resultados de cada búsqueda, para la actualización de estadísticas, se incluirán
únicamente registros ingresados por empleados (usuarios) pertenecientes a grupos de
empleados asignados al usuario de sesión, para grupos de objeto interno “IMPULSO” o
“REPOSICION”.
Funcionalidades requeridas
1. Mapa de seguimiento
La pantalla inicial de esta función requiere de una barra de variables de análisis (ver
2) y de un área de mapa (ver 3) donde se desplieguen las rutas seleccionadas en las
variables.
Versión 0.8 Estrictamente privado y confidencial Página 117 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
• Las variables de análisis requeridas son:
Dato Condición Descripción
Compañía Obligatorio Compañía a la que pertenece la ruta a revisar.
Por defecto debe estar seleccionada la compañía de sesión.
Otras compañías listadas según la seguridad.
Selección única.
País Opcional País para buscar ciudades.
Por defecto el país de la compañía seleccionada.
Selección única.
Ciudad Opcional Ciudad para buscar rutas, del país seleccionado.
Selección única.
Actividad Obligatorio Define el objeto interno para buscar rutas. Puede ser:
• Impulsos (IMPULSO), o
• Reposiciones (REPOSICION).
Por defecto: Impulsos.
Se permite seleccionar sólo un valor.
Ruta Obligatorio Ruta a monitorear, de la compañía y ciudad seleccionadas.
Se permite selección múltiple de rutas, pero todas del
“Objeto interno = Actividad” (campo anterior).
Versión 0.8 Estrictamente privado y confidencial Página 118 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
Dato Condición Descripción
Fecha Obligatorio Fecha para la cual se requiere revisar la ruta.
Por defecto es la fecha de sesión.
Equipo de Opcional Equipo de trabajo de “Tipo = Actividad” (campo anterior),
trabajo que podrá ser de tipo “IMPULSO” o “REPOSICION”, cuyos
datos se requieren mostrar en el mapa, para la compañía y
ruta seleccionadas.
Se permite selección múltiple.
Empleado Opcional Empleado cuyos datos se requieren mostrar en el mapa,
para la compañía, ruta y equipo seleccionados.
Se permite selección múltiple.
Inicialmente, las variables que no tienen valores por defecto se presentan vacías (sin
valor marcado), por lo que el mapa no muestra ninguna ruta.
Para las variables opcionales, si el usuario no marca valores significa “todos los valores”.
Una vez marcados valores para “Compañía” y “Ruta”, se debe mostrar la ruta
seleccionada en el mapa, como se detalla en el punto 3.
Cada cambio en la marca de valores de una variable debe actualizar la información en el
mapa.
• Cada vez que se actualice el mapa de seguimiento, este debe mostrar lo siguiente:
Mostrar las rutas seleccionadas, en diferentes colores (azul, verde, roja, etc.).
Sobre cada ruta, se requiere:
• Mostrar todos los PDV que la componen, con sus nombres;
• Diferenciar los pines de los PDV:
o PDV visitados (tienen entrada y salida en la fecha),
o PDV abierto (tiene entrada pero no salida la fecha; puede ser 1 por ruta),
o PDV por visitar (no tienen entrada ni salida en la fecha).
a) Si la ruta es de impulsos (Objeto interno = IMPULSO), mostrar inventarios de
impulso y ventas.
Un clic sobre un pin debe desplegar un cuadro emergente con la información del
PDV para la fecha, incluyendo todos los productos planificados para el PDV:
• Inventario, en una tabla como la que sigue:
SKU Nombre Q inicial Q ventas Q saldo UM
Versión 0.8 Estrictamente privado y confidencial Página 119 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales

Donde:
| Q inicial ->  | Inventario inicial en el PDV.               |     |     |     |
| ------------- | ------------------------------------------- | --- | --- | --- |
| Q ventas ->   | Suma de las ventas registradas al momento.  |     |     |     |
| Q saldo  ->   | Q inicial – Q venta                         |     |     |     |
UM    ->  Unidad de medida de venta del producto en el PDV.

•  Ventas, en una segunda tabla, como la que sigue, con totales por SKU:

| SKU            | Nombre  | Hora  | Q venta  | UM  |
| -------------- | ------- | ----- | -------- | --- |
|                |         |       |          |     |
| Total por SKU  |         |       |          |     |
|                |         |       |          |     |
|                |         |       |          |     |
| Total por SKU  |         |       |          |     |

Donde:
| Hora         | ->  Hora de la venta             |     |     |     |
| ------------ | -------------------------------- | --- | --- | --- |
| Q venta  ->  | Q vendida (1 registro de venta)  |     |     |     |
UM    ->  Unidad de medida de venta del producto en el PDV.

La suma de “Q venta” en esta tabla debe ser igual a “Q ventas” de la tabla
anterior para cada SKU.

b)  Si la ruta es de reposiciones (Objeto interno = REPOSICION), mostrar inventarios
de reposición.

Un clic sobre un pin debe desplegar un cuadro emergente con la información del
PDV para la fecha, incluyendo todos los productos planificados para el PDV:

•  Existencias, en una tabla como la que sigue:

| SKU  Nombre  | Q sala  | Q almacén  | Q total  Q min  | UM  Quiebre  |
| ------------ | ------- | ---------- | --------------- | ------------ |
|              |         |            |                 |              |
|              |         |            |                 |              |

Donde:
| Q sala  ->   | Cantidad del producto en sala                      |     |     |     |
| ------------ | -------------------------------------------------- | --- | --- | --- |
| Q almacén->  | Cantidad del producto en almacén                   |     |     |     |
| Q total  ->  | Q total del producto en existencia                 |     |     |     |
| Q min  ->    | Q mínima del producto en stock para el PVD         |     |     |     |
| UM  ->       | Unidad de medida de venta del producto en el PDV.  |     |     |     |
Quiebre  ->  Indicador: Quiebre de stock SI – rojo / NO – verde

•  Vencimientos, en una segunda tabla, como la que sigue, con totales por SKU:

Unidad  SKU  Nombre  Ubicación  Lote  Vencimiento  Días  Fecha
Versión 0.8  Estrictamente privado y confidencial  Página 120 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
restantes corta
Total unidades por SKU
Total unidades por SKU
Donde:
Ubicación -> Sala o Almacén
Lote -> Número de lote de la unidad
Vencimiento -> Fecha de vencimiento de la unidad
Días restantes -> Días restantes del producto antes del vencimiento
Fecha corta -> Indicador: Fecha corta SI – rojo / NO – verde
La suma de “Total unidades por SKU” en esta tabla debe ser igual a “Q total” de
la tabla anterior para cada SKU.
7.5 Reportes
Con códigos propios (SKU) / del cliente
7.5.1 Planificación
7.5.1.1 Agenda de campo
7.5.2 Impulsos
7.5.2.1 Reporte fotográfico de impulsos
7.5.2.2 Inventario
Fecha corta
Quiebre de stock
7.5.2.3 Reporte de ventas
Tabla dinámica en Excel por fecha, ciudad, impulsadora, producto, PDV, canal, otras
Versión 0.8 Estrictamente privado y confidencial Página 121 de 122

Great –Trade Marketing
Especificación de requerimientos funcionales
7.5.2.4 Reporte fotográfico de ventas
Pdf del impulso con fotos de ventas
El cliente cruza las fotos de facturas (que recibe en un drive) con el informe de ventas
7.5.3 Reposiciones
7.5.3.1 Reporte gráfico de reposiciones
7.5.3.2 Inventario por PDV
Vencimientos
7.5.3.3 Reporte de fecha corta
7.5.3.4 Reporte de quiebre de stock
7.5.4 Otros reportes
7.5.4.1 Tiempos por PDV
7.5.4.2 Reporte de bandeos
Gráfico
7.5.4.3 Reporte de puntos promocionales
Gráfico
Versión 0.8 Estrictamente privado y confidencial Página 122 de 122