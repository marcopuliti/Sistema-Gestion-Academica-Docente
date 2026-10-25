import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse

from django.db import models
from apps.planes.models import PlanEstudio
from apps.tramites.decorators import puede_revisar, solo_director_carrera, solo_director_departamento
from apps.tramites.models import EstadoTramite, CalendarioAcademico
from .forms import (
    SolicitudProtocolizacionForm, EquipoDocenteFormSet,
    CorrelativaFormSet, ActasAvalForm,
    RevisionCarreraForm, RevisionDirectorForm, RevisionDirectorProtocolizacionForm, RevisionAdminForm,
    SolicitudTallerForm, ActaConsejoTallerForm, EquipoTallerFormSet,
    TIPIFICACIONES_CURRICULARES,
)
from .models import SolicitudProtocolizacion, SolicitudTaller, TIPIFICACION_CHOICES
from .pdf import generar_pdf_solicitud, generar_pdf_nota_elevacion, generar_pdf_solicitud_completa, generar_pdf_taller
from .docx_gen import generar_docx_solicitud, generar_docx_nota_elevacion, generar_docx_nota_comision, generar_docx_solicitud_completa

TIPIFICACIONES_VALIDAS = {t[0] for t in TIPIFICACION_CHOICES}


def _carrera_qs_para_usuario(user):
    """Devuelve el queryset de carreras que el usuario puede seleccionar en el form.
    None = sin restricción (usa el default del modelo)."""
    if user.es_director_carrera and user.carrera_id:
        from apps.planes.models import Carrera
        return Carrera.objects.filter(pk=user.carrera_id)
    return None


def _materia_qs_para_plan(plan_id):
    from apps.planes.models import MateriaEnPlan, Materia
    if not plan_id:
        return Materia.objects.none()
    ids = MateriaEnPlan.objects.filter(plan_id=plan_id).values_list('materia_id', flat=True).distinct()
    return Materia.objects.filter(id__in=ids).order_by('nombre')


def _set_correlativas_materia_qs(formset, plan_id):
    qs = _materia_qs_para_plan(plan_id)
    for form in formset.forms:
        form.fields['materia'].queryset = qs


def _calendario_json():
    """Devuelve el calendario del año en curso como JSON para el template."""
    try:
        cal = CalendarioAcademico.objects.get(anno=date.today().year)
        return json.dumps({
            'inicio_1c': cal.fecha_inicio_1c.isoformat(),
            'fin_1c':    cal.fecha_fin_1c.isoformat(),
            'inicio_2c': cal.fecha_inicio_2c.isoformat(),
            'fin_2c':    cal.fecha_fin_2c.isoformat(),
            'semanas_cuatrimestre': cal.semanas_cuatrimestre,
            'semanas_anual':        cal.semanas_anual,
        })
    except CalendarioAcademico.DoesNotExist:
        return 'null'


# ── circuito docente → carrera → departamento → administración ─────────────

def _usuarios(**filtros):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.filter(is_active=True, **filtros)


def _directores_carrera(solicitud):
    if not solicitud.carrera_id:
        return _usuarios(pk__in=[])
    return _usuarios(rol='director_carrera', carrera_id=solicitud.carrera_id)


def _directores_departamento(solicitud):
    return _usuarios(rol='director_departamento', departamento=solicitud.departamento_destino)


def _notificar(destinatarios, titulo, mensaje, solicitud, excluir=None):
    from apps.notifications.utils import _crear_notificacion
    from django.urls import reverse
    url = reverse('solicitudes:detalle', args=[solicitud.pk])
    for u in destinatarios:
        if excluir is None or u.pk != excluir.pk:
            _crear_notificacion(u, 'nuevo_tramite', titulo, mensaje, url=url)


def _sudocu_txt(solicitud):
    return f' — SUDOCU {solicitud.numero_sudocu}' if solicitud.numero_sudocu else ''


def _enviar_a_revision(request, solicitud, reenvio=False):
    """Estado al crear o corregir una solicitud: queda con el director de carrera (si la cargó
    él mismo, para que la envíe con el N° SUDOCU). Si la carrera no tiene director, va directo
    al director de departamento como antes."""
    user = request.user
    if user.es_director_carrera and solicitud.carrera_id == user.carrera_id:
        solicitud.estado = EstadoTramite.EN_CARRERA
        solicitud.save(update_fields=['estado'])
        messages.success(
            request,
            'Solicitud guardada. Descargá la solicitud completa, iniciá el trámite en SUDOCU y enviala '
            'al director de departamento con el número de trámite.',
        )
        return
    directores = list(_directores_carrera(solicitud))
    if directores:
        solicitud.estado = EstadoTramite.EN_CARRERA
        solicitud.save(update_fields=['estado'])
        nombre = solicitud.get_nombre_docente
        _notificar(
            directores,
            f'{"Solicitud de protocolización corregida" if reenvio else "Nueva solicitud de protocolización"} — {solicitud.nombre_curso}',
            f'{nombre} {"corrigió" if reenvio else "envió"} la solicitud de protocolización de "{solicitud.nombre_curso}" '
            f'({solicitud.carrera.nombre}). Revisala: aceptala y enviala al director de departamento con el '
            'N° de trámite SUDOCU, o devolvela al docente con observaciones.',
            solicitud,
        )
        messages.success(request, 'Solicitud enviada al director de carrera.')
        return
    solicitud.estado = EstadoTramite.PENDIENTE
    solicitud.save(update_fields=['estado'])
    from apps.notifications.utils import notificar_nuevo_tramite
    from django.urls import reverse
    notificar_nuevo_tramite(solicitud, 'Solicitud de Protocolización',
                            url=reverse('solicitudes:detalle', args=[solicitud.pk]))
    messages.success(request, 'Solicitud enviada. Quedó pendiente de revisión.')


def _puede_editar(user, solicitud):
    """El dueño la corrige cuando se la devuelven; el director de carrera, también antes de enviarla."""
    if solicitud.usuario_id != user.pk:
        return False
    editables = {EstadoTramite.DEVUELTA_DOCENTE, EstadoTramite.DEVUELTA, EstadoTramite.RECHAZADO, EstadoTramite.OBSERVADA}
    if user.es_director_carrera:
        editables |= {EstadoTramite.EN_CARRERA, EstadoTramite.DEVUELTA_CARRERA}
    return solicitud.estado in editables


def _puede_revisar_carrera(user, solicitud):
    return (
        user.es_director_carrera and user.carrera_id and solicitud.carrera_id == user.carrera_id
        and solicitud.estado in (EstadoTramite.EN_CARRERA, EstadoTramite.DEVUELTA_CARRERA)
    )


def _es_de_su_departamento(user, solicitud):
    dep = user.departamento
    dep_solicitud = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
    carrera_dep = solicitud.carrera.departamento if solicitud.carrera else None
    return dep_solicitud == dep or carrera_dep == dep


def _con_acta(user, solicitud):
    """La solicitud completa del director de carrera (y de administración) incluye el acta de la
    Comisión de Carrera; la del docente, solo nota y programa."""
    return user.puede_revisar or (
        user.es_director_carrera and user.carrera_id and solicitud.carrera_id == user.carrera_id
    )


@login_required
def lista_solicitudes(request):
    if request.user.es_director_departamento:
        return redirect('solicitudes:lista_departamento')
    if request.user.es_director_carrera:
        carrera = request.user.carrera
        solicitudes = SolicitudProtocolizacion.objects.filter(carrera=carrera).select_related('usuario')
        return render(request, 'solicitudes/lista.html', {
            'solicitudes': solicitudes,
            'talleres':    SolicitudTaller.objects.none(),
        })
    if request.user.puede_revisar:
        solicitudes = SolicitudProtocolizacion.objects.select_related('usuario').all()
        talleres    = SolicitudTaller.objects.select_related('usuario').all()
    else:
        solicitudes = SolicitudProtocolizacion.objects.filter(usuario=request.user)
        talleres    = SolicitudTaller.objects.filter(usuario=request.user)
    return render(request, 'solicitudes/lista.html', {
        'solicitudes': solicitudes,
        'talleres':    talleres,
    })


@login_required
def seleccionar_tipificacion(request):
    """Paso 1: el docente elige la tipificación antes de abrir el formulario."""
    return render(request, 'solicitudes/seleccionar_tipificacion.html')


@login_required
def crear_solicitud(request, tipificacion):
    """Paso 2: formulario según tipificación."""
    if tipificacion not in TIPIFICACIONES_VALIDAS:
        messages.error(request, 'Tipo de solicitud inválido.')
        return redirect('solicitudes:crear')

    es_curricular = tipificacion in TIPIFICACIONES_CURRICULARES
    carrera_qs = _carrera_qs_para_usuario(request.user)

    if request.method == 'POST':
        form = SolicitudProtocolizacionForm(request.POST, tipificacion=tipificacion, anonimo=False, carrera_qs=carrera_qs)
        formset = EquipoDocenteFormSet(request.POST)
        plan_id = request.POST.get('plan_estudio') or None
        correlativas_formset = CorrelativaFormSet(request.POST, prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, plan_id)
        if form.is_valid() and formset.is_valid() and correlativas_formset.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario = request.user
            solicitud.save()
            formset.instance = solicitud
            formset.save()
            correlativas_formset.instance = solicitud
            correlativas_formset.save()
            _enviar_a_revision(request, solicitud)
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudProtocolizacionForm(tipificacion=tipificacion, anonimo=False, carrera_qs=carrera_qs)
        formset = EquipoDocenteFormSet()
        correlativas_formset = CorrelativaFormSet(prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, None)

    return render(request, 'solicitudes/form.html', {
        'form': form,
        'formset': formset,
        'correlativas_formset': correlativas_formset,
        'tipificacion': tipificacion,
        'es_curricular': es_curricular,
        'titulo': f'Nueva Solicitud — {dict(TIPIFICACION_CHOICES)[tipificacion]}',
        'calendario_json': _calendario_json(),
        'anonimo': False,
        'hs_totales_plan': None,
    })


def _puede_ver_solicitud(user, solicitud):
    """True si el usuario tiene acceso a esta solicitud."""
    if user.puede_revisar:
        return True
    if user.es_director_departamento:
        dep = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
        if dep == user.departamento:
            return True
        # solicitudes creadas por director_carrera: matchear por carrera.departamento
        if solicitud.carrera and solicitud.carrera.departamento == user.departamento:
            return True
        return False
    if user.es_director_carrera and user.carrera_id:
        return solicitud.carrera_id == user.carrera_id
    return solicitud.usuario == user


@login_required
def detalle_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para ver esta solicitud.')
        return redirect('solicitudes:lista')
    u = request.user
    puede_duplicar = (
        solicitud.usuario_id == u.pk or
        (u.es_director_carrera and u.carrera_id and solicitud.carrera_id == u.carrera_id)
    )
    return render(request, 'solicitudes/detalle.html', {
        'solicitud': solicitud,
        'puede_duplicar': puede_duplicar,
        'puede_editar': _puede_editar(u, solicitud),
        'puede_revisar_carrera': _puede_revisar_carrera(u, solicitud),
        'puede_revisar_departamento': (
            u.es_director_departamento and _es_de_su_departamento(u, solicitud)
            and solicitud.estado in (EstadoTramite.PENDIENTE, EstadoTramite.OBSERVADA)
        ),
        'puede_nota_aval': u.puede_revisar or (u.es_director_departamento and _es_de_su_departamento(u, solicitud)),
        'con_acta': _con_acta(u, solicitud),
    })


@login_required
@solo_director_carrera
def revisar_carrera(request, pk):
    """Director de carrera: envía la solicitud al director de departamento con el N° SUDOCU
    (y la fecha del acta de la Comisión de Carrera) o la devuelve al docente."""
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_revisar_carrera(request.user, solicitud):
        messages.error(request, 'Esta solicitud no está pendiente de revisión de tu carrera.')
        return redirect('solicitudes:detalle', pk=pk)
    puede_devolver = solicitud.usuario_id != request.user.pk

    if request.method == 'POST':
        form = RevisionCarreraForm(request.POST, puede_devolver=puede_devolver)
        if form.is_valid():
            from apps.notifications.utils import notificar_cambio_estado
            from django.urls import reverse
            from django.utils import timezone
            accion = form.cleaned_data['accion']
            solicitud.revisor = request.user
            if accion == 'enviar':
                solicitud.estado = EstadoTramite.PENDIENTE
                solicitud.numero_sudocu = form.cleaned_data['numero_sudocu']
                solicitud.fecha_acta_comision_carrera = form.cleaned_data['fecha_acta_comision_carrera']
                solicitud.director_carrera = request.user
                solicitud.fecha_envio_carrera = timezone.now()
                if form.cleaned_data['comentarios']:
                    solicitud.comentarios_revision = form.cleaned_data['comentarios']
                solicitud.save()
                _notificar(
                    _directores_departamento(solicitud),
                    f'Solicitud de protocolización — {solicitud.nombre_curso}{_sudocu_txt(solicitud)}',
                    f'{request.user.get_full_name()} (director de {solicitud.carrera.nombre}) envió la solicitud de '
                    f'protocolización de "{solicitud.nombre_curso}".\nTrámite SUDOCU: {solicitud.numero_sudocu}.\n\n'
                    'Revisala, generá la nota de aval del Consejo Departamental y elevala a Secretaría.',
                    solicitud,
                )
                messages.success(request, f'Solicitud enviada al director de departamento con el trámite SUDOCU {solicitud.numero_sudocu}.')
            else:
                solicitud.estado = EstadoTramite.DEVUELTA_DOCENTE
                solicitud.comentarios_revision = form.cleaned_data['comentarios']
                solicitud.save()
                messages.success(request, 'Solicitud devuelta al docente con observaciones.')
            if solicitud.usuario_id and solicitud.usuario_id != request.user.pk:
                notificar_cambio_estado(solicitud, 'Solicitud de Protocolización',
                                        url=reverse('solicitudes:detalle', args=[solicitud.pk]))
            return redirect('solicitudes:detalle', pk=pk)
    else:
        from django.utils import timezone
        form = RevisionCarreraForm(puede_devolver=puede_devolver, initial={
            'accion': '' if puede_devolver else 'enviar',
            'numero_sudocu': solicitud.numero_sudocu,
            'fecha_acta_comision_carrera': solicitud.fecha_acta_comision_carrera or timezone.localdate(),
        })
    return render(request, 'solicitudes/revision_carrera.html', {
        'solicitud': solicitud, 'form': form, 'puede_devolver': puede_devolver,
    })


@login_required
def editar_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk, usuario=request.user)
    if not _puede_editar(request.user, solicitud):
        messages.error(request, 'Solo podés editar solicitudes devueltas con observaciones.')
        return redirect('solicitudes:detalle', pk=pk)
    reenvio = solicitud.estado not in (EstadoTramite.EN_CARRERA,)

    tip = solicitud.tipificacion
    es_curricular = tip in TIPIFICACIONES_CURRICULARES
    carrera_qs = _carrera_qs_para_usuario(request.user)

    if request.method == 'POST':
        form = SolicitudProtocolizacionForm(request.POST, instance=solicitud, tipificacion=tip, carrera_qs=carrera_qs)
        formset = EquipoDocenteFormSet(request.POST, instance=solicitud)
        plan_id = request.POST.get('plan_estudio') or None
        correlativas_formset = CorrelativaFormSet(request.POST, instance=solicitud, prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, plan_id)
        if form.is_valid() and formset.is_valid() and correlativas_formset.is_valid():
            solicitud = form.save()
            formset.instance = solicitud
            formset.save()
            correlativas_formset.instance = solicitud
            correlativas_formset.save()
            _enviar_a_revision(request, solicitud, reenvio=reenvio)
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudProtocolizacionForm(instance=solicitud, tipificacion=tip, carrera_qs=carrera_qs)
        formset = EquipoDocenteFormSet(instance=solicitud)
        plan_id = solicitud.plan_estudio_id
        correlativas_formset = CorrelativaFormSet(instance=solicitud, prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, plan_id)

    hs_totales_plan = (
        solicitud.optativa_vinculada.hs_totales
        if solicitud.optativa_vinculada else None
    )
    return render(request, 'solicitudes/form.html', {
        'form': form,
        'formset': formset,
        'correlativas_formset': correlativas_formset,
        'tipificacion': tip,
        'es_curricular': es_curricular,
        'titulo': 'Editar Solicitud',
        'edicion': True,
        'calendario_json': _calendario_json(),
        'hs_totales_plan': hs_totales_plan,
    })


@login_required
@solo_director_departamento
def revisar_director(request, pk):
    """Director revisa una solicitud pendiente: la devuelve o la eleva al admin."""
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _es_de_su_departamento(request.user, solicitud):
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')
    if solicitud.estado not in (EstadoTramite.PENDIENTE, EstadoTramite.OBSERVADA):
        messages.error(request, 'Solo podés revisar solicitudes en estado Pendiente o Con Observaciones.')
        return redirect('solicitudes:detalle', pk=pk)

    if request.method == 'POST':
        form = RevisionDirectorProtocolizacionForm(request.POST)
        if form.is_valid():
            from apps.notifications.utils import notificar_cambio_estado
            from django.urls import reverse
            from django.utils import timezone
            accion = form.cleaned_data['accion']
            solicitud.comentarios_revision = form.cleaned_data['comentarios']
            solicitud.revisor = request.user
            if accion == 'elevada':
                solicitud.estado = EstadoTramite.ELEVADA
                solicitud.fecha_reunion_consejo = form.cleaned_data['fecha_reunion_consejo']
                solicitud.hora_reunion_consejo = form.cleaned_data['hora_reunion_consejo']
                solicitud.fecha_nota_aval = solicitud.fecha_nota_aval or timezone.localdate()
                solicitud.save()
                _notificar(
                    _usuarios(rol__in=['secretario', 'direccion_academica']),
                    f'Solicitud de protocolización elevada — {solicitud.nombre_curso}{_sudocu_txt(solicitud)}',
                    f'{request.user.get_full_name()} (director del Departamento de {solicitud.departamento_destino}) '
                    f'elevó la solicitud de protocolización de "{solicitud.nombre_curso}"'
                    + (f' ({solicitud.carrera.nombre})' if solicitud.carrera_id else '') + '.'
                    + (f'\nTrámite SUDOCU: {solicitud.numero_sudocu}.' if solicitud.numero_sudocu else ''),
                    solicitud,
                )
                messages.success(request, 'Solicitud elevada a Secretaría.')
            else:
                solicitud.estado = EstadoTramite.DEVUELTA_CARRERA
                solicitud.save()
                _notificar(
                    _directores_carrera(solicitud),
                    f'Solicitud de protocolización devuelta — {solicitud.nombre_curso}',
                    f'El director del Departamento de {solicitud.departamento_destino} devolvió la solicitud de '
                    f'"{solicitud.nombre_curso}" con observaciones:\n\n{solicitud.comentarios_revision}',
                    solicitud, excluir=solicitud.usuario,
                )
                messages.success(request, 'Solicitud devuelta al director de carrera con observaciones.')
            if solicitud.usuario_id:
                notificar_cambio_estado(solicitud, 'Solicitud de Protocolización',
                                        url=reverse('solicitudes:detalle', args=[solicitud.pk]))
            return redirect('solicitudes:detalle', pk=pk)
    else:
        form = RevisionDirectorProtocolizacionForm(initial={
            'fecha_reunion_consejo': solicitud.fecha_reunion_consejo,
            'hora_reunion_consejo': solicitud.hora_reunion_consejo,
        })
    return render(request, 'solicitudes/revision_director.html', {'solicitud': solicitud, 'form': form})


@login_required
def nota_aval_consejo(request, pk, formato):
    """Nota de aval del Consejo Departamental. El director de departamento la genera cargando la
    fecha y hora de la reunión (POST, desde la revisión); después la puede volver a descargar."""
    from django.utils import timezone
    from .docx_gen import generar_docx_nota_aval_consejo
    from .pdf import generar_pdf_nota_aval_consejo
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    user = request.user
    es_director = user.es_director_departamento and _es_de_su_departamento(user, solicitud)
    if not (es_director or user.puede_revisar) or formato not in ('pdf', 'docx'):
        messages.error(request, 'Solo el director del departamento puede generar la nota de aval.')
        return redirect('solicitudes:detalle', pk=pk)

    if request.method == 'POST' and es_director:
        form = RevisionDirectorProtocolizacionForm(request.POST)
        form.is_valid()
        fecha = form.cleaned_data.get('fecha_reunion_consejo')
        hora = form.cleaned_data.get('hora_reunion_consejo')
        if not (fecha and hora):
            messages.error(request, 'Para generar la nota de aval indicá la fecha y la hora de la reunión del Consejo Departamental.')
            return redirect('solicitudes:revisar_director', pk=pk)
        if (fecha, hora) != (solicitud.fecha_reunion_consejo, solicitud.hora_reunion_consejo) or not solicitud.fecha_nota_aval:
            solicitud.fecha_nota_aval = timezone.localdate()
        solicitud.fecha_reunion_consejo, solicitud.hora_reunion_consejo = fecha, hora
        solicitud.save(update_fields=['fecha_reunion_consejo', 'hora_reunion_consejo', 'fecha_nota_aval'])
    elif not (solicitud.fecha_reunion_consejo and solicitud.hora_reunion_consejo):
        messages.error(request, 'La nota de aval todavía no se generó.')
        return redirect('solicitudes:detalle', pk=pk)

    nombre = f'nota_aval_consejo_{solicitud.pk}'
    if formato == 'docx':
        response = HttpResponse(
            generar_docx_nota_aval_consejo(solicitud),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
    else:
        response = HttpResponse(generar_pdf_nota_aval_consejo(solicitud), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}.{formato}"'
    return response


@login_required
@puede_revisar
def revisar_solicitud(request, pk):
    """Administrador revisa una solicitud elevada: la aprueba o la devuelve."""
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if solicitud.estado != EstadoTramite.ELEVADA:
        messages.error(request, 'Solo podés revisar solicitudes elevadas al administrador.')
        return redirect('solicitudes:detalle', pk=pk)
    if request.method == 'POST':
        form = RevisionAdminForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data['accion']
            solicitud.estado = accion
            solicitud.comentarios_revision = form.cleaned_data['comentarios']
            solicitud.revisor = request.user
            if accion == 'aprobado':
                solicitud.numero_resolucion = form.cleaned_data['numero_resolucion']
            solicitud.save()
            from apps.notifications.utils import notificar_cambio_estado
            from django.urls import reverse
            notificar_cambio_estado(solicitud, 'Solicitud de Protocolización',
                                    url=reverse('solicitudes:detalle', args=[solicitud.pk]))
            if accion == 'aprobado':
                directores = list(_directores_carrera(solicitud)) + list(_directores_departamento(solicitud))
                _notificar(
                    directores,
                    f'Protocolización aprobada — {solicitud.nombre_curso} — Res. {solicitud.numero_resolucion}',
                    f'Secretaría aprobó la protocolización de "{solicitud.nombre_curso}"'
                    + (f' ({solicitud.carrera.nombre})' if solicitud.carrera_id else '')
                    + f'.\nNúmero de resolución: {solicitud.numero_resolucion}.'
                    + (f'\nTrámite SUDOCU: {solicitud.numero_sudocu}.' if solicitud.numero_sudocu else ''),
                    solicitud, excluir=solicitud.usuario,
                )
            elif accion == 'observada':
                _notificar(
                    _directores_departamento(solicitud),
                    f'Solicitud de protocolización observada — {solicitud.nombre_curso}',
                    f'Secretaría devolvió con observaciones la solicitud de "{solicitud.nombre_curso}":\n\n'
                    f'{solicitud.comentarios_revision}',
                    solicitud, excluir=solicitud.usuario,
                )
            messages.success(request, 'Revisión guardada.')
            if accion == 'aprobado' and solicitud.tipificacion == 'optativa':
                from apps.planes.optativas import agregar_a_bolsa
                materia, avisos = agregar_a_bolsa(solicitud)
                if materia:
                    messages.success(request, f'«{materia.nombre}» quedó en la bolsa de optativas con el código {materia.codigo}.')
                for aviso in avisos:
                    messages.warning(request, aviso)
            return redirect('solicitudes:detalle', pk=pk)
    else:
        form = RevisionAdminForm()
    return render(request, 'solicitudes/revision.html', {'solicitud': solicitud, 'form': form})


@login_required
def descargar_pdf_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista')
    buffer = generar_pdf_solicitud(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"programa_{solicitud.pk}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
def descargar_docx_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista')
    buffer = generar_docx_solicitud(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"programa_{solicitud.pk}_{apellido}.docx"
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
def descargar_pdf_nota_elevacion(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista')
    buffer = generar_pdf_nota_elevacion(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"solicitud_protocolizacion_{solicitud.pk}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
def descargar_docx_nota_elevacion(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista')
    buffer = generar_docx_nota_elevacion(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"solicitud_protocolizacion_{solicitud.pk}_{apellido}.docx"
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
def descargar_pdf_solicitud_completa(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista')
    buffer = generar_pdf_solicitud_completa(solicitud, con_acta=_con_acta(request.user, solicitud))
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"solicitud_completa_{solicitud.pk}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
def descargar_docx_solicitud_completa(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista')
    buffer = generar_docx_solicitud_completa(solicitud, con_acta=_con_acta(request.user, solicitud))
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"solicitud_completa_{solicitud.pk}_{apellido}.docx"
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


def _puede_generar_nota_comision(user, solicitud):
    """Solo director del departamento correspondiente o administrador."""
    if user.puede_revisar:
        return True
    if user.es_director_departamento:
        dep = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
        return dep == user.departamento
    return False


@login_required
def descargar_pdf_nota_comision(request, pk):
    from .pdf import generar_pdf_nota_comision
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_generar_nota_comision(request.user, solicitud):
        messages.error(request, 'Solo el director del departamento puede generar este documento.')
        return redirect('solicitudes:detalle', pk=pk)
    buffer = generar_pdf_nota_comision(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"nota_comision_{solicitud.pk}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
def descargar_docx_nota_comision(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_generar_nota_comision(request.user, solicitud):
        messages.error(request, 'Solo el director del departamento puede generar este documento.')
        return redirect('solicitudes:detalle', pk=pk)
    buffer = generar_docx_nota_comision(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"nota_comision_{solicitud.pk}_{apellido}.docx"
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@login_required
@solo_director_departamento
def lista_solicitudes_departamento(request):
    from django.db.models import Case, When, IntegerField
    dep = request.user.departamento
    dep_q_base = models.Q(usuario__departamento=dep) | models.Q(departamento_docente=dep)

    orden = Case(
        When(estado=EstadoTramite.APROBADO, then=1),
        default=0,
        output_field=IntegerField(),
    )

    solicitudes = (
        SolicitudProtocolizacion.objects
        .select_related('usuario', 'carrera')
        .filter(dep_q_base | models.Q(carrera__departamento=dep))
        .exclude(estado__in=[EstadoTramite.EN_CARRERA, EstadoTramite.DEVUELTA_DOCENTE])
        .annotate(orden_estado=orden)
        .order_by('orden_estado', '-fecha_creacion')
    )
    talleres = (
        SolicitudTaller.objects
        .select_related('usuario')
        .filter(dep_q_base)
        .annotate(orden_estado=orden)
        .order_by('orden_estado', '-fecha_creacion')
    )
    return render(request, 'solicitudes/lista_departamento.html', {
        'solicitudes': solicitudes,
        'talleres': talleres,
        'departamento': dep,
    })


@login_required
@solo_director_departamento
def agregar_codigo_materia(request, pk):
    from django import forms as dj_forms
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    dep = request.user.departamento
    dep_solicitud = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
    carrera_dep = solicitud.carrera.departamento if solicitud.carrera else None
    if dep_solicitud != dep and carrera_dep != dep:
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')
    if request.method == 'POST':
        codigo = request.POST.get('codigo_materia', '').strip()
        solicitud.codigo_materia = codigo
        solicitud.save(update_fields=['codigo_materia'])
        messages.success(request, f'Código de materia "{codigo}" guardado.')
    return redirect('solicitudes:detalle', pk=pk)


@login_required
@solo_director_departamento
def subir_actas_aval(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    dep = request.user.departamento
    dep_solicitud = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
    carrera_dep = solicitud.carrera.departamento if solicitud.carrera else None
    if dep_solicitud != dep and carrera_dep != dep:
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')

    if request.method == 'POST':
        f = request.FILES.get('acta_consejo_departamental')
        if f:
            if solicitud.acta_consejo_departamental:
                solicitud.acta_consejo_departamental.delete(save=False)  # reemplaza el anterior
            solicitud.acta_consejo_departamental = f
            solicitud.save(update_fields=['acta_consejo_departamental'])
            messages.success(request, 'Acta del Consejo Departamental guardada correctamente.')
        else:
            messages.warning(request, 'No se seleccionó ningún archivo.')

    return redirect('solicitudes:detalle', pk=pk)


@login_required
@solo_director_carrera
def subir_acta_comision_carrera(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if solicitud.carrera_id != request.user.carrera_id:
        messages.error(request, 'Esta solicitud no pertenece a tu carrera.')
        return redirect('solicitudes:lista')

    if request.method == 'POST':
        f = request.FILES.get('acta_comision_carrera')
        if f:
            if solicitud.acta_comision_carrera:
                solicitud.acta_comision_carrera.delete(save=False)  # reemplaza el anterior
            solicitud.acta_comision_carrera = f
            solicitud.save(update_fields=['acta_comision_carrera'])
            messages.success(request, 'Acta de Comisión de Carrera guardada correctamente.')
        else:
            messages.warning(request, 'No se seleccionó ningún archivo.')

    return redirect('solicitudes:detalle', pk=pk)


@login_required
def duplicar_solicitud(request, pk):
    fuente = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    u = request.user
    puede = (
        fuente.usuario_id == u.pk or
        (u.es_director_carrera and u.carrera_id and fuente.carrera_id == u.carrera_id)
    )
    if not puede:
        messages.error(request, 'No tenés permiso para duplicar esta solicitud.')
        return redirect('solicitudes:lista')

    tip = fuente.tipificacion
    es_curricular = tip in TIPIFICACIONES_CURRICULARES
    carrera_qs = _carrera_qs_para_usuario(u)

    if request.method == 'POST':
        form = SolicitudProtocolizacionForm(request.POST, tipificacion=tip, anonimo=False, carrera_qs=carrera_qs)
        formset = EquipoDocenteFormSet(request.POST)
        plan_id = request.POST.get('plan_estudio') or None
        correlativas_formset = CorrelativaFormSet(request.POST, prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, plan_id)
        if form.is_valid() and formset.is_valid() and correlativas_formset.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario = u
            solicitud.save()
            formset.instance = solicitud
            formset.save()
            correlativas_formset.instance = solicitud
            correlativas_formset.save()
            _enviar_a_revision(request, solicitud)
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        fk_fields = {'carrera', 'plan_estudio', 'optativa_vinculada'}
        initial = {}
        for f in SolicitudProtocolizacionForm.Meta.fields:
            if f in fk_fields:
                initial[f] = getattr(fuente, f'{f}_id', None)
            else:
                initial[f] = getattr(fuente, f, None)
        form = SolicitudProtocolizacionForm(initial=initial, tipificacion=tip, anonimo=False, carrera_qs=carrera_qs)
        from apps.planes.models import MateriaEnPlan
        if fuente.carrera_id:
            form.fields['plan_estudio'].queryset = PlanEstudio.objects.filter(
                carrera_id=fuente.carrera_id, vigente=True
            )
        if fuente.plan_estudio_id:
            form.fields['optativa_vinculada'].queryset = (
                MateriaEnPlan.objects
                .filter(plan_id=fuente.plan_estudio_id, es_optativa=True)
                .select_related('materia')
                .order_by('ano', 'materia__nombre')
            )
        formset = EquipoDocenteFormSet()
        correlativas_formset = CorrelativaFormSet(prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, fuente.plan_estudio_id)

    return render(request, 'solicitudes/form.html', {
        'form': form,
        'formset': formset,
        'correlativas_formset': correlativas_formset,
        'tipificacion': tip,
        'es_curricular': es_curricular,
        'titulo': f'Nueva Solicitud — basada en "{fuente.nombre_curso}"',
        'calendario_json': _calendario_json(),
        'anonimo': False,
        'hs_totales_plan': fuente.optativa_vinculada.hs_totales if fuente.optativa_vinculada else None,
    })


def materias_por_plan(request):
    """AJAX: devuelve las materias de un plan para correlatividades."""
    plan_id = request.GET.get('plan_id')
    qs = _materia_qs_para_plan(plan_id)
    return JsonResponse({'materias': [{'id': m.id, 'nombre': m.nombre} for m in qs]})


def planes_por_carrera(request):
    """AJAX: devuelve los planes vigentes de una carrera como JSON."""
    carrera_id = request.GET.get('carrera_id')
    if not carrera_id:
        return JsonResponse({'planes': []})
    planes = PlanEstudio.objects.filter(
        carrera_id=carrera_id, vigente=True
    ).values('id', 'codigo')
    return JsonResponse({'planes': list(planes)})


def optativas_por_plan(request):
    """AJAX: devuelve las optativas de un plan con ano y cuatrimestre."""
    from apps.planes.models import MateriaEnPlan
    plan_id = request.GET.get('plan_id')
    if not plan_id:
        return JsonResponse({'optativas': []})
    # cuatrimestre → codigo de periodo
    CUATRI_A_PERIODO = {1: '1c', 2: '2c', 3: 'anual'}
    qs = (
        MateriaEnPlan.objects
        .filter(plan_id=plan_id, es_optativa=True)
        .select_related('materia')
        .order_by('ano', 'materia__nombre')
    )
    data = [
        {
            'id': m.id,
            'label': f'{m.get_nombre()} ({m.materia.codigo})',
            'ano': str(m.ano),
            'periodo': CUATRI_A_PERIODO.get(m.cuatrimestre, ''),
            'hs_totales': m.hs_totales,
        }
        for m in qs
    ]
    return JsonResponse({'optativas': data})


# ─────────────────────────────────────────────────────────────────────────────
# TALLERES
# ─────────────────────────────────────────────────────────────────────────────

def _puede_ver_taller(user, taller):
    if user.puede_revisar:
        return True
    if user.es_director_departamento:
        dep = taller.usuario.departamento if taller.usuario else taller.departamento_docente
        return dep == user.departamento
    return taller.usuario == user


@login_required
def lista_talleres(request):
    if request.user.puede_revisar:
        talleres = SolicitudTaller.objects.all()
    elif request.user.es_director_departamento:
        dep = request.user.departamento
        talleres = SolicitudTaller.objects.filter(
            models.Q(usuario__departamento=dep) | models.Q(departamento_docente=dep)
        )
    else:
        talleres = SolicitudTaller.objects.filter(usuario=request.user)
    return render(request, 'solicitudes/lista_talleres.html', {'talleres': talleres})


@login_required
def crear_taller(request):
    if request.method == 'POST':
        form = SolicitudTallerForm(request.POST)
        equipo_fs = EquipoTallerFormSet(request.POST, prefix='equipo')
        if form.is_valid() and equipo_fs.is_valid():
            taller = form.save(commit=False)
            taller.usuario = request.user
            taller.estado = EstadoTramite.PENDIENTE
            taller.save()
            equipo_fs.instance = taller
            equipo_fs.save()
            messages.success(request, 'Solicitud de taller creada correctamente.')
            return redirect('solicitudes:detalle_taller', pk=taller.pk)
    else:
        form = SolicitudTallerForm()
        equipo_fs = EquipoTallerFormSet(prefix='equipo')
    return render(request, 'solicitudes/taller_form.html', {
        'form': form, 'equipo_fs': equipo_fs, 'titulo': 'Nueva Solicitud de Curso/Taller',
    })


@login_required
def detalle_taller(request, pk):
    taller = get_object_or_404(SolicitudTaller, pk=pk)
    if not _puede_ver_taller(request.user, taller):
        messages.error(request, 'No tenés permisos para ver esta solicitud.')
        return redirect('solicitudes:lista_talleres')
    return render(request, 'solicitudes/taller_detalle.html', {'taller': taller})


@login_required
def editar_taller(request, pk):
    taller = get_object_or_404(SolicitudTaller, pk=pk, usuario=request.user)
    EDITABLES = (EstadoTramite.DEVUELTA, EstadoTramite.RECHAZADO, EstadoTramite.OBSERVADA)
    if taller.estado not in EDITABLES:
        messages.error(request, 'Solo podés editar solicitudes que te fueron devueltas.')
        return redirect('solicitudes:detalle_taller', pk=pk)
    if request.method == 'POST':
        form = SolicitudTallerForm(request.POST, instance=taller)
        equipo_fs = EquipoTallerFormSet(request.POST, instance=taller, prefix='equipo')
        if form.is_valid() and equipo_fs.is_valid():
            t = form.save(commit=False)
            t.estado = EstadoTramite.PENDIENTE
            t.save()
            equipo_fs.instance = t
            equipo_fs.save()
            messages.success(request, 'Solicitud actualizada y enviada nuevamente.')
            return redirect('solicitudes:detalle_taller', pk=t.pk)
    else:
        form = SolicitudTallerForm(instance=taller)
        equipo_fs = EquipoTallerFormSet(instance=taller, prefix='equipo')
    return render(request, 'solicitudes/taller_form.html', {
        'form': form, 'equipo_fs': equipo_fs, 'titulo': 'Editar Solicitud de Curso/Taller', 'taller': taller,
    })


@login_required
@solo_director_departamento
def subir_acta_taller(request, pk):
    taller = get_object_or_404(SolicitudTaller, pk=pk)
    dep = request.user.departamento
    dep_taller = taller.usuario.departamento if taller.usuario else taller.departamento_docente
    if dep_taller != dep:
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')
    if request.method == 'POST':
        form = ActaConsejoTallerForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data.get('acta_consejo_departamental')
            if f:
                if taller.acta_consejo_departamental:
                    taller.acta_consejo_departamental.delete(save=False)  # reemplaza el anterior
                taller.acta_consejo_departamental = f
                taller.save(update_fields=['acta_consejo_departamental'])
                messages.success(request, 'Acta subida correctamente.')
            else:
                messages.warning(request, 'No se seleccionó ningún archivo.')
    return redirect('solicitudes:detalle_taller', pk=pk)


@login_required
@solo_director_departamento
def revisar_director_taller(request, pk):
    taller = get_object_or_404(SolicitudTaller, pk=pk)
    dep = request.user.departamento
    dep_taller = taller.usuario.departamento if taller.usuario else taller.departamento_docente
    if dep_taller != dep:
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')
    if taller.estado not in (EstadoTramite.PENDIENTE, EstadoTramite.OBSERVADA):
        messages.error(request, 'Solo podés revisar solicitudes en estado Pendiente o Con Observaciones.')
        return redirect('solicitudes:detalle_taller', pk=pk)
    if request.method == 'POST':
        form = RevisionDirectorForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data['accion']
            if accion == 'elevada' and not taller.acta_consejo_departamental:
                messages.error(request, 'Debés subir el Acta del Consejo Departamental antes de elevar.')
                return render(request, 'solicitudes/revisar_director_taller.html', {'taller': taller, 'form': form})
            taller.estado = accion
            taller.comentarios_revision = form.cleaned_data['comentarios']
            taller.revisor = request.user
            taller.save()
            from apps.notifications.utils import notificar_cambio_estado
            from django.urls import reverse
            notificar_cambio_estado(taller, 'Solicitud de Taller',
                                    url=reverse('solicitudes:detalle_taller', args=[taller.pk]))
            label = 'elevada al Administrador' if accion == 'elevada' else 'devuelta al docente con observaciones'
            messages.success(request, f'Solicitud {label}.')
            return redirect('solicitudes:detalle_taller', pk=pk)
    else:
        form = RevisionDirectorForm()
    return render(request, 'solicitudes/revisar_director_taller.html', {'taller': taller, 'form': form})


@login_required
@puede_revisar
def revisar_taller(request, pk):
    taller = get_object_or_404(SolicitudTaller, pk=pk)
    if taller.estado != EstadoTramite.ELEVADA:
        messages.error(request, 'Solo podés revisar solicitudes elevadas al administrador.')
        return redirect('solicitudes:detalle_taller', pk=pk)
    if request.method == 'POST':
        form = RevisionAdminForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data['accion']
            taller.estado = accion
            taller.comentarios_revision = form.cleaned_data['comentarios']
            taller.revisor = request.user
            if accion == 'aprobado':
                taller.numero_resolucion = form.cleaned_data['numero_resolucion']
            taller.save()
            from apps.notifications.utils import notificar_cambio_estado
            from django.urls import reverse
            notificar_cambio_estado(taller, 'Solicitud de Taller',
                                    url=reverse('solicitudes:detalle_taller', args=[taller.pk]))
            messages.success(request, 'Revisión guardada.')
            return redirect('solicitudes:detalle_taller', pk=pk)
    else:
        form = RevisionAdminForm()
    return render(request, 'solicitudes/revisar_taller.html', {'taller': taller, 'form': form})


@login_required
def descargar_pdf_taller(request, pk):
    taller = get_object_or_404(SolicitudTaller, pk=pk)
    if not _puede_ver_taller(request.user, taller):
        messages.error(request, 'No tenés permisos para descargar este documento.')
        return redirect('solicitudes:lista_talleres')
    buffer = generar_pdf_taller(taller)
    nombre = f"taller_{taller.pk}_{taller.denominacion_curso[:30].replace(' ', '_')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response
