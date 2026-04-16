from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Notificacion

User = get_user_model()

ESTADOS_DISPLAY = {
    'pendiente': 'Pendiente',
    'en_revision': 'En Revisión',
    'aprobado': 'Aprobado',
    'rechazado': 'Rechazado',
}


def _crear_notificacion(destinatario, tipo, titulo, mensaje, url=''):
    Notificacion.objects.create(
        destinatario=destinatario,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
    )
    if destinatario.email:
        try:
            send_mail(
                subject=titulo,
                message=mensaje,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario.email],
                fail_silently=True,
            )
        except Exception:
            pass


def notificar_nuevo_tramite(tramite, tipo_tramite):
    """Notifica a los revisores cuando un docente envía un trámite nuevo."""
    revisores = User.objects.filter(
        rol__in=['administrador'],
        is_active=True,
    )
    docente = tramite.usuario
    titulo = f"Nuevo trámite: {tipo_tramite}"
    mensaje = (
        f"El docente {docente.get_full_name()} ha enviado un nuevo trámite:\n"
        f"Tipo: {tipo_tramite}\n"
        f"Fecha: {tramite.fecha_creacion.strftime('%d/%m/%Y %H:%M')}\n\n"
        f"Ingresá al sistema para revisarlo."
    )
    for revisor in revisores:
        _crear_notificacion(revisor, 'nuevo_tramite', titulo, mensaje)


def notificar_cambio_estado(tramite, tipo_tramite):
    """Notifica al docente cuando cambia el estado de su trámite."""
    estado_display = ESTADOS_DISPLAY.get(tramite.estado, tramite.estado)
    titulo = f"Tu trámite fue actualizado: {estado_display}"
    mensaje = (
        f"El estado de tu {tipo_tramite} fue actualizado a: {estado_display}.\n"
    )
    if tramite.comentarios_revision:
        mensaje += f"\nComentarios del revisor:\n{tramite.comentarios_revision}\n"
    mensaje += "\nIngresá al sistema para ver los detalles."

    _crear_notificacion(tramite.usuario, 'cambio_estado', titulo, mensaje)
