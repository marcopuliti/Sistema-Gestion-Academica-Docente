import types

from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from apps.tramites.models import (
    CARGO_CHOICES, CONDICION_CHOICES, DEDICACION_CHOICES, DEPARTAMENTO_CHOICES, FUNCION_CHOICES,
)

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


class MateriaOptativa(models.Model):
    """Materia de la bolsa de optativas. Tiene su propio código y se vincula a uno o más
    slots optativos (MateriaEnPlan con es_optativa=True) de distintas carreras y planes."""
    codigo = models.CharField(max_length=30, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=250, verbose_name='Nombre')
    departamento = models.CharField(
        max_length=50, blank=True,
        choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento que la dicta',
    )
    hs_totales = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Horas totales')
    cuatrimestre = models.PositiveSmallIntegerField(
        null=True, blank=True,
        choices=MateriaEnPlan.CUATRIMESTRE_CHOICES, verbose_name='Cuatrimestre',
    )
    numero_resolucion = models.CharField(max_length=50, blank=True, verbose_name='N° de resolución')
    vigente = models.BooleanField(
        default=True, verbose_name='Vigente',
        help_text='Las materias dadas de baja salen de la bolsa pero conservan su historial.',
    )
    optativas = models.ManyToManyField(
        MateriaEnPlan, blank=True,
        related_name='materias_bolsa',
        limit_choices_to={'es_optativa': True},
        verbose_name='Optativas vinculadas',
    )

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Materia de la bolsa de optativas'
        verbose_name_plural = 'Bolsa de materias optativas'

    def __str__(self):
        return f'{self.nombre} ({self.codigo})'

    def slots_con_hs_distintas(self):
        """Optativas vinculadas cuyo slot tiene una carga horaria distinta a la de esta materia."""
        if self.hs_totales is None:
            return []
        return [
            s for s in self.optativas.all()
            if s.hs_totales is not None and s.hs_totales != self.hs_totales
        ]

    def carreras_vinculadas(self):
        return Carrera.objects.filter(planes__materias_en_plan__materias_bolsa=self).distinct()

    def sincronizar_tribunales(self):
        """Toda materia vigente tiene un tribunal por cada carrera donde está vinculada.
        Los tribunales que quedan sin vínculo se eliminan si están vacíos; si tienen datos
        o cambios propuestos se conservan (no aparecen en los listados)."""
        carreras = set(self.carreras_vinculadas().values_list('pk', flat=True)) if self.vigente else set()
        creados = eliminados = conservados = 0
        for carrera_id in carreras:
            _, creado = TribunalExaminador.objects.get_or_create(materia_optativa=self, carrera_id=carrera_id)
            creados += creado
        for t in self.tribunales.exclude(carrera_id__in=carreras):
            if t.esta_vacio() and not t.solicitud_items.exists():
                t.delete()
                eliminados += 1
            else:
                conservados += 1
        return creados, eliminados, conservados


class FilaOptativa:
    """Materia de la bolsa en una carrera, presentada con la interfaz de MateriaEnPlan
    (id, materia, plan, plan_id, ano, cuatrimestre) para reutilizar listados, PDFs y DOCX."""
    es_optativa_bolsa = True
    se_dicta = True

    def __init__(self, materia_optativa, carrera, clave, planes=None):
        self.id = clave
        self.materia = materia_optativa
        self.slots = [s for s in materia_optativa.optativas.all() if s.plan.carrera_id == carrera.pk]
        if planes is None:
            planes = [s.plan for s in self.slots]
        planes = sorted(set(planes), key=lambda p: p.codigo)
        if len(planes) == 1:
            self.plan = planes[0]
            self.plan_id = planes[0].pk
        else:
            self.plan = types.SimpleNamespace(
                carrera=carrera,
                codigo=', '.join(p.codigo for p in planes) or '—',
                vigente=any(p.vigente for p in planes),
                activo=any(p.activo for p in planes),
            )
            self.plan_id = 0
        self.ano = min((s.ano for s in self.slots), default=0)
        self.cuatrimestre = materia_optativa.cuatrimestre or 0

    def get_cuatrimestre_display(self):
        return self.materia.get_cuatrimestre_display() or 'Sin cuatrimestre'

    @property
    def slots_display(self):
        return ', '.join(sorted({s.materia.nombre for s in self.slots}))


class Docente(models.Model):
    nombre = models.CharField(max_length=250, verbose_name='Nombre completo')
    dni = models.CharField(max_length=15, unique=True, verbose_name='DNI')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'

    def __str__(self):
        return f'{self.nombre} (DNI {self.dni})'


CAMPOS_TRIBUNAL_COMPLETO = (
    'presidente_nombre', 'presidente_dni', 'vocal_1_nombre', 'vocal_1_dni',
    'vocal_2_nombre', 'vocal_2_dni', 'dia_semana', 'hora',
)


def tribunal_completo(obj):
    """Tribunal o item de cambio con los 3 integrantes (nombre y DNI), día y hora."""
    return all(getattr(obj, campo) for campo in CAMPOS_TRIBUNAL_COMPLETO)


class TribunalExaminadorQuerySet(models.QuerySet):
    def de_materias_en_plan(self):
        return self.filter(materia_en_plan__isnull=False)

    def de_optativas(self):
        """Tribunales de materias de la bolsa vigentes y todavía vinculadas a su carrera."""
        vinculo = MateriaOptativa.optativas.through.objects.filter(
            materiaoptativa_id=OuterRef('materia_optativa_id'),
            materiaenplan__plan__carrera_id=OuterRef('carrera_id'),
        )
        return self.filter(materia_optativa__vigente=True).filter(Exists(vinculo))

    def de_optativas_del_departamento(self, departamento):
        """Las que dicta el departamento, o las externas/sin departamento de sus carreras."""
        return self.de_optativas().filter(
            Q(materia_optativa__departamento=departamento) |
            Q(materia_optativa__departamento__in=['', 'Externo'], carrera__departamento=departamento)
        )


class TribunalExaminador(models.Model):
    """Tribunal de una MateriaEnPlan, o de una materia de la bolsa de optativas en una carrera."""
    materia_en_plan = models.OneToOneField(
        MateriaEnPlan, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='tribunal', verbose_name='Materia en plan',
    )
    materia_optativa = models.ForeignKey(
        MateriaOptativa, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='tribunales', verbose_name='Materia de la bolsa de optativas',
    )
    carrera = models.ForeignKey(
        Carrera, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='tribunales_optativas', verbose_name='Carrera',
    )
    presidente = models.ForeignKey(
        Docente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='como_presidente', verbose_name='Presidente',
    )
    vocal_1 = models.ForeignKey(
        Docente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='como_vocal_1', verbose_name='1er. Vocal',
    )
    vocal_2 = models.ForeignKey(
        Docente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='como_vocal_2', verbose_name='2do. Vocal',
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

    objects = TribunalExaminadorQuerySet.as_manager()

    class Meta:
        verbose_name = 'Tribunal Examinador'
        verbose_name_plural = 'Tribunales Examinadores'
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(materia_en_plan__isnull=False, materia_optativa__isnull=True, carrera__isnull=True) |
                    Q(materia_en_plan__isnull=True, materia_optativa__isnull=False, carrera__isnull=False)
                ),
                name='tribunal_materia_en_plan_o_optativa',
            ),
            models.UniqueConstraint(
                fields=['materia_optativa', 'carrera'],
                name='tribunal_unico_optativa_carrera',
            ),
        ]

    @property
    def es_optativa_bolsa(self):
        return self.materia_optativa_id is not None

    @property
    def fila_id(self):
        """Clave estable para mapas fila → tribunal (pk de MateriaEnPlan o 'opt-<pk>')."""
        return self.materia_en_plan_id if self.materia_en_plan_id else f'opt-{self.pk}'

    @property
    def fila(self):
        """La MateriaEnPlan, o una FilaOptativa con la misma interfaz."""
        if self.materia_en_plan_id:
            return self.materia_en_plan
        return FilaOptativa(self.materia_optativa, self.carrera, clave=self.fila_id)

    @property
    def departamento_responsable(self):
        """Departamento que informa el tribunal: el que dicta la materia, o el de la carrera
        si es propia o la dicta un externo (mismo criterio que _tribunales_del_depto)."""
        if self.materia_optativa_id:
            dictante, carrera = self.materia_optativa.departamento, self.carrera
        else:
            mep = self.materia_en_plan
            dictante = mep.departamento_dictante if mep.es_servicio else ''
            carrera = mep.plan.carrera
        return carrera.departamento if dictante in ('', 'Externo') else dictante

    def esta_vacio(self):
        return not any([
            self.presidente_nombre, self.vocal_1_nombre, self.vocal_2_nombre,
            self.dia_semana, self.hora,
        ])

    def save(self, *args, **kwargs):
        if self.presidente:
            self.presidente_nombre = self.presidente.nombre
            self.presidente_dni = self.presidente.dni
        if self.vocal_1:
            self.vocal_1_nombre = self.vocal_1.nombre
            self.vocal_1_dni = self.vocal_1.dni
        if self.vocal_2:
            self.vocal_2_nombre = self.vocal_2.nombre
            self.vocal_2_dni = self.vocal_2.dni
        super().save(*args, **kwargs)

    def __str__(self):
        if self.materia_optativa_id:
            return f'Tribunal — {self.materia_optativa} — {self.carrera.nombre}'
        return f'Tribunal — {self.materia_en_plan}'


class AgrupacionTribunal(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    departamento = models.CharField(max_length=50, verbose_name='Departamento')
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='agrupaciones_tribunal',
    )
    tribunales = models.ManyToManyField(
        TribunalExaminador, related_name='agrupaciones', blank=True,
    )

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Agrupación de tribunales'
        verbose_name_plural = 'Agrupaciones de tribunales'

    def __str__(self):
        return f'{self.nombre} ({self.departamento})'


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
    numero_sudocu = models.CharField(max_length=50, blank=True, verbose_name='N° de trámite SUDOCU')
    documento = models.FileField(
        upload_to='tribunales/informes/', blank=True, null=True,
        verbose_name='Documento enviado (DOCX)',
    )

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
    numero_sudocu = models.CharField(max_length=50, blank=True, verbose_name='N° de trámite SUDOCU')
    documento = models.FileField(
        upload_to='tribunales/solicitudes/', blank=True, null=True,
        verbose_name='Documento enviado (DOCX)',
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
    # Director de carrera que propuso el cambio (vacío si lo cargó el director de departamento)
    propuesto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='propuestas_tribunal', verbose_name='Propuesto por',
    )

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
        null=True, blank=True,
        related_name='solicitud_servicio_items', verbose_name='Materia en plan',
    )
    comision = models.ForeignKey(
        'Comision', on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='items_servicio', verbose_name='Comisión de optativa',
    )
    hs_totales = models.PositiveSmallIntegerField(verbose_name='Horas totales')
    destinatario = models.CharField(
        max_length=250, blank=True, verbose_name='A quien se dirige',
    )

    class Meta:
        verbose_name = 'Item de solicitud de servicio'
        verbose_name_plural = 'Items de solicitud de servicio'
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(materia_en_plan__isnull=False, comision__isnull=True) |
                    Q(materia_en_plan__isnull=True, comision__isnull=False)
                ),
                name='servicio_item_materia_o_comision',
            ),
            models.UniqueConstraint(
                fields=['solicitud', 'materia_en_plan'],
                condition=Q(materia_en_plan__isnull=False),
                name='servicio_item_unico_materia_en_plan',
            ),
            models.UniqueConstraint(
                fields=['solicitud', 'comision'],
                condition=Q(comision__isnull=False),
                name='servicio_item_unico_comision',
            ),
        ]

    def __str__(self):
        return f'{self.materia_en_plan or self.comision} en {self.solicitud}'

    @property
    def fila(self):
        """La MateriaEnPlan, o una FilaOptativa de la comisión con la misma interfaz."""
        if self.materia_en_plan_id:
            return self.materia_en_plan
        c = self.comision
        return FilaOptativa(c.materia_optativa, c.carrera, clave=f'com-{c.pk}', planes=list(c.planes.all()))


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


class Comision(models.Model):
    """Dictado de una materia en una carrera durante un período (año + cuatrimestre).
    - Materia de plan: la crea el informe cuatrimestral de comisiones y la completa el
      director del departamento responsable.
    - Materia de la bolsa de optativas: la crea y completa el director de carrera al pedir
      el dictado; entra en el informe del departamento que la dicta."""
    materia = models.ForeignKey(
        Materia, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='comisiones', verbose_name='Materia de plan',
    )
    materia_optativa = models.ForeignKey(
        MateriaOptativa, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='comisiones', verbose_name='Materia de la bolsa de optativas',
    )
    carrera = models.ForeignKey(
        Carrera, on_delete=models.PROTECT,
        related_name='comisiones', verbose_name='Carrera',
    )
    anio = models.PositiveSmallIntegerField(verbose_name='Año académico')
    cuatrimestre = models.PositiveSmallIntegerField(
        choices=MateriaEnPlan.CUATRIMESTRE_CHOICES, verbose_name='Período',
    )
    departamento = models.CharField(
        max_length=50, blank=True,
        choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento responsable',
        help_text='El que informa la comisión. Si la dicta un externo, el de la carrera.',
    )
    planes = models.ManyToManyField(
        PlanEstudio, blank=True,
        related_name='comisiones', verbose_name='Planes de estudio asociados',
    )
    condicion = models.CharField(
        max_length=20, blank=True,
        choices=CONDICION_CHOICES, verbose_name='Condición de cursada',
    )
    credito_horario = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Crédito horario (hs)',
    )
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='comisiones_solicitadas', verbose_name='Solicitada por',
    )
    se_dicta = models.BooleanField(
        default=True, verbose_name='Se dicta',
        help_text='Optativas: el director de carrera la quita si no se dicta en el período. '
                  'Queda registrada (no se vuelve a crear) pero no entra en el informe.',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    class Meta:
        ordering = ['-anio', 'cuatrimestre', 'materia__nombre', 'materia_optativa__nombre', 'carrera__nombre']
        verbose_name = 'Comisión'
        verbose_name_plural = 'Comisiones'
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(materia__isnull=False, materia_optativa__isnull=True) |
                    Q(materia__isnull=True, materia_optativa__isnull=False)
                ),
                name='comision_materia_o_optativa',
            ),
            models.UniqueConstraint(
                fields=['materia', 'carrera', 'anio', 'cuatrimestre'],
                condition=Q(materia__isnull=False),
                name='comision_unica_materia_carrera_periodo',
            ),
            models.UniqueConstraint(
                fields=['materia_optativa', 'carrera', 'anio'],
                condition=Q(materia_optativa__isnull=False),
                name='comision_unica_optativa_carrera_anio',
            ),
        ]

    def __str__(self):
        return f'{self.nombre_materia} — {self.carrera.nombre} — {self.periodo_display}'

    @staticmethod
    def departamento_responsable(departamento_dictante, carrera):
        if not departamento_dictante or departamento_dictante == 'Externo':
            return carrera.departamento
        return departamento_dictante

    @property
    def es_optativa_bolsa(self):
        return self.materia_optativa_id is not None

    @property
    def materia_obj(self):
        return self.materia_optativa if self.materia_optativa_id else self.materia

    @property
    def nombre_materia(self):
        return self.materia_obj.nombre

    @property
    def codigo_materia(self):
        return self.materia_obj.codigo

    @property
    def periodo_display(self):
        return f'{self.get_cuatrimestre_display()} {self.anio}'

    @property
    def departamento_dictante(self):
        if self.es_optativa_bolsa:
            return self.materia_optativa.departamento or self.carrera.departamento
        return self.departamento

    @property
    def requiere_servicio(self):
        """Optativa que dicta otro departamento (o un externo): va en la solicitud de servicio."""
        return self.es_optativa_bolsa and self.departamento_dictante != self.carrera.departamento

    @property
    def esta_completa(self):
        return bool(self.condicion and self.credito_horario and self.equipo.all())


class MiembroComision(models.Model):
    comision = models.ForeignKey(
        Comision, on_delete=models.CASCADE,
        related_name='equipo',
    )
    nombre = models.CharField(max_length=200, verbose_name='Apellido y Nombre')
    dni = models.CharField(max_length=20, blank=True, verbose_name='DNI')
    funcion = models.CharField(max_length=20, choices=FUNCION_CHOICES, verbose_name='Función')
    cargo = models.CharField(max_length=20, blank=True, choices=CARGO_CHOICES, verbose_name='Cargo')
    dedicacion = models.CharField(max_length=20, blank=True, choices=DEDICACION_CHOICES, verbose_name='Dedicación')
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'Miembro del equipo docente (comisión)'
        verbose_name_plural = 'Equipo docente (comisión)'

    def __str__(self):
        return f'{self.nombre} ({self.get_funcion_display()})'


class SolicitudInformeComisiones(models.Model):
    """Pedido de administración para que los departamentos informen las comisiones de un período."""
    CUATRIMESTRE_CHOICES = [
        (1, '1° Cuatrimestre + Anuales'),
        (2, '2° Cuatrimestre'),
    ]
    anio = models.PositiveSmallIntegerField(verbose_name='Año académico')
    cuatrimestre = models.PositiveSmallIntegerField(choices=CUATRIMESTRE_CHOICES, verbose_name='Período')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_informe_comisiones', verbose_name='Solicitante',
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        unique_together = [('anio', 'cuatrimestre')]
        ordering = ['-anio', '-cuatrimestre']
        verbose_name = 'Solicitud de informe de comisiones'
        verbose_name_plural = 'Solicitudes de informe de comisiones'

    def __str__(self):
        return f'Informe de comisiones — {self.get_cuatrimestre_display()} {self.anio}'

    @property
    def cuatrimestres(self):
        """Cuatrimestres de comisión que abarca: el 1° incluye las anuales."""
        return [1, 3] if self.cuatrimestre == 1 else [2]


class InformeComisionesEnviado(models.Model):
    """Registra que un departamento envió su informe de comisiones para una solicitud."""
    solicitud = models.ForeignKey(
        SolicitudInformeComisiones, on_delete=models.CASCADE,
        related_name='informes_enviados', verbose_name='Solicitud',
    )
    departamento = models.CharField(max_length=50, choices=DEPARTAMENTO_CHOICES, verbose_name='Departamento')
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='informes_comisiones_enviados', verbose_name='Director',
    )
    fecha_envio = models.DateTimeField(verbose_name='Fecha de envío')

    class Meta:
        unique_together = [('solicitud', 'departamento')]
        ordering = ['-fecha_envio']
        verbose_name = 'Informe de comisiones enviado'
        verbose_name_plural = 'Informes de comisiones enviados'

    def __str__(self):
        return f'Informe de comisiones {self.departamento} — {self.solicitud}'
