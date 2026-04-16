import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse

from apps.tramites.decorators import puede_revisar
from apps.tramites.models import EstadoTramite, CalendarioAcademico
from .forms import SolicitudProtocolizacionForm, EquipoDocenteFormSet, RevisionForm, TIPIFICACIONES_CURRICULARES
from .models import SolicitudProtocolizacion, TIPIFICACION_CHOICES
from .pdf import generar_pdf_solicitud

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
                solicitud.legajo_docente = form.cleaned_data['legajo_docente']
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
    })


@login_required
def detalle_solicitud(request, pk):
    if request.user.puede_revisar:
        solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    else:
        solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk, usuario=request.user)
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

    return render(request, 'solicitudes/form.html', {
        'form': form,
        'formset': formset,
        'tipificacion': tip,
        'es_curricular': es_curricular,
        'titulo': 'Editar Solicitud',
        'edicion': True,
        'calendario_json': _calendario_json(),
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
    if request.user.puede_revisar:
        solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk)
    else:
        solicitud = get_object_or_404(SolicitudProtocolizacion, pk=pk, usuario=request.user)
    buffer = generar_pdf_solicitud(solicitud)
    apellido = solicitud.usuario.last_name if solicitud.usuario else (solicitud.nombre_docente.split()[-1] if solicitud.nombre_docente else 'docente')
    nombre = f"solicitud_{solicitud.pk}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response
