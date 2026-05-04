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
    if destinatario.email and destinatario.email.lower().endswith('@unsl.edu.ar'):
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


def notificar_nuevo_tramite(tramite, tipo_tramite, url=''):
    """Notifica a administradores y director del departamento cuando llega un trámite nuevo."""
    docente = tramite.usuario
    nombre_docente = docente.get_full_name() if docente else getattr(tramite, 'nombre_docente', 'Docente anónimo')
    titulo = f"Nuevo trámite: {tipo_tramite}"
    mensaje = (
        f"El docente {nombre_docente} ha enviado un nuevo trámite:\n"
        f"Tipo: {tipo_tramite}\n"
        f"Fecha: {tramite.fecha_creacion.strftime('%d/%m/%Y %H:%M')}\n\n"
        f"Ingresá al sistema para revisarlo."
    )
    destinatarios = User.objects.filter(rol__in=['secretario', 'direccion_academica'], is_active=True)
    # Notificar también al director del departamento correspondiente
    departamento = (docente.departamento if docente else None) or getattr(tramite, 'departamento_docente', '')
    if departamento:
        directores = User.objects.filter(
            rol='director_departamento',
            departamento=departamento,
            is_active=True,
        )
        destinatarios = destinatarios | directores
    for dest in destinatarios.distinct():
        _crear_notificacion(dest, 'nuevo_tramite', titulo, mensaje, url=url)


def notificar_cambio_estado(tramite, tipo_tramite, url=''):
    """Notifica al docente cuando cambia el estado de su trámite."""
    estado_display = ESTADOS_DISPLAY.get(tramite.estado, tramite.estado)
    titulo = f"Tu trámite fue actualizado: {estado_display}"
    mensaje = (
        f"El estado de tu {tipo_tramite} fue actualizado a: {estado_display}.\n"
    )
    if tramite.comentarios_revision:
        mensaje += f"\nComentarios del revisor:\n{tramite.comentarios_revision}\n"
    mensaje += "\nIngresá al sistema para ver los detalles."

    _crear_notificacion(tramite.usuario, 'cambio_estado', titulo, mensaje, url=url)
