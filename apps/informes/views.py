from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse

from apps.tramites.decorators import puede_revisar
from apps.tramites.models import EstadoTramite
from .forms import InformeActividadAnualForm, RevisionForm
from .models import InformeActividadAnual
from .pdf import generar_pdf_informe


@login_required
def lista_informes(request):
    if request.user.puede_revisar:
        informes = InformeActividadAnual.objects.select_related('usuario').all()
    else:
        informes = InformeActividadAnual.objects.filter(usuario=request.user)
    return render(request, 'informes/lista.html', {'informes': informes})


def crear_informe(request):
    anonimo = not request.user.is_authenticated
    if request.method == 'POST':
        form = InformeActividadAnualForm(request.POST, anonimo=anonimo)
        if form.is_valid():
            informe = form.save(commit=False)
            if anonimo:
                informe.usuario = None
                informe.nombre_docente = form.cleaned_data['nombre_docente']
                informe.legajo_docente = form.cleaned_data['legajo_docente']
                informe.departamento_docente = form.cleaned_data.get('departamento_docente', '')
                informe.email_docente = form.cleaned_data.get('email_docente', '')
            else:
                informe.usuario = request.user
            informe.save()
            if anonimo:
                # Para anónimos: generar y devolver el PDF directamente
                buffer = generar_pdf_informe(informe)
                nombre = f"informe_{informe.anno_academico}_{informe.nombre_docente.split()[-1] if informe.nombre_docente else 'docente'}.pdf"
                response = HttpResponse(buffer, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{nombre}"'
                return response
            from apps.notifications.utils import notificar_nuevo_tramite
            notificar_nuevo_tramite(informe, 'Informe de Actividad Anual')
            messages.success(request, 'Informe enviado correctamente. Quedó pendiente de revisión.')
            return redirect('informes:detalle', pk=informe.pk)
    else:
        form = InformeActividadAnualForm(anonimo=anonimo)
    return render(request, 'informes/form.html', {
        'form': form,
        'titulo': 'Nuevo Informe de Actividad Anual',
        'anonimo': anonimo,
    })


@login_required
def detalle_informe(request, pk):
    if request.user.puede_revisar:
        informe = get_object_or_404(InformeActividadAnual, pk=pk)
    else:
        informe = get_object_or_404(InformeActividadAnual, pk=pk, usuario=request.user)
    return render(request, 'informes/detalle.html', {'informe': informe})


@login_required
def editar_informe(request, pk):
    informe = get_object_or_404(InformeActividadAnual, pk=pk, usuario=request.user)
    if informe.estado not in (EstadoTramite.PENDIENTE, EstadoTramite.RECHAZADO):
        messages.error(request, 'Solo podés editar informes pendientes o rechazados.')
        return redirect('informes:detalle', pk=pk)
    if request.method == 'POST':
        form = InformeActividadAnualForm(request.POST, instance=informe)
        if form.is_valid():
            informe = form.save(commit=False)
            informe.estado = EstadoTramite.PENDIENTE
            informe.save()
            messages.success(request, 'Informe actualizado y enviado nuevamente.')
            return redirect('informes:detalle', pk=informe.pk)
    else:
        form = InformeActividadAnualForm(instance=informe)
    return render(request, 'informes/form.html', {'form': form, 'titulo': 'Editar Informe', 'edicion': True})


@login_required
@puede_revisar
def revisar_informe(request, pk):
    informe = get_object_or_404(InformeActividadAnual, pk=pk)
    if request.method == 'POST':
        form = RevisionForm(request.POST)
        if form.is_valid():
            informe.estado = form.cleaned_data['estado']
            informe.comentarios_revision = form.cleaned_data['comentarios']
            informe.revisor = request.user
            informe.save()
            from apps.notifications.utils import notificar_cambio_estado
            notificar_cambio_estado(informe, 'Informe de Actividad Anual')
            messages.success(request, 'Revisión guardada correctamente.')
            return redirect('informes:detalle', pk=pk)
    else:
        form = RevisionForm()
    return render(request, 'informes/revision.html', {'informe': informe, 'form': form})


@login_required
def descargar_pdf_informe(request, pk):
    if request.user.puede_revisar:
        informe = get_object_or_404(InformeActividadAnual, pk=pk)
    else:
        informe = get_object_or_404(InformeActividadAnual, pk=pk, usuario=request.user)
    buffer = generar_pdf_informe(informe)
    apellido = informe.usuario.last_name if informe.usuario else (informe.nombre_docente.split()[-1] if informe.nombre_docente else 'docente')
    nombre = f"informe_{informe.anno_academico}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response
