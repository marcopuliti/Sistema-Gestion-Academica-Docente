from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    DOCENTE = 'docente'
    JEFE_DEPARTAMENTO = 'jefe_departamento'
    ADMINISTRADOR = 'administrador'

    ROL_CHOICES = [
        (DOCENTE, 'Docente'),
        (JEFE_DEPARTAMENTO, 'Jefe de Departamento'),
        (ADMINISTRADOR, 'Administrador'),
    ]

    rol = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        default=DOCENTE,
        verbose_name='Rol',
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
    def es_jefe(self):
        return self.rol == self.JEFE_DEPARTAMENTO

    @property
    def es_administrador(self):
        return self.rol == self.ADMINISTRADOR

    @property
    def puede_revisar(self):
        return self.rol in (self.JEFE_DEPARTAMENTO, self.ADMINISTRADOR)
