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
    ('optativa', 'Optativa'),
    ('electiva', 'Electiva'),
    ('extracurricular', 'Extracurricular'),
]

MODALIDAD_CURSADO_CHOICES = [
    ('teo_aula_campo',   'Teoría con Prácticas de Aula y Campo'),
    ('teo_aula_lab',     'Teoría con Prácticas de Aula y Laboratorios'),
    ('teo_aula',         'Teoría con Prácticas de Aula'),
    ('teo_aula_lab_campo', 'Teoría con Prácticas de Aula, Laboratorio y Campo'),
]

CONDICION_CHOICES = [
    ('regular',     'Regular'),
    ('libre',       'Libre'),
    ('promocional', 'Promocional'),
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
        verbose_name='Condición',
        blank=True,
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
