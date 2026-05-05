from django.conf import settings
from django.db import models
from apps.tramites.models import DEPARTAMENTO_CHOICES

DIA_SEMANA_CHOICES = [
    (1, 'Lunes'),
    (2, 'Martes'),
    (3, 'Miércoles'),
    (4, 'Jueves'),
    (5, 'Viernes'),
]


class Carrera(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=250, verbose_name='Nombre')
    duracion_anos = models.PositiveSmallIntegerField(verbose_name='Duración (años)')
    departamento = models.CharField(
        max_length=50, blank=True,
        choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento',
    )

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Carrera'
        verbose_name_plural = 'Carreras'

    def __str__(self):
        return f'{self.nombre} ({self.codigo})'


class PlanEstudio(models.Model):
    carrera = models.ForeignKey(
        Carrera, on_delete=models.CASCADE,
        related_name='planes', verbose_name='Carrera',
    )
    codigo = models.CharField(max_length=20, verbose_name='Código de plan')
    vigente = models.BooleanField(default=True, verbose_name='Vigente')
    activo = models.BooleanField(
        default=False, verbose_name='Activo',
        help_text='Sin nuevas inscripciones, pero estudiantes inscriptos pueden cursar últimos años y rendir cualquier materia.',
    )
    materias = models.ManyToManyField(
        'Materia', through='MateriaEnPlan',
        related_name='planes', verbose_name='Materias',
    )

    class Meta:
        unique_together = [('carrera', 'codigo')]
        ordering = ['carrera', 'codigo']
        verbose_name = 'Plan de Estudio'
        verbose_name_plural = 'Planes de Estudio'

    def __str__(self):
        return f'Plan {self.codigo} — {self.carrera.nombre}'

    def get_anos_dictados_display(self):
        anos = list(self.anos_dictados.values_list('ano', flat=True).order_by('ano'))
        if not anos:
            return '—'
        return ', '.join(f'{a}°' for a in anos)


class AnioDictado(models.Model):
    plan = models.ForeignKey(
        PlanEstudio, on_delete=models.CASCADE,
        related_name='anos_dictados', verbose_name='Plan de estudio',
    )
    ano = models.PositiveSmallIntegerField(verbose_name='Año')

    class Meta:
        unique_together = [('plan', 'ano')]
        ordering = ['plan', 'ano']
        verbose_name = 'Año dictado'
        verbose_name_plural = 'Años dictados'

    def __str__(self):
        return f'Año {self.ano} — {self.plan}'


class Materia(models.Model):
    codigo = models.CharField(max_length=30, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=250, verbose_name='Nombre')
    departamento = models.CharField(
        max_length=50, blank=True,
        choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento',
    )

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'

    def __str__(self):
        return f'{self.nombre} ({self.codigo})'


class MateriaEnPlan(models.Model):
    CUATRIMESTRE_CHOICES = [
        (1, '1° Cuatrimestre'),
        (2, '2° Cuatrimestre'),
        (3, 'Anual'),
    ]

    materia = models.ForeignKey(
        Materia, on_delete=models.CASCADE,
        related_name='en_planes', verbose_name='Materia',
    )
    plan = models.ForeignKey(
        PlanEstudio, on_delete=models.CASCADE,
        related_name='materias_en_plan', verbose_name='Plan de estudio',
    )
    es_optativa = models.BooleanField(default=False, verbose_name='Es optativa')
    es_servicio = models.BooleanField(default=False, verbose_name='Materia de servicio')
    departamento_dictante = models.CharField(
        max_length=50, blank=True,
        choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento que la dicta',
        help_text='Obligatorio cuando es materia de servicio.',
    )
    hs_totales = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Horas totales')
    tope_hs = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Tope de horas',
        help_text='Límite de horas para esta materia. Opcional.',
    )
    ano = models.PositiveSmallIntegerField(verbose_name='Año')
    cuatrimestre = models.PositiveSmallIntegerField(choices=CUATRIMESTRE_CHOICES, verbose_name='Cuatrimestre')

    class Meta:
        unique_together = [('materia', 'plan')]
        ordering = ['ano', 'cuatrimestre', 'materia__nombre']
        verbose_name = 'Materia en Plan'
        verbose_name_plural = 'Materias en Plan'

    def get_nombre(self):
        return self.materia.nombre

    def __str__(self):
        return f'{self.get_nombre()} — Año {self.ano} ({self.get_cuatrimestre_display()})'


class Docente(models.Model):
    nombre = models.CharField(max_length=250, verbose_name='Nombre completo')
    dni = models.CharField(max_length=15, unique=True, verbose_name='DNI')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'

    def __str__(self):
        return f'{self.nombre} (DNI {self.dni})'


class TribunalExaminador(models.Model):
    materia_en_plan = models.OneToOneField(
        MateriaEnPlan, on_delete=models.CASCADE,
        related_name='tribunal', verbose_name='Materia en plan',
    )
    presidente_nombre = models.CharField(max_length=250, blank=True, verbose_name='Presidente (nombre)')
    presidente_dni = models.CharField(max_length=15, blank=True, verbose_name='Presidente (DNI)')
    vocal_1_nombre = models.CharField(max_length=250, blank=True, verbose_name='1er. Vocal (nombre)')
    vocal_1_dni = models.CharField(max_length=15, blank=True, verbose_name='1er. Vocal (DNI)')
    vocal_2_nombre = models.CharField(max_length=250, blank=True, verbose_name='2do. Vocal (nombre)')
    vocal_2_dni = models.CharField(max_length=15, blank=True, verbose_name='2do. Vocal (DNI)')
    dia_semana = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=DIA_SEMANA_CHOICES, verbose_name='Día de la semana',
    )
    hora = models.TimeField(null=True, blank=True, verbose_name='Hora del examen')
    permite_libres = models.BooleanField(
        default=True, verbose_name='Pueden rendir libres',
        help_text='Si está desmarcado, solo pueden rendir alumnos regulares.',
    )

    class Meta:
        verbose_name = 'Tribunal Examinador'
        verbose_name_plural = 'Tribunales Examinadores'

    def __str__(self):
        return f'Tribunal — {self.materia_en_plan}'


class SolicitudInformeTribunal(models.Model):
    """Registro de cada solicitud de informe de tribunales enviada por el admin."""
    CUATRIMESTRE_CHOICES = [
        (1, 'Primer cuatrimestre'),
        (2, 'Segundo cuatrimestre'),
    ]
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='solicitudes_informe_tribunal',
        verbose_name='Solicitante',
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')
    cuatrimestre = models.PositiveSmallIntegerField(
        choices=CUATRIMESTRE_CHOICES,
        default=1,
        verbose_name='Cuatrimestre',
    )
    anio = models.PositiveIntegerField(default=2025, verbose_name='Año')
    departamentos_notificados = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Departamentos notificados',
        help_text='Q1: vacío (todos). Q2: lista de departamentos con nuevos tribunales.',
    )

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Solicitud de informe de tribunal'
        verbose_name_plural = 'Solicitudes de informe de tribunal'

    def __str__(self):
        label = 'Q1' if self.cuatrimestre == 1 else 'Q2'
        return f'Solicitud informe tribunales — {label} {self.anio}'


class InformeTribunalesEnviado(models.Model):
    """Registra que un director ya envió su informe anual para una solicitud dada."""
    solicitud = models.ForeignKey(
        SolicitudInformeTribunal,
        on_delete=models.CASCADE,
        related_name='informes_enviados',
        verbose_name='Solicitud',
    )
    departamento = models.CharField(
        max_length=50, choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento',
    )
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='informes_tribunales_enviados',
        verbose_name='Director',
    )
    fecha_envio = models.DateTimeField(verbose_name='Fecha de envío')

    class Meta:
        unique_together = [('solicitud', 'departamento')]
        ordering = ['-fecha_envio']
        verbose_name = 'Informe de tribunales enviado'
        verbose_name_plural = 'Informes de tribunales enviados'

    def __str__(self):
        return f'Informe {self.departamento} — {self.solicitud.fecha.year}'

    @property
    def ano(self):
        return self.solicitud.anio


class SolicitudCambioTribunal(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
        ('aplicada', 'Aplicada'),
    ]
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_cambio_tribunal',
        verbose_name='Director',
    )
    departamento = models.CharField(
        max_length=50, choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de envío')
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado',
    )

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Solicitud de cambio de tribunal'
        verbose_name_plural = 'Solicitudes de cambio de tribunal'

    def __str__(self):
        return f'Solicitud cambio — Dpto. {self.departamento} — {self.fecha_creacion:%d/%m/%Y}'


class SolicitudCambioItem(models.Model):
    solicitud = models.ForeignKey(
        SolicitudCambioTribunal, on_delete=models.CASCADE,
        related_name='items', verbose_name='Solicitud',
    )
    tribunal = models.ForeignKey(
        TribunalExaminador, on_delete=models.CASCADE,
        related_name='solicitud_items', verbose_name='Tribunal',
    )
    presidente_nombre = models.CharField(max_length=250, blank=True, verbose_name='Presidente (nombre)')
    presidente_dni = models.CharField(max_length=15, blank=True, verbose_name='Presidente (DNI)')
    vocal_1_nombre = models.CharField(max_length=250, blank=True, verbose_name='1er. Vocal (nombre)')
    vocal_1_dni = models.CharField(max_length=15, blank=True, verbose_name='1er. Vocal (DNI)')
    vocal_2_nombre = models.CharField(max_length=250, blank=True, verbose_name='2do. Vocal (nombre)')
    vocal_2_dni = models.CharField(max_length=15, blank=True, verbose_name='2do. Vocal (DNI)')
    dia_semana = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=DIA_SEMANA_CHOICES, verbose_name='Día de la semana',
    )
    hora = models.TimeField(null=True, blank=True, verbose_name='Hora del examen')
    permite_libres = models.BooleanField(default=True, verbose_name='Pueden rendir libres')
    # Snapshot of tribunal state at the moment this item was first proposed
    snapshot_tribunal = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = [('solicitud', 'tribunal')]
        verbose_name = 'Item de solicitud de cambio'
        verbose_name_plural = 'Items de solicitud de cambio'

    def __str__(self):
        return f'Item — {self.tribunal} en {self.solicitud}'


class SolicitudServicio(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
    ]
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_servicio', verbose_name='Director',
    )
    carrera = models.ForeignKey(
        'Carrera', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_servicio', verbose_name='Carrera',
    )
    departamento_solicitante = models.CharField(
        max_length=50, choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento solicitante',
    )
    departamento_dictante = models.CharField(
        max_length=50, choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento dictante',
    )
    dictante_externo_nombre = models.CharField(
        max_length=250, blank=True, verbose_name='Nombre del receptor externo',
        help_text='Solo cuando el departamento dictante es "Externo".',
    )
    anio_academico = models.PositiveSmallIntegerField(verbose_name='Año académico')
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de envío')

    class Meta:
        verbose_name = 'Solicitud de servicio'
        verbose_name_plural = 'Solicitudes de servicio'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Solicitud servicio — {self.departamento_solicitante} → {self.departamento_dictante} ({self.anio_academico})'


class SolicitudServicioItem(models.Model):
    solicitud = models.ForeignKey(
        SolicitudServicio, on_delete=models.CASCADE,
        related_name='items', verbose_name='Solicitud',
    )
    materia_en_plan = models.ForeignKey(
        MateriaEnPlan, on_delete=models.PROTECT,
        related_name='solicitud_servicio_items', verbose_name='Materia en plan',
    )
    hs_totales = models.PositiveSmallIntegerField(verbose_name='Horas totales')

    class Meta:
        unique_together = [('solicitud', 'materia_en_plan')]
        verbose_name = 'Item de solicitud de servicio'
        verbose_name_plural = 'Items de solicitud de servicio'

    def __str__(self):
        return f'{self.materia_en_plan} en {self.solicitud}'


class ConvocatoriaSolicitudServicio(models.Model):
    CUATRIMESTRE_CHOICES = [
        (1, '1° Cuatrimestre + Anuales'),
        (2, '2° Cuatrimestre'),
    ]
    cuatrimestre = models.PositiveSmallIntegerField(choices=CUATRIMESTRE_CHOICES, verbose_name='Cuatrimestre')
    anio = models.PositiveSmallIntegerField(verbose_name='Año')
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='convocatorias_servicio', verbose_name='Enviado por',
    )
    fecha_envio = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de envío')
    directores_notificados = models.PositiveSmallIntegerField(default=0, verbose_name='Directores notificados')

    class Meta:
        unique_together = [('cuatrimestre', 'anio')]
        verbose_name = 'Convocatoria de solicitud de servicio'
        verbose_name_plural = 'Convocatorias de solicitud de servicio'
        ordering = ['-anio', '-cuatrimestre']

    def __str__(self):
        return f'Convocatoria {self.get_cuatrimestre_display()} {self.anio}'
