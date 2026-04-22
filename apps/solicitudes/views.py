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
from .forms import SolicitudProtocolizacionForm, EquipoDocenteFormSet, RevisionForm, TIPIFICACIONES_CURRICULARES
from .models import SolicitudProtocolizacion, TIPIFICACION_CHOICES
from .pdf import generar_pdf_solicitud, generar_pdf_nota_elevacion, generar_pdf_solicitud_completa
from .docx_gen import generar_docx_solicitud, generar_docx_nota_elevacion, generar_docx_nota_comision, generar_docx_solicitud_completa

TIPIFICACIONES_VALIDAS = {t[0] for t in TIPIFICACION_CHOICES}


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
    if request.user.puede_revisar:
        solicitudes = SolicitudProtocolizacion.objects.select_related('usuario').all()
    else:
        solicitudes = SolicitudProtocolizacion.objects.filter(usuario=request.user)
    return render(request, 'solicitudes/lista.html', {'solicitudes': solicitudes})


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
        if form.is_valid() and formset.is_valid():
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
            notificar_nuevo_tramite(solicitud, 'Solicitud de Protocolización')
            messages.success(request, 'Solicitud enviada. Quedó pendiente de revisión.')
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudProtocolizacionForm(tipificacion=tipificacion, anonimo=anonimo)
        formset = EquipoDocenteFormSet()

    return render(request, 'solicitudes/form.html', {
        'form': form,
        'formset': formset,
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
    if solicitud.estado not in (EstadoTramite.PENDIENTE, EstadoTramite.RECHAZADO):
        messages.error(request, 'Solo podés editar solicitudes pendientes o rechazadas.')
        return redirect('solicitudes:detalle', pk=pk)

    tip = solicitud.tipificacion
    es_curricular = tip in TIPIFICACIONES_CURRICULARES

    if request.method == 'POST':
        form = SolicitudProtocolizacionForm(request.POST, instance=solicitud, tipificacion=tip)
        formset = EquipoDocenteFormSet(request.POST, instance=solicitud)
        if form.is_valid() and formset.is_valid():
            solicitud = form.save(commit=False)
            solicitud.estado = EstadoTramite.PENDIENTE
            solicitud.save()
            formset.instance = solicitud
            formset.save()
            messages.success(request, 'Solicitud actualizada y enviada nuevamente.')
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudProtocolizacionForm(instance=solicitud, tipificacion=tip)
        formset = EquipoDocenteFormSet(instance=solicitud)

    hs_totales_plan = (
        solicitud.optativa_vinculada.hs_totales
        if solicitud.optativa_vinculada else None
    )
    return render(request, 'solicitudes/form.html', {
        'form': form,
        'formset': formset,
        'tipificacion': tip,
        'es_curricular': es_curricular,
        'titulo': 'Editar Solicitud',
        'edicion': True,
        'calendario_json': _calendario_json(),
        'hs_totales_plan': hs_totales_plan,
    })


@login_required
@puede_revisar
def revisar_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    if request.method == 'POST':
        form = RevisionForm(request.POST)
        if form.is_valid():
            solicitud.estado = form.cleaned_data['estado']
            solicitud.comentarios_revision = form.cleaned_data['comentarios']
            solicitud.revisor = request.user
            solicitud.save()
            from apps.notifications.utils import notificar_cambio_estado
            notificar_cambio_estado(solicitud, 'Solicitud de Protocolización')
            messages.success(request, 'Revisión guardada.')
            return redirect('solicitudes:detalle', pk=pk)
    else:
        form = RevisionForm()
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
    from apps.tramites.models import EstadoTramite
    dep = request.user.departamento
    qs = SolicitudProtocolizacion.objects.select_related('usuario').filter(
        models.Q(usuario__departamento=dep) | models.Q(departamento_docente=dep)
    )
    # No aprobadas primero, luego por fecha descendente
    from django.db.models import Case, When, IntegerField
    qs = qs.annotate(
        orden_estado=Case(
            When(estado=EstadoTramite.APROBADO, then=1),
            default=0,
            output_field=IntegerField(),
        )
    ).order_by('orden_estado', '-fecha_creacion')
    return render(request, 'solicitudes/lista_departamento.html', {
        'solicitudes': qs,
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
