from django.db import models
from apps.tramites.models import TramiteBase

ANNO_CHOICES = [(str(y), str(y)) for y in range(2020, 2035)]

CARGO_CHOICES = [
    ('PAD', 'Profesor Adjunto (PAD)'),
    ('PAS', 'Profesor Asociado (PAS)'),
    ('PTI', 'Profesor Titular (PTI)'),
    ('JTP', 'Jefe de Trabajos Prácticos (JTP)'),
    ('AY1', 'Ayudante de Primera (AY1)'),
    ('AY2', 'Ayudante de Segunda (AY2)'),
]

DEDICACION_CHOICES = [
    ('exclusiva', 'Exclusiva'),
    ('semi_exclusiva', 'Semi Exclusiva'),
    ('simple', 'Simple'),
]

DESIGNACION_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('interino', 'Interino'),
    ('contratado', 'Contratado'),
]


class PlanificacionActividades(TramiteBase):
    anno = models.CharField(max_length=4, choices=ANNO_CHOICES, verbose_name='Año')
    fecha_desde = models.DateField(verbose_name='Período desde')
    fecha_hasta = models.DateField(verbose_name='Período hasta')

    # Datos del cargo
    cargo = models.CharField(max_length=10, choices=CARGO_CHOICES, verbose_name='Cargo')
    dedicacion = models.CharField(max_length=20, choices=DEDICACION_CHOICES, verbose_name='Dedicación')
    designacion = models.CharField(max_length=20, choices=DESIGNACION_CHOICES, verbose_name='Designación')
    area = models.CharField(max_length=150, blank=True, verbose_name='Área')

    # A.1 Actividades curriculares de grado y pregrado
    a1_descripcion = models.TextField(verbose_name='A.1 — Descripción', help_text='Actividades curriculares de grado y pregrado (asignaturas de carreras).')
    a1_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    a1_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # A.2 Cursos extracurriculares
    a2_descripcion = models.TextField(blank=True, verbose_name='A.2 — Descripción', help_text='Cursos extracurriculares.')
    a2_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    a2_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # A.3 Tareas de Posgrado
    a3_descripcion = models.TextField(blank=True, verbose_name='A.3 — Descripción', help_text='Tareas de posgrado.')
    a3_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    a3_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # A.4 Formación de Recursos Humanos
    a4_descripcion = models.TextField(blank=True, verbose_name='A.4 — Descripción', help_text='Formación de recursos humanos.')
    a4_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    a4_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # B. Investigación
    b_descripcion = models.TextField(blank=True, verbose_name='B — Descripción', help_text='Investigación.')
    b_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    b_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # C. Transferencias o Servicios
    c_descripcion = models.TextField(blank=True, verbose_name='C — Descripción', help_text='Transferencias o servicios.')
    c_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    c_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # D. Extensión Universitaria
    d_descripcion = models.TextField(blank=True, verbose_name='D — Descripción', help_text='Extensión universitaria.')
    d_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    d_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # E. Perfeccionamiento
    e_descripcion = models.TextField(blank=True, verbose_name='E — Descripción', help_text='Perfeccionamiento.')
    e_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    e_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # F. Gobierno y Gestión
    f_descripcion = models.TextField(blank=True, verbose_name='F — Descripción', help_text='Gobierno y gestión.')
    f_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    f_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    # G. Otros
    g_descripcion = models.TextField(blank=True, verbose_name='G — Descripción', help_text='Otros.')
    g_hs_1c = models.PositiveIntegerField(default=0, verbose_name='Hs 1º Cuat.')
    g_hs_2c = models.PositiveIntegerField(default=0, verbose_name='Hs 2º Cuat.')

    class Meta(TramiteBase.Meta):
        verbose_name = 'Planificación de Actividades'
        verbose_name_plural = 'Planificaciones de Actividades'

    def __str__(self):
        return f"Planificación {self.anno} — {self.get_nombre_docente}"

    # Totales por sección
    @property
    def total_a_1c(self):
        return self.a1_hs_1c + self.a2_hs_1c + self.a3_hs_1c + self.a4_hs_1c

    @property
    def total_a_2c(self):
        return self.a1_hs_2c + self.a2_hs_2c + self.a3_hs_2c + self.a4_hs_2c

    @property
    def total_1c(self):
        return (self.a1_hs_1c + self.a2_hs_1c + self.a3_hs_1c + self.a4_hs_1c +
                self.b_hs_1c + self.c_hs_1c + self.d_hs_1c +
                self.e_hs_1c + self.f_hs_1c + self.g_hs_1c)

    @property
    def total_2c(self):
        return (self.a1_hs_2c + self.a2_hs_2c + self.a3_hs_2c + self.a4_hs_2c +
                self.b_hs_2c + self.c_hs_2c + self.d_hs_2c +
                self.e_hs_2c + self.f_hs_2c + self.g_hs_2c)

    @property
    def resumen_items(self):
        """Lista de (label, hs_1c, hs_2c) para la tabla resumen."""
        return [
            ('A. Docencia', self.total_a_1c, self.total_a_2c),
            ('A.1 Act. curriculares grado/pregrado', self.a1_hs_1c, self.a1_hs_2c),
            ('A.2 Cursos extracurriculares', self.a2_hs_1c, self.a2_hs_2c),
            ('A.3 Tareas de posgrado', self.a3_hs_1c, self.a3_hs_2c),
            ('A.4 Formación RRHH', self.a4_hs_1c, self.a4_hs_2c),
            ('B. Investigación', self.b_hs_1c, self.b_hs_2c),
            ('C. Transferencias/Servicios', self.c_hs_1c, self.c_hs_2c),
            ('D. Extensión universitaria', self.d_hs_1c, self.d_hs_2c),
            ('E. Perfeccionamiento', self.e_hs_1c, self.e_hs_2c),
            ('F. Gobierno y gestión', self.f_hs_1c, self.f_hs_2c),
            ('G. Otros', self.g_hs_1c, self.g_hs_2c),
            ('TOTAL', self.total_1c, self.total_2c),
        ]


# Alias para compatibilidad con código existente (dashboard, etc.)
PlanillaActividades = PlanificacionActividades
