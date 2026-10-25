from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.tramites.decorators import solo_administrador, solo_admin_general, solo_director_carrera, solo_director_departamento, solo_director_departamento_o_carrera
from apps.tramites.models import DEPARTAMENTO_CHOICES
from apps.notifications.utils import _crear_notificacion
from .forms import ComisionForm, MateriaOptativaForm, MiembroComisionFormSet, TribunalForm
from .models import CAMPOS_TRIBUNAL_COMPLETO, tribunal_completo, AgrupacionTribunal, AnioDictado, Carrera, Comision, ConvocatoriaSolicitudServicio, Docente, InformeComisionesEnviado, InformeTribunalesEnviado, MateriaEnPlan, MateriaOptativa, SolicitudCambioItem, SolicitudCambioTribunal, SolicitudInformeComisiones, SolicitudInformeTribunal, SolicitudServicio, SolicitudServicioItem, TribunalExaminador
from .optativas import advertencias_hs, crear_comision, crear_comisiones_del_periodo, materias_ofrecidas_en_carrera
from .pdf import generar_pdf_informe_comisiones, generar_pdf_informe_tribunales, generar_pdf_solicitud_cambio, generar_pdf_solicitud_servicio
from .docx_gen import generar_docx_informe_comisiones, generar_docx_informe_tribunales, generar_docx_solicitud_cambio

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
    filas, tribunal_map, _ = _filas_informe_departamento(departamento)
    return generar_pdf_informe_tribunales(director_user, admin, filas, tribunal_map, tribunal_map)


def _filas_informe_departamento(departamento):
    """Tribunales que entran en el informe del departamento: materias que se dictan (planes en
    uso, años dictados) y optativas de la bolsa. Devuelve (filas, tribunal_map, sin_tribunal)."""
    meps = list(
        _meps_del_departamento(departamento)
        .select_related('materia', 'plan__carrera')
        .order_by('materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    )
    tribunales = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=[m.id for m in meps])
    }
    filas, tribunal_map, sin_tribunal = [], {}, []
    for mep in meps:
        t = tribunales.get(mep.id)
        if t:
            filas.append(mep)
            tribunal_map[mep.id] = t
        else:
            sin_tribunal.append(mep)
    for t in _tribunales_optativas(departamento).order_by('materia_optativa__codigo', 'carrera__nombre'):
        filas.append(t.fila)
        tribunal_map[t.fila_id] = t
    return filas, tribunal_map, sin_tribunal


def _q_tribunal_incompleto(prefijo=''):
    """Q de tribunales a los que les falta algún integrante (nombre o DNI), día u hora."""
    q = models.Q()
    for campo in CAMPOS_TRIBUNAL_COMPLETO:
        if campo in ('dia_semana', 'hora'):
            q |= models.Q(**{f'{prefijo}{campo}__isnull': True})
        else:
            q |= models.Q(**{f'{prefijo}{campo}': ''})
    return q


def _describir_incompletos(filas, limite=5):
    nombres = [f'{f.materia.nombre} ({f.plan.carrera.nombre})' for f in filas[:limite]]
    resto = f' y {len(filas) - limite} más' if len(filas) > limite else ''
    return ', '.join(nombres) + resto


def _tribunales_optativas(departamento=None, carrera=None):
    """Tribunales de la bolsa de optativas (de un departamento, de una carrera, o todos) listos para mostrar."""
    if departamento:
        qs = TribunalExaminador.objects.de_optativas_del_departamento(departamento)
    elif carrera:
        qs = TribunalExaminador.objects.de_optativas().filter(carrera=carrera)
    else:
        qs = TribunalExaminador.objects.de_optativas()
    return qs.select_related('materia_optativa', 'carrera').prefetch_related(
        'materia_optativa__optativas__plan__carrera', 'materia_optativa__optativas__materia',
    )


def _tribunales_del_depto(departamento):
    """Tribunales que el director del departamento puede ver y proponer cambiar."""
    return TribunalExaminador.objects.filter(
        models.Q(materia_en_plan_id__in=_mep_ids_para_depto(departamento)) |
        models.Q(pk__in=TribunalExaminador.objects.de_optativas_del_departamento(departamento).values('pk'))
    )


def _tribunales_de_carrera(carrera):
    """Tribunales de las materias de la carrera (de plan y optativas de la bolsa)."""
    return TribunalExaminador.objects.filter(
        models.Q(materia_en_plan__plan__carrera=carrera, materia_en_plan__es_optativa=False) |
        models.Q(pk__in=TribunalExaminador.objects.de_optativas().filter(carrera=carrera).values('pk'))
    )


def _tribunales_del_usuario(user):
    """Tribunales sobre los que el director (de departamento o de carrera) puede proponer cambios."""
    if user.es_director_departamento:
        return _tribunales_del_depto(user.departamento)
    if user.es_director_carrera and user.carrera_id:
        return _tribunales_de_carrera(user.carrera)
    return TribunalExaminador.objects.none()


def _director_del_departamento(departamento):
    from django.contrib.auth import get_user_model
    return (
        get_user_model().objects
        .filter(rol='director_departamento', departamento=departamento, is_active=True)
        .order_by('pk')
        .first()
    )


def _filas_de_items(items):
    """(filas ordenadas, item_map, current_map) de items de una solicitud de cambio, para PDF/DOCX."""
    filas = sorted(
        (item.tribunal.fila for item in items),
        key=lambda m: (m.materia.codigo, m.plan.carrera.nombre, m.plan.codigo, m.ano, m.cuatrimestre),
    )
    item_map = {item.tribunal.fila_id: item for item in items}
    current_map = {item.tribunal.fila_id: item.tribunal for item in items}
    return filas, item_map, current_map


_ITEMS_RELACIONADOS = (
    'tribunal__materia_en_plan__materia', 'tribunal__materia_en_plan__plan__carrera',
    'tribunal__materia_optativa', 'tribunal__carrera',
)


def _meps_del_departamento(departamento):
    """MateriaEnPlan de años activos dictados por este departamento, sin optativas."""
    ano_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    plan_activo = models.Q(plan__vigente=True) | models.Q(plan__activo=True)
    propios = models.Q(plan__carrera__departamento=departamento, es_servicio=False)
    servicio = models.Q(departamento_dictante=departamento)
    servicio_externo = models.Q(plan__carrera__departamento=departamento, es_servicio=True, departamento_dictante='Externo')
    return (
        MateriaEnPlan.objects
        .filter(plan_activo)
        .filter(propios | servicio | servicio_externo)
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
def lista_tribunales(request):
    user = request.user
    if not (user.es_director_departamento or user.es_director_carrera or user.es_administrador):
        messages.error(request, 'No tenés permisos para acceder a esta sección.')
        return redirect('tramites:dashboard')
    if user.es_director_carrera and not user.carrera_id:
        messages.error(request, 'No tenés una carrera asignada. Contactá a administración.')
        return redirect('tramites:dashboard')

    # Modos: director de departamento (propone y envía), director de carrera (propone al
    # departamento responsable) o administración (solo consulta).
    modo_carrera = user.es_director_carrera
    es_solo_consulta = user.es_administrador and not user.es_director_departamento
    departamento = user.departamento if user.es_director_departamento else None
    carrera = user.carrera if modo_carrera else None
    q = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '')

    _ano_dictado_qs = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))

    if modo_carrera:
        base_qs = MateriaEnPlan.objects.filter(plan__carrera=carrera, es_optativa=False)
        orden = ('materia__nombre', 'materia__codigo', 'plan__codigo', 'ano', 'cuatrimestre')
    elif es_solo_consulta:
        base_qs = MateriaEnPlan.objects.filter(es_optativa=False)
        orden = ('plan__carrera__departamento', 'materia__codigo', 'plan__carrera__nombre', 'plan__codigo')
    else:
        base_qs = MateriaEnPlan.objects.filter(
            # Materia propia (no servicio)
            models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
            # Servicio ofrecido por este departamento (no externo)
            models.Q(departamento_dictante=departamento) |
            # Servicio externo de una carrera de este departamento
            models.Q(plan__carrera__departamento=departamento, es_servicio=True, departamento_dictante='Externo')
        ).filter(es_optativa=False)
        orden = ('materia__nombre', 'materia__codigo', 'plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    base_qs = (
        base_qs
        .annotate(se_dicta=Exists(_ano_dictado_qs))
        .select_related('materia', 'plan__carrera')
        .order_by(*orden)
    )

    # Cambios propuestos pendientes (antes de filtrar, para poder usarlos como filtro)
    borrador = None
    if modo_carrera:
        items_pendientes = (
            SolicitudCambioItem.objects
            .filter(solicitud__estado='borrador', tribunal__in=_tribunales_de_carrera(carrera))
            .select_related('propuesto_por')
        )
        borrador_items_map = {item.tribunal_id: item for item in items_pendientes}
        borrador_count = sum(1 for item in borrador_items_map.values() if item.propuesto_por_id == user.pk)
    elif not es_solo_consulta:
        borrador = (
            SolicitudCambioTribunal.objects
            .filter(director=request.user, departamento=departamento, estado='borrador')
            .prefetch_related('items__propuesto_por')
            .first()
        )
        borrador_items_map = {item.tribunal_id: item for item in borrador.items.all()} if borrador else {}
        borrador_count = len(borrador_items_map)
    else:
        borrador_items_map, borrador_count = {}, 0
    borrador_tribunal_ids = set(borrador_items_map.keys())

    meps_qs = base_qs
    if q:
        meps_qs = meps_qs.filter(
            models.Q(materia__nombre__unaccent__icontains=q) |
            models.Q(materia__codigo__icontains=q)
        )
    if filtro == 'sin_registro':
        meps_qs = meps_qs.filter(tribunal__isnull=True)
    elif filtro == 'incompletos':
        meps_qs = meps_qs.filter(_q_tribunal_incompleto('tribunal__'))
    elif filtro == 'sin_dictado':
        meps_qs = meps_qs.filter(se_dicta=False)
    elif filtro == 'con_propuesta' and borrador_tribunal_ids:
        meps_qs = meps_qs.filter(tribunal__pk__in=borrador_tribunal_ids)

    paginator = Paginator(meps_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_mep_ids = [mep.id for mep in page_obj]
    tribunales_map = {
        t.materia_en_plan_id: t
        for t in TribunalExaminador.objects.filter(materia_en_plan_id__in=page_mep_ids)
    }

    for mep in page_obj:
        mep.tribunal_obj = tribunales_map.get(mep.id)
        mep.tribunal_tiene_propuesta = (
            mep.tribunal_obj is not None and mep.tribunal_obj.pk in borrador_tribunal_ids
        )
        mep.propuesta_item = (
            borrador_items_map.get(mep.tribunal_obj.pk) if mep.tribunal_obj else None
        )

    # Optativas de la bolsa: siempre tienen tribunal y se listan aparte (en la primera página)
    opt_qs = _tribunales_optativas(departamento, carrera=carrera).order_by('materia_optativa__nombre', 'carrera__nombre')
    if q:
        opt_qs = opt_qs.filter(
            models.Q(materia_optativa__nombre__unaccent__icontains=q) |
            models.Q(materia_optativa__codigo__icontains=q)
        )
    if filtro in ('sin_registro', 'sin_dictado'):
        opt_qs = opt_qs.none()
    elif filtro == 'incompletos':
        opt_qs = opt_qs.filter(_q_tribunal_incompleto())
    elif filtro == 'con_propuesta' and borrador_tribunal_ids:
        opt_qs = opt_qs.filter(pk__in=borrador_tribunal_ids)
    filas_optativas = []
    if page_obj.number == 1:
        for t in opt_qs:
            fila = t.fila
            fila.tribunal_obj = t
            fila.tribunal_tiene_propuesta = t.pk in borrador_tribunal_ids
            fila.propuesta_item = borrador_items_map.get(t.pk)
            filas_optativas.append(fila)

    all_ids = base_qs.values_list('id', flat=True)
    sin_registro_count = base_qs.filter(tribunal__isnull=True).count()
    incompletos_count = (
        TribunalExaminador.objects.filter(materia_en_plan_id__in=all_ids).filter(_q_tribunal_incompleto()).count()
        + _tribunales_optativas(departamento, carrera=carrera).filter(_q_tribunal_incompleto()).count()
    )
    no_dictados_count = base_qs.filter(se_dicta=False).count()

    contexto = {
        'page_obj': page_obj,
        'filas_optativas': filas_optativas,
        'departamento': departamento,
        'carrera': carrera,
        'q': q,
        'filtro': filtro,
        'solicitud': None,
        'solicitud_activa': False,
        'informe_enviado': None,
        'sin_registro_count': sin_registro_count,
        'incompletos_count': incompletos_count,
        'no_dictados_count': no_dictados_count,
        'borrador': borrador,
        'borrador_count': borrador_count,
        'solicitudes_enviadas': 0,
        'solicitudes_cambio': [],
        'es_solo_consulta': es_solo_consulta,
        'modo_carrera': modo_carrera,
    }
    if es_solo_consulta or modo_carrera:
        return render(request, 'planes/tribunales.html', contexto)

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

    if solicitud is not None:
        if solicitud.cuatrimestre == 1:
            solicitud_para_dept = True
        else:
            solicitud_para_dept = departamento in solicitud.departamentos_notificados
    else:
        solicitud_para_dept = False

    contexto.update({
        'solicitud': solicitud,
        'solicitud_activa': solicitud_para_dept and not ya_enviado_esta_solicitud,
        'informe_enviado': informe_enviado,
        'solicitudes_enviadas': SolicitudCambioTribunal.objects.filter(
            departamento=departamento, estado='enviada',
        ).count(),
        'solicitudes_cambio': (
            SolicitudCambioTribunal.objects
            .filter(departamento=departamento)
            .exclude(estado='borrador')
            .prefetch_related('items')
            .order_by('-fecha_creacion')[:10]
        ),
        'cerrada': (
            SolicitudCambioTribunal.objects
            .filter(director=request.user, departamento=departamento, estado='cerrada')
            .prefetch_related('items')
            .first()
        ),
        'agrupaciones': (
            AgrupacionTribunal.objects
            .filter(director=request.user, departamento=departamento)
            .prefetch_related('tribunales__materia_en_plan__materia', 'tribunales__materia_optativa')
            .order_by('nombre')
        ),
    })
    return render(request, 'planes/tribunales.html', contexto)


# ── agrupaciones de tribunales ───────────────────────────────────────────────

def _mep_ids_para_depto(departamento):
    return MateriaEnPlan.objects.filter(
        models.Q(plan__carrera__departamento=departamento, es_servicio=False) |
        models.Q(departamento_dictante=departamento) |
        models.Q(plan__carrera__departamento=departamento, es_servicio=True, departamento_dictante='Externo')
    ).filter(es_optativa=False).values_list('id', flat=True)


@login_required
@solo_director_departamento
def crear_agrupacion(request):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')
    departamento = request.user.departamento
    nombre = request.POST.get('nombre', '').strip()
    tribunal_ids = request.POST.getlist('tribunal_ids')
    if not nombre:
        messages.error(request, 'El nombre de la agrupación es requerido.')
        return redirect('planes:lista_tribunales')
    validos = _tribunales_del_depto(departamento).filter(pk__in=tribunal_ids)
    if not validos.exists():
        messages.error(request, 'Seleccioná al menos un tribunal válido.')
        return redirect('planes:lista_tribunales')
    ag = AgrupacionTribunal.objects.create(
        nombre=nombre, departamento=departamento, director=request.user,
    )
    ag.tribunales.set(validos)
    messages.success(request, f'Agrupación "{nombre}" creada con {validos.count()} tribunal(es).')
    return redirect('planes:lista_tribunales')


@login_required
@solo_director_departamento
def eliminar_agrupacion(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')
    ag = get_object_or_404(AgrupacionTribunal, pk=pk, director=request.user)
    nombre = ag.nombre
    ag.delete()
    messages.success(request, f'Agrupación "{nombre}" eliminada.')
    return redirect('planes:lista_tribunales')


@login_required
@solo_director_departamento
def proponer_cambio_agrupacion(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')
    next_url = request.POST.get('next', '')
    departamento = request.user.departamento
    ag = get_object_or_404(AgrupacionTribunal, pk=pk, director=request.user)

    def _docente_by_id(raw):
        if raw:
            try:
                return Docente.objects.get(pk=int(raw))
            except (Docente.DoesNotExist, ValueError):
                pass
        return None

    pres = _docente_by_id(request.POST.get('presidente_id'))
    voc1 = _docente_by_id(request.POST.get('vocal_1_id'))
    voc2 = _docente_by_id(request.POST.get('vocal_2_id'))

    form = TribunalForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Corregí los errores del formulario.')
        return redirect('planes:lista_tribunales')

    draft, _ = SolicitudCambioTribunal.objects.get_or_create(
        director=request.user, departamento=departamento, estado='borrador',
    )
    dia = form.cleaned_data['dia_semana']
    item_defaults = {
        'presidente_nombre': pres.nombre if pres else '',
        'presidente_dni':    pres.dni    if pres else '',
        'vocal_1_nombre':    voc1.nombre if voc1 else '',
        'vocal_1_dni':       voc1.dni    if voc1 else '',
        'vocal_2_nombre':    voc2.nombre if voc2 else '',
        'vocal_2_dni':       voc2.dni    if voc2 else '',
        'dia_semana':        int(dia) if dia else None,
        'hora':              form.cleaned_data['hora'],
        'permite_libres':    form.cleaned_data['permite_libres'],
    }

    count = 0
    for tribunal in ag.tribunales.select_related('materia_en_plan'):
        item, created = SolicitudCambioItem.objects.update_or_create(
            solicitud=draft, tribunal=tribunal, defaults=item_defaults,
        )
        if created:
            item.snapshot_tribunal = {
                'presidente_nombre': tribunal.presidente_nombre,
                'presidente_dni':    tribunal.presidente_dni,
                'vocal_1_nombre':    tribunal.vocal_1_nombre,
                'vocal_1_dni':       tribunal.vocal_1_dni,
                'vocal_2_nombre':    tribunal.vocal_2_nombre,
                'vocal_2_dni':       tribunal.vocal_2_dni,
                'dia_semana':        tribunal.dia_semana,
                'hora':              tribunal.hora.strftime('%H:%M') if tribunal.hora else None,
                'permite_libres':    tribunal.permite_libres,
            }
            item.save(update_fields=['snapshot_tribunal'])
        count += 1

    messages.success(request, f'Cambio propuesto para {count} tribunal(es) de "{ag.nombre}".')
    if next_url and next_url.startswith('/'):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(next_url)
    return redirect('planes:lista_tribunales')


# ── docentes: búsqueda y creación AJAX ───────────────────────────────────────

@login_required
@solo_director_departamento_o_carrera
def datos_tribunal_ajax(request, pk):
    from django.http import JsonResponse
    tribunal = _tribunales_del_usuario(request.user).filter(
        pk=pk,
    ).select_related('presidente', 'vocal_1', 'vocal_2').first()
    if not tribunal:
        return JsonResponse({'ok': False}, status=404)
    def _d(docente_obj, nombre_char, dni_char):
        if docente_obj:
            return {'id': docente_obj.pk, 'nombre': docente_obj.nombre, 'dni': docente_obj.dni}
        if nombre_char:
            return {'id': '', 'nombre': nombre_char, 'dni': dni_char}
        return None
    return JsonResponse({
        'ok': True,
        'presidente': _d(tribunal.presidente, tribunal.presidente_nombre, tribunal.presidente_dni),
        'vocal_1':    _d(tribunal.vocal_1,    tribunal.vocal_1_nombre,    tribunal.vocal_1_dni),
        'vocal_2':    _d(tribunal.vocal_2,    tribunal.vocal_2_nombre,    tribunal.vocal_2_dni),
        'dia_semana': tribunal.dia_semana or '',
        'hora':       tribunal.hora.strftime('%H:%M') if tribunal.hora else '',
        'permite_libres': tribunal.permite_libres,
    })


@login_required
@solo_director_departamento
def buscar_tribunal_ajax(request):
    from django.http import JsonResponse
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    departamento = request.user.departamento
    tribunales = (
        _tribunales_del_depto(departamento)
        .filter(
            models.Q(materia_en_plan__materia__nombre__unaccent__icontains=q) |
            models.Q(materia_optativa__nombre__unaccent__icontains=q)
        )
        .exclude(presidente_nombre='', vocal_1_nombre='', vocal_2_nombre='')
        .select_related(
            'materia_en_plan__materia', 'materia_en_plan__plan__carrera',
            'materia_optativa', 'carrera',
        )
        .order_by('materia_en_plan__materia__nombre', 'materia_optativa__nombre')[:10]
    )

    def _label(t):
        if t.es_optativa_bolsa:
            return f"{t.materia_optativa.nombre} — Optativa ({t.carrera.nombre})"
        mep = t.materia_en_plan
        return f"{mep.materia.nombre} — Plan {mep.plan.codigo} ({mep.plan.carrera.nombre})"

    return JsonResponse({'results': [{'id': t.pk, 'label': _label(t)} for t in tribunales]})


@login_required
@solo_director_departamento_o_carrera
def buscar_docente(request):
    from django.http import JsonResponse
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    docentes = Docente.objects.filter(nombre__unaccent__icontains=q).order_by('nombre')[:10]
    return JsonResponse({'results': [
        {'id': d.pk, 'nombre': d.nombre, 'dni': d.dni} for d in docentes
    ]})


@login_required
@solo_director_departamento_o_carrera
def crear_docente_ajax(request):
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    nombre = request.POST.get('nombre', '').strip()
    dni = request.POST.get('dni', '').strip()
    if not nombre or not dni:
        return JsonResponse({'ok': False, 'error': 'Nombre y DNI son requeridos.'})
    existente = Docente.objects.filter(dni=dni).first()
    if existente:
        return JsonResponse({'ok': True, 'id': existente.pk, 'nombre': existente.nombre, 'dni': existente.dni, 'existia': True})
    d = Docente.objects.create(nombre=nombre, dni=dni)
    return JsonResponse({'ok': True, 'id': d.pk, 'nombre': d.nombre, 'dni': d.dni, 'existia': False})


# ── director: proponer y enviar cambios de tribunal ──────────────────────────

@login_required
@solo_director_departamento_o_carrera
def proponer_cambio_tribunal(request, pk):
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')
    next_url = request.POST.get('next', '')

    user = request.user
    tribunal = get_object_or_404(
        _tribunales_del_usuario(user).select_related(
            'materia_en_plan__plan__carrera', 'materia_en_plan__materia', 'materia_optativa', 'carrera',
        ),
        pk=pk,
    )
    if user.es_director_departamento:
        departamento, director_borrador, propuesto_por = user.departamento, user, None
    else:
        # El director de carrera propone: el cambio va al borrador del departamento responsable
        departamento = tribunal.departamento_responsable
        director_borrador = _director_del_departamento(departamento)
        propuesto_por = user
        if director_borrador is None:
            messages.error(request, f'El Departamento de {departamento} no tiene director asignado; no se puede enviar la propuesta.')
            return redirect('planes:lista_tribunales')

    def _docente_by_id(raw):
        if raw:
            try:
                return Docente.objects.get(pk=int(raw))
            except (Docente.DoesNotExist, ValueError):
                pass
        return None

    pres = _docente_by_id(request.POST.get('presidente_id'))
    voc1 = _docente_by_id(request.POST.get('vocal_1_id'))
    voc2 = _docente_by_id(request.POST.get('vocal_2_id'))

    form = TribunalForm(request.POST)
    if form.is_valid():
        draft, _ = SolicitudCambioTribunal.objects.get_or_create(
            director=director_borrador,
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
                'presidente_nombre': pres.nombre if pres else '',
                'presidente_dni': pres.dni if pres else '',
                'vocal_1_nombre': voc1.nombre if voc1 else '',
                'vocal_1_dni': voc1.dni if voc1 else '',
                'vocal_2_nombre': voc2.nombre if voc2 else '',
                'vocal_2_dni': voc2.dni if voc2 else '',
                'dia_semana': int(dia) if dia else None,
                'hora': form.cleaned_data['hora'],
                'permite_libres': form.cleaned_data['permite_libres'],
                **({'propuesto_por': propuesto_por} if propuesto_por else {}),
            },
        )
        if created:
            item.snapshot_tribunal = _snapshot(tribunal)
            item.save(update_fields=['snapshot_tribunal'])

        # Si los valores propuestos son idénticos al original, eliminar el item
        snap = item.snapshot_tribunal or {}
        import datetime as _dt
        snap_hora = None
        if snap.get('hora'):
            try:
                snap_hora = _dt.time.fromisoformat(snap['hora'])
            except ValueError:
                pass
        igual = (
            item.presidente_nombre == snap.get('presidente_nombre', '') and
            item.presidente_dni    == snap.get('presidente_dni', '') and
            item.vocal_1_nombre    == snap.get('vocal_1_nombre', '') and
            item.vocal_1_dni       == snap.get('vocal_1_dni', '') and
            item.vocal_2_nombre    == snap.get('vocal_2_nombre', '') and
            item.vocal_2_dni       == snap.get('vocal_2_dni', '') and
            item.dia_semana        == snap.get('dia_semana') and
            item.hora              == snap_hora and
            item.permite_libres    == snap.get('permite_libres', True)
        )
        if igual:
            item.delete()
            messages.success(request, 'La propuesta quedó sin cambios respecto al tribunal original y fue eliminada.')
        elif propuesto_por:
            fila = tribunal.fila
            _crear_notificacion(
                director_borrador, 'nuevo_tramite',
                f'Propuesta de cambio de tribunal — {fila.materia.nombre}',
                f'{user.get_full_name() or user.username} (director de {user.carrera.nombre}) propuso un cambio '
                f'en el tribunal de {fila.materia.nombre} ({fila.plan.carrera.nombre}). '
                f'Revisalo, completalo si hace falta y envialo a administración con la solicitud de cambio.',
                url=reverse('planes:lista_tribunales') + '?filtro=con_propuesta',
            )
            messages.success(request, f'Propuesta enviada al director del Departamento de {departamento}.')
        else:
            messages.success(request, 'Cambio propuesto guardado.')
    else:
        messages.error(request, 'Corregí los errores del formulario.')

    from django.urls import is_valid_path
    if next_url and next_url.startswith('/'):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(next_url)
    return redirect('planes:lista_tribunales')


@login_required
@solo_director_departamento
def cerrar_solicitud_cambio(request):
    """Cierra el borrador: valida que todos los tribunales estén completos y genera el docx."""
    if request.method != 'POST':
        return redirect('planes:lista_tribunales')

    departamento = request.user.departamento
    borrador = SolicitudCambioTribunal.objects.filter(
        director=request.user, departamento=departamento, estado='borrador',
    ).first()
    items = list(
        borrador.items.select_related(*_ITEMS_RELACIONADOS)
        .prefetch_related('tribunal__materia_optativa__optativas__plan__carrera')
    ) if borrador else []
    if not items:
        messages.error(request, 'No hay cambios propuestos para cerrar.')
        return redirect('planes:lista_tribunales')

    cerrada = SolicitudCambioTribunal.objects.filter(
        director=request.user, departamento=departamento, estado='cerrada',
    ).first()
    if cerrada:
        messages.error(
            request,
            'Ya tenés una modificación cerrada sin enviar. Enviala o reabrila antes de cerrar otra.',
        )
        return redirect('planes:detalle_mi_solicitud_cambio', pk=cerrada.pk)

    incompletos = [item.tribunal.fila for item in items if not tribunal_completo(item)]
    if incompletos:
        messages.error(
            request,
            f'No se puede cerrar: hay {len(incompletos)} tribunal(es) incompleto(s): '
            f'{_describir_incompletos(incompletos)}. Cada tribunal debe tener presidente, '
            '1er. y 2do. vocal con nombre y DNI, día y hora.',
        )
        return redirect(reverse('planes:lista_tribunales') + '?filtro=con_propuesta')

    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    User = get_user_model()

    filas, item_map, current_map = _filas_de_items(items)
    admin = User.objects.filter(rol='secretario', is_active=True).first()
    docx = generar_docx_solicitud_cambio(request.user, admin, filas, item_map, current_map)
    nombre = f'solicitud_cambio_tribunales_{departamento.lower().replace(" ", "_")}_{timezone.now():%Y%m%d}.docx'
    if borrador.documento:
        borrador.documento.delete(save=False)
    borrador.documento.save(nombre, ContentFile(docx.read()), save=False)
    borrador.estado = 'cerrada'
    borrador.save()

    messages.success(
        request,
        'Modificación cerrada: se generó el Word con la nota y las tablas de los tribunales modificados. '
        'Descargalo, iniciá el trámite en SUDOCU y enviá la solicitud con el número de trámite.',
    )
    return redirect('planes:detalle_mi_solicitud_cambio', pk=borrador.pk)


@login_required
@solo_director_departamento
def enviar_solicitud_cambio(request, pk):
    """Envía a administración una modificación cerrada, con su número de trámite SUDOCU."""
    solicitud = get_object_or_404(SolicitudCambioTribunal, pk=pk, director=request.user)
    if request.method != 'POST':
        return redirect('planes:detalle_mi_solicitud_cambio', pk=pk)
    if solicitud.estado != 'cerrada':
        messages.error(request, 'Solo se puede enviar una modificación cerrada.')
        return redirect('planes:detalle_mi_solicitud_cambio', pk=pk)

    numero_sudocu = request.POST.get('numero_sudocu', '').strip()
    if not numero_sudocu:
        messages.error(request, 'Ingresá el número de trámite SUDOCU.')
        return redirect('planes:detalle_mi_solicitud_cambio', pk=pk)

    solicitud.numero_sudocu = numero_sudocu
    solicitud.estado = 'enviada'
    solicitud.fecha_envio = timezone.now()
    solicitud.save(update_fields=['numero_sudocu', 'estado', 'fecha_envio'])

    from django.contrib.auth import get_user_model
    User = get_user_model()
    departamento = solicitud.departamento
    cantidad = solicitud.items.count()
    url_lista = reverse('planes:lista_solicitudes_cambio')
    for admin_user in User.objects.filter(rol__in=['secretario', 'direccion_academica', 'dpto_estudiantes'], is_active=True):
        _crear_notificacion(
            admin_user, 'nuevo_tramite',
            f'Solicitud de cambio de tribunales — Dpto. {departamento} — SUDOCU {numero_sudocu}',
            f'{request.user.get_full_name()} envió una solicitud de cambio de {cantidad} tribunal(es) '
            f'del Departamento de {departamento}.\nTrámite SUDOCU: {numero_sudocu}.',
            url=url_lista,
        )

    messages.success(request, f'Solicitud enviada a administración con el trámite SUDOCU {numero_sudocu}.')
    return redirect('planes:detalle_mi_solicitud_cambio', pk=pk)


@login_required
@solo_director_departamento
def descargar_solicitud_cambio(request, pk):
    from django.http import HttpResponse
    from django.contrib.auth import get_user_model
    User = get_user_model()

    departamento = request.user.departamento
    solicitud = get_object_or_404(SolicitudCambioTribunal, pk=pk, departamento=departamento)

    items = list(solicitud.items.select_related(*_ITEMS_RELACIONADOS).prefetch_related(
        'tribunal__materia_optativa__optativas__plan__carrera',
    ))
    meps, item_map, current_map = _filas_de_items(items)

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


@login_required
@solo_director_departamento
def descargar_solicitud_cambio_docx(request, pk):
    from django.http import HttpResponse
    from django.contrib.auth import get_user_model
    User = get_user_model()

    departamento = request.user.departamento
    solicitud = get_object_or_404(SolicitudCambioTribunal, pk=pk, departamento=departamento)

    items = list(solicitud.items.select_related(*_ITEMS_RELACIONADOS).prefetch_related(
        'tribunal__materia_optativa__optativas__plan__carrera',
    ))
    meps, item_map, current_map = _filas_de_items(items)

    admin = User.objects.filter(rol='secretario', is_active=True).first()
    director_user = solicitud.director or request.user
    buffer = generar_docx_solicitud_cambio(director_user, admin, meps, item_map, current_map)

    safe_dept = departamento.lower().replace(' ', '_')
    fecha_str = solicitud.fecha_creacion.strftime('%Y%m%d')
    filename = f'solicitud_cambio_tribunales_{safe_dept}_{fecha_str}.docx'
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    response = HttpResponse(buffer.read(), content_type=content_type)
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

    numero_sudocu = request.POST.get('numero_sudocu', '').strip()
    if not numero_sudocu:
        return JsonResponse({'ok': False, 'error': 'Ingresá el número de trámite SUDOCU.'})

    filas, tribunal_map, sin_tribunal = _filas_informe_departamento(departamento)
    incompletos = sin_tribunal + [f for f in filas if not tribunal_completo(tribunal_map[f.id])]
    if incompletos:
        return JsonResponse({'ok': False, 'error': (
            f'Hay {len(incompletos)} tribunal(es) incompleto(s): {_describir_incompletos(incompletos)}. '
            'Todos los tribunales deben tener presidente, 1er. y 2do. vocal con nombre y DNI, día y hora. '
            'Usá el filtro «Incompletos» para encontrarlos.'
        )})

    from django.core.files.base import ContentFile
    admin = User.objects.filter(rol='secretario', is_active=True).first()
    docx = generar_docx_informe_tribunales(director, admin, filas, tribunal_map)
    informe, _ = InformeTribunalesEnviado.objects.update_or_create(
        solicitud=solicitud,
        departamento=departamento,
        defaults={'director': director, 'fecha_envio': timezone.now(), 'numero_sudocu': numero_sudocu},
    )
    if informe.documento:
        informe.documento.delete(save=False)
    nombre = f'informe_tribunales_{departamento.lower().replace(" ", "_")}_{solicitud.anio}_c{solicitud.cuatrimestre}.docx'
    informe.documento.save(nombre, ContentFile(docx.read()), save=True)

    for admin_user in User.objects.filter(rol__in=['secretario', 'direccion_academica'], is_active=True):
        _crear_notificacion(
            admin_user, 'nuevo_tramite',
            f'Informe de tribunales enviado — Dpto. {departamento} — SUDOCU {numero_sudocu}',
            f'{director.get_full_name()} envió el informe de tribunales '
            f'del Departamento de {departamento} ({len(filas)} tribunales).\nTrámite SUDOCU: {numero_sudocu}.',
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


@login_required
@solo_director_departamento
def reabrir_solicitud_cambio(request, pk):
    if request.method != 'POST':
        return redirect('planes:mis_solicitudes_cambio')
    solicitud = get_object_or_404(
        SolicitudCambioTribunal,
        pk=pk,
        director=request.user,
    )
    if solicitud.estado == 'aplicada':
        messages.error(request, 'No podés modificar una solicitud ya aplicada.')
        return redirect('planes:mis_solicitudes_cambio')
    if solicitud.estado == 'borrador':
        return redirect('planes:lista_tribunales')

    # Si mientras tanto se abrió otro borrador (propuestas nuevas), se fusiona en la reabierta:
    # para un mismo tribunal vale la propuesta más reciente.
    otro = (
        SolicitudCambioTribunal.objects
        .filter(director=request.user, departamento=solicitud.departamento, estado='borrador')
        .exclude(pk=solicitud.pk)
        .first()
    )
    if otro:
        solicitud.items.filter(tribunal_id__in=otro.items.values('tribunal_id')).delete()
        otro.items.update(solicitud=solicitud)
        otro.delete()

    if solicitud.documento:
        solicitud.documento.delete(save=False)  # se regenera al volver a cerrarla
    solicitud.estado = 'borrador'
    solicitud.fecha_envio = None
    solicitud.save(update_fields=['estado', 'fecha_envio', 'documento'])
    messages.success(request, 'Solicitud reabierta. Podés modificar los cambios desde Tribunales.')
    return redirect('planes:lista_tribunales')


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
            models.Q(materia__nombre__unaccent__icontains=q) |
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
    bolsa_por_slot = dict(
        MateriaOptativa.optativas.through.objects
        .filter(materiaenplan_id__in=page_mep_ids)
        .values('materiaenplan_id')
        .annotate(n=models.Count('id'))
        .values_list('materiaenplan_id', 'n')
    )
    for mep in page_obj:
        mep.tribunal_obj = tribunales_map.get(mep.id)
        mep.n_bolsa = bolsa_por_slot.get(mep.id, 0)

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

    informes = InformeTribunalesEnviado.objects.select_related('solicitud', 'director').order_by('-fecha_envio')
    if dept_filtro:
        informes = informes.filter(departamento=dept_filtro)
    return render(request, 'planes/admin_lista_solicitudes_cambio.html', {
        'informes_enviados': informes[:30],
        'page_obj': page_obj,
        'dept_filtro': dept_filtro,
        'departamento_opciones': DEPARTAMENTO_OPCIONES,
    })


def _preparar_items_solicitud_cambio(solicitud):
    """Prepara items con t_actual y diff para vistas de detalle de solicitud de cambio."""
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
            dia_semana=dia, hora=hora,
            permite_libres=snap.get('permite_libres', True),
        )
        obj.get_dia_semana_display = lambda: _DIAS_DISPLAY.get(dia, '')
        return obj

    items = list(
        solicitud.items
        .select_related(*_ITEMS_RELACIONADOS, 'propuesto_por')
        .prefetch_related('tribunal__materia_optativa__optativas__plan__carrera')
        .order_by(
            'tribunal__materia_en_plan__materia__codigo',
            'tribunal__materia_en_plan__plan__carrera__nombre',
            'tribunal__materia_en_plan__plan__codigo',
            'tribunal__materia_en_plan__ano',
            'tribunal__materia_optativa__codigo',
            'tribunal__carrera__nombre',
        )
    )
    for item in items:
        item.fila = item.tribunal.fila
        snap = item.snapshot_tribunal or {}
        baseline = _snap_to_obj(snap) if snap else item.tribunal
        item.t_actual = baseline
        item.diff = {
            'presidente': (item.presidente_nombre != baseline.presidente_nombre or
                           item.presidente_dni != baseline.presidente_dni),
            'vocal_1': (item.vocal_1_nombre != baseline.vocal_1_nombre or
                        item.vocal_1_dni != baseline.vocal_1_dni),
            'vocal_2': (item.vocal_2_nombre != baseline.vocal_2_nombre or
                        item.vocal_2_dni != baseline.vocal_2_dni),
            'dia':      item.dia_semana != baseline.dia_semana,
            'hora':     item.hora != baseline.hora,
            'modalidad': item.permite_libres != baseline.permite_libres,
        }
    return items


@login_required
@solo_director_departamento
def detalle_mi_solicitud_cambio(request, pk):
    solicitud = get_object_or_404(
        SolicitudCambioTribunal.objects.select_related('director'),
        pk=pk,
        director=request.user,
    )
    items = _preparar_items_solicitud_cambio(solicitud)
    return render(request, 'planes/detalle_mi_solicitud_cambio.html', {
        'solicitud': solicitud,
        'items': items,
    })


@login_required
@solo_administrador
def detalle_solicitud_cambio(request, pk):
    solicitud = get_object_or_404(
        SolicitudCambioTribunal.objects.select_related('director'),
        pk=pk,
    )
    items = _preparar_items_solicitud_cambio(solicitud)

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
        tribunal.presidente = Docente.objects.filter(dni=item.presidente_dni).first() if item.presidente_dni else None
        tribunal.vocal_1 = Docente.objects.filter(dni=item.vocal_1_dni).first() if item.vocal_1_dni else None
        tribunal.vocal_2 = Docente.objects.filter(dni=item.vocal_2_dni).first() if item.vocal_2_dni else None
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

    items = list(solicitud.items.select_related(*_ITEMS_RELACIONADOS).prefetch_related(
        'tribunal__materia_optativa__optativas__plan__carrera',
    ))
    meps, item_map, current_map = _filas_de_items(items)

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
        .select_related(*_ITEMS_SERVICIO_RELACIONADOS)
        .prefetch_related('comision__planes', 'comision__materia_optativa__optativas__plan')
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
        .select_related(*_ITEMS_SERVICIO_RELACIONADOS)
        .prefetch_related('comision__planes', 'comision__materia_optativa__optativas__plan')
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
    return (
        MateriaEnPlan.objects
        .filter(
            plan__carrera=carrera,
            es_servicio=True,
            departamento_dictante=departamento_dictante,
        )
        .filter(models.Q(plan__vigente=True) | models.Q(plan__activo=True))
        .filter(es_optativa=False)
        .select_related('materia', 'plan__carrera')
        .order_by('cuatrimestre', 'plan__codigo', 'materia__nombre')
    )


def _comisiones_servicio_para_carrera(carrera, departamento_dictante, anio, cuatrimestres):
    """Comisiones de optativas de la carrera que dicta otro departamento (o un externo)."""
    if departamento_dictante == carrera.departamento:
        return Comision.objects.none()
    return (
        Comision.objects
        .filter(
            carrera=carrera, anio=anio, cuatrimestre__in=cuatrimestres, se_dicta=True,
            materia_optativa__departamento=departamento_dictante,
        )
        .select_related('materia_optativa', 'carrera')
        .prefetch_related('planes')
        .order_by('cuatrimestre', 'materia_optativa__nombre')
    )


_ITEMS_SERVICIO_RELACIONADOS = (
    'materia_en_plan__materia', 'materia_en_plan__plan__carrera',
    'comision__materia_optativa', 'comision__carrera',
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

    convocatoria = ConvocatoriaSolicitudServicio.objects.order_by('-anio', '-cuatrimestre').first()
    estado_deptos = []
    if convocatoria:
        cuats_validos = _cuatrimestres_validos(convocatoria.cuatrimestre)
        dept_solicitante = carrera.departamento
        enviadas_este_anio = {
            s.departamento_dictante
            for s in SolicitudServicio.objects.filter(
                carrera=carrera,
                anio_academico=convocatoria.anio,
            )
        }
        for valor, label in DEPARTAMENTO_OPCIONES:
            if valor == dept_solicitante:
                continue
            tiene_materias = _meps_servicio_para_carrera(carrera, valor).filter(
                cuatrimestre__in=cuats_validos
            ).exists() or _comisiones_servicio_para_carrera(
                carrera, valor, convocatoria.anio, cuats_validos,
            ).exists()
            if valor in enviadas_este_anio:
                estado = 'realizada'
            elif not tiene_materias:
                estado = 'sin_materias'
            else:
                estado = 'pendiente'
            estado_deptos.append({
                'valor': valor,
                'label': label,
                'estado': estado,
            })

    return render(request, 'planes/solicitudes_servicio_carrera.html', {
        'enviadas': enviadas,
        'carrera': carrera,
        'convocatoria': convocatoria,
        'estado_deptos': estado_deptos,
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
    comisiones = []
    if dept_destino and dept_destino in valid_deptos:
        meps = list(
            _meps_servicio_para_carrera(carrera, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )
        sin_hs = [m for m in meps if m.hs_totales is None]
        comisiones = list(_comisiones_servicio_para_carrera(carrera, dept_destino, anio, cuats_validos))

    def _ctx(meps, sin_hs, dept_destino, dest_map=None, dest_com_map=None):
        dest_map = dest_map or {}
        dest_com_map = dest_com_map or {}
        return {
            'departamento_opciones': [(v, l) for v, l in DEPARTAMENTO_OPCIONES if v != departamento_solicitante],
            'dept_destino': dept_destino,
            'meps_con_dest': [(m, dest_map.get(m.pk, '')) for m in meps],
            'sin_hs': sin_hs,
            'comisiones_con_dest': [(c, dest_com_map.get(c.pk, '')) for c in comisiones],
            'comisiones_sin_credito': [c for c in comisiones if not c.credito_horario],
            'convocatoria': convocatoria,
            'carrera': carrera,
        }

    if request.method == 'POST':
        dept_destino = request.POST.get('departamento_dictante', '').strip()

        if dept_destino not in valid_deptos:
            messages.error(request, 'Departamento destino no válido.')
            return redirect('planes:nueva_solicitud_servicio_carrera')

        meps = list(
            _meps_servicio_para_carrera(carrera, dept_destino)
            .filter(cuatrimestre__in=cuats_validos)
        )
        comisiones = list(_comisiones_servicio_para_carrera(carrera, dept_destino, anio, cuats_validos))
        if not meps and not comisiones:
            messages.error(request, 'No hay materias de servicio habilitadas para ese departamento en la convocatoria actual.')
            return redirect('planes:nueva_solicitud_servicio_carrera')

        sin_hs = [m for m in meps if m.hs_totales is None]

        if dept_destino == 'Externo':
            dest_map = {mep.pk: request.POST.get(f'dest_{mep.pk}', '').strip() for mep in meps}
            dest_com_map = {c.pk: request.POST.get(f'dest_com_{c.pk}', '').strip() for c in comisiones}
            errores_dest = (
                [m.materia.nombre for m in meps if not dest_map.get(m.pk)] +
                [c.materia_optativa.nombre for c in comisiones if not dest_com_map.get(c.pk)]
            )
            if errores_dest:
                messages.error(request, f'Falta el destinatario de: {", ".join(errores_dest)}.')
                return render(request, 'planes/nueva_solicitud_servicio_carrera.html',
                              _ctx(meps, sin_hs, dept_destino, dest_map, dest_com_map))
        else:
            dest_auto = f'Director/a del Departamento de {dept_destino}'
            dest_map = {mep.pk: dest_auto for mep in meps}
            dest_com_map = {c.pk: dest_auto for c in comisiones}

        sin_credito = [c.materia_optativa.nombre for c in comisiones if not c.credito_horario]
        if sin_credito:
            messages.error(request, f'Completá el crédito horario de la comisión de: {", ".join(sin_credito)}.')
            return render(request, 'planes/nueva_solicitud_servicio_carrera.html',
                          _ctx(meps, sin_hs, dept_destino, dest_map, dest_com_map))

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
            return render(request, 'planes/nueva_solicitud_servicio_carrera.html',
                          _ctx(meps, sin_hs, dept_destino, dest_map, dest_com_map))

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
            dictante_externo_nombre='',
            anio_academico=anio,
            estado='enviada',
            fecha_envio=timezone.now(),
        )
        for mep in meps:
            SolicitudServicioItem.objects.create(
                solicitud=solicitud,
                materia_en_plan=mep,
                hs_totales=hs_map.get(mep.pk, mep.hs_totales or 0),
                destinatario=dest_map.get(mep.pk, ''),
            )
        for c in comisiones:
            SolicitudServicioItem.objects.create(
                solicitud=solicitud,
                comision=c,
                hs_totales=c.credito_horario,
                destinatario=dest_com_map.get(c.pk, ''),
            )

        messages.success(request, 'Solicitud de servicio enviada correctamente.')
        return redirect('planes:detalle_solicitud_servicio', pk=solicitud.pk)

    return render(request, 'planes/nueva_solicitud_servicio_carrera.html',
                  _ctx(meps, sin_hs, dept_destino))


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


# ── admin: bolsa de materias optativas ────────────────────────────────────────

@login_required
@solo_admin_general
def admin_lista_optativas(request):
    q = request.GET.get('q', '').strip()
    carrera_pk = request.GET.get('carrera', '')
    estado = request.GET.get('estado', 'vigentes')

    qs = MateriaOptativa.objects.prefetch_related('optativas__plan__carrera', 'optativas__materia')
    if q:
        qs = qs.filter(models.Q(nombre__unaccent__icontains=q) | models.Q(codigo__icontains=q))
    if carrera_pk:
        qs = qs.filter(optativas__plan__carrera__pk=carrera_pk).distinct()
    if estado == 'vigentes':
        qs = qs.filter(vigente=True)
    elif estado == 'baja':
        qs = qs.filter(vigente=False)

    materias = list(qs.order_by('nombre'))
    for m in materias:
        m.hs_distintas = m.slots_con_hs_distintas()

    return render(request, 'planes/admin_optativas.html', {
        'materias': materias,
        'q': q,
        'carrera_pk': carrera_pk,
        'estado': estado,
        'carrera_opciones': Carrera.objects.values_list('pk', 'nombre').order_by('nombre'),
    })


@login_required
@solo_admin_general
def admin_editar_optativa(request, pk=None):
    materia = get_object_or_404(MateriaOptativa, pk=pk) if pk else None
    form = MateriaOptativaForm(request.POST or None, instance=materia)

    if request.method == 'POST' and form.is_valid():
        materia = form.save()
        creados, _, conservados = materia.sincronizar_tribunales()
        messages.success(request, f'«{materia.nombre}» guardada en la bolsa de optativas.')
        if creados:
            messages.info(request, f'Se crearon {creados} tribunal{"es" if creados != 1 else ""} (uno por carrera).')
        if conservados:
            messages.warning(
                request,
                f'{conservados} tribunal{"es" if conservados != 1 else ""} quedaron sin vínculo pero se '
                'conservaron porque tienen datos o cambios propuestos.',
            )
        for aviso in advertencias_hs(materia):
            messages.warning(request, aviso)
        return redirect('planes:admin_lista_optativas')

    # Opciones de vinculación agrupadas por carrera
    seleccion = {str(v) for v in (form['optativas'].value() or [])}
    grupos = []
    for mep in form.fields['optativas'].queryset:
        if not grupos or grupos[-1]['carrera'] != mep.plan.carrera:
            grupos.append({'carrera': mep.plan.carrera, 'slots': []})
        grupos[-1]['slots'].append((mep, str(mep.pk) in seleccion))

    return render(request, 'planes/admin_optativa_form.html', {
        'form': form,
        'materia': materia,
        'grupos': grupos,
        'tribunales': (
            materia.tribunales.select_related('carrera').order_by('carrera__nombre') if materia else []
        ),
    })


# ── director de carrera: dictado de optativas ────────────────────────────────

@login_required
@solo_director_carrera
def optativas_carrera(request):
    carrera = request.user.carrera
    if not carrera:
        messages.error(request, 'No tenés una carrera asignada. Contactá a administración.')
        return redirect('tramites:dashboard')

    # El período es el del informe de comisiones abierto por administración
    informe = SolicitudInformeComisiones.objects.filter(activa=True).first()
    materias = list(
        materias_ofrecidas_en_carrera(carrera)
        .prefetch_related('optativas__plan', 'optativas__materia')
        .order_by('nombre')
    )
    for m in materias:
        m.slots_carrera = [s for s in m.optativas.all() if s.plan.carrera_id == carrera.pk]

    cuats = informe.cuatrimestres if informe else []
    habilitadas = [m for m in materias if m.cuatrimestre in cuats]
    comisiones = {
        c.materia_optativa_id: c
        for c in Comision.objects.filter(carrera=carrera, anio=informe.anio, materia_optativa__isnull=False)
    } if informe else {}
    for m in habilitadas:
        m.comision = comisiones.get(m.pk)

    if request.method == 'POST':
        if not informe:
            messages.error(request, 'No hay un informe de comisiones abierto. Esperá que administración lo solicite.')
            return redirect('planes:optativas_carrera')
        elegidas = {int(x) for x in request.POST.getlist('dictar') if x.isdigit()}
        activadas, quitadas, bloqueadas, con_servicio = 0, 0, [], 0
        for m in habilitadas:
            c = m.comision
            if m.pk in elegidas and (c is None or not c.se_dicta):
                if c is None:
                    c, _ = crear_comision(m, carrera, informe.anio, request.user)
                else:
                    c.se_dicta = True
                    c.save(update_fields=['se_dicta'])
                activadas += 1
                con_servicio += c.requiere_servicio
            elif m.pk not in elegidas and c is not None and c.se_dicta:
                if c.items_servicio.exists():
                    bloqueadas.append(m.nombre)
                else:
                    c.se_dicta = False
                    c.save(update_fields=['se_dicta'])
                    quitadas += 1
        if activadas or quitadas:
            messages.success(
                request,
                f'Dictado actualizado: {activadas} optativa(s) se dicta(n), {quitadas} quitada(s).',
            )
        else:
            messages.info(request, 'No hubo cambios.')
        if con_servicio:
            messages.info(
                request,
                'Las optativas que dicta otro departamento aparecen en tus solicitudes de servicio.',
            )
        if bloqueadas:
            messages.warning(
                request,
                f'No se quitó el dictado de {", ".join(bloqueadas)} porque ya figura en una solicitud de servicio enviada.',
            )
        return redirect('planes:optativas_carrera')

    return render(request, 'planes/optativas_carrera.html', {
        'carrera': carrera,
        'informe': informe,
        'habilitadas': habilitadas,
        'otras': [m for m in materias if m.cuatrimestre and m not in habilitadas],
        'sin_cuatrimestre': [m for m in materias if not m.cuatrimestre],
    })


# ── comisiones ───────────────────────────────────────────────────────────────

def _comisiones_visibles(user):
    qs = Comision.objects.select_related('materia', 'materia_optativa', 'carrera', 'director')
    if user.es_administrador:
        return qs
    if user.es_director_carrera and user.carrera_id:
        return qs.filter(carrera_id=user.carrera_id)
    if user.es_director_departamento:
        return qs.filter(departamento=user.departamento)
    return qs.none()


def _puede_editar_comision(user, comision):
    """El director de carrera, todas las de su carrera. El director de departamento, las de
    materias de plan que informa su departamento (las optativas las completa la carrera)."""
    if user.es_director_carrera and comision.carrera_id == user.carrera_id:
        return True
    return (
        user.es_director_departamento and not comision.es_optativa_bolsa
        and comision.departamento == user.departamento
    )


def _cuatrimestres_de_periodo(periodo):
    """Período del informe ('1' = 1° cuatrimestre + anuales, '2' = 2° cuatrimestre)."""
    return [1, 3] if periodo == '1' else [2]


@login_required
def lista_comisiones(request):
    user = request.user
    if not (user.es_administrador or user.es_director_carrera or user.es_director_departamento):
        messages.error(request, 'No tenés permisos para acceder a esta sección.')
        return redirect('tramites:dashboard')

    activa = SolicitudInformeComisiones.objects.filter(activa=True).first()
    try:
        anio = int(request.GET.get('anio') or (activa.anio if activa else timezone.now().year))
    except ValueError:
        anio = timezone.now().year
    periodo = request.GET.get('periodo') or (str(activa.cuatrimestre) if activa else '1')
    if periodo not in ('1', '2'):
        periodo = '1'
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')

    qs = (
        _comisiones_visibles(user)
        .filter(anio=anio, cuatrimestre__in=_cuatrimestres_de_periodo(periodo))
        .prefetch_related('planes', 'equipo')
        .order_by('materia__nombre', 'materia_optativa__nombre', 'carrera__nombre')
    )
    if tipo == 'plan':
        qs = qs.filter(materia__isnull=False)
    elif tipo == 'optativas':
        qs = qs.filter(materia_optativa__isnull=False)
    comisiones = list(qs)
    for c in comisiones:
        c.editable = _puede_editar_comision(user, c)
    incompletas = sum(1 for c in comisiones if c.se_dicta and not c.esta_completa)
    if estado == 'incompletas':
        comisiones = [c for c in comisiones if c.se_dicta and not c.esta_completa]

    informe = None
    if (user.es_director_departamento and activa
            and activa.anio == anio and str(activa.cuatrimestre) == periodo):
        informe = {
            'solicitud': activa,
            'enviado': InformeComisionesEnviado.objects.filter(
                solicitud=activa, departamento=user.departamento,
            ).first(),
            'incompletas': _comisiones_incompletas(activa, user.departamento),
        }

    anios = sorted(set(_comisiones_visibles(user).values_list('anio', flat=True)) | {anio}, reverse=True)
    return render(request, 'planes/comisiones.html', {
        'comisiones': comisiones,
        'anio': anio,
        'anios': anios,
        'periodo': periodo,
        'tipo': tipo,
        'estado': estado,
        'incompletas': incompletas,
        'informe': informe,
    })


@login_required
def detalle_comision(request, pk):
    """Detalle de la comisión; quien puede editarla la completa en la misma página."""
    comision = get_object_or_404(
        _comisiones_visibles(request.user).prefetch_related('planes', 'equipo'), pk=pk,
    )
    puede_editar = _puede_editar_comision(request.user, comision)
    form = formset = None
    if puede_editar:
        datos = request.POST if request.method == 'POST' else None
        form = ComisionForm(datos, instance=comision)
        formset = MiembroComisionFormSet(datos, instance=comision, prefix='equipo')
        if datos is not None and form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            for i, f in enumerate(formset.forms):
                if f.instance.pk and f not in formset.deleted_forms:
                    type(f.instance).objects.filter(pk=f.instance.pk).update(orden=i)
            messages.success(request, 'Comisión guardada.')
            return redirect('planes:detalle_comision', pk=comision.pk)
        if datos is not None:
            messages.error(request, 'Corregí los errores marcados.')

    return render(request, 'planes/comision_detalle.html', {
        'comision': comision,
        'puede_editar': puede_editar,
        'form': form,
        'formset': formset,
        'items_servicio': comision.items_servicio.select_related('solicitud'),
    })


@login_required
def editar_comision(request, pk):
    """Compatibilidad: la edición ahora se hace en el detalle."""
    return redirect('planes:detalle_comision', pk=pk)


# ── informe cuatrimestral de comisiones ──────────────────────────────────────

def _comisiones_incompletas(solicitud, departamento):
    """Comisiones del informe del departamento (solo las que se dictan) sin completar."""
    return [c for c in _comisiones_del_informe(solicitud, departamento) if not c.esta_completa]


def _comisiones_del_informe(solicitud, departamento):
    return (
        Comision.objects
        .filter(departamento=departamento, anio=solicitud.anio, cuatrimestre__in=solicitud.cuatrimestres, se_dicta=True)
        .select_related('materia', 'materia_optativa', 'carrera')
        .prefetch_related('planes', 'equipo')
        .order_by('cuatrimestre', 'materia__nombre', 'materia_optativa__nombre', 'carrera__nombre')
    )


@login_required
@solo_admin_general
def solicitar_informe_comisiones(request):
    if request.method != 'POST':
        return redirect('planes:admin_informes_comisiones')
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        cuatrimestre = int(request.POST.get('cuatrimestre', 0))
        anio = int(request.POST.get('anio', 0))
    except ValueError:
        cuatrimestre = anio = 0
    if cuatrimestre not in (1, 2) or anio < 2020:
        messages.error(request, 'Cuatrimestre o año inválido.')
        return redirect('planes:admin_informes_comisiones')

    from django.db import transaction
    with transaction.atomic():
        solicitud, _ = SolicitudInformeComisiones.objects.get_or_create(
            anio=anio, cuatrimestre=cuatrimestre, defaults={'solicitante': request.user},
        )
        SolicitudInformeComisiones.objects.exclude(pk=solicitud.pk).update(activa=False)
        if not solicitud.activa:
            solicitud.activa = True
            solicitud.save(update_fields=['activa'])
        creadas, departamentos = crear_comisiones_del_periodo(anio, solicitud.cuatrimestres)
    departamentos |= set(
        Comision.objects
        .filter(anio=anio, cuatrimestre__in=solicitud.cuatrimestres)
        .exclude(departamento='')
        .values_list('departamento', flat=True)
    )

    periodo_label = solicitud.get_cuatrimestre_display()
    url = reverse('planes:lista_comisiones') + f'?anio={anio}&periodo={cuatrimestre}'
    notificados = 0
    for director in User.objects.filter(rol='director_departamento', is_active=True, departamento__in=departamentos):
        _crear_notificacion(
            director, 'nuevo_tramite',
            f'Informe de comisiones — {periodo_label} {anio}',
            (
                f'Se solicita el informe de comisiones del {periodo_label.lower()} {anio} de las materias '
                'de tu departamento.\n\nCompletá la condición de cursada, el crédito horario, los planes '
                'y el equipo docente de cada comisión y enviá el informe.'
            ),
            url=url,
        )
        notificados += 1

    messages.success(
        request,
        f'Informe de comisiones {periodo_label} {anio} solicitado a {notificados} '
        f'director{"es" if notificados != 1 else ""}. Se crearon {creadas} comisión(es) nuevas.',
    )
    return redirect(reverse('planes:admin_informes_comisiones') + f'?solicitud={solicitud.pk}')


@login_required
@solo_admin_general
def admin_informes_comisiones(request):
    solicitudes = list(SolicitudInformeComisiones.objects.all())
    solicitud = None
    if request.GET.get('solicitud', '').isdigit():
        solicitud = next((s for s in solicitudes if s.pk == int(request.GET['solicitud'])), None)
    if solicitud is None:
        solicitud = next((s for s in solicitudes if s.activa), solicitudes[0] if solicitudes else None)

    filas = []
    if solicitud:
        enviados = {i.departamento: i for i in solicitud.informes_enviados.select_related('director')}
        for dep, label in DEPARTAMENTO_OPCIONES:
            if dep == 'Externo':
                continue
            comisiones = list(_comisiones_del_informe(solicitud, dep))
            filas.append({
                'departamento': dep,
                'label': label,
                'total': len(comisiones),
                'completas': sum(1 for c in comisiones if c.esta_completa),
                'enviado': enviados.get(dep),
            })

    return render(request, 'planes/admin_informes_comisiones.html', {
        'solicitudes': solicitudes,
        'solicitud': solicitud,
        'filas': filas,
        'anio_actual': timezone.now().year,
    })


@login_required
@solo_director_departamento
def enviar_informe_comisiones(request):
    if request.method != 'POST':
        return redirect('planes:lista_comisiones')
    from django.contrib.auth import get_user_model
    User = get_user_model()

    solicitud = SolicitudInformeComisiones.objects.filter(activa=True).first()
    if not solicitud:
        messages.error(request, 'No hay un informe de comisiones solicitado.')
        return redirect('planes:lista_comisiones')

    departamento = request.user.departamento
    incompletas = _comisiones_incompletas(solicitud, departamento)
    if incompletas:
        nombres = ', '.join(f'{c.nombre_materia} ({c.carrera.nombre})' for c in incompletas[:5])
        resto = f' y {len(incompletas) - 5} más' if len(incompletas) > 5 else ''
        messages.error(
            request,
            f'No se puede enviar el informe: hay {len(incompletas)} comisión(es) de materias que se '
            f'dictan sin completar ({nombres}{resto}). Completá condición, crédito horario y equipo docente.',
        )
        return redirect(
            reverse('planes:lista_comisiones')
            + f'?anio={solicitud.anio}&periodo={solicitud.cuatrimestre}&estado=incompletas'
        )
    InformeComisionesEnviado.objects.update_or_create(
        solicitud=solicitud, departamento=departamento,
        defaults={'director': request.user, 'fecha_envio': timezone.now()},
    )
    for admin_user in User.objects.filter(rol__in=['secretario', 'direccion_academica'], is_active=True):
        _crear_notificacion(
            admin_user, 'nuevo_tramite',
            f'Informe de comisiones enviado — Dpto. {departamento}',
            f'{request.user.get_full_name()} envió el informe de comisiones del '
            f'{solicitud.get_cuatrimestre_display().lower()} {solicitud.anio} del Departamento de {departamento}.',
            url=reverse('planes:admin_informes_comisiones') + f'?solicitud={solicitud.pk}',
        )
    messages.success(request, 'Informe de comisiones enviado.')
    return redirect(reverse('planes:lista_comisiones') + f'?anio={solicitud.anio}&periodo={solicitud.cuatrimestre}')


@login_required
def descargar_informe_comisiones(request, pk):
    from django.contrib.auth import get_user_model
    from django.http import HttpResponse
    User = get_user_model()

    solicitud = get_object_or_404(SolicitudInformeComisiones, pk=pk)
    user = request.user
    if user.puede_admin_general:
        departamento = request.GET.get('departamento', '')
        if departamento not in {v for v, _ in DEPARTAMENTO_OPCIONES}:
            messages.error(request, 'Departamento inválido.')
            return redirect('planes:admin_informes_comisiones')
    elif user.es_director_departamento:
        departamento = user.departamento
    else:
        messages.error(request, 'No tenés permiso.')
        return redirect('tramites:dashboard')

    comisiones = list(_comisiones_del_informe(solicitud, departamento))
    enviado = solicitud.informes_enviados.filter(departamento=departamento).select_related('director').first()
    director = (
        (enviado.director if enviado else None)
        or (user if user.es_director_departamento else None)
        or User.objects.filter(rol='director_departamento', departamento=departamento, is_active=True).first()
    )
    admin_user = User.objects.filter(rol='secretario', is_active=True).first()

    nombre = f'informe_comisiones_{departamento.lower().replace(" ", "_")}_{solicitud.anio}_c{solicitud.cuatrimestre}'
    if request.GET.get('formato') == 'docx':
        buffer = generar_docx_informe_comisiones(departamento, director, admin_user, solicitud, comisiones)
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        response['Content-Disposition'] = f'attachment; filename="{nombre}.docx"'
        return response
    buffer = generar_pdf_informe_comisiones(departamento, director, admin_user, solicitud, comisiones)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre}.pdf"'
    return response
