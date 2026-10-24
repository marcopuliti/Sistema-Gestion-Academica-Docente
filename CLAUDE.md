# CLAUDE.md

Guidance for working in this repository. See [README.md](README.md) for the user-facing feature description, install steps and management command reference (in Spanish).

## What this is

**DELTA** (Dispositivo de Elevación y Logística de Trámites Académicos): a Django 5.2 monolith for the Facultad de Ciencias Físico Matemáticas y Naturales, UNSL (Argentina). It handles course protocolization requests, exam tribunals (tribunales examinadores), and inter-department "service" course requests. Server-rendered templates with Bootstrap 5; no JS build step, no API layer, no Celery.

All code, identifiers, UI text, commit-adjacent docs and messages are in **Spanish** (Argentine voseo in user messages: "No tenés permisos…", "Corregí los errores…"). Keep new code consistent with that.

## Commands

```bash
python manage.py runserver
python manage.py makemigrations && python manage.py migrate
python manage.py check                     # there is no test suite; this is the main sanity check
python -X utf8 manage.py loaddata datos.json   # -X utf8 is required on Windows
python manage.py collectstatic             # production (WhiteNoise CompressedManifestStaticFilesStorage)
```

There are **no tests** (no `tests.py` in any app). Verify changes by running `check` and exercising the flow in the browser with a user of the relevant role.

**The `.env` `DATABASE_URL` points to the production Neon database.** Any `migrate`, `shell` or test client run without overriding it writes to production. To work against real data safely, dump Neon read-only and load it into a throwaway SQLite file (migrations skip the `unaccent` extension on SQLite; only `__unaccent__` searches fail there):

```bash
# dump with the code of the last deployed commit (e.g. from a `git worktree`), then:
export DATABASE_URL="sqlite:///C:/path/to/scratch/test.db"   # decouple prefers the env var over .env
python manage.py migrate && python -X utf8 manage.py loaddata prod.json
```

Two virtualenv dirs exist (`venv/` and `.venv/`), both gitignored. Exclude them from searches — grepping the repo root without excluding them is slow and noisy.

## Configuration gotchas

- `config/settings.py` reads **`DATABASE_URL`** via `dj_database_url.parse(config('DATABASE_URL'))` with no default — the app will not start without it. `.env.example` and the README still list the old `DB_NAME`/`DB_USER`/… variables, which are no longer used (the old `DATABASES` block is commented out).
- **PostgreSQL is required**, not just preferred: `django.contrib.postgres` is installed and views use `__unaccent__icontains` lookups (migration `planes/0039` installs the extension). SQLite will fail on those queries.
- `EMAIL_BACKEND` defaults to the console backend; set it in `.env` to actually send mail.
- **Uploaded files (actas) are stored in the database**, not on disk: `STORAGES['default']` is `apps.tramites.storage.DatabaseStorage` (one `tramites.ArchivoAlmacenado` row per file), because Render's disk is wiped on every deploy. Files are served by the login-only view `tramites:archivo` (`/archivos/<name>`), which is what `FieldFile.url` returns. Never use `FieldFile.path`; read with `field.open('rb')`. When replacing a file, delete the old one (`field.delete(save=False)`) so rows don't pile up.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are hardcoded to localhost + the Render deployment (`sistema-gestion-academica-docente.onrender.com`). Deployment uses gunicorn + WhiteNoise.
- `apps/tramites/apps.py` monkeypatches `django.template.context.BaseContext.__copy__` in `ready()` for Python 3.14 compatibility. Don't remove it.

## Layout

```
config/            settings, root urls, wsgi
apps/accounts/     CustomUser (roles), registration + email verification, user admin (Secretario only)
apps/tramites/     shared base: TramiteBase, EstadoTramite, DEPARTAMENTO_CHOICES, CalendarioAcademico,
                   role decorators, the role-dispatching dashboard (root URL "/")
apps/solicitudes/  SolicitudProtocolizacion (+ equipo docente, correlativas) and SolicitudTaller
apps/planes/       Carrera, PlanEstudio, Materia, MateriaEnPlan, Docente, TribunalExaminador,
                   tribunal change requests, annual tribunal reports, SolicitudServicio, convocatorias
apps/notifications/ Notificacion model, unread-count context processor, notify helpers
templates/<app>/   all templates live here (not inside apps); base.html holds the role-based navbar
static/escudo.gif  university crest embedded in every generated PDF/DOCX
docs/diagrama_bd.md  Mermaid ER diagram
```

URL namespaces: `tramites` and `planes` are both mounted at `''` (planes routes are prefixed `planes/…` in `apps/planes/urls.py`), `accounts` at `cuentas/`, `solicitudes` at `solicitudes/`, `notifications` at `notificaciones/`. Always reverse with the namespace (`'planes:lista_tribunales'`).

`apps/planes/views.py` (~1900 lines) and `apps/solicitudes/views.py` are large single files organized by `# ── section ──` comment banners. Add new views into the matching section.

## Roles and permissions

Roles are a `rol` CharField on `accounts.CustomUser` (`AUTH_USER_MODEL`), not Django groups/permissions. Always check roles through the model properties, never by comparing strings in views:

| Property | Roles |
|---|---|
| `es_docente`, `es_secretario`, `es_direccion_academica`, `es_dpto_estudiantes`, `es_director_departamento`, `es_director_carrera` | the single role |
| `es_administrador` | secretario, direccion_academica, dpto_estudiantes |
| `puede_admin_general`, `puede_revisar` | secretario, direccion_academica |
| `puede_gestionar_usuarios` | secretario |

View decorators in [apps/tramites/decorators.py](apps/tramites/decorators.py) map 1:1 onto those (`solo_administrador`, `solo_admin_general`, `solo_secretario`, `puede_revisar`, `solo_director_departamento`, `solo_director_carrera`). They redirect to the dashboard with an error message. They assume an authenticated user, so **always stack `@login_required` above them**:

```python
@login_required
@solo_director_departamento
def mi_vista(request): ...
```

Object-level access is enforced inside views with helpers like `_puede_ver_solicitud` / `_puede_ver_taller` / `_puede_generar_nota_comision` in `solicitudes/views.py`, and by filtering querysets by the user's department (`get_object_or_404(..., materia_en_plan_id__in=mep_ids)`). New views that take a `pk` must do the same.

Directors: `director_departamento` users are scoped by `user.departamento` (a string); `director_carrera` users are scoped by `user.carrera` (FK to `planes.Carrera`).

## Domain model essentials

- **Departments are plain strings**, not a model: `DEPARTAMENTO_CHOICES` in `apps/tramites/models.py` (`'Matemática'`, `'Física'`, …, plus `'Externo'`). They appear on `CustomUser.departamento`, `Carrera.departamento`, `Materia.departamento`, `MateriaEnPlan.departamento_dictante`, and request models. Values include accents — match them exactly.
- **`MateriaEnPlan`** is the central join (materia × plan, with año/cuatrimestre, `es_optativa`, `es_servicio`, `departamento_dictante`). A plan is "in use" when `vigente=True or activo=True`, and a year is only taught if an `AnioDictado(plan, ano)` row exists.
- **Which MateriaEnPlan belong to a department** (used throughout tribunal code) — see `_meps_del_departamento` in [apps/planes/views.py](apps/planes/views.py):
  own career's non-service subjects **OR** subjects where `departamento_dictante == dept` **OR** own career's service subjects dictated by `'Externo'`; always excluding optativas. Several views inline variants of this filter; keep them consistent if you change the rule.
- **`TribunalExaminador`** stores both `Docente` FKs (`presidente`, `vocal_1`, `vocal_2`) and denormalized `*_nombre`/`*_dni` text fields. `save()` copies FK data into the text fields; much code (dashboards, PDFs, "incomplete" counts via `presidente_nombre=''`) reads the text fields. Keep both in sync.
- A tribunal belongs to **either** a `MateriaEnPlan` (OneToOne, now nullable) **or** a `MateriaOptativa` + `Carrera` (DB check constraint enforces exactly one). Never assume `tribunal.materia_en_plan` is set. Use `tribunal.fila` (the MateriaEnPlan, or a `FilaOptativa` exposing the same `id/materia/plan/plan_id/ano/cuatrimestre` interface) and `tribunal.fila_id` as the key in fila→tribunal maps; templates, PDF and DOCX all consume filas. Department scope: `_tribunales_del_depto()` in `planes/views.py` and the `TribunalExaminador.objects.de_optativas*()` queryset methods.
- **Optativas:** a `MateriaEnPlan` with `es_optativa=True` is only a *slot* ("Optativa I") and never has a tribunal (migration `planes/0042` removed the old empty ones). The actual electives are **`MateriaOptativa`** (the *bolsa*: own unique `codigo`, departamento, hs, cuatrimestre, resolución, `vigente`), linked M2M to slots across careers/plans. `MateriaOptativa.sincronizar_tribunales()` keeps one tribunal per linked career; call it after changing links or `vigente`. Logic shared by views lives in `apps/planes/optativas.py`.
- **`Comision`** (+ `MiembroComision` team): the dictado of a subject in **one career** for a period (`anio` + `cuatrimestre`, 3 = anual), for either a plan `Materia` or a bolsa `MateriaOptativa` (check constraint: exactly one). `departamento` is the department that *reports* it (service subject → `departamento_dictante`; `'Externo'` or own → the career's), computed with `Comision.departamento_responsable()`.
  - Plan subjects: created by `optativas.crear_comisiones_del_periodo()` when admin opens a `SolicitudInformeComisiones` (period 1 = 1° cuatrimestre + anuales, 2 = 2°), one per materia × carrera × cuatrimestre with the career's plans where it is taught that period; completed by the director of `departamento`, who then sends the report (`InformeComisionesEnviado`; PDF/DOCX in `pdf.py`/`docx_gen.py`).
  - Bolsa electives: created when the career director marks them in `optativas_carrera` during a `ConvocatoriaSolicitudServicio`; completed by that career director; they appear in the report of the department that teaches them. If another department teaches one (`requiere_servicio`), it becomes a `SolicitudServicioItem` with `comision` set instead of `materia_en_plan` (use `item.fila` to display either).
  - Edit permission lives in `_puede_editar_comision()` in `planes/views.py`: the career director can edit every comisión of their career; the department director, the plan-subject ones their department reports. Editing happens inline on the detail page (`detalle_comision` handles the POST; `editar_comision` just redirects).
- Shared choice lists for teaching teams and condición (`FUNCION_/CARGO_/DEDICACION_/CONDICION_CHOICES`) live in `apps/tramites/models.py` (re-exported by `solicitudes.models`) so `planes` can use them without a circular import.

## Workflows (state machines)

**Protocolización / Taller** (`TramiteBase` subclasses, states in `EstadoTramite`):

```
PENDIENTE ──director──▶ ELEVADA ──admin──▶ APROBADO (sets numero_resolucion)
    ▲         └─▶ DEVUELTA            └─▶ RECHAZADO / OBSERVADA
    └── docente edits a DEVUELTA/RECHAZADO/OBSERVADA request → back to PENDIENTE
```

The director can only elevate after uploading `acta_consejo_departamental`. `EN_REVISION` is legacy, kept for compatibility. Approving a protocolización with `tipificacion='optativa'` calls `optativas.agregar_a_bolsa()`: it creates/updates the `MateriaOptativa` with the director-assigned `codigo_materia`, links it to `optativa_vinculada` and creates its tribunals (warns if the hours differ from the slot's). Each transition sets `revisor`, `comentarios_revision`, and calls `notificar_cambio_estado`. `TramiteBase.usuario` is nullable: anonymous submissions use the `*_docente` text fields, so use `get_nombre_docente` / `get_legajo_docente` and handle `usuario is None`.

**Tribunal change requests** (`SolicitudCambioTribunal`: `borrador → enviada → aplicada`):
- A director has at most one `borrador` per department (`get_or_create`). Each proposal is a `SolicitudCambioItem`; on first creation it stores `snapshot_tribunal` (JSON of the tribunal's prior state). If a proposal ends up identical to the snapshot, the item is deleted.
- `enviar_solicitud_cambio` notifies all admin roles. `aplicar_solicitud` copies `_CAMPOS_TRIBUNAL` onto each tribunal, re-resolves `Docente` FKs **by DNI**, and refuses to apply if an older `enviada` request from the same department is still pending (requests apply in order).
- Annual reports: admins open a `SolicitudInformeTribunal` (cuatrimestre 1 = all departments; cuatrimestre 2 = only those in `departamentos_notificados`); directors respond, recorded as `InformeTribunalesEnviado` (unique per solicitud × departamento).

**Service requests** (`SolicitudServicio`): admins issue a `ConvocatoriaSolicitudServicio` (unique per cuatrimestre × año; cuatrimestre 1 includes anuales). Department directors and career directors create requests toward a dictating department; for `'Externo'` the receiver name goes in `dictante_externo_nombre`.

## Notifications and email

Use [apps/notifications/utils.py](apps/notifications/utils.py): `_crear_notificacion(user, tipo, titulo, mensaje, url)` creates the in-app `Notificacion` **and** sends an email, but only to addresses ending in `@unsl.edu.ar` (others are skipped silently; failures are swallowed). `notificar_nuevo_tramite` notifies admins plus the matching department director; `notificar_cambio_estado` notifies the request owner. Account emails (welcome, admin password reset) live in `apps/accounts/emails.py` with the same domain restriction. Pass a reversed `url` so the notification links to the object.

## Document generation (PDF / DOCX)

- `apps/solicitudes/pdf.py` and `apps/planes/pdf.py` use ReportLab; `apps/*/docx_gen.py` use python-docx. Generators take model instances and return a `BytesIO`; the view wraps it in an `HttpResponse` with `Content-Disposition`. `pypdf` merges PDFs (e.g. the "solicitud completa" = nota de elevación + programa).
- Most documents exist in **both** PDF and DOCX with mirrored layout. When changing a document's content, update both generators.
- The crest is loaded from `os.path.join(settings.BASE_DIR, 'static', 'escudo.gif')`.

## Conventions

- Function-based views only, with `messages` for feedback and `redirect` after POST. AJAX endpoints return `JsonResponse` (often imported locally inside the view) and are called from inline `<script>` in templates.
- Imports inside function bodies are common (e.g. `from apps.notifications.utils import notificar_cambio_estado`), partly to avoid circular imports between `planes`, `solicitudes` and `tramites`. Follow the surrounding style.
- Templates extend `base.html`, use Bootstrap 5.3 + Bootstrap Icons from jsDelivr, and set the active nav item by overriding a `{% block nav_* %}active{% endblock %}`. New pages linked from the navbar need a block in `base.html`, shown conditionally on the user's role properties.
- Forms use crispy-forms (bootstrap5) and django-widget-tweaks.
- Models use Spanish `verbose_name`s and explicit `related_name`s; choices are module-level `*_CHOICES` lists or `TextChoices`.
- Commit messages follow `feat: …` / `fix: …` / `refactor: …`.

## Migrations

`planes` has a long migration history with merge migrations (duplicate numbers at `0026` and `0036`, merged in `0027` and `0040`). `0041_bolsa_optativas` / `0042` (data) and `solicitudes/0026` add the bolsa de optativas; `0043`/`0044` generalize `ComisionOptativa` → `Comision` and add the comisiones report. When renaming a field referenced by a constraint, drop the constraint before the `RenameField` (SQLite rebuilds the table with the old reference and fails). Run `makemigrations` and check for conflicts before committing; create a merge migration rather than renumbering. Some migrations are data migrations — don't squash or edit applied ones.

## Data files — don't hand-edit

- `datos.json` (~750 KB): fixture of carreras, planes, materias, tribunales, calendario. Regenerate with `dumpdata` as shown in the README.
- `backup.sql`: a PostgreSQL dump.
- `media/` (uploaded actas) and `staticfiles/` are gitignored.

## Known loose ends

- `nueva_solicitud_servicio` in `apps/planes/views.py` (department-director version) has a template but **no URL route**; only the career-director version (`nueva_solicitud_servicio_carrera`) is routed. Check with the user before wiring it up or deleting it.
- `ESTADOS_DISPLAY` in `notifications/utils.py` lacks `observada`/`devuelta`/`elevada`, so those notifications show the raw state value.
- A career director un-ticking `es_optativa` on a slot (`materias_carrera`) does not unlink bolsa materias from it.
