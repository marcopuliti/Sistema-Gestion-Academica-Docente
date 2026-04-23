import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    DOCENTE = 'docente'
    ADMINISTRADOR = 'administrador'
    DIRECTOR_DEPARTAMENTO = 'director_departamento'

    ROL_CHOICES = [
        (DOCENTE, 'Docente'),
        (ADMINISTRADOR, 'Administrador'),
        (DIRECTOR_DEPARTAMENTO, 'Director de Departamento'),
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
    def es_administrador(self):
        return self.rol == self.ADMINISTRADOR

    @property
    def es_director_departamento(self):
        return self.rol == self.DIRECTOR_DEPARTAMENTO

    @property
    def puede_revisar(self):
        return self.rol == self.ADMINISTRADOR


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
