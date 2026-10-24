"""Bolsa de materias optativas y comisiones: alta desde protocolizaciones, comisiones de
dictado de optativas y comisiones de materias de plan para el informe cuatrimestral."""
from collections import defaultdict

from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from apps.tramites.models import DEPARTAMENTO_CHOICES, EstadoTramite
from .models import AnioDictado, Comision, Materia, MateriaEnPlan, MateriaOptativa, MiembroComision, PlanEstudio

CUATRIMESTRE_DE_PERIODO = {'1c': 1, '2c': 2, 'anual': 3}
_PLAN_EN_USO = Q(vigente=True) | Q(activo=True)


def advertencias_hs(materia):
    """Mensajes para cada optativa vinculada cuya carga horaria difiere de la de la materia."""
    return [
        f'La carga horaria de {materia.nombre} ({materia.hs_totales} hs) es distinta a la de '
        f'«{s.materia.nombre}» del plan {s.plan.codigo} — {s.plan.carrera.nombre} ({s.hs_totales} hs).'
        for s in materia.slots_con_hs_distintas()
    ]


def agregar_a_bolsa(solicitud):
    """Crea o actualiza la materia de la bolsa al aprobar una protocolización de tipo optativa
    y la vincula a la optativa elegida en la solicitud. Devuelve (materia | None, avisos)."""
    if solicitud.tipificacion != 'optativa':
        return None, []
    codigo = (solicitud.codigo_materia or '').strip()
    if not codigo:
        return None, ['La solicitud no tiene código de materia asignado: no se agregó a la bolsa de optativas.']

    avisos = []
    if Materia.objects.filter(codigo=codigo).exists():
        avisos.append(f'El código {codigo} ya corresponde a una materia de plan; revisá que sea correcto.')

    departamento = solicitud.usuario.departamento if solicitud.usuario_id else solicitud.departamento_docente
    if not departamento and solicitud.carrera_id:
        departamento = solicitud.carrera.departamento
    datos = {
        'nombre': solicitud.nombre_curso,
        'hs_totales': solicitud.total_horas or None,
        'cuatrimestre': CUATRIMESTRE_DE_PERIODO.get(solicitud.periodo),
        'numero_resolucion': solicitud.numero_resolucion,
        'vigente': True,
    }
    if departamento in {v for v, _ in DEPARTAMENTO_CHOICES if v}:
        datos['departamento'] = departamento

    with transaction.atomic():
        materia, _ = MateriaOptativa.objects.update_or_create(codigo=codigo, defaults=datos)
        if solicitud.optativa_vinculada_id:
            materia.optativas.add(solicitud.optativa_vinculada_id)
        solicitud.materia_optativa = materia
        solicitud.save(update_fields=['materia_optativa'])
        materia.sincronizar_tribunales()
    return materia, avisos + advertencias_hs(materia)


def materias_ofrecidas_en_carrera(carrera):
    """Materias vigentes de la bolsa vinculadas a optativas de planes en uso de la carrera."""
    return (
        MateriaOptativa.objects
        .filter(vigente=True, optativas__plan__carrera=carrera)
        .filter(Q(optativas__plan__vigente=True) | Q(optativas__plan__activo=True))
        .distinct()
    )


def crear_comision(materia, carrera, anio, director):
    """Crea la comisión del año para la materia en la carrera. Si la materia viene de una
    protocolización aprobada, precarga su condición y su equipo docente."""
    comision, creada = Comision.objects.get_or_create(
        materia_optativa=materia, carrera=carrera, anio=anio,
        defaults={
            'cuatrimestre': materia.cuatrimestre,
            'credito_horario': materia.hs_totales,
            'director': director,
            'departamento': Comision.departamento_responsable(materia.departamento, carrera),
        },
    )
    if not creada:
        return comision, False

    comision.planes.set(
        PlanEstudio.objects
        .filter(carrera=carrera, materias_en_plan__materias_bolsa=materia)
        .filter(_PLAN_EN_USO)
        .distinct()
    )
    protocolizacion = (
        materia.protocolizaciones
        .filter(estado=EstadoTramite.APROBADO)
        .order_by('-fecha_actualizacion')
        .first()
    )
    if protocolizacion:
        if protocolizacion.condicion:
            comision.condicion = protocolizacion.condicion
            comision.save(update_fields=['condicion'])
        MiembroComision.objects.bulk_create([
            MiembroComision(
                comision=comision, nombre=m.nombre, dni=m.dni, funcion=m.funcion,
                cargo=m.cargo, dedicacion=m.dedicacion, orden=i,
            )
            for i, m in enumerate(protocolizacion.equipo_docente.all())
        ])
    return comision, True


# ── comisiones de materias de plan (informe cuatrimestral) ────────────────────

def meps_del_periodo(cuatrimestres):
    """MateriaEnPlan que se dictan en el período: planes en uso, años dictados, sin slots optativos."""
    ano_dictado = AnioDictado.objects.filter(plan=OuterRef('plan'), ano=OuterRef('ano'))
    return (
        MateriaEnPlan.objects
        .filter(Q(plan__vigente=True) | Q(plan__activo=True))
        .filter(cuatrimestre__in=cuatrimestres, es_optativa=False)
        .filter(Exists(ano_dictado))
        .select_related('materia', 'plan__carrera')
    )


def crear_comisiones_del_periodo(anio, cuatrimestres):
    """Crea las comisiones que falten: una por materia, carrera y cuatrimestre, con los planes
    de esa carrera donde se dicta. Devuelve (creadas, departamentos responsables)."""
    grupos = defaultdict(list)
    for mep in meps_del_periodo(cuatrimestres):
        grupos[(mep.materia_id, mep.plan.carrera_id, mep.cuatrimestre)].append(mep)

    creadas, departamentos = 0, set()
    with transaction.atomic():
        for (materia_id, carrera_id, cuatrimestre), meps in grupos.items():
            mep = meps[0]
            dictante = mep.departamento_dictante if mep.es_servicio else ''
            comision, creada = Comision.objects.get_or_create(
                materia_id=materia_id, carrera_id=carrera_id, anio=anio, cuatrimestre=cuatrimestre,
                defaults={
                    'departamento': Comision.departamento_responsable(dictante, mep.plan.carrera),
                    'credito_horario': next((m.hs_totales for m in meps if m.hs_totales), None),
                },
            )
            if creada:
                comision.planes.set({m.plan_id for m in meps})
                creadas += 1
            if comision.departamento:
                departamentos.add(comision.departamento)
    return creadas, departamentos
