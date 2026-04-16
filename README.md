# Sistema de Gestión Académica Docente

Plataforma web para la gestión de trámites académicos docentes universitarios. Permite a docentes cargar planillas de actividades, informes anuales y solicitudes de protocolización; y a jefes de departamento / administradores revisarlos y aprobarlos.

## Módulos

| Módulo | Descripción |
|--------|-------------|
| **Planillas** | Planificación de actividades docentes anuales (docencia, investigación, extensión, gestión, etc.) con carga horaria por cuatrimestre |
| **Informes** | Informe de actividad anual con materias dictadas, investigación, extensión, formación y gestión |
| **Solicitudes** | Solicitud de protocolización de cursos con programa completo, equipo docente y bibliografía |
| **Trámites** | Base común para todos los módulos: estados (Pendiente → En Revisión → Aprobado/Rechazado), revisión y comentarios |
| **Notificaciones** | Notificaciones internas en tiempo real para cambios de estado |
| **Accounts** | Autenticación con roles: Docente, Jefe de Departamento, Administrador |

## Roles

- **Docente** — carga y consulta sus propios trámites
- **Jefe de Departamento / Administrador** — ve todos los trámites, puede revisar, aprobar o rechazar con comentarios

## Stack

- **Backend:** Python / Django
- **Base de datos:** PostgreSQL
- **Frontend:** Bootstrap 5, crispy-forms, widget-tweaks
- **PDF:** generación de documentos por módulo
- **Config:** python-decouple (variables de entorno)

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
# Editar .env con los datos de la base de datos y email

# 5. Base de datos
python manage.py migrate

# 6. Cargar datos iniciales (carreras, planes, materias, etc.)
python manage.py loaddata datos.json

# 7. Crear superusuario (las cuentas no están incluidas en datos.json)
python manage.py createsuperuser

# 8. Servidor de desarrollo
python manage.py runserver
```

Abrir en `http://127.0.0.1:8000`

## Variables de entorno

Ver [.env.example](.env.example). Variables principales:

| Variable | Descripción |
|----------|-------------|
| `SECRET_KEY` | Clave secreta de Django |
| `DEBUG` | `True` en desarrollo, `False` en producción |
| `DB_NAME` | Nombre de la base de datos |
| `DB_USER` | Usuario de PostgreSQL |
| `DB_PASSWORD` | Contraseña de PostgreSQL |
| `DB_HOST` | Host de PostgreSQL (default: `localhost`) |
| `DB_PORT` | Puerto de PostgreSQL (default: `5432`) |
| `EMAIL_HOST_USER` | Cuenta de correo para notificaciones |
| `EMAIL_HOST_PASSWORD` | Contraseña / app password |

## Estructura del proyecto

```
├── apps/
│   ├── accounts/        # Usuarios y roles
│   ├── tramites/        # Base común (estados, calendario académico, dashboard)
│   ├── planillas/       # Planificación de actividades
│   ├── informes/        # Informe de actividad anual
│   ├── solicitudes/     # Solicitud de protocolización
│   └── notifications/   # Notificaciones internas
├── config/              # Settings, URLs, WSGI
├── templates/           # Templates HTML
├── static/              # Archivos estáticos
└── .env.example         # Ejemplo de configuración
```

## Datos iniciales (`datos.json`)

El archivo `datos.json` incluye los datos base del sistema listos para importar:

| Tabla | Contenido |
|-------|-----------|
| `planes.carrera` | Carreras de la facultad |
| `planes.planestudio` | Planes de estudio por carrera |
| `planes.materia` | Materias del catálogo |
| `planes.materiaenplan` | Materias por plan con año, cuatrimestre y carga horaria |
| `tramites.calendarioacademico` | Calendario académico inicial |
| `solicitudes.*` | Solicitudes de ejemplo |

> **Nota:** Las cuentas de usuario **no** están incluidas por seguridad. Crear con `createsuperuser` y luego desde el admin.

Para regenerar el archivo desde una instalación existente (sin usuarios):

```bash
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission \
  -e accounts.customuser -e admin.logentry -e sessions.session \
  --indent 2 > datos.json
```

## Gestión de estados de trámites

```
Pendiente → En Revisión → Aprobado
                       ↘ Rechazado
```

Los revisores (Jefe de Departamento o Administrador) pueden agregar comentarios al cambiar el estado. El docente recibe una notificación interna.
