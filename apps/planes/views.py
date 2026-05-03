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
from .models import AnioDictado, InformeTribunalesEnviado, MateriaEnPlan, SolicitudInformeTribunal, TribunalAdmin, TribunalExaminador
from .pdf import generar_pdf_informe_tribunales, generar_pdf_modificaciones_tribunales

DEPARTAMENTO_OPCIONES = [(v, l) for v, l in DEPARTAMENTO_CHOICES if v]


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
        .select_related('materia', 'plan__carrera')
        .order_by('materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    )
    mep_ids = [mep.id for mep in meps]
    dir_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=mep_ids)
    }
    adm_map = {
        t.materia_en_plan_id: t
        for t in TribunalAdmin.objects.filter(materia_en_plan_id__in=mep_ids)
    }
    return generar_pdf_informe_tribunales(director_user, admin, meps, dir_map, adm_map)


def _meps_del_departamento(departamento):
    """MateriaEnPlan de años activos dictados por este departamento."""
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    plan_activo = models.Q(plan__vigente=True) | models.Q(plan__activo=True)
    propios = models.Q(plan__carrera__departamento=departamento, es_servicio=False)
    servicio = models.Q(departamento_dictante=departamento)
    return (
        MateriaEnPlan.objects
        .filter(plan_activo)
        .filter(propios | servicio)
        .filter(Exists(ano_qs))
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
        servicio_ids = set(int(x) for x in request.POST.getlist('es_servicio') if x.isdigit())
        servicio_ids &= all_ids

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
                MateriaEnPlan.objects.filter(id=mep_id).update(es_servicio=True, departamento_dictante=dep)
            MateriaEnPlan.objects.filter(id__in=all_ids - servicio_ids).update(es_servicio=False, departamento_dictante='')
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
    elif filtro == 'pendientes':
        meps_qs = meps_qs.filter(tribunal__pendiente_sincronizacion=True)

    paginator = Paginator(meps_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_mep_ids = [mep.id for mep in page_obj]
    tribunales_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=page_mep_ids)
    }
    for mep in page_obj:
        mep.tribunal_obj = tribunales_map.get(mep.id)

    all_ids = base_qs.values_list('id', flat=True)
    pendientes_count = TribunalExaminador.objects.filter(
        materia_en_plan_id__in=all_ids,
        pendiente_sincronizacion=True,
    ).count()
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

    return render(request, 'planes/tribunales.html', {
        'page_obj': page_obj,
        'departamento': departamento,
        'q': q,
        'filtro': filtro,
        'solicitud_activa': solicitud is not None and not ya_enviado_esta_solicitud,
        'informe_enviado': informe_enviado,
        'pendientes_count': pendientes_count,
        'sin_registro_count': sin_registro_count,
        'incompletos_count': incompletos_count,
    })


@login_required
@solo_director_departamento
def modificar_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')

    departamento = request.user.departamento
    mep_ids = MateriaEnPlan.objects.filter(
        models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
        models.Q(departamento_dictante=departamento)
    ).values_list('id', flat=True)
    tribunal = get_object_or_404(TribunalExaminador, pk=pk, materia_en_plan_id__in=mep_ids)

    form = TribunalForm(request.POST)
    if form.is_valid():
        tribunal.presidente_nombre = form.cleaned_data['presidente_nombre']
        tribunal.presidente_dni = form.cleaned_data['presidente_dni']
        tribunal.vocal_1_nombre = form.cleaned_data['vocal_1_nombre']
        tribunal.vocal_1_dni = form.cleaned_data['vocal_1_dni']
        tribunal.vocal_2_nombre = form.cleaned_data['vocal_2_nombre']
        tribunal.vocal_2_dni = form.cleaned_data['vocal_2_dni']
        dia = form.cleaned_data['dia_semana']
        tribunal.dia_semana = int(dia) if dia else None
        tribunal.hora = form.cleaned_data['hora']
        tribunal.permite_libres = form.cleaned_data['permite_libres']
        tribunal.pendiente_sincronizacion = True
        tribunal.save()

        from django.contrib.auth import get_user_model
        User = get_user_model()
        materia = tribunal.materia_en_plan.materia.nombre
        for admin_user in User.objects.filter(rol='administrador', is_active=True):
            _crear_notificacion(
                admin_user, 'nuevo_tramite',
                f'Cambio en tribunal — {materia}',
                f'{request.user.get_full_name()} modificó el tribunal de {materia} '
                f'(Dpto. {departamento}). Pendiente de sincronización en sistema externo.',
                url=reverse('planes:lista_comparacion_tribunales') + '?pendientes=1',
            )
        messages.success(request, 'Tribunal actualizado. Administración será notificada para sincronizarlo.')
    else:
        messages.error(request, 'Corregí los errores del formulario.')

    return redirect('planes:lista_tribunales')


_CAMPOS_TRIBUNAL = [
    'presidente_nombre', 'presidente_dni',
    'vocal_1_nombre', 'vocal_1_dni',
    'vocal_2_nombre', 'vocal_2_dni',
    'dia_semana', 'hora', 'permite_libres',
]


@login_required
@solo_director_departamento
def copiar_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')

    departamento = request.user.departamento
    mep_ids_qs = MateriaEnPlan.objects.filter(
        models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
        models.Q(departamento_dictante=departamento)
    ).values_list('id', flat=True)

    fuente = get_object_or_404(
        TribunalExaminador.objects.select_related('materia_en_plan__materia'),
        pk=pk,
        materia_en_plan_id__in=mep_ids_qs,
    )

    codigo_materia = fuente.materia_en_plan.materia.codigo
    otros_ids = list(
        MateriaEnPlan.objects
        .filter(id__in=mep_ids_qs, materia__codigo=codigo_materia)
        .exclude(id=fuente.materia_en_plan_id)
        .values_list('id', flat=True)
    )

    destinos = list(TribunalExaminador.objects.filter(materia_en_plan_id__in=otros_ids))
    if not destinos:
        messages.info(request, 'No hay otros planes con esta materia en el departamento.')
        return redirect('planes:lista_tribunales')

    actualizados = 0
    for dest in destinos:
        if not any(getattr(dest, c) != getattr(fuente, c) for c in _CAMPOS_TRIBUNAL):
            continue
        for c in _CAMPOS_TRIBUNAL:
            setattr(dest, c, getattr(fuente, c))
        dest.pendiente_sincronizacion = True
        dest.save()
        actualizados += 1

    if actualizados:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        materia = fuente.materia_en_plan.materia.nombre
        n = actualizados
        for admin_user in User.objects.filter(rol='administrador', is_active=True):
            _crear_notificacion(
                admin_user, 'nuevo_tramite',
                f'Copia de tribunal — {materia}',
                f'{request.user.get_full_name()} copió el tribunal de {materia} '
                f'a {n} plan{"es" if n != 1 else ""} adicional{"es" if n != 1 else ""} '
                f'(Dpto. {departamento}).',
                url=reverse('planes:lista_comparacion_tribunales') + '?pendientes=1',
            )
        messages.success(request, f'Tribunal copiado a {n} plan{"es" if n != 1 else ""} adicional{"es" if n != 1 else ""}.')
    else:
        messages.info(request, 'Los demás planes ya tienen los mismos datos.')

    return redirect('planes:lista_tribunales')


# ── admin: comparación de tribunales ─────────────────────────────────────────

@login_required
@solo_administrador
def lista_comparacion_tribunales(request):
    solo_pendientes = request.GET.get('pendientes') == '1'
    dept_filtro = request.GET.get('departamento', '')
    q = request.GET.get('q', '').strip()

    meps_qs = (
        MateriaEnPlan.objects
        .filter(models.Q(plan__vigente=True) | models.Q(plan__activo=True))
        .select_related('materia', 'plan__carrera')
        .order_by('materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    )

    if dept_filtro:
        meps_qs = meps_qs.filter(
            models.Q(plan__carrera__departamento=dept_filtro, es_servicio=False) |
            models.Q(departamento_dictante=dept_filtro)
        )

    if solo_pendientes:
        meps_qs = meps_qs.filter(tribunal__pendiente_sincronizacion=True)

    if q:
        meps_qs = meps_qs.filter(
            models.Q(materia__nombre__icontains=q) |
            models.Q(materia__codigo__icontains=q)
        )

    meps = list(meps_qs)
    mep_ids = [mep.id for mep in meps]

    dir_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=mep_ids)
    }
    adm_map = {
        t.materia_en_plan_id: t
        for t in TribunalAdmin.objects.filter(materia_en_plan_id__in=mep_ids)
    }
    for mep in meps:
        mep.t_dir = dir_map.get(mep.id)
        mep.t_adm = adm_map.get(mep.id)

    # Agrupar por departamento efectivo → materia.codigo
    dept_labels = {v: l for v, l in DEPARTAMENTO_CHOICES if v}
    grupos_dict = {}
    for mep in meps:
        dept = mep.departamento_dictante if mep.es_servicio else mep.plan.carrera.departamento
        dept = dept or ''
        if dept not in grupos_dict:
            grupos_dict[dept] = {}
        cod = mep.materia.codigo
        if cod not in grupos_dict[dept]:
            grupos_dict[dept][cod] = {'nombre': mep.materia.nombre, 'meps': []}
        grupos_dict[dept][cod]['meps'].append(mep)

    grupos = [
        {
            'departamento': dept,
            'departamento_label': dept_labels.get(dept, dept or 'Sin departamento'),
            'materias': [
                {'codigo': cod, 'nombre': datos['nombre'], 'meps': datos['meps']}
                for cod, datos in sorted(grupos_dict[dept].items())
            ],
        }
        for dept in sorted(grupos_dict.keys())
    ]

    return render(request, 'planes/comparacion_tribunales.html', {
        'grupos': grupos,
        'solo_pendientes': solo_pendientes,
        'dept_filtro': dept_filtro,
        'q': q,
        'total': len(meps),
        'departamento_opciones': DEPARTAMENTO_OPCIONES,
    })


@login_required
@solo_administrador
def admin_modificar_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_comparacion_tribunales')

    tribunal = get_object_or_404(TribunalExaminador, pk=pk)
    form = TribunalForm(request.POST)
    if form.is_valid():
        tribunal.presidente_nombre = form.cleaned_data['presidente_nombre']
        tribunal.presidente_dni = form.cleaned_data['presidente_dni']
        tribunal.vocal_1_nombre = form.cleaned_data['vocal_1_nombre']
        tribunal.vocal_1_dni = form.cleaned_data['vocal_1_dni']
        tribunal.vocal_2_nombre = form.cleaned_data['vocal_2_nombre']
        tribunal.vocal_2_dni = form.cleaned_data['vocal_2_dni']
        dia = form.cleaned_data['dia_semana']
        tribunal.dia_semana = int(dia) if dia else None
        tribunal.hora = form.cleaned_data['hora']
        tribunal.permite_libres = form.cleaned_data['permite_libres']
        tribunal.pendiente_sincronizacion = False
        tribunal.save()

        t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=tribunal.materia_en_plan)
        for campo in _CAMPOS_TRIBUNAL:
            setattr(t_adm, campo, getattr(tribunal, campo))
        t_adm.ultima_sincronizacion = timezone.now()
        t_adm.save()

        messages.success(request, 'Tribunal actualizado y sincronizado correctamente.')
    else:
        messages.error(request, 'Error en el formulario. Verificá los datos ingresados.')

    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('planes:lista_comparacion_tribunales')


@login_required
@solo_administrador
def detalle_tribunal_admin(request, pk):
    mep = get_object_or_404(
        MateriaEnPlan.objects.select_related('materia', 'plan__carrera'),
        pk=pk,
    )
    t_dir = get_object_or_404(TribunalExaminador, materia_en_plan=mep)
    t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)

    diffs = {
        'presidente': (t_dir.presidente_nombre != t_adm.presidente_nombre
                       or t_dir.presidente_dni != t_adm.presidente_dni),
        'vocal_1': (t_dir.vocal_1_nombre != t_adm.vocal_1_nombre
                    or t_dir.vocal_1_dni != t_adm.vocal_1_dni),
        'vocal_2': (t_dir.vocal_2_nombre != t_adm.vocal_2_nombre
                    or t_dir.vocal_2_dni != t_adm.vocal_2_dni),
        'dia_hora': (t_dir.dia_semana != t_adm.dia_semana
                     or t_dir.hora != t_adm.hora),
        'modalidad': t_dir.permite_libres != t_adm.permite_libres,
    }

    return render(request, 'planes/detalle_tribunal_admin.html', {
        'mep': mep,
        't_dir': t_dir,
        't_adm': t_adm,
        'diffs': diffs,
    })


@login_required
@solo_administrador
def sincronizar_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_comparacion_tribunales')

    mep = get_object_or_404(MateriaEnPlan, pk=pk)
    t_dir = get_object_or_404(TribunalExaminador, materia_en_plan=mep)
    t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)

    for campo in _CAMPOS_TRIBUNAL:
        setattr(t_adm, campo, getattr(t_dir, campo))
    t_adm.ultima_sincronizacion = timezone.now()
    t_adm.save()

    t_dir.pendiente_sincronizacion = False
    t_dir.save(update_fields=['pendiente_sincronizacion'])

    messages.success(request, 'Tribunal sincronizado correctamente.')
    return redirect('planes:lista_comparacion_tribunales')


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

    # Crear TribunalExaminador y TribunalAdmin para MEPs que aún no tienen uno
    plan_activo = models.Q(plan__vigente=True) | models.Q(plan__activo=True)
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    meps_sin_tribunal = (
        MateriaEnPlan.objects
        .filter(plan_activo)
        .filter(Exists(ano_qs))
        .filter(tribunal__isnull=True)
        .select_related('materia', 'plan')
    )
    creados = 0
    for mep in meps_sin_tribunal:
        TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
        TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
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
            'Una vez revisados, los cambios quedarán pendientes de sincronización para el administrador.',
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
            url=reverse('planes:lista_comparacion_tribunales') + '?pendientes=1',
        )

    return JsonResponse({'ok': True})


@login_required
@solo_director_departamento
def generar_pdf_modificaciones(request):
    from django.contrib.auth import get_user_model
    from django.http import HttpResponse
    User = get_user_model()

    departamento = request.user.departamento

    meps = list(
        MateriaEnPlan.objects
        .filter(
            models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
            models.Q(departamento_dictante=departamento)
        )
        .filter(tribunal__pendiente_sincronizacion=True)
        .select_related('materia', 'plan__carrera')
        .order_by('materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    )

    if not meps:
        messages.error(request, 'No hay tribunales con modificaciones pendientes.')
        return redirect('planes:lista_tribunales')

    mep_ids = [mep.id for mep in meps]
    dir_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=mep_ids)
    }
    adm_map = {
        t.materia_en_plan_id: t
        for t in TribunalAdmin.objects.filter(materia_en_plan_id__in=mep_ids)
    }

    admin = User.objects.filter(rol='administrador', is_active=True).first()
    buffer = generar_pdf_modificaciones_tribunales(request.user, admin, meps, dir_map, adm_map)

    import datetime
    safe_dept = departamento.lower().replace(' ', '_')
    fecha_str = datetime.date.today().strftime('%Y%m%d')
    filename = f'modificaciones_tribunales_{safe_dept}_{fecha_str}.pdf'

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


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
