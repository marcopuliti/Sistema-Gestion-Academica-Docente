# Sistema de Gestión Académica Docente

Plataforma web para la gestión de solicitudes de protocolización de programas, tribunales examinadores y solicitudes de servicio de la Facultad de Ciencias Físico Matemáticas y Naturales — Universidad Nacional de San Luis.

## Módulos

| Módulo | Descripción |
|--------|-------------|
| **Solicitudes** | Solicitud de protocolización de cursos (curriculares y optativos) y talleres: programa completo, equipo docente, carga horaria, correlativas y bibliografía |
| **Planes** | Carreras, planes de estudio, materias, tribunales examinadores y gestión del ciclo anual de confirmación/cambio de tribunales |
| **Solicitudes de Servicio** | Generación de notas formales a otros departamentos (o externos) para solicitar el dictado de materias de servicio; convocatoria masiva desde secretaría |
| **Trámites** | Base común: estados (Pendiente → Observada → Aprobado/Rechazado), revisión con comentarios, calendario académico |
| **Notificaciones** | Notificaciones internas para cambios de estado, nuevas solicitudes y ciclos de informe de tribunales |
| **Accounts** | Autenticación, registro con verificación por email, roles y gestión de usuarios |

---

## Roles

| Rol | Permisos |
|-----|----------|
| **Docente** | Crea y consulta sus propias solicitudes de protocolización. Descarga el documento completo (nota + programa) |
| **Director de Departamento** | Ve solicitudes de su departamento; asigna código de materia; visualiza y propone cambios en los tribunales examinadores; genera y envía el informe anual de tribunales; genera solicitudes de servicio a otros departamentos |
| **Secretario** | Acceso total: gestiona usuarios, revisa y aprueba solicitudes, administra materias en plan, crea tribunales, aplica solicitudes de cambio de tribunal, gestiona solicitudes de servicio y emite convocatorias |
| **Dirección Académica** | Igual que Secretario excepto la gestión de usuarios |
| **Departamento de Estudiantes** | Gestiona únicamente las solicitudes de cambio de tribunales (lista, detalle, aplicar, descargar PDF) |

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

# 6. Datos iniciales (carreras, planes, materias, tribunales, calendario)
python -X utf8 manage.py loaddata datos.json

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

El Secretario puede crear usuarios directamente desde el panel sin restricciones de contraseña, asignando una contraseña temporal que el usuario deberá cambiar al ingresar.

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

1. El **Secretario / Dirección Académica** accede a *Dashboard → Solicitar informe* para inicializar tribunales vacíos y notificar a todos los directores.
2. Cada **director** revisa los tribunales de su departamento y propone los cambios que correspondan.
3. Los cambios propuestos se agrupan en una `SolicitudCambioTribunal` que el director envía.
4. El **Secretario, Dirección Académica o Departamento de Estudiantes** revisa cada solicitud y la aplica, actualizando los tribunales en la base de datos.
5. Una vez conformes, el director descarga el informe PDF.

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
Pendiente → Elevada al Admin → Aprobado
                             ↘ Rechazado
                             ↘ Observada → (vuelve al director)
```

Al cambiar estado el docente recibe una notificación interna. Al crear una solicitud, el director del departamento correspondiente también es notificado.

### Tipos de solicitud

| Tipificación | Descripción |
|--------------|-------------|
| Optativa | Materia optativa del plan de estudios |
| Jornada | Jornada académica |
| Congreso | Congreso o evento académico |

### Documentos generados

| Documento | Quién puede descargar | Formato |
|-----------|----------------------|---------|
| **Solicitud Completa** (nota de elevación + programa) | Todos los usuarios con acceso | PDF / DOCX |
| **Nota de Comisión** | Solo Director y Secretario | PDF / DOCX |

---

## Solicitudes de Taller

Permite registrar talleres y cursos especiales con equipo docente externo, cupo, crédito horario y acta del Consejo Departamental. Flujo de estados idéntico al de protocolización.

---

## Solicitudes de Servicio

Los directores generan notas formales para solicitar el dictado de materias de servicio (dictadas por otro departamento o por una institución externa).

### Flujo

1. El **Secretario / Dirección Académica** emite una convocatoria desde el panel administrativo (una por cuatrimestre y año). Las materias anuales se convocan junto con el 1° cuatrimestre.
2. Los directores reciben una notificación y generan las solicitudes para cada departamento receptor.
3. Para departamentos **externos** (institución fuera de la facultad), el director ingresa el nombre del receptor. La solicitud solo es visible para el director solicitante y el Secretario.
4. El sistema genera un PDF con la nota formal. Las solicitudes recibidas también son visibles para el departamento receptor.

---

## Datos iniciales (`datos.json`)

Contiene el estado completo de la base de datos exportado con:

```bash
python -X utf8 manage.py dumpdata --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --indent 2 -o datos.json
```

Incluye carreras, planes, materias, tribunales, calendario académico y usuarios del sistema (excepto superusuario). Para regenerar desde una instalación existente sin incluir datos de producción sensibles:

```bash
python -X utf8 manage.py dumpdata --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude accounts.customuser --exclude admin.logentry --exclude sessions.session \
  --indent 2 -o datos.json
```

> El flag `-X utf8` es necesario en Windows para exportar correctamente caracteres especiales.

---

## Diagrama de base de datos

Ver [docs/diagrama_bd.md](docs/diagrama_bd.md) — renderizable en GitHub, [Mermaid Live](https://mermaid.live) o VSCode con la extensión *Markdown Preview Mermaid Support*.

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
│   ├── planes/              # Carreras, planes, materias, tribunales, servicios
│   │   ├── pdf.py           # PDF (informe tribunales, solicitud de cambio, solicitud de servicio)
│   │   └── management/commands/
│   │       ├── actualizar_carreras.py            # Carga las carreras de FCFMyN
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
├── docs/
│   └── diagrama_bd.md       # Diagrama entidad-relación (Mermaid)
├── datos.json               # Fixture de datos completo
└── .env.example             # Ejemplo de configuración
```
