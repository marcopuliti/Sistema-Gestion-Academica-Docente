# Diagrama de Base de Datos

> Generado a partir de los modelos Django del proyecto.  
> Se puede visualizar en GitHub, [Mermaid Live](https://mermaid.live) o con la extensión **Markdown Preview Mermaid Support** en VSCode.

```mermaid
erDiagram

    %% ── ACCOUNTS ─────────────────────────────────────────────────────────────
    CustomUser {
        bigint      id              PK
        varchar     username        "prefijo del email institucional"
        varchar     email
        varchar     first_name
        varchar     last_name
        varchar     rol             "docente | secretario | direccion_academica | dpto_estudiantes | director_departamento"
        varchar     departamento    "Matemática | Física | Geología | Electrónica | Informática | Minería"
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
        bigint      id                          PK
        varchar     nombre_docente              "para envíos anónimos"
        varchar     legajo_docente
        varchar     departamento_docente
        varchar     email_docente
        varchar     estado                      "pendiente | observada | devuelta | elevada | aprobado | rechazado"
        datetime    fecha_creacion
        datetime    fecha_actualizacion
        text        comentarios_revision
        varchar     nombre_curso
        varchar     area
        varchar     anno_carrera
        varchar     periodo                     "1c | 2c | anual"
        int         hs_teorico_practico
        int         hs_teoricas
        int         hs_practicas_aula
        int         hs_lab_campo
        varchar     tipificacion                "optativa | jornada | congreso"
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
        varchar     numero_comision
        varchar     condicion                   "regular | promocional"
        varchar     codigo_materia
        varchar     numero_resolucion
        file        acta_comision_carrera
        file        acta_consejo_departamental
    }

    MiembroEquipoDocente {
        bigint      id          PK
        varchar     nombre
        varchar     dni
        varchar     funcion     "prof_responsable | prof_colaborador | resp_practico | aux_practico | aux_laboratorio"
        varchar     cargo       "titular | asociado | adjunto | jtp | ay1 | ay2 | otro"
        varchar     dedicacion  "10hs | 20hs | 40hs"
        int         orden
    }

    CorrelativaRequerida {
        bigint      id          PK
        varchar     condicion   "aprobada | regularizada"
        varchar     tipo        "cursar | rendir"
    }

    SolicitudTaller {
        bigint      id                      PK
        varchar     nombre_docente
        varchar     legajo_docente
        varchar     departamento_docente
        varchar     email_docente
        varchar     estado                  "pendiente | observada | devuelta | elevada | aprobado | rechazado"
        datetime    fecha_creacion
        datetime    fecha_actualizacion
        text        comentarios_revision
        varchar     denominacion_curso
        int         credito_horario_total
        text        destinatarios
        int         cupo
        text        calendario_actividades
        date        fecha_elevar_nomina
        text        objetivos
        text        contenidos_minimos
        text        programa
        text        sistema_evaluacion
        text        bibliografia
        text        costos_financiamiento
        file        acta_consejo_departamental
        varchar     numero_resolucion
    }

    MiembroEquipoTaller {
        bigint      id          PK
        varchar     rol         "responsable | responsable_coordinador | co_responsable | coordinador | colaborador | auxiliar"
        varchar     nombre
        varchar     titulo
        varchar     documento
        varchar     institucion
        varchar     email
        varchar     telefono
        int         orden
    }

    %% ── PLANES ───────────────────────────────────────────────────────────────
    Carrera {
        bigint      id              PK
        varchar     codigo
        varchar     nombre
        int         duracion_anos
        varchar     departamento    "departamento al que pertenece la carrera"
    }

    PlanEstudio {
        bigint      id          PK
        varchar     codigo
        boolean     vigente     "recibe nuevos inscriptos"
        boolean     activo      "inscriptos activos aún cursando"
    }

    AnioDictado {
        bigint      id      PK
        int         ano     "año de la carrera que se dicta actualmente"
    }

    Materia {
        bigint      id          PK
        varchar     codigo
        varchar     nombre
        varchar     departamento
    }

    MateriaEnPlan {
        bigint      id                      PK
        boolean     es_optativa
        boolean     es_servicio             "dictada por otro departamento"
        varchar     departamento_dictante   "departamento que la dicta (si es servicio o Externo)"
        int         hs_totales
        int         tope_hs
        int         ano                     "año de la carrera en que se cursa"
        int         cuatrimestre            "1=1° | 2=2° | 3=Anual"
    }

    Docente {
        bigint      id      PK
        varchar     nombre
        varchar     dni
    }

    TribunalExaminador {
        bigint      id                  PK
        varchar     presidente_nombre
        varchar     presidente_dni
        varchar     vocal_1_nombre
        varchar     vocal_1_dni
        varchar     vocal_2_nombre
        varchar     vocal_2_dni
        int         dia_semana          "1=Lunes ... 5=Viernes"
        time        hora
        boolean     permite_libres
    }

    SolicitudInformeTribunal {
        bigint      id      PK
        datetime    fecha
        boolean     activa
    }

    InformeTribunalesEnviado {
        bigint      id          PK
        varchar     departamento
        datetime    fecha_envio
    }

    SolicitudCambioTribunal {
        bigint      id              PK
        varchar     departamento
        datetime    fecha_creacion
        datetime    fecha_envio
        varchar     estado          "borrador | enviada | aplicada"
    }

    SolicitudCambioItem {
        bigint      id                  PK
        varchar     presidente_nombre
        varchar     presidente_dni
        varchar     vocal_1_nombre
        varchar     vocal_1_dni
        varchar     vocal_2_nombre
        varchar     vocal_2_dni
        int         dia_semana
        time        hora
        boolean     permite_libres
        json        snapshot_tribunal   "estado del tribunal al proponer el cambio"
    }

    SolicitudServicio {
        bigint      id                      PK
        varchar     departamento_solicitante
        varchar     departamento_dictante   "departamento receptor (o Externo)"
        varchar     dictante_externo_nombre "nombre del receptor cuando dictante=Externo"
        int         anio_academico
        varchar     estado                  "borrador | enviada"
        datetime    fecha_creacion
        datetime    fecha_envio
    }

    SolicitudServicioItem {
        bigint      id          PK
        int         hs_totales  "carga horaria acordada para esta materia"
    }

    ConvocatoriaSolicitudServicio {
        bigint      id                      PK
        int         cuatrimestre            "1=1°+Anuales | 2=2°"
        int         anio
        datetime    fecha_envio
        int         directores_notificados
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
        bigint      id      PK
        varchar     tipo    "nuevo_tramite | cambio_estado | comentario"
        varchar     titulo
        text        mensaje
        boolean     leida
        datetime    fecha
        varchar     url
    }

    %% ── RELACIONES ───────────────────────────────────────────────────────────

    %% Accounts
    CustomUser                    ||--o|  TokenVerificacionEmail          : "token_verificacion"

    %% Solicitudes de Protocolización
    CustomUser                    ||--o{  SolicitudProtocolizacion        : "docente"
    CustomUser                    ||--o{  SolicitudProtocolizacion        : "revisor"
    SolicitudProtocolizacion      }o--o|  Carrera                         : "carrera"
    SolicitudProtocolizacion      }o--o|  PlanEstudio                     : "plan_estudio"
    SolicitudProtocolizacion      }o--o|  MateriaEnPlan                   : "optativa_vinculada"
    SolicitudProtocolizacion      ||--o{  MiembroEquipoDocente            : "equipo_docente"
    SolicitudProtocolizacion      ||--o{  CorrelativaRequerida            : "correlativas"
    CorrelativaRequerida          }o--||  Materia                         : "materia"

    %% Solicitudes de Curso/Taller
    CustomUser                    ||--o{  SolicitudTaller                 : "docente"
    CustomUser                    ||--o{  SolicitudTaller                 : "revisor"
    SolicitudTaller               ||--o{  MiembroEquipoTaller             : "equipo"

    %% Planes
    PlanEstudio                   }o--||  Carrera                         : "carrera"
    AnioDictado                   }o--||  PlanEstudio                     : "plan"
    MateriaEnPlan                 }o--||  Materia                         : "materia"
    MateriaEnPlan                 }o--||  PlanEstudio                     : "plan"

    %% Tribunales
    TribunalExaminador            ||--||  MateriaEnPlan                   : "materia_en_plan"
    SolicitudInformeTribunal      }o--o|  CustomUser                      : "solicitante"
    InformeTribunalesEnviado      }o--||  SolicitudInformeTribunal        : "solicitud"
    InformeTribunalesEnviado      }o--o|  CustomUser                      : "director"
    SolicitudCambioTribunal       }o--o|  CustomUser                      : "director"
    SolicitudCambioItem           }o--||  SolicitudCambioTribunal         : "solicitud"
    SolicitudCambioItem           }o--||  TribunalExaminador              : "tribunal"

    %% Solicitudes de Servicio
    SolicitudServicio             }o--o|  CustomUser                      : "director"
    SolicitudServicioItem         }o--||  SolicitudServicio               : "solicitud"
    SolicitudServicioItem         }o--||  MateriaEnPlan                   : "materia_en_plan"
    ConvocatoriaSolicitudServicio }o--o|  CustomUser                      : "enviado_por"

    %% Notificaciones
    CustomUser                    ||--o{  Notificacion                    : "destinatario"
```
