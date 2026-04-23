from django.db import models
from apps.tramites.models import TramiteBase
from apps.planes.models import Carrera, PlanEstudio, MateriaEnPlan


PERIODO_CHOICES = [
    ('1c', '1° Cuatrimestre'),
    ('2c', '2° Cuatrimestre'),
    ('anual', 'Anual'),
]

FUNCION_CHOICES = [
    ('prof_responsable', 'Prof. Responsable'),
    ('prof_colaborador', 'Prof. Colaborador'),
    ('resp_practico',    'Responsable de Práctico'),
    ('aux_practico',     'Auxiliar de Práctico'),
    ('aux_laboratorio',  'Auxiliar de Laboratorio'),
]

CARGO_CHOICES = [
    ('titular', 'Titular'),
    ('asociado', 'Asociado'),
    ('adjunto', 'Adjunto'),
    ('jtp', 'J.T.P.'),
    ('ay1', 'Ayudante de 1ra'),
    ('ay2', 'Ayudante de 2da'),
    ('otro', 'Otro'),
]

DEDICACION_CHOICES = [
    ('10hs', '10 Hs'),
    ('20hs', '20 Hs'),
    ('40hs', '40 Hs'),
]

TIPIFICACION_CHOICES = [
    ('optativa',  'Optativa'),
    ('jornada',   'Jornada'),
    ('congreso',  'Congreso'),
]

MODALIDAD_CURSADO_CHOICES = [
    ('teo_aula_campo',   'Teoría con Prácticas de Aula y Campo'),
    ('teo_aula_lab',     'Teoría con Prácticas de Aula y Laboratorios'),
    ('teo_aula',         'Teoría con Prácticas de Aula'),
    ('teo_aula_lab_campo', 'Teoría con Prácticas de Aula, Laboratorio y Campo'),
]

CONDICION_CHOICES = [
    ('regular',     'Regular'),
    ('promocional', 'Promocional'),
]

CONDICION_CORRELATIVA_CHOICES = [
    ('aprobada',     'Aprobada'),
    ('regularizada', 'Regularizada'),
]

TIPO_CORRELATIVA_CHOICES = [
    ('cursar', 'Para cursar'),
    ('rendir', 'Para rendir'),
]


class SolicitudProtocolizacion(TramiteBase):
    # ── I. Oferta Académica ──────────────────────────────────────────────────
    nombre_curso = models.CharField(max_length=200, verbose_name='Nombre / Materia')
    area = models.CharField(max_length=200, verbose_name='Área', blank=True)
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Carrera',
    )
    plan_estudio = models.ForeignKey(
        PlanEstudio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Plan de estudio',
    )
    optativa_vinculada = models.ForeignKey(
        MateriaEnPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Optativa vinculada',
        help_text='Optativa del plan a la que corresponde esta protocolización.',
    )
    anno_carrera = models.CharField(max_length=10, verbose_name='Año en la carrera', blank=True)
    periodo = models.CharField(
        max_length=10, choices=PERIODO_CHOICES,
        verbose_name='Período', blank=True,
    )

    # ── III. Características del Curso ───────────────────────────────────────
    hs_teorico_practico = models.PositiveIntegerField(default=0, verbose_name='Hs. Teórico/Práctico')
    hs_teoricas = models.PositiveIntegerField(default=0, verbose_name='Hs. Teóricas')
    hs_practicas_aula = models.PositiveIntegerField(default=0, verbose_name='Hs. Prácticas de Aula')
    hs_lab_campo = models.PositiveIntegerField(default=0, verbose_name='Hs. Práct. Lab/Campo')
    tipificacion = models.CharField(
        max_length=20, choices=TIPIFICACION_CHOICES,
        verbose_name='Tipificación', blank=True,
    )
    modalidad_cursado = models.CharField(
        max_length=20,
        choices=MODALIDAD_CURSADO_CHOICES,
        verbose_name='Modalidad de cursado',
        blank=True,
    )
    fecha_inicio = models.DateField(verbose_name='Fecha de inicio')
    fecha_hasta = models.DateField(verbose_name='Fecha hasta')
    cantidad_semanas = models.PositiveIntegerField(default=0, verbose_name='Semanas')

    # ── IV. Fundamentación ───────────────────────────────────────────────────
    fundamentacion = models.TextField(verbose_name='Fundamentación')

    # ── V. Objetivos ─────────────────────────────────────────────────────────
    objetivos = models.TextField(verbose_name='Objetivos / Resultados de Aprendizaje')

    # ── VI. Contenidos ───────────────────────────────────────────────────────
    contenidos_minimos = models.TextField(
        verbose_name='Contenidos Mínimos', blank=True,
        help_text='Síntesis de los contenidos mínimos según el Plan de Estudios.',
    )
    unidades = models.TextField(
        verbose_name='Unidades temáticas',
        help_text='Descripción de cada unidad (I, II, III…). Una unidad por línea o separadas por doble salto.',
    )

    # ── VII. Plan de Trabajos Prácticos ──────────────────────────────────────
    plan_trabajos_practicos = models.TextField(
        verbose_name='Plan de Trabajos Prácticos', blank=True,
    )

    # ── VIII. Régimen de Aprobación ───────────────────────────────────────────
    regimen_aprobacion = models.TextField(
        verbose_name='Régimen de Aprobación',
    )

    # ── IX / X. Bibliografía ─────────────────────────────────────────────────
    bibliografia_basica = models.TextField(
        verbose_name='Bibliografía Básica',
    )
    bibliografia_complementaria = models.TextField(
        verbose_name='Bibliografía Complementaria', blank=True,
    )

    # ── XI / XII. Resúmenes ───────────────────────────────────────────────────
    resumen_objetivos = models.TextField(
        verbose_name='Resumen de Objetivos', blank=True,
    )
    resumen_programa = models.TextField(
        verbose_name='Resumen del Programa', blank=True,
    )

    # ── XIII. Imprevistos ────────────────────────────────────────────────────
    imprevistos = models.TextField(
        verbose_name='Imprevistos', blank=True,
    )

    # ── XIV. Otros ───────────────────────────────────────────────────────────
    contacto_otros = models.TextField(
        verbose_name='Otros / Datos de contacto', blank=True,
    )

    # ── Datos de Comisión (para nota al Secretario Académico) ─────────────────
    numero_comision = models.CharField(
        max_length=20,
        verbose_name='Número de comisión',
        blank=True,
    )
    condicion = models.CharField(
        max_length=20,
        choices=CONDICION_CHOICES,
        verbose_name='Condición de aprobación',
        blank=True,
    )
    codigo_materia = models.CharField(
        max_length=30,
        verbose_name='Código de materia',
        blank=True,
    )

    # ── Resolución (asigna el Administrador al aprobar) ──────────────────────
    numero_resolucion = models.CharField(
        max_length=50,
        verbose_name='Número de resolución',
        blank=True,
    )

    # ── Actas de aval (sube el Director de Departamento) ─────────────────────
    acta_comision_carrera = models.FileField(
        upload_to='solicitudes/actas/',
        blank=True,
        null=True,
        verbose_name='Acta Comisión de Carrera',
    )
    acta_consejo_departamental = models.FileField(
        upload_to='solicitudes/actas/',
        blank=True,
        null=True,
        verbose_name='Acta Consejo Departamental',
    )

    class Meta(TramiteBase.Meta):
        verbose_name = 'Solicitud de Protocolización'
        verbose_name_plural = 'Solicitudes de Protocolización'

    def __str__(self):
        return f"Solicitud: {self.nombre_curso} — {self.get_nombre_docente}"

    @property
    def total_horas_semanales(self):
        return self.hs_teorico_practico + self.hs_teoricas + self.hs_practicas_aula + self.hs_lab_campo

    @property
    def total_horas(self):
        return self.cantidad_semanas * self.total_horas_semanales


class CorrelativaRequerida(models.Model):
    solicitud = models.ForeignKey(
        SolicitudProtocolizacion,
        on_delete=models.CASCADE,
        related_name='correlativas',
    )
    materia = models.ForeignKey(
        'planes.Materia',
        on_delete=models.CASCADE,
        verbose_name='Materia',
    )
    condicion = models.CharField(
        max_length=15,
        choices=CONDICION_CORRELATIVA_CHOICES,
        verbose_name='Condición',
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CORRELATIVA_CHOICES,
        verbose_name='Tipo',
    )

    class Meta:
        ordering = ['tipo', 'materia__nombre']
        verbose_name = 'Correlativa Requerida'
        verbose_name_plural = 'Correlativas Requeridas'

    def __str__(self):
        return f'{self.materia.nombre} ({self.get_condicion_display()}, {self.get_tipo_display()})'


class MiembroEquipoDocente(models.Model):
    solicitud = models.ForeignKey(
        SolicitudProtocolizacion,
        on_delete=models.CASCADE,
        related_name='equipo_docente',
    )
    nombre = models.CharField(max_length=200, verbose_name='Apellido y Nombre')
    dni = models.CharField(max_length=20, verbose_name='DNI', blank=True)
    funcion = models.CharField(
        max_length=20, choices=FUNCION_CHOICES,
        verbose_name='Función',
    )
    cargo = models.CharField(
        max_length=20, choices=CARGO_CHOICES,
        verbose_name='Cargo', blank=True,
    )
    dedicacion = models.CharField(
        max_length=20, choices=DEDICACION_CHOICES,
        verbose_name='Dedicación', blank=True,
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'Miembro del Equipo Docente'

    def __str__(self):
        return f"{self.nombre} ({self.get_funcion_display()})"

    def get_cargo_display(self):
        return dict(CARGO_CHOICES).get(self.cargo, self.cargo)

    def get_dedicacion_display(self):
        return dict(DEDICACION_CHOICES).get(self.dedicacion, self.dedicacion)


ROL_TALLER_CHOICES = [
    ('responsable',             'Responsable'),
    ('responsable_coordinador', 'Responsable y Coordinador'),
    ('co_responsable',          'Co-responsable'),
    ('coordinador',             'Coordinador'),
    ('colaborador',             'Colaborador'),
    ('auxiliar',                'Auxiliar'),
]

ROL_TALLER_CON_DETALLE = {'responsable', 'responsable_coordinador', 'co_responsable'}


class SolicitudTaller(TramiteBase):
    denominacion_curso = models.CharField(max_length=200, verbose_name='Denominación del curso')

    # Características
    credito_horario_total = models.PositiveIntegerField(default=0, verbose_name='Crédito horario total (hs)')
    destinatarios         = models.TextField(verbose_name='Destinatarios')
    cupo                  = models.PositiveIntegerField(default=0, verbose_name='Cupo')

    # Calendario y fechas
    calendario_actividades = models.TextField(blank=True, verbose_name='Calendario de actividades')
    fecha_elevar_nomina    = models.DateField(null=True, blank=True, verbose_name='Fecha prevista para elevar la nómina de alumnos aprobados')

    # Contenido académico
    objetivos           = models.TextField(verbose_name='Objetivos')
    contenidos_minimos  = models.TextField(verbose_name='Contenidos mínimos')
    programa            = models.TextField(verbose_name='Programa')
    sistema_evaluacion  = models.TextField(verbose_name='Sistema de evaluación')
    bibliografia        = models.TextField(verbose_name='Bibliografía')
    costos_financiamiento = models.TextField(blank=True, verbose_name='Costos y fuentes de financiamiento')

    # Aval del director (solo consejo departamental)
    acta_consejo_departamental = models.FileField(
        upload_to='talleres/actas/',
        blank=True, null=True,
        verbose_name='Acta Consejo Departamental',
    )

    # Resolución (asigna el administrador al aprobar)
    numero_resolucion = models.CharField(max_length=50, blank=True, verbose_name='Número de resolución')

    class Meta(TramiteBase.Meta):
        verbose_name = 'Solicitud de Curso/Taller'
        verbose_name_plural = 'Solicitudes de Curso/Taller'

    def __str__(self):
        return f"Curso/Taller: {self.denominacion_curso} — {self.get_nombre_docente}"

    @property
    def nombre_curso(self):
        return self.denominacion_curso


class MiembroEquipoTaller(models.Model):
    taller      = models.ForeignKey(SolicitudTaller, on_delete=models.CASCADE, related_name='equipo')
    rol         = models.CharField(max_length=30, choices=ROL_TALLER_CHOICES, verbose_name='Rol')
    nombre      = models.CharField(max_length=200, verbose_name='Nombre y apellido')
    # Detalle adicional (solo para responsable y co-responsable)
    titulo      = models.CharField(max_length=100, blank=True, verbose_name='Título')
    documento   = models.CharField(max_length=20,  blank=True, verbose_name='N° Documento')
    institucion = models.CharField(max_length=200, blank=True, verbose_name='Institución de origen')
    email       = models.EmailField(blank=True, verbose_name='E-mail')
    telefono    = models.CharField(max_length=50,  blank=True, verbose_name='Teléfono / FAX')
    orden       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'Miembro del equipo (Taller)'

    def __str__(self):
        return f"{self.nombre} ({self.get_rol_display()})"
