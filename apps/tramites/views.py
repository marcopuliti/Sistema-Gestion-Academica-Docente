from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render, redirect

from apps.notifications.models import Notificacion
from apps.planes.models import (
    AnioDictado, InformeTribunalesEnviado, MateriaEnPlan,
    SolicitudInformeTribunal, TribunalExaminador,
)
from apps.solicitudes.models import SolicitudProtocolizacion, SolicitudTaller
from apps.tramites.models import EstadoTramite


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, 'tramites/landing.html')

    user = request.user

    if user.es_director_departamento:
        return _dashboard_director(request, user)

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


def _dashboard_director(request, user):
    departamento = user.departamento
    dep_q = Q(usuario__departamento=departamento) | Q(departamento_docente=departamento)
    estados_revision = [EstadoTramite.PENDIENTE, EstadoTramite.OBSERVADA]

    por_revisar = (
        SolicitudProtocolizacion.objects.filter(dep_q, estado__in=estados_revision).count() +
        SolicitudTaller.objects.filter(dep_q, estado__in=estados_revision).count()
    )

    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    meps_activos = (
        MateriaEnPlan.objects
        .filter(Q(plan__vigente=True) | Q(plan__activo=True))
        .filter(
            Q(plan__carrera__departamento=departamento, es_servicio=False) |
            Q(departamento_dictante=departamento)
        )
        .filter(Exists(ano_qs))
    )
    total_tribunales = meps_activos.count()
    sin_tribunal = meps_activos.filter(tribunal__isnull=True).count()
    mep_ids = meps_activos.values_list('id', flat=True)
    con_datos_faltantes = TribunalExaminador.objects.filter(
        materia_en_plan_id__in=mep_ids,
        presidente_nombre='',
    ).count()
    pendientes_sinc = TribunalExaminador.objects.filter(
        materia_en_plan_id__in=mep_ids,
        pendiente_sincronizacion=True,
    ).count()

    solicitud = SolicitudInformeTribunal.objects.filter(activa=True).first()
    informe_enviado = (
        InformeTribunalesEnviado.objects
        .filter(departamento=departamento)
        .select_related('solicitud')
        .order_by('-fecha_envio')
        .first()
    )
    ya_enviado = (
        solicitud is not None and
        informe_enviado is not None and
        informe_enviado.solicitud_id == solicitud.pk
    )

    return render(request, 'tramites/dashboard_director.html', {
        'departamento': departamento,
        'por_revisar': por_revisar,
        'total_tribunales': total_tribunales,
        'sin_tribunal': sin_tribunal,
        'con_datos_faltantes': con_datos_faltantes,
        'pendientes_sinc': pendientes_sinc,
        'solicitud_informe_activa': solicitud is not None and not ya_enviado,
        'informe_enviado': informe_enviado,
        'ultimas_notificaciones': Notificacion.objects.filter(destinatario=user).order_by('-fecha')[:5],
    })
