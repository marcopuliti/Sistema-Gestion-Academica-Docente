from django.shortcuts import render

from apps.informes.models import InformeActividadAnual
from apps.planillas.models import PlanificacionActividades
from apps.solicitudes.models import SolicitudProtocolizacion
from apps.tramites.models import EstadoTramite


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, 'tramites/landing.html')

    user = request.user

    if user.puede_revisar:
        informes = InformeActividadAnual.objects.all()
        planillas = PlanificacionActividades.objects.all()
        solicitudes = SolicitudProtocolizacion.objects.all()
    else:
        informes = InformeActividadAnual.objects.filter(usuario=user)
        planillas = PlanificacionActividades.objects.filter(usuario=user)
        solicitudes = SolicitudProtocolizacion.objects.filter(usuario=user)

    context = {
        'total_informes': informes.count(),
        'total_planillas': planillas.count(),
        'total_solicitudes': solicitudes.count(),
        'pendientes_informes': informes.filter(estado=EstadoTramite.PENDIENTE).count(),
        'pendientes_planillas': planillas.filter(estado=EstadoTramite.PENDIENTE).count(),
        'pendientes_solicitudes': solicitudes.filter(estado=EstadoTramite.PENDIENTE).count(),
        'ultimos_informes': informes[:5],
        'ultimas_planillas': planillas[:5],
        'ultimas_solicitudes': solicitudes[:5],
    }
    return render(request, 'tramites/dashboard.html', context)
