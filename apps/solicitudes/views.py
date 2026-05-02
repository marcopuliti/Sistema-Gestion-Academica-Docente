import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse

from django.db import models
from apps.planes.models import PlanEstudio
from apps.tramites.decorators import puede_revisar, solo_director_departamento
from apps.tramites.models import EstadoTramite, CalendarioAcademico
from .forms import (
    SolicitudProtocolizacionForm, EquipoDocenteFormSet,
    CorrelativaFormSet, ActasAvalForm,
    RevisionDirectorForm, RevisionAdminForm,
    SolicitudTallerForm, ActaConsejoTallerForm, EquipoTallerFormSet,
    TIPIFICACIONES_CURRICULARES,
)
from .models import SolicitudProtocolizacion, SolicitudTaller, TIPIFICACION_CHOICES
from .pdf import generar_pdf_solicitud, generar_pdf_nota_elevacion, generar_pdf_solicitud_completa, generar_pdf_taller
from .docx_gen import generar_docx_solicitud, generar_docx_nota_elevacion, generar_docx_nota_comision, generar_docx_solicitud_completa

TIPIFICACIONES_VALIDAS = {t[0] for t in TIPIFICACION_CHOICES}


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


@login_required
def lista_solicitudes(request):
    if request.user.es_director_departamento:
        return redirect('solicitudes:lista_departamento')
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


def seleccionar_tipificacion(request):
    """Paso 1: el docente elige la tipificación antes de abrir el formulario."""
    return render(request, 'solicitudes/seleccionar_tipificacion.html')


def crear_solicitud(request, tipificacion):
    """Paso 2: formulario según tipificación."""
    if tipificacion not in TIPIFICACIONES_VALIDAS:
        messages.error(request, 'Tipo de solicitud inválido.')
        return redirect('solicitudes:crear')

    anonimo = not request.user.is_authenticated
    es_curricular = tipificacion in TIPIFICACIONES_CURRICULARES

    if request.method == 'POST':
        form = SolicitudProtocolizacionForm(request.POST, tipificacion=tipificacion, anonimo=anonimo)
        formset = EquipoDocenteFormSet(request.POST)
        plan_id = request.POST.get('plan_estudio') or None
        correlativas_formset = CorrelativaFormSet(request.POST, prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, plan_id)
        if form.is_valid() and formset.is_valid() and correlativas_formset.is_valid():
            solicitud = form.save(commit=False)
            if anonimo:
                solicitud.usuario = None
                solicitud.nombre_docente = form.cleaned_data['nombre_docente']
                solicitud.departamento_docente = form.cleaned_data.get('departamento_docente', '')
                solicitud.email_docente = form.cleaned_data.get('email_docente', '')
            else:
                solicitud.usuario = request.user
            solicitud.save()
            formset.instance = solicitud
            formset.save()
            correlativas_formset.instance = solicitud
            correlativas_formset.save()
            if anonimo:
                from .pdf import generar_pdf_solicitud
                buffer = generar_pdf_solicitud(solicitud)
                apellido = solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente'
                nombre = f"solicitud_{solicitud.pk}_{apellido}.pdf"
                from django.http import HttpResponse
                response = HttpResponse(buffer, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{nombre}"'
                return response
            from apps.notifications.utils import notificar_nuevo_tramite
            from django.urls import reverse
            notificar_nuevo_tramite(solicitud, 'Solicitud de Protocolización',
                                    url=reverse('solicitudes:detalle', args=[solicitud.pk]))
            messages.success(request, 'Solicitud enviada. Quedó pendiente de revisión.')
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudProtocolizacionForm(tipificacion=tipificacion, anonimo=anonimo)
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
        'anonimo': anonimo,
        'hs_totales_plan': None,
    })


def _puede_ver_solicitud(user, solicitud):
    """True si el usuario tiene acceso a esta solicitud."""
    if user.puede_revisar:
        return True
    if user.es_director_departamento:
        dep = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
        return dep == user.departamento
    return solicitud.usuario == user


@login_required
def detalle_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if not _puede_ver_solicitud(request.user, solicitud):
        messages.error(request, 'No tenés permisos para ver esta solicitud.')
        return redirect('solicitudes:lista')
    return render(request, 'solicitudes/detalle.html', {'solicitud': solicitud})


@login_required
def editar_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk, usuario=request.user)
    EDITABLES = (EstadoTramite.DEVUELTA, EstadoTramite.RECHAZADO, EstadoTramite.OBSERVADA)
    if solicitud.estado not in EDITABLES:
        messages.error(request, 'Solo podés editar solicitudes pendientes o con observaciones.')
        return redirect('solicitudes:detalle', pk=pk)

    tip = solicitud.tipificacion
    es_curricular = tip in TIPIFICACIONES_CURRICULARES

    if request.method == 'POST':
        form = SolicitudProtocolizacionForm(request.POST, instance=solicitud, tipificacion=tip)
        formset = EquipoDocenteFormSet(request.POST, instance=solicitud)
        plan_id = request.POST.get('plan_estudio') or None
        correlativas_formset = CorrelativaFormSet(request.POST, instance=solicitud, prefix='correlativas')
        _set_correlativas_materia_qs(correlativas_formset, plan_id)
        if form.is_valid() and formset.is_valid() and correlativas_formset.is_valid():
            solicitud = form.save(commit=False)
            solicitud.estado = EstadoTramite.PENDIENTE
            solicitud.save()
            formset.instance = solicitud
            formset.save()
            correlativas_formset.instance = solicitud
            correlativas_formset.save()
            messages.success(request, 'Solicitud actualizada y enviada nuevamente.')
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudProtocolizacionForm(instance=solicitud, tipificacion=tip)
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
    dep = request.user.departamento
    dep_solicitud = solicitud.usuario.departamento if solicitud.usuario else solicitud.departamento_docente
    if dep_solicitud != dep:
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')
    if solicitud.estado not in (EstadoTramite.PENDIENTE, EstadoTramite.OBSERVADA):
        messages.error(request, 'Solo podés revisar solicitudes en estado Pendiente o Con Observaciones.')
        return redirect('solicitudes:detalle', pk=pk)

    if request.method == 'POST':
        form = RevisionDirectorForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data['accion']
            if accion == 'elevada':
                if not solicitud.acta_comision_carrera or not solicitud.acta_consejo_departamental:
                    messages.error(request, 'Debés subir ambas actas (Comisión de Carrera y Consejo Departamental) antes de elevar.')
                    return render(request, 'solicitudes/revision_director.html', {'solicitud': solicitud, 'form': form})
            solicitud.estado = accion  # 'devuelta' | 'elevada'
            solicitud.comentarios_revision = form.cleaned_data['comentarios']
            solicitud.revisor = request.user
            solicitud.save()
            from apps.notifications.utils import notificar_cambio_estado
            from django.urls import reverse
            notificar_cambio_estado(solicitud, 'Solicitud de Protocolización',
                                    url=reverse('solicitudes:detalle', args=[solicitud.pk]))
            label = 'elevada al Administrador' if accion == 'elevada' else 'devuelta al docente con observaciones'
            messages.success(request, f'Solicitud {label}.')
            return redirect('solicitudes:detalle', pk=pk)
    else:
        form = RevisionDirectorForm()
    return render(request, 'solicitudes/revision_director.html', {'solicitud': solicitud, 'form': form})


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
            messages.success(request, 'Revisión guardada.')
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
    buffer = generar_pdf_solicitud_completa(solicitud)
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
    buffer = generar_docx_solicitud_completa(solicitud)
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
    dep_q = models.Q(usuario__departamento=dep) | models.Q(departamento_docente=dep)

    orden = Case(
        When(estado=EstadoTramite.APROBADO, then=1),
        default=0,
        output_field=IntegerField(),
    )

    solicitudes = (
        SolicitudProtocolizacion.objects
        .select_related('usuario')
        .filter(dep_q)
        .annotate(orden_estado=orden)
        .order_by('orden_estado', '-fecha_creacion')
    )
    talleres = (
        SolicitudTaller.objects
        .select_related('usuario')
        .filter(dep_q)
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
    if dep_solicitud != dep:
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
    if dep_solicitud != dep:
        messages.error(request, 'Esta solicitud no pertenece a tu departamento.')
        return redirect('solicitudes:lista_departamento')

    if request.method == 'POST':
        form = ActasAvalForm(request.POST, request.FILES)
        if form.is_valid():
            campos = []
            if form.cleaned_data.get('acta_comision_carrera'):
                solicitud.acta_comision_carrera = form.cleaned_data['acta_comision_carrera']
                campos.append('acta_comision_carrera')
            if form.cleaned_data.get('acta_consejo_departamental'):
                solicitud.acta_consejo_departamental = form.cleaned_data['acta_consejo_departamental']
                campos.append('acta_consejo_departamental')
            if campos:
                solicitud.save(update_fields=campos)
                messages.success(request, 'Acta(s) guardada(s) correctamente.')
            else:
                messages.warning(request, 'No se seleccionó ningún archivo.')
        else:
            for error in form.errors.values():
                messages.error(request, error[0])

    return redirect('solicitudes:detalle', pk=pk)


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
