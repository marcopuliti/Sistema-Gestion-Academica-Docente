from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.tramites.decorators import solo_administrador, solo_director_departamento
from apps.tramites.models import DEPARTAMENTO_CHOICES
from apps.notifications.utils import _crear_notificacion
from .forms import TribunalForm
from .models import AnioDictado, Carrera, InformeTribunalesEnviado, MateriaEnPlan, SolicitudCambioItem, SolicitudCambioTribunal, SolicitudInformeTribunal, TribunalExaminador
from .pdf import generar_pdf_informe_tribunales, generar_pdf_solicitud_cambio

DEPARTAMENTO_OPCIONES = [(v, l) for v, l in DEPARTAMENTO_CHOICES if v]

_CAMPOS_TRIBUNAL = [
    'presidente_nombre', 'presidente_dni',
    'vocal_1_nombre', 'vocal_1_dni',
    'vocal_2_nombre', 'vocal_2_dni',
    'dia_semana', 'hora', 'permite_libres',
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _pdf_buffer_departamento(departamento, director_user):
    """Genera el buffer PDF del informe de tribunales para un departamento."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admin = User.objects.filter(rol='administrador', is_active=True).first()
    meps = list(
        MateriaEnPlan.objects
        .filter(
            models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
            models.Q(departamento_dictante=departamento)
        )
        .filter(es_optativa=False)
        .select_related('materia', 'plan__carrera')
        .order_by('materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    )
    mep_ids = [mep.id for mep in meps]
    dir_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=mep_ids)
    }
    return generar_pdf_informe_tribunales(director_user, admin, meps, dir_map, dir_map)


def _meps_del_departamento(departamento):
    """MateriaEnPlan de años activos dictados por este departamento, sin optativas."""
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    plan_activo = models.Q(plan__vigente=True) | models.Q(plan__activo=True)
    propios = models.Q(plan__carrera__departamento=departamento, es_servicio=False)
    servicio = models.Q(departamento_dictante=departamento)
    return (
        MateriaEnPlan.objects
        .filter(plan_activo)
        .filter(propios | servicio)
        .filter(Exists(ano_qs))
        .filter(es_optativa=False)
    )


# ── director: materias del departamento ──────────────────────────────────────

@login_required
@solo_director_departamento
def materias_servicio(request):
    departamento = request.user.departamento

    ano_activo_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))

    meps = (
        MateriaEnPlan.objects
        .filter(plan__carrera__departamento=departamento)
        .filter(models.Q(plan__vigente=True) | models.Q(plan__activo=True))
        .filter(Exists(ano_activo_qs))
        .select_related('materia', 'plan__carrera')
        .order_by('plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre', 'materia__nombre')
    )

    all_ids = set(meps.values_list('id', flat=True))

    if request.method == 'POST':
        servicio_ids = set(int(x) for x in request.POST.getlist('es_servicio') if x.isdigit()) & all_ids
        optativa_ids = set(int(x) for x in request.POST.getlist('es_optativa') if x.isdigit()) & all_ids

        departamentos_por_mep = {}
        valid_depts = {v for v, _ in DEPARTAMENTO_OPCIONES}
        errores = []
        for mep_id in servicio_ids:
            dep = request.POST.get(f'departamento_{mep_id}', '').strip()
            if not dep or dep not in valid_depts:
                errores.append(mep_id)
            else:
                departamentos_por_mep[mep_id] = dep

        if errores:
            messages.error(request, 'Todas las materias marcadas como servicio deben tener un departamento seleccionado.')
        else:
            for mep_id, dep in departamentos_por_mep.items():
                MateriaEnPlan.objects.filter(id=mep_id).update(
                    es_servicio=True, departamento_dictante=dep,
                    es_optativa=mep_id in optativa_ids,
                )
            non_servicio = all_ids - servicio_ids
            MateriaEnPlan.objects.filter(id__in=non_servicio & optativa_ids).update(
                es_servicio=False, departamento_dictante='', es_optativa=True,
            )
            MateriaEnPlan.objects.filter(id__in=non_servicio - optativa_ids).update(
                es_servicio=False, departamento_dictante='', es_optativa=False,
            )
            messages.success(request, 'Cambios guardados correctamente.')
            return redirect('planes:materias_servicio')

    carreras_data = []
    carrera_entry = plan_entry = ano_entry = cuat_entry = None
    prev_carrera = prev_plan = prev_ano = prev_cuat = None

    for mep in meps:
        if mep.plan.carrera_id != prev_carrera:
            prev_carrera = mep.plan.carrera_id
            prev_plan = prev_ano = prev_cuat = None
            carrera_entry = {'carrera': mep.plan.carrera, 'planes': []}
            carreras_data.append(carrera_entry)
        if mep.plan_id != prev_plan:
            prev_plan = mep.plan_id
            prev_ano = prev_cuat = None
            plan_entry = {'plan': mep.plan, 'anos': []}
            carrera_entry['planes'].append(plan_entry)
        if mep.ano != prev_ano:
            prev_ano = mep.ano
            prev_cuat = None
            ano_entry = {'ano': mep.ano, 'cuatrimestres': []}
            plan_entry['anos'].append(ano_entry)
        if mep.cuatrimestre != prev_cuat:
            prev_cuat = mep.cuatrimestre
            cuat_entry = {'label': mep.get_cuatrimestre_display(), 'materias': []}
            ano_entry['cuatrimestres'].append(cuat_entry)
        cuat_entry['materias'].append(mep)

    ano_dictado_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    base_ext = (
        MateriaEnPlan.objects
        .filter(es_servicio=True, departamento_dictante=departamento)
        .exclude(plan__carrera__departamento=departamento)
        .filter(Exists(ano_dictado_qs))
        .select_related('materia', 'plan__carrera')
        .order_by('plan__carrera__nombre', 'ano', 'materia__nombre')
    )
    servicios_externos = {
        '1er Cuatrimestre': base_ext.filter(cuatrimestre=1),
        '2do Cuatrimestre': base_ext.filter(cuatrimestre=2),
        'Anuales':          base_ext.filter(cuatrimestre=3),
    }

    return render(request, 'planes/materias_servicio.html', {
        'carreras_data': carreras_data,
        'departamento': departamento,
        'departamento_opciones': DEPARTAMENTO_OPCIONES,
        'servicios_externos': servicios_externos,
    })


# ── director: tribunales ──────────────────────────────────────────────────────

@login_required
@solo_director_departamento
def lista_tribunales(request):
    departamento = request.user.departamento
    q = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '')

    base_qs = (
        MateriaEnPlan.objects
        .filter(
            models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
            models.Q(departamento_dictante=departamento)
        )
        .filter(es_optativa=False)
        .select_related('materia', 'plan__carrera')
        .order_by('materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    )

    meps_qs = base_qs
    if q:
        meps_qs = meps_qs.filter(
            models.Q(materia__nombre__icontains=q) |
            models.Q(materia__codigo__icontains=q)
        )
    if filtro == 'sin_registro':
        meps_qs = meps_qs.filter(tribunal__isnull=True)
    elif filtro == 'incompletos':
        meps_qs = meps_qs.filter(tribunal__presidente_nombre='')

    paginator = Paginator(meps_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_mep_ids = [mep.id for mep in page_obj]
    tribunales_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=page_mep_ids)
    }

    # Pre-build borrador proposal set to avoid N+1 queries
    borrador = (
        SolicitudCambioTribunal.objects
        .filter(director=request.user, departamento=departamento, estado='borrador')
        .prefetch_related('items')
        .first()
    )
    borrador_count = borrador.items.count() if borrador else 0
    borrador_tribunal_ids = (
        set(borrador.items.values_list('tribunal_id', flat=True)) if borrador else set()
    )

    for mep in page_obj:
        mep.tribunal_obj = tribunales_map.get(mep.id)
        mep.tribunal_tiene_propuesta = (
            mep.tribunal_obj is not None and mep.tribunal_obj.pk in borrador_tribunal_ids
        )

    all_ids = base_qs.values_list('id', flat=True)
    sin_registro_count = base_qs.filter(tribunal__isnull=True).count()
    incompletos_count = TribunalExaminador.objects.filter(
        materia_en_plan_id__in=all_ids,
        presidente_nombre='',
    ).count()

    solicitud = SolicitudInformeTribunal.objects.filter(activa=True).first()
    informe_enviado = (
        InformeTribunalesEnviado.objects
        .filter(departamento=departamento)
        .select_related('solicitud')
        .order_by('-fecha_envio')
        .first()
    )
    ya_enviado_esta_solicitud = (
        solicitud is not None and
        informe_enviado is not None and
        informe_enviado.solicitud_id == solicitud.pk
    )

    solicitudes_enviadas = SolicitudCambioTribunal.objects.filter(
        departamento=departamento, estado='enviada'
    ).count()

    solicitudes_cambio = (
        SolicitudCambioTribunal.objects
        .filter(departamento=departamento)
        .exclude(estado='borrador')
        .prefetch_related('items')
        .order_by('-fecha_creacion')[:10]
    )

    return render(request, 'planes/tribunales.html', {
        'page_obj': page_obj,
        'departamento': departamento,
        'q': q,
        'filtro': filtro,
        'solicitud_activa': solicitud is not None and not ya_enviado_esta_solicitud,
        'informe_enviado': informe_enviado,
        'sin_registro_count': sin_registro_count,
        'incompletos_count': incompletos_count,
        'borrador': borrador,
        'borrador_count': borrador_count,
        'solicitudes_enviadas': solicitudes_enviadas,
        'solicitudes_cambio': solicitudes_cambio,
    })


# ── director: proponer y enviar cambios de tribunal ──────────────────────────

@login_required
@solo_director_departamento
def proponer_cambio_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')

    departamento = request.user.departamento
    mep_ids = MateriaEnPlan.objects.filter(
        models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
        models.Q(departamento_dictante=departamento)
    ).filter(es_optativa=False).values_list('id', flat=True)

    tribunal = get_object_or_404(TribunalExaminador, pk=pk, materia_en_plan_id__in=mep_ids)

    form = TribunalForm(request.POST)
    if form.is_valid():
        # Get or create the current draft solicitud for this director/dept
        draft, _ = SolicitudCambioTribunal.objects.get_or_create(
            director=request.user,
            departamento=departamento,
            estado='borrador',
        )

        dia = form.cleaned_data['dia_semana']
        # Create or update the item for this tribunal in the draft
        SolicitudCambioItem.objects.update_or_create(
            solicitud=draft,
            tribunal=tribunal,
            defaults={
                'presidente_nombre': form.cleaned_data['presidente_nombre'],
                'presidente_dni': form.cleaned_data['presidente_dni'],
                'vocal_1_nombre': form.cleaned_data['vocal_1_nombre'],
                'vocal_1_dni': form.cleaned_data['vocal_1_dni'],
                'vocal_2_nombre': form.cleaned_data['vocal_2_nombre'],
                'vocal_2_dni': form.cleaned_data['vocal_2_dni'],
                'dia_semana': int(dia) if dia else None,
                'hora': form.cleaned_data['hora'],
                'permite_libres': form.cleaned_data['permite_libres'],
            },
        )
        messages.success(request, 'Cambio propuesto guardado.')
    else:
        messages.error(request, 'Corregí los errores del formulario.')

    return redirect('planes:lista_tribunales')


@login_required
@solo_director_departamento
def enviar_solicitud_cambio(request):
    from django.http import JsonResponse

    if request.method != 'POST':
        return redirect('planes:lista_tribunales')

    departamento = request.user.departamento

    try:
        borrador = SolicitudCambioTribunal.objects.get(
            director=request.user,
            departamento=departamento,
            estado='borrador',
        )
    except SolicitudCambioTribunal.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No hay cambios propuestos.'}, status=400)

    if not borrador.items.exists():
        return JsonResponse({'ok': False, 'error': 'No hay cambios propuestos.'}, status=400)

    borrador.estado = 'enviada'
    borrador.fecha_envio = timezone.now()
    borrador.save()

    from django.contrib.auth import get_user_model
    User = get_user_model()
    url_lista = reverse('planes:lista_solicitudes_cambio')
    for admin_user in User.objects.filter(rol='administrador', is_active=True):
        _crear_notificacion(
            admin_user, 'nuevo_tramite',
            f'Solicitud de cambio de tribunales — Dpto. {departamento}',
            f'{request.user.get_full_name()} envió una solicitud de cambio de tribunales '
            f'del Departamento de {departamento}.',
            url=url_lista,
        )

    download_url = reverse('planes:descargar_solicitud_cambio', args=[borrador.pk])
    return JsonResponse({'ok': True, 'pk': borrador.pk, 'download_url': download_url})


@login_required
@solo_director_departamento
def descargar_solicitud_cambio(request, pk):
    from django.http import HttpResponse
    from django.contrib.auth import get_user_model
    User = get_user_model()

    departamento = request.user.departamento
    solicitud = get_object_or_404(SolicitudCambioTribunal, pk=pk, departamento=departamento)

    items = list(
        solicitud.items
        .select_related('tribunal__materia_en_plan__materia', 'tribunal__materia_en_plan__plan__carrera')
        .all()
    )
    meps = sorted(
        [item.tribunal.materia_en_plan for item in items],
        key=lambda m: (m.materia.codigo, m.plan.carrera.nombre, m.plan.codigo, m.ano, m.cuatrimestre),
    )
    item_map = {item.tribunal.materia_en_plan_id: item for item in items}
    mep_ids = [mep.id for mep in meps]
    current_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=mep_ids)
    }

    admin = User.objects.filter(rol='administrador', is_active=True).first()
    director_user = solicitud.director or request.user
    buffer = generar_pdf_solicitud_cambio(director_user, admin, meps, item_map, current_map)

    safe_dept = departamento.lower().replace(' ', '_')
    fecha_str = solicitud.fecha_creacion.strftime('%Y%m%d')
    filename = f'solicitud_cambio_tribunales_{safe_dept}_{fecha_str}.pdf'
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── admin: informes de tribunales ─────────────────────────────────────────────

@login_required
@solo_administrador
def solicitar_informe_tribunales(request):
    if request.method != 'POST':
        return redirect('tramites:dashboard')

    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Marcar solicitudes anteriores como inactivas y crear la nueva
    SolicitudInformeTribunal.objects.filter(activa=True).update(activa=False)
    SolicitudInformeTribunal.objects.create(solicitante=request.user)

    # Crear TribunalExaminador para MEPs que aún no tienen uno
    plan_activo = models.Q(plan__vigente=True) | models.Q(plan__activo=True)
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    meps_sin_tribunal = (
        MateriaEnPlan.objects
        .filter(plan_activo)
        .filter(Exists(ano_qs))
        .filter(tribunal__isnull=True)
        .filter(es_optativa=False)
        .select_related('materia', 'plan')
    )
    creados = 0
    for mep in meps_sin_tribunal:
        TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
        creados += 1

    # Notificar a todos los directores activos
    url_tribunales = reverse('planes:lista_tribunales')
    directores = User.objects.filter(rol='director_departamento', is_active=True)
    notificados = 0
    for director in directores:
        _crear_notificacion(
            director,
            'nuevo_tramite',
            'Informe de comisiones anuales — Revisión de tribunales',
            'Se solicita que revises los tribunales examinadores de tu departamento para el presente año.\n\n'
            'Verificá que los datos estén actualizados, realizá los cambios necesarios y confirmá el estado de cada tribunal.\n\n'
            'Una vez revisados, podés proponer cambios usando el formulario de cada tribunal.',
            url=url_tribunales,
        )
        notificados += 1

    resumen = f'Solicitud enviada a {notificados} director{"es" if notificados != 1 else ""}.'
    if creados:
        resumen += f' Se inicializaron {creados} tribunal{"es" if creados != 1 else ""} sin datos previos.'
    messages.success(request, resumen)
    return redirect('tramites:dashboard')


@login_required
@solo_director_departamento
def enviar_informe_tribunales(request):
    from django.http import JsonResponse
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')

    solicitud = SolicitudInformeTribunal.objects.filter(activa=True).first()
    if not solicitud:
        return JsonResponse({'ok': False, 'error': 'No hay una solicitud de informe activa.'}, status=400)

    from django.contrib.auth import get_user_model
    User = get_user_model()

    director = request.user
    departamento = director.departamento

    InformeTribunalesEnviado.objects.update_or_create(
        solicitud=solicitud,
        departamento=departamento,
        defaults={'director': director, 'fecha_envio': timezone.now()},
    )

    admin = User.objects.filter(rol='administrador', is_active=True).first()
    if admin:
        _crear_notificacion(
            admin, 'nuevo_tramite',
            f'Informe de tribunales enviado — Dpto. {departamento}',
            f'{director.get_full_name()} envió el informe anual de tribunales '
            f'del Departamento de {departamento}.',
            url=reverse('planes:lista_solicitudes_cambio'),
        )

    return JsonResponse({'ok': True})


@login_required
@solo_director_departamento
def descargar_informe_tribunales(request):
    from django.http import HttpResponse
    departamento = request.user.departamento
    informe = (
        InformeTribunalesEnviado.objects
        .filter(departamento=departamento)
        .select_related('solicitud')
        .order_by('-fecha_envio')
        .first()
    )
    if not informe:
        messages.error(request, 'No hay informe enviado para descargar.')
        return redirect('planes:lista_tribunales')

    buffer = _pdf_buffer_departamento(departamento, request.user)

    safe_dept = departamento.lower().replace(' ', '_')
    filename = f'tribunales_{safe_dept}_{informe.ano}.pdf'
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── director: mis solicitudes de cambio ──────────────────────────────────────

@login_required
@solo_director_departamento
def mis_solicitudes_cambio(request):
    qs = (
        SolicitudCambioTribunal.objects
        .filter(director=request.user)
        .prefetch_related('items')
        .order_by('-fecha_creacion')
    )
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'planes/mis_solicitudes_cambio.html', {
        'page_obj': page_obj,
    })


# ── admin: listado de materias en plan ───────────────────────────────────────

@login_required
@solo_administrador
def admin_lista_materias_en_plan(request):
    q = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '')
    dept = request.GET.get('departamento', '')
    carrera_pk = request.GET.get('carrera', '')

    base_qs = (
        MateriaEnPlan.objects
        .select_related('materia', 'plan__carrera')
        .order_by('plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre', 'materia__nombre')
    )

    if q:
        base_qs = base_qs.filter(
            models.Q(materia__nombre__icontains=q) |
            models.Q(materia__codigo__icontains=q)
        )
    if dept:
        base_qs = base_qs.filter(
            models.Q(plan__carrera__departamento=dept) |
            models.Q(departamento_dictante=dept)
        )
    if carrera_pk:
        base_qs = base_qs.filter(plan__carrera__pk=carrera_pk)

    sin_tribunal_count = base_qs.filter(es_optativa=False, tribunal__isnull=True).count()
    incompleto_count = base_qs.filter(es_optativa=False, tribunal__presidente_nombre='').count()
    completo_count = base_qs.filter(es_optativa=False).exclude(tribunal__isnull=True).exclude(tribunal__presidente_nombre='').count()
    optativa_count = base_qs.filter(es_optativa=True).count()

    qs = base_qs
    if filtro == 'sin_tribunal':
        qs = base_qs.filter(es_optativa=False, tribunal__isnull=True)
    elif filtro == 'incompleto':
        qs = base_qs.filter(es_optativa=False, tribunal__presidente_nombre='')
    elif filtro == 'completo':
        qs = base_qs.filter(es_optativa=False).exclude(tribunal__isnull=True).exclude(tribunal__presidente_nombre='')
    elif filtro == 'optativas':
        qs = base_qs.filter(es_optativa=True)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_mep_ids = [mep.id for mep in page_obj]
    tribunales_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=page_mep_ids)
    }
    for mep in page_obj:
        mep.tribunal_obj = tribunales_map.get(mep.id)

    carrera_opciones = Carrera.objects.values_list('pk', 'nombre').order_by('nombre')

    return render(request, 'planes/admin_lista_materias_en_plan.html', {
        'page_obj': page_obj,
        'q': q,
        'filtro': filtro,
        'dept': dept,
        'carrera_pk': carrera_pk,
        'departamento_opciones': DEPARTAMENTO_OPCIONES,
        'carrera_opciones': carrera_opciones,
        'sin_tribunal_count': sin_tribunal_count,
        'incompleto_count': incompleto_count,
        'completo_count': completo_count,
        'optativa_count': optativa_count,
        'total_count': base_qs.count(),
    })


# ── admin: crear tribunal vacío ──────────────────────────────────────────────

@login_required
@solo_administrador
def admin_crear_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:admin_lista_materias_en_plan')
    mep = get_object_or_404(MateriaEnPlan, pk=pk)
    _, created = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
    if created:
        messages.success(request, f'Tribunal creado para {mep.materia.nombre}.')
    else:
        messages.info(request, f'{mep.materia.nombre} ya tenía tribunal.')
    next_url = request.POST.get('next') or reverse('planes:admin_lista_materias_en_plan')
    return redirect(next_url)


# ── admin: solicitudes de cambio de tribunal ──────────────────────────────────

@login_required
@solo_administrador
def lista_solicitudes_cambio(request):
    dept_filtro = request.GET.get('departamento', '')

    qs = (
        SolicitudCambioTribunal.objects
        .select_related('director')
        .prefetch_related('items')
        .order_by('-fecha_creacion')
    )
    if dept_filtro:
        qs = qs.filter(departamento=dept_filtro)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'planes/admin_lista_solicitudes_cambio.html', {
        'page_obj': page_obj,
        'dept_filtro': dept_filtro,
        'departamento_opciones': DEPARTAMENTO_OPCIONES,
    })


@login_required
@solo_administrador
def detalle_solicitud_cambio(request, pk):
    solicitud = get_object_or_404(
        SolicitudCambioTribunal.objects.select_related('director'),
        pk=pk,
    )

    items = list(
        solicitud.items
        .select_related(
            'tribunal__materia_en_plan__materia',
            'tribunal__materia_en_plan__plan__carrera',
        )
        .order_by(
            'tribunal__materia_en_plan__materia__codigo',
            'tribunal__materia_en_plan__plan__carrera__nombre',
            'tribunal__materia_en_plan__plan__codigo',
            'tribunal__materia_en_plan__ano',
        )
    )

    for item in items:
        item.t_actual = item.tribunal
        t = item.tribunal
        item.diff = {
            'presidente': (
                item.presidente_nombre != t.presidente_nombre or
                item.presidente_dni != t.presidente_dni
            ),
            'vocal_1': (
                item.vocal_1_nombre != t.vocal_1_nombre or
                item.vocal_1_dni != t.vocal_1_dni
            ),
            'vocal_2': (
                item.vocal_2_nombre != t.vocal_2_nombre or
                item.vocal_2_dni != t.vocal_2_dni
            ),
            'dia_hora': (
                item.dia_semana != t.dia_semana or
                item.hora != t.hora
            ),
            'modalidad': item.permite_libres != t.permite_libres,
        }

    return render(request, 'planes/admin_detalle_solicitud_cambio.html', {
        'solicitud': solicitud,
        'items': items,
    })


@login_required
@solo_administrador
def aplicar_solicitud(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_solicitudes_cambio')

    solicitud = get_object_or_404(
        SolicitudCambioTribunal,
        pk=pk,
        estado='enviada',
    )

    for item in solicitud.items.select_related('tribunal'):
        tribunal = item.tribunal
        for campo in _CAMPOS_TRIBUNAL:
            setattr(tribunal, campo, getattr(item, campo))
        tribunal.save()

    solicitud.estado = 'aplicada'
    solicitud.save()

    if solicitud.director:
        _crear_notificacion(
            solicitud.director, 'nuevo_tramite',
            'Tu solicitud de cambio fue aplicada',
            f'La solicitud de cambio de tribunales del Departamento de {solicitud.departamento} '
            f'fue revisada y aplicada por administración.',
            url=reverse('planes:lista_tribunales'),
        )

    messages.success(request, 'Solicitud aplicada correctamente.')
    return redirect('planes:detalle_solicitud_cambio', pk=pk)


@login_required
@solo_administrador
def admin_descargar_solicitud_cambio(request, pk):
    from django.http import HttpResponse
    from django.contrib.auth import get_user_model
    User = get_user_model()

    solicitud = get_object_or_404(
        SolicitudCambioTribunal.objects.select_related('director'),
        pk=pk,
    )

    items = list(
        solicitud.items
        .select_related('tribunal__materia_en_plan__materia', 'tribunal__materia_en_plan__plan__carrera')
        .all()
    )
    meps = sorted(
        [item.tribunal.materia_en_plan for item in items],
        key=lambda m: (m.materia.codigo, m.plan.carrera.nombre, m.plan.codigo, m.ano, m.cuatrimestre),
    )
    item_map = {item.tribunal.materia_en_plan_id: item for item in items}
    mep_ids = [mep.id for mep in meps]
    current_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=mep_ids)
    }

    admin_user = User.objects.filter(rol='administrador', is_active=True).first()
    director_user = solicitud.director or admin_user
    buffer = generar_pdf_solicitud_cambio(director_user, admin_user, meps, item_map, current_map)

    safe_dept = solicitud.departamento.lower().replace(' ', '_')
    fecha_str = solicitud.fecha_creacion.strftime('%Y%m%d')
    filename = f'solicitud_cambio_tribunales_{safe_dept}_{fecha_str}.pdf'
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
