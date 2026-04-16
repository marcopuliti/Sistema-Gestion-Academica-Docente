from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse

from apps.tramites.decorators import puede_revisar
from apps.tramites.models import EstadoTramite
from .forms import PlanificacionActividadesForm, RevisionForm
from .models import PlanificacionActividades
from .pdf import generar_pdf_planificacion


@login_required
def lista_planillas(request):
    if request.user.puede_revisar:
        qs = PlanificacionActividades.objects.select_related('usuario').all()
    else:
        qs = PlanificacionActividades.objects.filter(usuario=request.user)
    return render(request, 'planillas/lista.html', {'planillas': qs})


def crear_planilla(request):
    anonimo = not request.user.is_authenticated
    if request.method == 'POST':
        form = PlanificacionActividadesForm(request.POST, anonimo=anonimo)
        if form.is_valid():
            obj = form.save(commit=False)
            if anonimo:
                obj.usuario = None
                obj.nombre_docente = form.cleaned_data['nombre_docente']
                obj.legajo_docente = form.cleaned_data['legajo_docente']
                obj.departamento_docente = form.cleaned_data.get('departamento_docente', '')
                obj.email_docente = form.cleaned_data.get('email_docente', '')
            else:
                obj.usuario = request.user
            obj.save()
            if anonimo:
                buffer = generar_pdf_planificacion(obj)
                apellido = obj.nombre_docente.split()[-1] if obj.nombre_docente else 'docente'
                nombre = f"planificacion_{obj.anno}_{apellido}.pdf"
                response = HttpResponse(buffer, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{nombre}"'
                return response
            from apps.notifications.utils import notificar_nuevo_tramite
            notificar_nuevo_tramite(obj, 'Planificación de Actividades')
            messages.success(request, 'Planificación enviada. Queda pendiente de revisión.')
            return redirect('planillas:detalle', pk=obj.pk)
    else:
        form = PlanificacionActividadesForm(anonimo=anonimo)
    return render(request, 'planillas/form.html', {
        'form': form,
        'titulo': 'Nueva Planificación de Actividades',
        'anonimo': anonimo,
    })


@login_required
def detalle_planilla(request, pk):
    if request.user.puede_revisar:
        obj = get_object_or_404(PlanificacionActividades, pk=pk)
    else:
        obj = get_object_or_404(PlanificacionActividades, pk=pk, usuario=request.user)
    secciones_a = [
        ('A.1', 'Actividades curriculares de grado y pregrado', obj.a1_descripcion, obj.a1_hs_1c, obj.a1_hs_2c),
        ('A.2', 'Cursos extracurriculares',                    obj.a2_descripcion, obj.a2_hs_1c, obj.a2_hs_2c),
        ('A.3', 'Tareas de posgrado',                          obj.a3_descripcion, obj.a3_hs_1c, obj.a3_hs_2c),
        ('A.4', 'Formación de recursos humanos',               obj.a4_descripcion, obj.a4_hs_1c, obj.a4_hs_2c),
    ]
    secciones_bg = [
        ('B', 'INVESTIGACIÓN',            obj.b_descripcion, obj.b_hs_1c, obj.b_hs_2c),
        ('C', 'TRANSFERENCIAS O SERVICIOS', obj.c_descripcion, obj.c_hs_1c, obj.c_hs_2c),
        ('D', 'EXTENSIÓN UNIVERSITARIA',  obj.d_descripcion, obj.d_hs_1c, obj.d_hs_2c),
        ('E', 'PERFECCIONAMIENTO',         obj.e_descripcion, obj.e_hs_1c, obj.e_hs_2c),
        ('F', 'GOBIERNO Y GESTIÓN',        obj.f_descripcion, obj.f_hs_1c, obj.f_hs_2c),
        ('G', 'OTROS',                     obj.g_descripcion, obj.g_hs_1c, obj.g_hs_2c),
    ]
    return render(request, 'planillas/detalle.html', {
        'planilla': obj,
        'secciones_a': secciones_a,
        'secciones_bg': secciones_bg,
    })


@login_required
def editar_planilla(request, pk):
    obj = get_object_or_404(PlanificacionActividades, pk=pk, usuario=request.user)
    if obj.estado not in (EstadoTramite.PENDIENTE, EstadoTramite.RECHAZADO):
        messages.error(request, 'Solo podés editar planificaciones pendientes o rechazadas.')
        return redirect('planillas:detalle', pk=pk)
    if request.method == 'POST':
        form = PlanificacionActividadesForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.estado = EstadoTramite.PENDIENTE
            obj.save()
            messages.success(request, 'Planificación actualizada y reenviada.')
            return redirect('planillas:detalle', pk=obj.pk)
    else:
        form = PlanificacionActividadesForm(instance=obj)
    return render(request, 'planillas/form.html', {'form': form, 'titulo': 'Editar Planificación', 'edicion': True})


@login_required
@puede_revisar
def revisar_planilla(request, pk):
    obj = get_object_or_404(PlanificacionActividades, pk=pk)
    if request.method == 'POST':
        form = RevisionForm(request.POST)
        if form.is_valid():
            obj.estado = form.cleaned_data['estado']
            obj.comentarios_revision = form.cleaned_data['comentarios']
            obj.revisor = request.user
            obj.save()
            from apps.notifications.utils import notificar_cambio_estado
            notificar_cambio_estado(obj, 'Planificación de Actividades')
            messages.success(request, 'Revisión guardada.')
            return redirect('planillas:detalle', pk=pk)
    else:
        form = RevisionForm()
    return render(request, 'planillas/revision.html', {'planilla': obj, 'form': form})


@login_required
def descargar_pdf_planilla(request, pk):
    if request.user.puede_revisar:
        obj = get_object_or_404(PlanificacionActividades, pk=pk)
    else:
        obj = get_object_or_404(PlanificacionActividades, pk=pk, usuario=request.user)
    buffer = generar_pdf_planificacion(obj)
    apellido = obj.usuario.last_name if obj.usuario else (obj.nombre_docente.split()[-1] if obj.nombre_docente else 'docente')
    nombre = f"planificacion_{obj.anno}_{apellido}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response
