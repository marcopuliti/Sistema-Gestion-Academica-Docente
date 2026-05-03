# Sistema de Gestión Académica Docente

Plataforma web para la gestión de solicitudes de protocolización de programas y de tribunales examinadores de la Facultad de Ciencias Físico Matemáticas y Naturales — Universidad Nacional de San Luis.

## Módulos

| Módulo | Descripción |
|--------|-------------|
| **Solicitudes** | Solicitud de protocolización de cursos (curriculares y optativos) y talleres: programa completo, equipo docente, carga horaria, correlativas y bibliografía |
| **Planes** | Carreras, planes de estudio, materias, tribunales examinadores y gestión del ciclo anual de confirmación/cambio de tribunales |
| **Trámites** | Base común: estados (Pendiente → En Revisión → Aprobado/Rechazado), revisión con comentarios, calendario académico |
| **Notificaciones** | Notificaciones internas para cambios de estado, nuevas solicitudes y ciclos de informe de tribunales |
| **Accounts** | Autenticación, registro con verificación por email, roles y gestión de usuarios |

---

## Roles

| Rol | Permisos |
|-----|----------|
| **Docente** | Crea y consulta sus propias solicitudes de protocolización. Descarga el documento completo (nota + programa) |
| **Director de Departamento** | Ve solicitudes de su departamento; asigna código de materia; visualiza y propone cambios en los tribunales examinadores de su departamento; genera y envía el informe anual de tribunales |
| **Administrador** | Acceso total: gestiona usuarios, revisa y aprueba solicitudes, administra todas las materias en plan, crea tribunales vacíos, aplica solicitudes de cambio de tribunal y solicita el informe anual |

---

## Stack

- **Backend:** Python 3.10+ / Django
- **Base de datos:** PostgreSQL
- **Frontend:** Bootstrap 5 + Bootstrap Icons
- **Documentos:** ReportLab (PDF), python-docx (DOCX)
- **Email:** SMTP via Gmail con App Password
- **Config:** python-decouple (`.env`)

---

## Instalación

### Requisitos

- Python 3.10+
- PostgreSQL

### Pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/marcopuliti/Sistema-Gestion-Academica-Docente.git
cd Sistema-Gestion-Academica-Docente

# 2. Entorno virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Dependencias
pip install -r requirements.txt

# 4. Variables de entorno
cp .env.example .env
# Editar .env con credenciales de base de datos y email

# 5. Migraciones
python manage.py migrate

# 6. Datos iniciales (carreras, planes, materias, calendario)
python manage.py loaddata datos.json

# 7. Superusuario administrador
python manage.py createsuperuser

# 8. Directores de departamento
python manage.py crear_directores_departamento

# 9. Servidor de desarrollo
python manage.py runserver
```

Abrir en `http://127.0.0.1:8000`

---

## Variables de entorno

Ver [.env.example](.env.example).

| Variable | Descripción |
|----------|-------------|
| `SECRET_KEY` | Clave secreta de Django |
| `DEBUG` | `True` en desarrollo, `False` en producción |
| `DB_NAME` | Nombre de la base de datos |
| `DB_USER` | Usuario de PostgreSQL |
| `DB_PASSWORD` | Contraseña de PostgreSQL |
| `DB_HOST` | Host (default: `localhost`) |
| `DB_PORT` | Puerto (default: `5432`) |
| `EMAIL_HOST` | Servidor SMTP (default: `smtp.gmail.com`) |
| `EMAIL_PORT` | Puerto SMTP (default: `587`) |
| `EMAIL_USE_TLS` | `True` para TLS |
| `EMAIL_HOST_USER` | Cuenta Gmail remitente |
| `EMAIL_HOST_PASSWORD` | App Password de Google (no la contraseña de la cuenta) |
| `DEFAULT_FROM_EMAIL` | Nombre y dirección que aparece en los emails enviados |

### Configurar App Password de Gmail

1. Activar verificación en dos pasos en la cuenta Google
2. Ir a **Cuenta de Google → Seguridad → Contraseñas de aplicaciones**
3. Generar una contraseña para "Correo / Windows" (o cualquier nombre)
4. Usar esa contraseña de 16 caracteres en `EMAIL_HOST_PASSWORD`

> Solo se envían emails a dominios `@unsl.edu.ar`. Correos a otros dominios se omiten silenciosamente.

---

## Registro y verificación de cuentas

Los docentes se registran desde `/cuentas/registro/` con su email institucional `@unsl.edu.ar`. El sistema:

1. Crea la cuenta con `is_active=False`
2. Genera un token UUID con validez de 24 horas
3. Envía un email de verificación al `@unsl.edu.ar` del docente
4. Al hacer clic en el enlace, activa la cuenta (`is_active=True`)

Hasta verificar, el login muestra un mensaje específico indicando que debe verificarse el email.

El username se genera automáticamente a partir del prefijo del email (ej: `juan.perez@unsl.edu.ar` → username `juan.perez`). Si ya existe, se agrega un número correlativo.

---

## Directores de Departamento

Hay un usuario director por cada uno de los 6 departamentos de la facultad.

### Crear en nuevo despliegue

```bash
python manage.py crear_directores_departamento
```

Crea los siguientes usuarios con **contraseña inicial = username**:

| Username | Departamento |
|----------|-------------|
| `matematica` | Matemática |
| `fisica` | Física |
| `geologia` | Geología |
| `electronica` | Electrónica |
| `informatica` | Informática |
| `mineria` | Minería |

Cambiar contraseñas en el primer acceso:

```bash
python manage.py changepassword matematica
# (repetir para cada director)
```

El comando es idempotente: si los usuarios ya existen, los omite sin error.

---

## Tribunales Examinadores

Cada `MateriaEnPlan` no optativa puede tener un `TribunalExaminador` con presidente, dos vocales, día/hora de examen y si admite alumnos libres.

### Ciclo anual

1. El **administrador** accede a *Dashboard → Solicitar informe* para inicializar tribunales vacíos y notificar a todos los directores.
2. Cada **director** revisa los tribunales de su departamento y propone los cambios que correspondan.
3. Los cambios propuestos se agrupan en una `SolicitudCambioTribunal` que el director envía al administrador.
4. El **administrador** revisa cada solicitud y la aplica, actualizando los tribunales en la base de datos.
5. Una vez conformes, el director descarga el informe PDF y lo envía al administrador para su archivo.

### Comandos de carga inicial

```bash
# Crear tribunales vacíos para todas las materias activas sin tribunal
python manage.py crear_tribunales

# Cargar tribunales del Departamento Matemática (lunes)
python manage.py cargar_tribunales_matematica

# Cargar tribunales del Departamento Matemática (martes–viernes)
python manage.py cargar_tribunales_matematica_resto

# Corregir acentos y numerales romanos en nombres de materias
python manage.py corregir_nombres_materias [--dry-run]
```

### Importar materias desde UNSL

```bash
# Importar materias de todas las carreras
python manage.py importar_materias [--limpiar] [--carrera CODIGO]

# Importar materias de un plan específico por URL
python manage.py importar_desde_url URL [--limpiar]
```

---

## Solicitudes de Protocolización

Flujo de estados:

```
Pendiente → En Revisión → Aprobado
                       ↘ Rechazado
```

Al cambiar estado el docente recibe una notificación interna. Al crear una solicitud, el director del departamento correspondiente también es notificado.

### Tipos de solicitud

| Tipificación | Descripción |
|--------------|-------------|
| Obligatoria curricular | Materia obligatoria del plan de estudios |
| Optativa curricular | Materia optativa del plan de estudios |
| Electiva curricular | Materia electiva del plan de estudios |
| Extracurricular | Curso o actividad fuera del plan |

### Documentos generados

| Documento | Quién puede descargar | Formato |
|-----------|----------------------|---------|
| **Solicitud Completa** (nota de elevación + programa) | Todos los usuarios con acceso | PDF / DOCX |
| **Nota de Comisión** | Solo Director y Administrador | PDF / DOCX |

---

## Solicitudes de Taller

Permite registrar talleres y cursos especiales con equipo docente externo, cupo, crédito horario y acta del Consejo Departamental. Flujo de estados idéntico al de protocolización.

---

## Datos iniciales (`datos.json`)

Incluye los datos base del sistema listos para importar:

| Tabla | Contenido |
|-------|-----------|
| `planes.carrera` | Carreras de la facultad |
| `planes.planestudio` | Planes de estudio por carrera |
| `planes.materia` | Materias del catálogo |
| `planes.materiaenplan` | Materias por plan con año, cuatrimestre y carga horaria |
| `tramites.calendarioacademico` | Calendario académico inicial |

> Las cuentas de usuario **no** están incluidas. Crearlas con los comandos de instalación.

Para regenerar el archivo desde una instalación existente (sin usuarios):

```bash
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission \
  -e accounts.customuser -e admin.logentry -e sessions.session \
  --indent 2 > datos.json
```

---

## Diagrama de base de datos

> Renderizable en GitHub, [Mermaid Live](https://mermaid.live) o VSCode con la extensión *Markdown Preview Mermaid Support*.

```mermaid
erDiagram

    %% ── ACCOUNTS ─────────────────────────────────────────────────────────────
    CustomUser {
        bigint      id              PK
        varchar     username        "prefijo del email institucional"
        varchar     email           "debe ser @unsl.edu.ar"
        varchar     first_name
        varchar     last_name
        varchar     rol             "docente | administrador | director_departamento"
        varchar     departamento    "Matemática | Física | Geología | ..."
        varchar     legajo
        varchar     telefono
        boolean     is_active       "False hasta verificar email"
    }

    TokenVerificacionEmail {
        bigint      id          PK
        uuid        token       "UUID único de verificación"
        datetime    creado_en   "expira a las 24 horas"
    }

    %% ── SOLICITUDES ──────────────────────────────────────────────────────────
    SolicitudProtocolizacion {
        bigint      id                  PK
        varchar     estado              "pendiente | en_revision | aprobado | rechazado"
        datetime    fecha_creacion
        varchar     nombre_curso
        varchar     tipificacion        "obligatoria | optativa | electiva | extracurricular"
        varchar     modalidad_cursado
        date        fecha_inicio
        date        fecha_hasta
        int         cantidad_semanas
        int         hs_teorico_practico
        int         hs_teoricas
        int         hs_practicas_aula
        int         hs_lab_campo
        text        fundamentacion
        text        objetivos
        text        contenidos_minimos
        text        unidades
        text        bibliografia_basica
        varchar     codigo_materia      "asignado por el director"
        text        comentarios_revision
    }

    MiembroEquipoDocente {
        bigint      id          PK
        varchar     nombre
        varchar     dni
        varchar     funcion     "responsable | titular | adjunto | ..."
        varchar     cargo       "profesor | jtp | ayudante | ..."
        varchar     dedicacion  "10h | 20h | 40h"
        int         orden
    }

    SolicitudTaller {
        bigint      id                      PK
        varchar     estado
        varchar     denominacion_curso
        int         credito_horario_total
        int         cupo
        text        objetivos
        text        contenidos_minimos
        text        programa
        text        sistema_evaluacion
        file        acta_consejo_departamental
    }

    MiembroEquipoTaller {
        bigint      id          PK
        varchar     rol         "responsable | coordinador | co-responsable | ..."
        varchar     nombre
        varchar     titulo
        varchar     institucion
        varchar     email
    }

    %% ── PLANES ───────────────────────────────────────────────────────────────
    Carrera {
        bigint      id              PK
        varchar     codigo
        varchar     nombre
        int         duracion_anos
        varchar     departamento
    }

    PlanEstudio {
        bigint      id          PK
        varchar     codigo
        boolean     vigente
        boolean     activo
    }

    Materia {
        bigint      id      PK
        varchar     codigo
        varchar     nombre
        varchar     departamento
    }

    MateriaEnPlan {
        bigint      id                  PK
        boolean     es_optativa
        boolean     es_servicio
        varchar     departamento_dictante
        int         hs_totales
        int         tope_hs
        int         ano
        int         cuatrimestre        "1 | 2 | 3 (anual)"
    }

    TribunalExaminador {
        bigint      id                  PK
        varchar     presidente_nombre
        varchar     presidente_dni
        varchar     vocal_1_nombre
        varchar     vocal_1_dni
        varchar     vocal_2_nombre
        varchar     vocal_2_dni
        int         dia_semana          "1 lunes … 5 viernes"
        time        hora
        boolean     permite_libres
    }

    SolicitudCambioTribunal {
        bigint      id              PK
        varchar     departamento
        datetime    fecha_creacion
        datetime    fecha_envio
        varchar     estado          "borrador | enviada | aplicada"
    }

    SolicitudCambioItem {
        bigint      id              PK
        varchar     presidente_nombre
        varchar     presidente_dni
        varchar     vocal_1_nombre
        varchar     vocal_1_dni
        varchar     vocal_2_nombre
        varchar     vocal_2_dni
        int         dia_semana
        time        hora
        boolean     permite_libres
    }

    SolicitudInformeTribunal {
        bigint      id          PK
        datetime    fecha
        boolean     activa
    }

    InformeTribunalesEnviado {
        bigint      id          PK
        varchar     departamento
        datetime    fecha_envio
    }

    %% ── TRAMITES ─────────────────────────────────────────────────────────────
    CalendarioAcademico {
        bigint      id                      PK
        int         anno
        date        fecha_inicio_1c
        date        fecha_fin_1c
        date        fecha_inicio_2c
        date        fecha_fin_2c
        int         semanas_cuatrimestre
        int         semanas_anual
    }

    %% ── NOTIFICATIONS ────────────────────────────────────────────────────────
    Notificacion {
        bigint      id       PK
        varchar     tipo
        varchar     titulo
        text        mensaje
        boolean     leida
        datetime    fecha
        varchar     url
    }

    %% ── RELACIONES ───────────────────────────────────────────────────────────

    CustomUser              ||--o|   TokenVerificacionEmail          : "verificacion"
    CustomUser              ||--o{   SolicitudProtocolizacion        : "docente"
    CustomUser              ||--o{   SolicitudTaller                 : "docente"
    CustomUser              ||--o{   Notificacion                    : "destinatario"
    CustomUser              ||--o{   SolicitudCambioTribunal         : "director"
    CustomUser              ||--o{   InformeTribunalesEnviado        : "director"
    CustomUser              ||--o{   SolicitudInformeTribunal        : "solicitante"

    SolicitudProtocolizacion  }o--o|  Carrera                       : "carrera"
    SolicitudProtocolizacion  }o--o|  PlanEstudio                   : "plan_estudio"
    SolicitudProtocolizacion  }o--o|  MateriaEnPlan                 : "optativa_vinculada"
    SolicitudProtocolizacion  ||--|{  MiembroEquipoDocente           : "equipo_docente"

    SolicitudTaller           ||--|{  MiembroEquipoTaller            : "equipo"

    PlanEstudio               }o--||  Carrera                       : "carrera"
    MateriaEnPlan             }o--||  Materia                       : "materia"
    MateriaEnPlan             }o--||  PlanEstudio                   : "plan"
    MateriaEnPlan             ||--o|  TribunalExaminador            : "tribunal"

    SolicitudCambioTribunal   ||--|{  SolicitudCambioItem           : "items"
    SolicitudCambioItem       }o--||  TribunalExaminador            : "tribunal"

    SolicitudInformeTribunal  ||--o{  InformeTribunalesEnviado      : "informes"
```

---

## Estructura del proyecto

```
├── apps/
│   ├── accounts/            # Usuarios, roles, registro, verificación de email
│   │   └── management/commands/
│   │       └── crear_directores_departamento.py
│   ├── tramites/            # Base común (estados, calendario, dashboard)
│   ├── solicitudes/         # Solicitudes de protocolización y talleres
│   │   ├── pdf.py           # PDF (programa, nota comisión, solicitud completa)
│   │   └── docx_gen.py      # DOCX (ídem)
│   ├── planes/              # Carreras, planes, materias, tribunales
│   │   ├── pdf.py           # PDF (informe tribunales, solicitud de cambio)
│   │   └── management/commands/
│   │       ├── actualizar_carreras.py            # Carga las 22 carreras de FCFMyN
│   │       ├── crear_tribunales.py               # Crea tribunales vacíos para materias activas
│   │       ├── corregir_nombres_materias.py      # Corrige acentos y numerales romanos
│   │       ├── importar_materias.py              # Importa materias desde planesestudio.unsl.edu.ar
│   │       ├── importar_desde_url.py             # Importa materias de un plan por URL
│   │       ├── cargar_tribunales_matematica.py   # Carga tribunales Matemática (lunes)
│   │       └── cargar_tribunales_matematica_resto.py  # Carga tribunales Matemática (mar–vie)
│   └── notifications/       # Notificaciones internas
├── config/                  # Settings, URLs, WSGI
├── templates/               # Templates HTML
├── static/                  # Archivos estáticos (escudo para documentos)
├── datos.json               # Fixture de datos iniciales
└── .env.example             # Ejemplo de configuración
```
