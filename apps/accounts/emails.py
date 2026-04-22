from django.core.mail import send_mail
from django.conf import settings


def _es_email_valido(email):
    return bool(email and email.lower().endswith('@unsl.edu.ar'))


def enviar_bienvenida(usuario, password_temporal):
    """Envía credenciales al usuario recién creado."""
    if not _es_email_valido(usuario.email):
        return
    asunto = 'Bienvenido/a al Sistema de Gestión Docente — UNSL'
    mensaje = (
        f'Hola {usuario.get_full_name() or usuario.username},\n\n'
        f'Tu cuenta fue creada en el Sistema de Gestión Docente de la '
        f'Facultad de Cs. Físico Matemáticas y Naturales (UNSL).\n\n'
        f'Tus credenciales de acceso son:\n'
        f'  Usuario:    {usuario.username}\n'
        f'  Contraseña: {password_temporal}\n\n'
        f'Por seguridad, cambiá tu contraseña en tu primer ingreso.\n\n'
        f'Sistema de Gestión Docente — UNSL'
    )
    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
    except Exception as exc:
        # Loguear sin interrumpir el flujo
        import logging
        logging.getLogger(__name__).warning('No se pudo enviar email de bienvenida: %s', exc)


def enviar_reset_password(usuario, nueva_password):
    """Notifica al usuario que su contraseña fue restablecida por un admin."""
    if not _es_email_valido(usuario.email):
        return
    asunto = 'Contraseña restablecida — Sistema de Gestión Docente UNSL'
    mensaje = (
        f'Hola {usuario.get_full_name() or usuario.username},\n\n'
        f'Un administrador restableció tu contraseña.\n\n'
        f'Tu nueva contraseña temporal es:\n'
        f'  {nueva_password}\n\n'
        f'Ingresá al sistema y cambiala a la brevedad.\n\n'
        f'Sistema de Gestión Docente — UNSL'
    )
    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('No se pudo enviar email de reset: %s', exc)
