import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    DOCENTE = 'docente'
    SECRETARIO = 'secretario'
    DIRECCION_ACADEMICA = 'direccion_academica'
    DPTO_ESTUDIANTES = 'dpto_estudiantes'
    DIRECTOR_DEPARTAMENTO = 'director_departamento'
    DIRECTOR_CARRERA = 'director_carrera'

    ROL_CHOICES = [
        (DOCENTE, 'Docente'),
        (SECRETARIO, 'Secretario'),
        (DIRECCION_ACADEMICA, 'Dirección Académica'),
        (DPTO_ESTUDIANTES, 'Departamento de Estudiantes'),
        (DIRECTOR_DEPARTAMENTO, 'Director de Departamento'),
        (DIRECTOR_CARRERA, 'Director de Carrera'),
    ]

    rol = models.CharField(
        max_length=30,
        choices=ROL_CHOICES,
        default=DOCENTE,
        verbose_name='Rol',
    )
    email = models.EmailField(
        verbose_name='Correo electrónico',
        blank=True,
    )
    departamento = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Departamento',
    )
    carrera = models.ForeignKey(
        'planes.Carrera',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='directores',
        verbose_name='Carrera',
    )
    legajo = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Legajo',
    )
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Teléfono',
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_rol_display()})"

    @property
    def es_docente(self):
        return self.rol == self.DOCENTE

    @property
    def es_secretario(self):
        return self.rol == self.SECRETARIO

    @property
    def es_direccion_academica(self):
        return self.rol == self.DIRECCION_ACADEMICA

    @property
    def es_dpto_estudiantes(self):
        return self.rol == self.DPTO_ESTUDIANTES

    @property
    def es_administrador(self):
        """Cualquier rol con acceso administrativo (total o parcial)."""
        return self.rol in (self.SECRETARIO, self.DIRECCION_ACADEMICA, self.DPTO_ESTUDIANTES)

    @property
    def puede_admin_general(self):
        """Secretario y Dirección Académica — acceso administrativo completo excepto usuarios."""
        return self.rol in (self.SECRETARIO, self.DIRECCION_ACADEMICA)

    @property
    def puede_gestionar_usuarios(self):
        """Solo Secretario puede crear/editar/desactivar usuarios."""
        return self.rol == self.SECRETARIO

    @property
    def es_director_departamento(self):
        return self.rol == self.DIRECTOR_DEPARTAMENTO

    @property
    def es_director_carrera(self):
        return self.rol == self.DIRECTOR_CARRERA

    @property
    def puede_revisar(self):
        return self.rol in (self.SECRETARIO, self.DIRECCION_ACADEMICA)


class TokenVerificacionEmail(models.Model):
    usuario = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='token_verificacion',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    EXPIRACION_HORAS = 24

    def esta_expirado(self):
        delta = timezone.now() - self.creado_en
        return delta.total_seconds() > self.EXPIRACION_HORAS * 3600

    def __str__(self):
        return f'Token verificación — {self.usuario.email}'
