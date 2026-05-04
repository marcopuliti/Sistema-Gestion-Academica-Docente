from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render, redirect

from apps.notifications.models import Notificacion
from apps.planes.models import (
    AnioDictado, InformeTribunalesEnviado, MateriaEnPlan,
    SolicitudCambioItem, SolicitudCambioTribunal, SolicitudInformeTribunal, TribunalExaminador,
)
from apps.solicitudes.models import SolicitudProtocolizacion, SolicitudTaller
from apps.tramites.models import EstadoTramite


def dashboard(request):
    if not request.user.is_authenticated:
        from django.urls import reverse
        return redirect(reverse('accounts:login'))

    user = request.user

    if user.es_director_departamento:
        return _dashboard_director(request, user)

    if user.es_administrador:
        return _dashboard_admin(request, user)

    solicitudes = SolicitudProtocolizacion.objects.filter(usuario=user)
    context = {
        'total_solicitudes': solicitudes.count(),
        'pendientes_solicitudes': solicitudes.filter(estado=EstadoTramite.PENDIENTE).count(),
        'ultimas_solicitudes': solicitudes[:5],
    }
    return render(request, 'tramites/dashboard.html', context)


def _dashboard_admin(request, user):
    from django.utils import timezone as tz
    todas_meps = MateriaEnPlan.objects.filter(es_optativa=False)
    total_meps = todas_meps.count()
    sin_tribunal = todas_meps.filter(tribunal__isnull=True).count()
    incompleto = TribunalExaminador.objects.filter(presidente_nombre='').count()
    completo = total_meps - sin_tribunal - incompleto

    solicitudes_prot = SolicitudProtocolizacion.objects.all()
    pendientes_prot = solicitudes_prot.filter(estado=EstadoTramite.PENDIENTE).count()

    cambios_enviados = SolicitudCambioTribunal.objects.filter(estado='enviada').count()
    ultimos_cambios = (
        SolicitudCambioTribunal.objects
        .filter(estado='enviada')
        .select_related('director')
        .order_by('-fecha_creacion')[:5]
    )

    solicitud_informe = SolicitudInformeTribunal.objects.filter(activa=True).first()

    return render(request, 'tramites/dashboard_admin.html', {
        'total_meps': total_meps,
        'sin_tribunal': sin_tribunal,
        'incompleto': incompleto,
        'completo': completo,
        'total_solicitudes': solicitudes_prot.count(),
        'pendientes_prot': pendientes_prot,
        'cambios_enviados': cambios_enviados,
        'ultimos_cambios': ultimos_cambios,
        'solicitud_informe_activa': solicitud_informe is not None,
        'anio_actual': tz.now().year,
        'ultimas_notificaciones': Notificacion.objects.filter(destinatario=user).order_by('-fecha')[:5],
    })


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
        .filter(es_optativa=False)
    )
    total_tribunales = meps_activos.count()
    sin_tribunal = meps_activos.filter(tribunal__isnull=True).count()
    mep_ids = meps_activos.values_list('id', flat=True)
    con_datos_faltantes = TribunalExaminador.objects.filter(
        materia_en_plan_id__in=mep_ids,
        presidente_nombre='',
    ).count()
    borrador_count = SolicitudCambioItem.objects.filter(
        solicitud__director=user,
        solicitud__departamento=departamento,
        solicitud__estado='borrador',
    ).count()
    solicitudes_enviadas = SolicitudCambioTribunal.objects.filter(
        departamento=departamento, estado='enviada',
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

    if solicitud is not None:
        solicitud_para_dept = (
            solicitud.cuatrimestre == 1 or
            departamento in solicitud.departamentos_notificados
        )
    else:
        solicitud_para_dept = False

    return render(request, 'tramites/dashboard_director.html', {
        'departamento': departamento,
        'por_revisar': por_revisar,
        'total_tribunales': total_tribunales,
        'sin_tribunal': sin_tribunal,
        'con_datos_faltantes': con_datos_faltantes,
        'borrador_count': borrador_count,
        'solicitudes_enviadas': solicitudes_enviadas,
        'solicitud_informe_activa': solicitud_para_dept and not ya_enviado,
        'informe_enviado': informe_enviado,
        'ultimas_notificaciones': Notificacion.objects.filter(destinatario=user).order_by('-fecha')[:5],
    })
