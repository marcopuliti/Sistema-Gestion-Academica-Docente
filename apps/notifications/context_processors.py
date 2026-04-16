from .models import Notificacion


def notificaciones_no_leidas(request):
    if request.user.is_authenticated:
        cantidad = Notificacion.objects.filter(
            destinatario=request.user, leida=False
        ).count()
        return {'notificaciones_no_leidas': cantidad}
    return {'notificaciones_no_leidas': 0}
