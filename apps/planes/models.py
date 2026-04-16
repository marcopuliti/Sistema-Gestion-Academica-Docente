from django.db import models


class Carrera(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=250, verbose_name='Nombre')
    duracion_anos = models.PositiveSmallIntegerField(verbose_name='Duración (años)')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Carrera'
        verbose_name_plural = 'Carreras'

    def __str__(self):
        return f'{self.nombre} ({self.codigo})'


class PlanEstudio(models.Model):
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.CASCADE,
        related_name='planes',
        verbose_name='Carrera',
    )
    codigo = models.CharField(max_length=20, verbose_name='Código de plan')  # ej: "28/12"
    vigente = models.BooleanField(default=True, verbose_name='Vigente')
    materias = models.ManyToManyField(
        'Materia',
        through='MateriaEnPlan',
        related_name='planes',
        verbose_name='Materias',
    )

    class Meta:
        unique_together = [('carrera', 'codigo')]
        ordering = ['carrera', 'codigo']
        verbose_name = 'Plan de Estudio'
        verbose_name_plural = 'Planes de Estudio'

    def __str__(self):
        return f'Plan {self.codigo} — {self.carrera.nombre}'


class Materia(models.Model):
    codigo = models.CharField(max_length=30, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=250, verbose_name='Nombre')

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
        Materia,
        on_delete=models.CASCADE,
        related_name='en_planes',
        verbose_name='Materia',
    )
    plan = models.ForeignKey(
        PlanEstudio,
        on_delete=models.CASCADE,
        related_name='materias_en_plan',
        verbose_name='Plan de estudio',
    )
    # Nombre en este plan (puede diferir del nombre canónico en Materia)
    nombre = models.CharField(
        max_length=250,
        blank=True,
        verbose_name='Nombre en el plan',
        help_text='Si está vacío se usa el nombre de la materia.',
    )
    es_optativa = models.BooleanField(
        default=False,
        verbose_name='Es optativa',
    )
    hs_totales = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Horas totales',
    )
    tope_hs = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Tope de horas',
        help_text='Límite de horas para esta materia. Opcional.',
    )
    ano = models.PositiveSmallIntegerField(verbose_name='Año')
    cuatrimestre = models.PositiveSmallIntegerField(
        choices=CUATRIMESTRE_CHOICES,
        verbose_name='Cuatrimestre',
    )

    class Meta:
        unique_together = [('materia', 'plan')]
        ordering = ['ano', 'cuatrimestre', 'materia__nombre']
        verbose_name = 'Materia en Plan'
        verbose_name_plural = 'Materias en Plan'

    def get_nombre(self):
        """Nombre efectivo: el del plan si existe, sino el canónico de la materia."""
        return self.nombre or self.materia.nombre

    def __str__(self):
        return f'{self.get_nombre()} — Año {self.ano} ({self.get_cuatrimestre_display()})'
