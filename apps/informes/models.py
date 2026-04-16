from django.db import models
from apps.tramites.models import TramiteBase

ANNO_CHOICES = [(str(y), str(y)) for y in range(2020, 2035)]


class InformeActividadAnual(TramiteBase):
    anno_academico = models.CharField(
        max_length=4,
        choices=ANNO_CHOICES,
        verbose_name='Año académico',
    )

    # Datos del docente en el momento del informe
    categoria = models.CharField(max_length=100, verbose_name='Categoría docente')
    dedicacion = models.CharField(
        max_length=50,
        choices=[
            ('exclusiva', 'Dedicación Exclusiva'),
            ('semi_exclusiva', 'Semi Exclusiva'),
            ('simple', 'Dedicación Simple'),
        ],
        verbose_name='Dedicación',
    )

    # Actividades de Docencia
    materias_dictadas = models.TextField(
        verbose_name='Materias / Asignaturas dictadas',
        help_text='Listá cada materia con carrera, año y carga horaria.',
    )
    carga_horaria_docencia = models.PositiveIntegerField(
        verbose_name='Carga horaria total de docencia (hs/semana)',
    )

    # Actividades de Investigación
    actividades_investigacion = models.TextField(
        blank=True,
        verbose_name='Actividades de investigación',
        help_text='Proyectos, publicaciones, dirección de tesis, etc.',
    )

    # Actividades de Extensión
    actividades_extension = models.TextField(
        blank=True,
        verbose_name='Actividades de extensión',
        help_text='Proyectos de extensión, vinculación con la comunidad, etc.',
    )

    # Actividades de Gestión
    actividades_gestion = models.TextField(
        blank=True,
        verbose_name='Actividades de gestión',
        help_text='Cargos de gestión, comisiones, etc.',
    )

    # Formación
    actividades_formacion = models.TextField(
        blank=True,
        verbose_name='Formación y capacitación',
        help_text='Cursos, posgrados, congresos asistidos, etc.',
    )

    observaciones = models.TextField(blank=True, verbose_name='Observaciones adicionales')

    class Meta(TramiteBase.Meta):
        verbose_name = 'Informe de Actividad Anual'
        verbose_name_plural = 'Informes de Actividad Anual'

    def __str__(self):
        return f"Informe {self.anno_academico} - {self.get_nombre_docente}"
