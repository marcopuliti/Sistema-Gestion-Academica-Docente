# Diagrama de Base de Datos

> Generado a partir de los modelos Django del proyecto.  
> Se puede visualizar en GitHub, [Mermaid Live](https://mermaid.live) o con la extensión **Markdown Preview Mermaid Support** en VSCode.

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
        varchar     nombre_docente      "para envíos anónimos"
        varchar     departamento_docente
        varchar     email_docente
        varchar     estado              "pendiente | en_revision | aprobado | rechazado"
        datetime    fecha_creacion
        varchar     nombre_curso
        varchar     area
        varchar     anno_carrera
        varchar     periodo             "1c | 2c | anual"
        int         hs_teorico_practico
        int         hs_teoricas
        int         hs_practicas_aula
        int         hs_lab_campo
        varchar     tipificacion        "obligatoria | optativa | electiva | extracurricular"
        varchar     modalidad_cursado
        date        fecha_inicio
        date        fecha_hasta
        int         cantidad_semanas
        text        fundamentacion
        text        objetivos
        text        contenidos_minimos
        text        unidades
        text        plan_trabajos_practicos
        text        regimen_aprobacion
        text        bibliografia_basica
        text        bibliografia_complementaria
        text        resumen_objetivos
        text        resumen_programa
        text        imprevistos
        text        contacto_otros
        varchar     condicion           "regular | promocional"
        varchar     codigo_materia      "asignado por el director"
        text        comentarios_revision
    }

    MiembroEquipoDocente {
        bigint      id          PK
        varchar     nombre
        varchar     dni
        varchar     funcion     "responsable | titular | adjunto | ..."
        varchar     cargo       "profesor | jtp | ayudante | ..."
        varchar     dedicacion  "exclusiva | semi | simple"
        int         orden
    }

    %% ── PLANES ───────────────────────────────────────────────────────────────
    Carrera {
        bigint      id              PK
        varchar     codigo
        varchar     nombre
        int         duracion_anos
    }

    PlanEstudio {
        bigint      id          PK
        varchar     codigo
        boolean     vigente
    }

    Materia {
        bigint      id      PK
        varchar     codigo
        varchar     nombre
    }

    MateriaEnPlan {
        bigint      id              PK
        varchar     nombre          "puede diferir del nombre en Materia"
        boolean     es_optativa
        int         hs_totales
        int         tope_hs
        int         ano             "año de la carrera en que se cursa"
        int         cuatrimestre    "1 | 2 | 3 (anual)"
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

    %% Accounts
    CustomUser         ||--o|  TokenVerificacionEmail       : "token_verificacion"

    %% Solicitudes → usuarios (ambas FK son nullable)
    CustomUser         ||--o{  SolicitudProtocolizacion     : "docente (usuario)"
    CustomUser         ||--o{  SolicitudProtocolizacion     : "revisor"

    %% Solicitudes → planes (nullable)
    SolicitudProtocolizacion  }o--o|  Carrera               : "carrera"
    SolicitudProtocolizacion  }o--o|  PlanEstudio           : "plan_estudio"
    SolicitudProtocolizacion  }o--o|  MateriaEnPlan         : "optativa_vinculada"

    %% Equipo docente
    SolicitudProtocolizacion  ||--|{  MiembroEquipoDocente  : "equipo_docente"

    %% Planes
    PlanEstudio        }o--||  Carrera                      : "carrera"
    MateriaEnPlan      }o--||  Materia                      : "materia"
    MateriaEnPlan      }o--||  PlanEstudio                  : "plan"

    %% Notificaciones
    CustomUser         ||--o{  Notificacion                 : "destinatario"
```
