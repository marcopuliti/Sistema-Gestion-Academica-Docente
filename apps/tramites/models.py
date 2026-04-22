from django.db import models
from django.conf import settings

DEPARTAMENTO_CHOICES = [
    ('', '---------'),
    ('Matemática', 'Matemática'),
    ('Física', 'Física'),
    ('Geología', 'Geología'),
    ('Electrónica', 'Electrónica'),
    ('Informática', 'Informática'),
    ('Minería', 'Minería'),
]


class CalendarioAcademico(models.Model):
    """Fechas de inicio/fin de cada cuatrimestre por año, configuradas por el superusuario."""
    anno = models.PositiveIntegerField(unique=True, verbose_name='Año')
    fecha_inicio_1c = models.DateField(verbose_name='Inicio 1° Cuatrimestre')
    fecha_fin_1c = models.DateField(verbose_name='Fin 1° Cuatrimestre')
    fecha_inicio_2c = models.DateField(verbose_name='Inicio 2° Cuatrimestre')
    fecha_fin_2c = models.DateField(verbose_name='Fin 2° Cuatrimestre')
    semanas_cuatrimestre = models.PositiveIntegerField(default=15, verbose_name='Semanas por cuatrimestre')
    semanas_anual = models.PositiveIntegerField(default=30, verbose_name='Semanas anuales')

    class Meta:
        ordering = ['-anno']
        verbose_name = 'Calendario Académico'
        verbose_name_plural = 'Calendarios Académicos'

    def __str__(self):
        return f'Calendario {self.anno}'


class EstadoTramite(models.TextChoices):
    PENDIENTE = 'pendiente', 'Pendiente'
    EN_REVISION = 'en_revision', 'En Revisión'
    APROBADO = 'aprobado', 'Aprobado'
    RECHAZADO = 'rechazado', 'Rechazado'


class TramiteBase(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name='Docente',
    )
    # Datos del docente para envíos sin cuenta (anónimos)
    nombre_docente     = models.CharField(max_length=200, blank=True, verbose_name='Nombre y apellido')
    legajo_docente     = models.CharField(max_length=20,  blank=True, verbose_name='Legajo')
    departamento_docente = models.CharField(max_length=150, blank=True, verbose_name='Departamento')
    email_docente      = models.EmailField(blank=True, verbose_name='Email')
    estado = models.CharField(
        max_length=20,
        choices=EstadoTramite.choices,
        default=EstadoTramite.PENDIENTE,
        verbose_name='Estado',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Última actualización')
    comentarios_revision = models.TextField(
        blank=True,
        verbose_name='Comentarios de revisión',
        help_text='Observaciones del revisor.',
    )
    revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_revisados',
        verbose_name='Revisado por',
    )

    class Meta:
        abstract = True
        ordering = ['-fecha_creacion']

    @property
    def get_nombre_docente(self):
        """Nombre completo: usuario autenticado o campo libre."""
        if self.usuario_id:
            return self.usuario.get_full_name() or self.usuario.username
        return self.nombre_docente

    @property
    def get_legajo_docente(self):
        if self.usuario_id:
            return getattr(self.usuario, 'legajo', self.legajo_docente)
        return self.legajo_docente

    @property
    def estado_badge(self):
        clases = {
            EstadoTramite.PENDIENTE: 'bg-warning text-dark',
            EstadoTramite.EN_REVISION: 'bg-info text-dark',
            EstadoTramite.APROBADO: 'bg-success',
            EstadoTramite.RECHAZADO: 'bg-danger',
        }
        return clases.get(self.estado, 'bg-secondary')
