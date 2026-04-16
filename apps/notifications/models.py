from django.db import models
from django.conf import settings


class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('nuevo_tramite', 'Nuevo trámite enviado'),
        ('cambio_estado', 'Cambio de estado'),
        ('comentario', 'Nuevo comentario'),
    ]

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        verbose_name='Destinatario',
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200, verbose_name='Título')
    mensaje = models.TextField(verbose_name='Mensaje')
    leida = models.BooleanField(default=False, verbose_name='Leída')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    url = models.CharField(max_length=300, blank=True, verbose_name='Enlace')

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.titulo} → {self.destinatario.get_full_name()}"
