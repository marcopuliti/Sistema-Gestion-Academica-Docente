"""Textos de las notas del circuito de protocolización: el acta de la Comisión de Carrera (la
genera el director de carrera) y la nota de aval del Consejo Departamental (la genera el director
de departamento). pdf.py y docx_gen.py las dibujan con el mismo formato a partir de este dict:

    {'fecha': date, 'destinatario': [líneas], 'parrafos': [[(texto, negrita), ...], ...], 'firma': [líneas]}
"""
from django.contrib.auth import get_user_model
from django.utils import timezone

MESES = [
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

# "decide avalar el dictado ..." según la tipificación
_DICTADO_DE = {
    'optativa': 'de la asignatura optativa',
    'jornada': 'de la jornada',
    'congreso': 'del congreso',
}


def fecha_larga(d):
    return f'{d.day} de {MESES[d.month]} de {d.year}'


def _nombre(user):
    return (user.get_full_name() or user.username) if user else ''


def director_de_carrera(solicitud):
    if solicitud.director_carrera_id:
        return solicitud.director_carrera
    if not solicitud.carrera_id:
        return None
    return (
        get_user_model().objects
        .filter(rol='director_carrera', carrera_id=solicitud.carrera_id, is_active=True)
        .order_by('pk').first()
    )


def director_de_departamento(departamento):
    if not departamento:
        return None
    return (
        get_user_model().objects
        .filter(rol='director_departamento', departamento=departamento, is_active=True)
        .order_by('pk').first()
    )


def de_la_carrera(nombre):
    """'de la Licenciatura en …' / 'del Profesorado en …'."""
    masculinos = ('Profesorado', 'Doctorado', 'Bachillerato', 'Técnico', 'Tecnico', 'Ciclo')
    return f'del {nombre}' if nombre.startswith(masculinos) else f'de la {nombre}'


def _datos(solicitud):
    carrera = solicitud.carrera.nombre if solicitud.carrera_id else '(carrera)'
    plan = solicitud.plan_estudio.codigo if solicitud.plan_estudio_id else ''
    return {
        'carrera': carrera,
        'plan': plan,
        'nombre': solicitud.nombre_curso or '(denominación)',
        'dictado_de': _DICTADO_DE.get(solicitud.tipificacion, 'de la asignatura'),
    }


def acta_comision_carrera(solicitud):
    d = _datos(solicitud)
    departamento = solicitud.departamento_destino or '(departamento)'
    director_dep = director_de_departamento(solicitud.departamento_destino)
    director_car = director_de_carrera(solicitud)
    plan = f', para el Plan {d["plan"]}' if d['plan'] else ''
    return {
        'fecha': solicitud.fecha_acta_comision_carrera or timezone.localdate(),
        'destinatario': [
            f'Al Sr./Sra. Director/a del Departamento de {departamento}',
            *([_nombre(director_dep)] if director_dep else []),
            'S / D',
        ],
        'parrafos': [
            [
                ('Por la presente nos dirigimos a Ud. y por su intermedio ante quien corresponda, a fin de '
                 'hacer constar que, luego del análisis de la propuesta, la Comisión de Carrera '
                 f'{de_la_carrera(d["carrera"])} decide avalar el dictado {d["dictado_de"]} ', False),
                (f'"{d["nombre"]}"', True),
                (f' y su programa{plan}. Por lo tanto, se solicita su protocolización y la apertura de la '
                 'Comisión correspondiente en el Sistema SIU Guaraní.', False),
            ],
            [
                ('Agradeciendo desde ya su gestión, nos despedimos de Ud. muy cordialmente, quedando a su '
                 'disposición para cualquier aclaración.', False),
            ],
        ],
        'firma': [
            _nombre(director_car),
            f'Director/a {de_la_carrera(d["carrera"])}',
            'Comisión de Carrera',
        ],
    }


def nota_aval_consejo(solicitud):
    d = _datos(solicitud)
    departamento = solicitud.departamento_destino or '(departamento)'
    director_dep = solicitud.revisor if (solicitud.revisor_id and solicitud.revisor.es_director_departamento) else None
    director_dep = director_dep or director_de_departamento(solicitud.departamento_destino)
    reunion = fecha_larga(solicitud.fecha_reunion_consejo) if solicitud.fecha_reunion_consejo else '(fecha)'
    hora = solicitud.hora_reunion_consejo.strftime('%H:%M') if solicitud.hora_reunion_consejo else '(hora)'
    plan = f', Plan {d["plan"]}' if d['plan'] else ''
    return {
        'fecha': solicitud.fecha_nota_aval or timezone.localdate(),
        'destinatario': [
            'Al Sr./Sra. Secretario/a Académico/a',
            'Facultad de Ciencias Físico Matemáticas y Naturales',
            'S / D',
        ],
        'parrafos': [
            [
                ('Me dirijo a Ud. a fin de informarle que el Consejo Departamental del Departamento de ', False),
                (departamento, True),
                (f', en su reunión del {reunion} a las {hora} hs, resolvió avalar el dictado {d["dictado_de"]} ', False),
                (f'"{d["nombre"]}"', True),
                (f' {de_la_carrera(d["carrera"])}{plan}, y su programa. Por lo tanto, se solicita su protocolización.', False),
            ],
            [('Sin otro particular, saludo a Ud. muy atentamente.', False)],
        ],
        'firma': [
            _nombre(director_dep),
            f'Director/a del Departamento de {departamento}',
        ],
    }
