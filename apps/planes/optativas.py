"""Bolsa de materias optativas: alta desde protocolizaciones y comisiones de dictado."""
from django.db import transaction
from django.db.models import Q

from apps.tramites.models import DEPARTAMENTO_CHOICES, EstadoTramite
from .models import ComisionOptativa, Materia, MateriaOptativa, MiembroComisionOptativa, PlanEstudio

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
    comision, creada = ComisionOptativa.objects.get_or_create(
        materia_optativa=materia, carrera=carrera, anio=anio,
        defaults={
            'cuatrimestre': materia.cuatrimestre,
            'credito_horario': materia.hs_totales,
            'director': director,
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
        MiembroComisionOptativa.objects.bulk_create([
            MiembroComisionOptativa(
                comision=comision, nombre=m.nombre, dni=m.dni, funcion=m.funcion,
                cargo=m.cargo, dedicacion=m.dedicacion, orden=i,
            )
            for i, m in enumerate(protocolizacion.equipo_docente.all())
        ])
    return comision, True
