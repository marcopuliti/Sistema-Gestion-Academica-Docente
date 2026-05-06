from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.tramites.decorators import solo_administrador, solo_admin_general, solo_director_carrera, solo_director_departamento
from apps.tramites.models import DEPARTAMENTO_CHOICES
from apps.notifications.utils import _crear_notificacion
from .forms import TribunalForm
from .models import AnioDictado, Carrera, ConvocatoriaSolicitudServicio, InformeTribunalesEnviado, MateriaEnPlan, SolicitudCambioItem, SolicitudCambioTribunal, SolicitudInformeTribunal, SolicitudServicio, SolicitudServicioItem, TribunalExaminador
from .pdf import generar_pdf_informe_tribunales, generar_pdf_solicitud_cambio, generar_pdf_solicitud_servicio

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
    admin = User.objects.filter(rol='secretario', is_active=True).first()
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
        .annotate(se_dicta=Exists(ano_activo_qs))
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
            ano_entry = {'ano': mep.ano, 'se_dicta': mep.se_dicta, 'cuatrimestres': []}
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

    _ano_dictado_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))

    base_qs = (
        MateriaEnPlan.objects
        .filter(
            models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
            models.Q(departamento_dictante=departamento)
        )
        .filter(es_optativa=False)
        .annotate(se_dicta=Exists(_ano_dictado_qs))
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
    elif filtro == 'sin_dictado':
        meps_qs = meps_qs.filter(se_dicta=False)

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
    no_dictados_count = base_qs.filter(se_dicta=False).count()

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

    # Q1: todos los departamentos; Q2: solo los departamentos con nuevos tribunales
    if solicitud is not None:
        if solicitud.cuatrimestre == 1:
            solicitud_para_dept = True
        else:
            solicitud_para_dept = departamento in solicitud.departamentos_notificados
    else:
        solicitud_para_dept = False

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
        'solicitud': solicitud,
        'solicitud_activa': solicitud_para_dept and not ya_enviado_esta_solicitud,
        'informe_enviado': informe_enviado,
        'sin_registro_count': sin_registro_count,
        'incompletos_count': incompletos_count,
        'no_dictados_count': no_dictados_count,
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

        def _snapshot(t):
            return {
                'presidente_nombre': t.presidente_nombre,
                'presidente_dni': t.presidente_dni,
                'vocal_1_nombre': t.vocal_1_nombre,
                'vocal_1_dni': t.vocal_1_dni,
                'vocal_2_nombre': t.vocal_2_nombre,
                'vocal_2_dni': t.vocal_2_dni,
                'dia_semana': t.dia_semana,
                'hora': t.hora.strftime('%H:%M') if t.hora else None,
                'permite_libres': t.permite_libres,
            }

        item, created = SolicitudCambioItem.objects.update_or_create(
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
        if created:
            item.snapshot_tribunal = _snapshot(tribunal)
            item.save(update_fields=['snapshot_tribunal'])
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
    for admin_user in User.objects.filter(rol__in=['secretario', 'direccion_academica', 'dpto_estudiantes'], is_active=True):
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

    admin = User.objects.filter(rol='secretario', is_active=True).first()
    director_user = solicitud.director or request.user
    buffer = generar_pdf_solicitud_cambio(director_user, admin, meps, item_map, current_map)

    safe_dept = departamento.lower().replace(' ', '_')
    fecha_str = solicitud.fecha_creacion.strftime('%Y%m%d')
    filename = f'solicitud_cambio_tribunales_{safe_dept}_{fecha_str}.pdf'
    pdf_bytes = buffer.read()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Length'] = len(pdf_bytes)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── admin: informes de tribunales ─────────────────────────────────────────────

@login_required
@solo_admin_general
def solicitar_informe_tribunales(request):
    if request.method != 'POST':
        return redirect('tramites:dashboard')

    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        cuatrimestre = int(request.POST.get('cuatrimestre', 1))
        anio = int(request.POST.get('anio', timezone.now().year))
        if cuatrimestre not in (1, 2):
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, 'Cuatrimestre o año inválido.')
        return redirect('tramites:dashboard')

    # Desactivar solicitudes anteriores
    SolicitudInformeTribunal.objects.filter(activa=True).update(activa=False)

    # Filtro por cuatrimestre: Q1 incluye anuales (3), Q2 solo cuatrimestre 2
    plan_activo = models.Q(plan__vigente=True) | models.Q(plan__activo=True)
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    if cuatrimestre == 1:
        cuatrimestre_filter = models.Q(cuatrimestre__in=[1, 3])
    else:
        cuatrimestre_filter = models.Q(cuatrimestre=2)

    meps_sin_tribunal = (
        MateriaEnPlan.objects
        .filter(plan_activo)
        .filter(cuatrimestre_filter)
        .filter(Exists(ano_qs))
        .filter(tribunal__isnull=True)
        .filter(es_optativa=False)
        .select_related('materia', 'plan__carrera')
    )
    creados = 0
    departamentos_nuevos = set()
    for mep in meps_sin_tribunal:
        TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
        creados += 1
        dept = mep.departamento_dictante if (mep.es_servicio and mep.departamento_dictante) else mep.plan.carrera.departamento
        if dept:
            departamentos_nuevos.add(dept)

    # Q1: departamentos_notificados vacío = todos; Q2: solo los afectados
    solicitud = SolicitudInformeTribunal.objects.create(
        solicitante=request.user,
        cuatrimestre=cuatrimestre,
        anio=anio,
        departamentos_notificados=[] if cuatrimestre == 1 else list(departamentos_nuevos),
    )

    url_tribunales = reverse('planes:lista_tribunales')
    cuatrimestre_label = 'primer cuatrimestre' if cuatrimestre == 1 else 'segundo cuatrimestre'
    if cuatrimestre == 1:
        directores = User.objects.filter(rol='director_departamento', is_active=True)
        mensaje_cuerpo = (
            f'Se solicita que revises los tribunales examinadores de tu departamento '
            f'para el {cuatrimestre_label} del año {anio}.\n\n'
            'Verificá que todos los datos estén actualizados y realizá los cambios necesarios. '
            'Una vez revisados, confirmá enviando el informe.'
        )
    else:
        if departamentos_nuevos:
            directores = User.objects.filter(
                rol='director_departamento', is_active=True,
                departamento__in=departamentos_nuevos,
            )
        else:
            directores = User.objects.none()
        mensaje_cuerpo = (
            f'Se crearon nuevos tribunales examinadores para el {cuatrimestre_label} del año {anio} '
            f'en tu departamento.\n\n'
            'Completá los datos de los tribunales recién creados y confirmá enviando el informe.'
        )

    notificados = 0
    for director in directores:
        _crear_notificacion(
            director,
            'nuevo_tramite',
            f'Informe de tribunales — {cuatrimestre_label.capitalize()} {anio}',
            mensaje_cuerpo,
            url=url_tribunales,
        )
        notificados += 1

    resumen = f'Solicitud de {cuatrimestre_label} {anio} enviada a {notificados} director{"es" if notificados != 1 else ""}.'
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

    # Para Q2, solo los departamentos con nuevos tribunales pueden enviar informe
    if solicitud.cuatrimestre == 2 and departamento not in solicitud.departamentos_notificados:
        return JsonResponse({'ok': False, 'error': 'Tu departamento no tiene tribunales nuevos para informar en este cuatrimestre.'}, status=400)

    InformeTribunalesEnviado.objects.update_or_create(
        solicitud=solicitud,
        departamento=departamento,
        defaults={'director': director, 'fecha_envio': timezone.now()},
    )

    admin = User.objects.filter(rol__in=['secretario', 'direccion_academica'], is_active=True).first()
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
    pdf_bytes = buffer.read()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Length'] = len(pdf_bytes)
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
@solo_admin_general
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
@solo_admin_general
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

    import datetime as _dt
    import types as _types
    from .models import DIA_SEMANA_CHOICES as _DIAS

    _DIAS_DISPLAY = dict(_DIAS)

    def _snap_to_obj(snap):
        dia = snap.get('dia_semana')
        hora_str = snap.get('hora')
        hora = _dt.time.fromisoformat(hora_str) if hora_str else None
        obj = _types.SimpleNamespace(
            presidente_nombre=snap.get('presidente_nombre', ''),
            presidente_dni=snap.get('presidente_dni', ''),
            vocal_1_nombre=snap.get('vocal_1_nombre', ''),
            vocal_1_dni=snap.get('vocal_1_dni', ''),
            vocal_2_nombre=snap.get('vocal_2_nombre', ''),
            vocal_2_dni=snap.get('vocal_2_dni', ''),
            dia_semana=dia,
            hora=hora,
            permite_libres=snap.get('permite_libres', True),
        )
        obj.get_dia_semana_display = lambda: _DIAS_DISPLAY.get(dia, '')
        return obj

    for item in items:
        snap = item.snapshot_tribunal or {}
        if snap:
            baseline = _snap_to_obj(snap)
            item.t_actual = baseline
            item.diff = {
                'presidente': (
                    item.presidente_nombre != baseline.presidente_nombre or
                    item.presidente_dni != baseline.presidente_dni
                ),
                'vocal_1': (
                    item.vocal_1_nombre != baseline.vocal_1_nombre or
                    item.vocal_1_dni != baseline.vocal_1_dni
                ),
                'vocal_2': (
                    item.vocal_2_nombre != baseline.vocal_2_nombre or
                    item.vocal_2_dni != baseline.vocal_2_dni
                ),
                'dia':      item.dia_semana != baseline.dia_semana,
                'hora':     item.hora != baseline.hora,
                'modalidad': item.permite_libres != baseline.permite_libres,
            }
        else:
            # Legacy items without snapshot: compare against live tribunal
            t = item.tribunal
            item.t_actual = t
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
                'dia':      item.dia_semana != t.dia_semana,
                'hora':     item.hora != t.hora,
                'modalidad': item.permite_libres != t.permite_libres,
            }

    # Solicitud más antigua del mismo departamento aún sin aplicar (bloquea esta)
    bloqueada_por = None
    if solicitud.estado == 'enviada':
        bloqueada_por = (
            SolicitudCambioTribunal.objects
            .filter(
                departamento=solicitud.departamento,
                estado='enviada',
                fecha_creacion__lt=solicitud.fecha_creacion,
            )
            .order_by('fecha_creacion')
            .first()
        )

    return render(request, 'planes/admin_detalle_solicitud_cambio.html', {
        'solicitud': solicitud,
        'items': items,
        'bloqueada_por': bloqueada_por,
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

    pendiente_anterior = (
        SolicitudCambioTribunal.objects
        .filter(
            departamento=solicitud.departamento,
            estado='enviada',
            fecha_creacion__lt=solicitud.fecha_creacion,
        )
        .exists()
    )
    if pendiente_anterior:
        messages.error(
            request,
            'No se puede aplicar esta solicitud porque existe una solicitud anterior '
            f'del Departamento de {solicitud.departamento} que aún no fue aplicada. '
            'Aplicá primero esa solicitud.',
        )
        return redirect('planes:detalle_solicitud_cambio', pk=pk)

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

    admin_user = User.objects.filter(rol='secretario', is_active=True).first()
    director_user = solicitud.director or admin_user
    buffer = generar_pdf_solicitud_cambio(director_user, admin_user, meps, item_map, current_map)

    safe_dept = solicitud.departamento.lower().replace(' ', '_')
    fecha_str = solicitud.fecha_creacion.strftime('%Y%m%d')
    filename = f'solicitud_cambio_tribunales_{safe_dept}_{fecha_str}.pdf'
    pdf_bytes = buffer.read()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Length'] = len(pdf_bytes)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── solicitudes de servicio ───────────────────────────────────────────────────

def _meps_servicio_para(departamento_solicitante, departamento_dictante):
    """MateriaEnPlan de servicio de carreras del dept solicitante dictadas por dept dictante."""
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    return (
        MateriaEnPlan.objects
        .filter(
            plan__carrera__departamento=departamento_solicitante,
            es_servicio=True,
            departamento_dictante=departamento_dictante,
        )
        .filter(models.Q(plan__vigente=True) | models.Q(plan__activo=True))
        .filter(Exists(ano_qs))
        .filter(es_optativa=False)
        .select_related('materia', 'plan__carrera')
        .order_by('cuatrimestre', 'plan__carrera__nombre', 'plan__codigo', 'materia__nombre')
    )


@login_required
@solo_director_departamento
def lista_solicitudes_servicio(request):
    departamento = request.user.departamento
    enviadas = SolicitudServicio.objects.filter(
        departamento_solicitante=departamento,
    ).order_by('-fecha_creacion')
    recibidas = SolicitudServicio.objects.filter(
        departamento_dictante=departamento,
        estado='enviada',
    ).order_by('-fecha_envio')
    return render(request, 'planes/solicitudes_servicio.html', {
        'enviadas': enviadas,
        'recibidas': recibidas,
    })


def _cuatrimestres_validos(convocatoria_cuatrimestre):
    """Cuatrimestres de MateriaEnPlan habilitados por la convocatoria."""
    # Cuatrimestre 1 incluye anuales (código 3); cuatrimestre 2 solo incluye el 2.
    return [1, 3] if convocatoria_cuatrimestre == 1 else [2]


@login_required
@solo_director_departamento
def nueva_solicitud_servicio(request):
    departamento = request.user.departamento

    # La convocatoria activa es la más reciente emitida por administración.
    convocatoria = ConvocatoriaSolicitudServicio.objects.order_by('-anio', '-cuatrimestre').first()
    if not convocatoria:
        messages.error(request, 'No hay ninguna convocatoria activa. Esperá que administración habilite el período.')
        return redirect('planes:lista_solicitudes_servicio')

    cuats_validos = _cuatrimestres_validos(convocatoria.cuatrimestre)
    anio = convocatoria.anio
    valid_deptos = {v for v, _ in DEPARTAMENTO_OPCIONES if v != departamento}

    dept_destino = request.GET.get('dpto') or request.POST.get('departamento_dictante', '')

    meps = []
    sin_hs = []
    if dept_destino and dept_destino in valid_deptos:
        meps = list(
            _meps_servicio_para(departamento, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )
        sin_hs = [m for m in meps if m.hs_totales is None]

    if request.method == 'POST':
        dept_destino = request.POST.get('departamento_dictante', '').strip()
        dictante_externo_nombre = request.POST.get('dictante_externo_nombre', '').strip()

        if dept_destino not in valid_deptos:
            messages.error(request, 'Departamento destino no válido.')
            return redirect('planes:nueva_solicitud_servicio')

        if dept_destino == 'Externo' and not dictante_externo_nombre:
            messages.error(request, 'Ingresá el nombre del organismo o cátedra externa.')
            meps = list(
                _meps_servicio_para(departamento, dept_destino)
                .filter(cuatrimestre__in=cuats_validos)
            )
            sin_hs = [m for m in meps if m.hs_totales is None]
            return render(request, 'planes/nueva_solicitud_servicio.html', {
                'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento],
                'dept_destino': dept_destino,
                'dictante_externo_nombre': dictante_externo_nombre,
                'meps': meps,
                'sin_hs': sin_hs,
                'convocatoria': convocatoria,
            })

        meps = list(
            _meps_servicio_para(departamento, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )
        if not meps:
            messages.error(request, 'No hay materias de servicio habilitadas para ese departamento en la convocatoria actual.')
            return redirect('planes:nueva_solicitud_servicio')

        # Validate and save missing hs_totales
        errores_hs = []
        hs_map = {}
        for mep in meps:
            raw = request.POST.get(f'hs_{mep.pk}', '').strip()
            if mep.hs_totales is None:
                if not raw or not raw.isdigit() or int(raw) <= 0:
                    errores_hs.append(mep.materia.nombre)
                else:
                    hs_map[mep.pk] = int(raw)
            else:
                hs_map[mep.pk] = mep.hs_totales

        if errores_hs:
            messages.error(request, f'Falta la carga horaria de: {", ".join(errores_hs)}.')
            sin_hs = [m for m in meps if m.hs_totales is None]
            return render(request, 'planes/nueva_solicitud_servicio.html', {
                'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento],
                'dept_destino': dept_destino,
                'dictante_externo_nombre': dictante_externo_nombre,
                'meps': meps,
                'sin_hs': sin_hs,
                'convocatoria': convocatoria,
            })

        # Persist hs_totales permanently
        for mep_pk, hs in hs_map.items():
            MateriaEnPlan.objects.filter(pk=mep_pk, hs_totales__isnull=True).update(hs_totales=hs)

        meps = list(
            _meps_servicio_para(departamento, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )

        solicitud = SolicitudServicio.objects.create(
            director=request.user,
            departamento_solicitante=departamento,
            departamento_dictante=dept_destino,
            dictante_externo_nombre=dictante_externo_nombre if dept_destino == 'Externo' else '',
            anio_academico=anio,
            estado='enviada',
            fecha_envio=timezone.now(),
        )
        for mep in meps:
            SolicitudServicioItem.objects.create(
                solicitud=solicitud,
                materia_en_plan=mep,
                hs_totales=hs_map.get(mep.pk, mep.hs_totales or 0),
            )

        messages.success(request, 'Solicitud de servicio enviada correctamente.')
        return redirect('planes:detalle_solicitud_servicio', pk=solicitud.pk)

    return render(request, 'planes/nueva_solicitud_servicio.html', {
        'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento],
        'dept_destino': dept_destino,
        'dictante_externo_nombre': '',
        'meps': meps,
        'sin_hs': sin_hs,
        'convocatoria': convocatoria,
    })


@login_required
def detalle_solicitud_servicio(request, pk):
    user = request.user
    solicitud = get_object_or_404(
        SolicitudServicio.objects.select_related('director'),
        pk=pk,
    )
    puede_ver = (
        user.es_administrador or
        (user.es_director_departamento and (
            user.departamento == solicitud.departamento_solicitante or
            (solicitud.departamento_dictante != 'Externo' and
             user.departamento == solicitud.departamento_dictante)
        )) or
        (user.es_director_carrera and solicitud.director_id == user.pk)
    )
    if not puede_ver:
        messages.error(request, 'No tenés permiso para ver esta solicitud.')
        return redirect('tramites:dashboard')

    items = (
        solicitud.items
        .select_related('materia_en_plan__materia', 'materia_en_plan__plan__carrera')
        .order_by(
            'materia_en_plan__cuatrimestre',
            'materia_en_plan__plan__carrera__nombre',
            'materia_en_plan__plan__codigo',
            'materia_en_plan__materia__nombre',
        )
    )
    return render(request, 'planes/detalle_solicitud_servicio.html', {
        'solicitud': solicitud,
        'items': items,
    })


@login_required
def descargar_solicitud_servicio(request, pk):
    from django.http import HttpResponse
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user = request.user
    solicitud = get_object_or_404(
        SolicitudServicio.objects.select_related('director'),
        pk=pk,
    )
    puede_ver = (
        user.es_administrador or
        (user.es_director_departamento and (
            user.departamento == solicitud.departamento_solicitante or
            (solicitud.departamento_dictante != 'Externo' and
             user.departamento == solicitud.departamento_dictante)
        )) or
        (user.es_director_carrera and solicitud.director_id == user.pk)
    )
    if not puede_ver:
        messages.error(request, 'No tenés permiso.')
        return redirect('tramites:dashboard')

    items = list(
        solicitud.items
        .select_related('materia_en_plan__materia', 'materia_en_plan__plan__carrera')
        .order_by(
            'materia_en_plan__cuatrimestre',
            'materia_en_plan__plan__carrera__nombre',
            'materia_en_plan__plan__codigo',
            'materia_en_plan__materia__nombre',
        )
    )
    admin_user = User.objects.filter(rol='secretario', is_active=True).first()
    buffer = generar_pdf_solicitud_servicio(solicitud, admin_user, items)

    safe_sol = f"{solicitud.departamento_solicitante}_a_{solicitud.departamento_dictante}".lower().replace(' ', '_')
    filename = f'solicitud_servicio_{safe_sol}_{solicitud.anio_academico}.pdf'
    pdf_bytes = buffer.read()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Length'] = len(pdf_bytes)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@solo_admin_general
def admin_lista_solicitudes_servicio(request):
    import datetime as _dt
    solicitudes = (
        SolicitudServicio.objects
        .select_related('director')
        .order_by('-fecha_creacion')
    )
    convocatorias = ConvocatoriaSolicitudServicio.objects.select_related('enviado_por').all()
    anio_actual = _dt.date.today().year
    try:
        anio_sel = int(request.GET.get('anio', anio_actual))
    except ValueError:
        anio_sel = anio_actual
    enviadas_anio = {c.cuatrimestre for c in convocatorias if c.anio == anio_sel}
    return render(request, 'planes/admin_solicitudes_servicio.html', {
        'solicitudes': solicitudes,
        'convocatorias': convocatorias,
        'anio_actual': anio_actual,
        'anio_sel': anio_sel,
        'enviadas_anio': enviadas_anio,
    })


# ── director de carrera: materias ────────────────────────────────────────────

@login_required
@solo_director_carrera
def materias_carrera(request):
    carrera = request.user.carrera
    if not carrera:
        messages.error(request, 'No tenés una carrera asignada. Contactá a administración.')
        return redirect('tramites:dashboard')

    ano_activo_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))

    meps = (
        MateriaEnPlan.objects
        .filter(plan__carrera=carrera)
        .filter(models.Q(plan__vigente=True) | models.Q(plan__activo=True))
        .annotate(se_dicta=Exists(ano_activo_qs))
        .select_related('materia', 'plan__carrera')
        .order_by('plan__codigo', 'ano', 'cuatrimestre', 'materia__nombre')
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
            return redirect('planes:materias_carrera')

    planes_data = []
    plan_entry = ano_entry = cuat_entry = None
    prev_plan = prev_ano = prev_cuat = None

    for mep in meps:
        if mep.plan_id != prev_plan:
            prev_plan = mep.plan_id
            prev_ano = prev_cuat = None
            plan_entry = {'plan': mep.plan, 'anos': []}
            planes_data.append(plan_entry)
        if mep.ano != prev_ano:
            prev_ano = mep.ano
            prev_cuat = None
            ano_entry = {'ano': mep.ano, 'se_dicta': mep.se_dicta, 'cuatrimestres': []}
            plan_entry['anos'].append(ano_entry)
        if mep.cuatrimestre != prev_cuat:
            prev_cuat = mep.cuatrimestre
            cuat_entry = {'label': mep.get_cuatrimestre_display(), 'materias': []}
            ano_entry['cuatrimestres'].append(cuat_entry)
        cuat_entry['materias'].append(mep)

    return render(request, 'planes/materias_carrera.html', {
        'planes_data': planes_data,
        'carrera': carrera,
        'departamento_opciones': DEPARTAMENTO_OPCIONES,
    })


# ── director de carrera: solicitudes de servicio ──────────────────────────────

def _meps_servicio_para_carrera(carrera, departamento_dictante):
    """MateriaEnPlan de servicio de una carrera específica dictadas por dept dictante."""
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    return (
        MateriaEnPlan.objects
        .filter(
            plan__carrera=carrera,
            es_servicio=True,
            departamento_dictante=departamento_dictante,
        )
        .filter(models.Q(plan__vigente=True) | models.Q(plan__activo=True))
        .filter(Exists(ano_qs))
        .filter(es_optativa=False)
        .select_related('materia', 'plan__carrera')
        .order_by('cuatrimestre', 'plan__codigo', 'materia__nombre')
    )


@login_required
@solo_director_carrera
def lista_solicitudes_servicio_carrera(request):
    carrera = request.user.carrera
    if not carrera:
        messages.error(request, 'No tenés una carrera asignada. Contactá a administración.')
        return redirect('tramites:dashboard')
    enviadas = SolicitudServicio.objects.filter(
        director=request.user,
    ).order_by('-fecha_creacion')
    return render(request, 'planes/solicitudes_servicio_carrera.html', {
        'enviadas': enviadas,
        'carrera': carrera,
    })


@login_required
@solo_director_carrera
def nueva_solicitud_servicio_carrera(request):
    user = request.user
    carrera = user.carrera
    if not carrera:
        messages.error(request, 'No tenés una carrera asignada. Contactá a administración.')
        return redirect('tramites:dashboard')

    departamento_solicitante = carrera.departamento
    convocatoria = ConvocatoriaSolicitudServicio.objects.order_by('-anio', '-cuatrimestre').first()
    if not convocatoria:
        messages.error(request, 'No hay ninguna convocatoria activa. Esperá que administración habilite el período.')
        return redirect('planes:lista_solicitudes_servicio_carrera')

    cuats_validos = _cuatrimestres_validos(convocatoria.cuatrimestre)
    anio = convocatoria.anio
    valid_deptos = {v for v, _ in DEPARTAMENTO_OPCIONES if v != departamento_solicitante}

    dept_destino = request.GET.get('dpto') or request.POST.get('departamento_dictante', '')

    meps = []
    sin_hs = []
    if dept_destino and dept_destino in valid_deptos:
        meps = list(
            _meps_servicio_para_carrera(carrera, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )
        sin_hs = [m for m in meps if m.hs_totales is None]

    if request.method == 'POST':
        dept_destino = request.POST.get('departamento_dictante', '').strip()
        dictante_externo_nombre = request.POST.get('dictante_externo_nombre', '').strip()

        if dept_destino not in valid_deptos:
            messages.error(request, 'Departamento destino no válido.')
            return redirect('planes:nueva_solicitud_servicio_carrera')

        if dept_destino == 'Externo' and not dictante_externo_nombre:
            messages.error(request, 'Ingresá el nombre del organismo o cátedra externa.')
            meps = list(
                _meps_servicio_para_carrera(carrera, dept_destino)
                .filter(cuatrimestre__in=cuats_validos)
            )
            sin_hs = [m for m in meps if m.hs_totales is None]
            return render(request, 'planes/nueva_solicitud_servicio_carrera.html', {
                'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento_solicitante],
                'dept_destino': dept_destino,
                'dictante_externo_nombre': dictante_externo_nombre,
                'meps': meps,
                'sin_hs': sin_hs,
                'convocatoria': convocatoria,
                'carrera': carrera,
            })

        meps = list(
            _meps_servicio_para_carrera(carrera, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )
        if not meps:
            messages.error(request, 'No hay materias de servicio habilitadas para ese departamento en la convocatoria actual.')
            return redirect('planes:nueva_solicitud_servicio_carrera')

        errores_hs = []
        hs_map = {}
        for mep in meps:
            raw = request.POST.get(f'hs_{mep.pk}', '').strip()
            if mep.hs_totales is None:
                if not raw or not raw.isdigit() or int(raw) <= 0:
                    errores_hs.append(mep.materia.nombre)
                else:
                    hs_map[mep.pk] = int(raw)
            else:
                hs_map[mep.pk] = mep.hs_totales

        if errores_hs:
            messages.error(request, f'Falta la carga horaria de: {", ".join(errores_hs)}.')
            sin_hs = [m for m in meps if m.hs_totales is None]
            return render(request, 'planes/nueva_solicitud_servicio_carrera.html', {
                'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento_solicitante],
                'dept_destino': dept_destino,
                'dictante_externo_nombre': dictante_externo_nombre,
                'meps': meps,
                'sin_hs': sin_hs,
                'convocatoria': convocatoria,
                'carrera': carrera,
            })

        for mep_pk, hs in hs_map.items():
            MateriaEnPlan.objects.filter(pk=mep_pk, hs_totales__isnull=True).update(hs_totales=hs)

        meps = list(
            _meps_servicio_para_carrera(carrera, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )

        solicitud = SolicitudServicio.objects.create(
            director=user,
            carrera=carrera,
            departamento_solicitante=departamento_solicitante,
            departamento_dictante=dept_destino,
            dictante_externo_nombre=dictante_externo_nombre if dept_destino == 'Externo' else '',
            anio_academico=anio,
            estado='enviada',
            fecha_envio=timezone.now(),
        )
        for mep in meps:
            SolicitudServicioItem.objects.create(
                solicitud=solicitud,
                materia_en_plan=mep,
                hs_totales=hs_map.get(mep.pk, mep.hs_totales or 0),
            )

        messages.success(request, 'Solicitud de servicio enviada correctamente.')
        return redirect('planes:detalle_solicitud_servicio', pk=solicitud.pk)

    return render(request, 'planes/nueva_solicitud_servicio_carrera.html', {
        'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento_solicitante],
        'dept_destino': dept_destino,
        'dictante_externo_nombre': '',
        'meps': meps,
        'sin_hs': sin_hs,
        'convocatoria': convocatoria,
        'carrera': carrera,
    })


@login_required
@solo_admin_general
def convocar_solicitudes_servicio(request):
    import datetime as _dt
    from django.contrib.auth import get_user_model
    if request.method != 'POST':
        return redirect('planes:admin_lista_solicitudes_servicio')

    User = get_user_model()
    try:
        cuatrimestre = int(request.POST.get('cuatrimestre', 0))
        anio = int(request.POST.get('anio', 0))
    except ValueError:
        messages.error(request, 'Datos inválidos.')
        return redirect('planes:admin_lista_solicitudes_servicio')

    if cuatrimestre not in (1, 2) or anio < 2020:
        messages.error(request, 'Cuatrimestre o año inválido.')
        return redirect('planes:admin_lista_solicitudes_servicio')

    if ConvocatoriaSolicitudServicio.objects.filter(cuatrimestre=cuatrimestre, anio=anio).exists():
        messages.error(request, f'Ya se envió una convocatoria para ese cuatrimestre y año.')
        return redirect('planes:admin_lista_solicitudes_servicio')

    cuat_label = '1° cuatrimestre (y anuales)' if cuatrimestre == 1 else '2° cuatrimestre'
    anual_nota = ' Las materias anuales deben solicitarse en conjunto con las del 1° cuatrimestre.' if cuatrimestre == 1 else ''

    url_nueva_carrera = reverse('planes:nueva_solicitud_servicio_carrera')
    count = 0
    for director in User.objects.filter(rol='director_carrera', is_active=True):
        _crear_notificacion(
            director,
            'nuevo_tramite',
            f'Convocatoria: Solicitudes de servicio {anio} — {cuat_label}',
            (
                f'Se solicita generar las solicitudes de dictado por servicio correspondientes '
                f'al {cuat_label} del ciclo lectivo {anio}.{anual_nota} '
                f'Ingresá al sistema para generar las solicitudes a los departamentos correspondientes.'
            ),
            url=url_nueva_carrera,
        )
        count += 1

    ConvocatoriaSolicitudServicio.objects.create(
        cuatrimestre=cuatrimestre,
        anio=anio,
        enviado_por=request.user,
        directores_notificados=count,
    )

    messages.success(request, f'Convocatoria enviada a {count} director{"es" if count != 1 else ""}.')
    return redirect('planes:admin_lista_solicitudes_servicio')
