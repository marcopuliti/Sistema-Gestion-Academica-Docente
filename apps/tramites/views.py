from django.shortcuts import render, redirect

from apps.solicitudes.models import SolicitudProtocolizacion
from apps.tramites.models import EstadoTramite


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, 'tramites/landing.html')

    user = request.user

    if user.es_director_departamento:
        return redirect('solicitudes:lista_departamento')

    if user.puede_revisar:
        solicitudes = SolicitudProtocolizacion.objects.all()
    else:
        solicitudes = SolicitudProtocolizacion.objects.filter(usuario=user)

    context = {
        'total_solicitudes': solicitudes.count(),
        'pendientes_solicitudes': solicitudes.filter(estado=EstadoTramite.PENDIENTE).count(),
        'ultimas_solicitudes': solicitudes[:5],
    }
    return render(request, 'tramites/dashboard.html', context)
