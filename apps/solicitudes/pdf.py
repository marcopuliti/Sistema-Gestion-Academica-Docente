import os
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN
NEGRO = colors.black

ESTADO_LABEL = {
    'pendiente':   'en trámite de aprobación',
    'en_revision': 'en revisión',
    'aprobado':    'aprobado',
    'rechazado':   'rechazado',
}


# ── Estilos ────────────────────────────────────────────────────────────────────
def _s():
    base = getSampleStyleSheet()
    return {
        'inst_bold': ParagraphStyle(
            'InstBold', parent=base['Normal'],
            fontName='Times-Bold', fontSize=11,
            alignment=TA_CENTER, leading=15, spaceAfter=0,
        ),
        'status': ParagraphStyle(
            'Status', parent=base['Normal'],
            fontName='Times-Roman', fontSize=10,
            alignment=TA_CENTER, leading=14, spaceAfter=0,
        ),
        'sec_titulo': ParagraphStyle(
            'SecTitulo', parent=base['Normal'],
            fontName='Times-Bold', fontSize=10,
            spaceBefore=8, spaceAfter=3, leading=13,
        ),
        'th': ParagraphStyle(
            'TH', parent=base['Normal'],
            fontName='Times-Bold', fontSize=9, leading=11,
        ),
        'th_c': ParagraphStyle(
            'THC', parent=base['Normal'],
            fontName='Times-Bold', fontSize=9,
            alignment=TA_CENTER, leading=11,
        ),
        'td': ParagraphStyle(
            'TD', parent=base['Normal'],
            fontName='Times-Roman', fontSize=9, leading=11,
        ),
        'td_c': ParagraphStyle(
            'TDC', parent=base['Normal'],
            fontName='Times-Roman', fontSize=9,
            alignment=TA_CENTER, leading=11,
        ),
        'caja': ParagraphStyle(
            'Caja', parent=base['Normal'],
            fontName='Times-Roman', fontSize=9, leading=12,
        ),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────
_TABLA_BASE = [
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('GRID', (0, 0), (-1, -1), 0.5, NEGRO),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
]


def _tabla(datos, col_widths, extra_cmds=None):
    t = Table(datos, colWidths=col_widths)
    cmds = list(_TABLA_BASE)
    if extra_cmds:
        cmds.extend(extra_cmds)
    t.setStyle(TableStyle(cmds))
    return t


def _p(texto, estilo):
    """Paragraph con saltos de línea y escape HTML básico."""
    if texto is None:
        texto = ''
    escaped = (texto
               .replace('&', '&amp;')
               .replace('<', '&lt;')
               .replace('>', '&gt;'))
    return Paragraph(escaped.replace('\n', '<br/>'), estilo)


def _caja(texto, s):
    """Sección de texto libre dentro de un recuadro con borde."""
    t = Table([[_p(texto or '', s['caja'])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle(_TABLA_BASE))
    return t


def _sec_titulo(texto, s):
    return Paragraph(f'<u>{texto}</u>', s['sec_titulo'])


def _pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Roman', 9)
    canvas.drawCentredString(PAGE_W / 2, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


# ── Generador principal ────────────────────────────────────────────────────────
def generar_pdf_solicitud(solicitud):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=2 * cm,
    )
    s = _s()
    E = []  # elementos

    # ── ENCABEZADO ──────────────────────────────────────────────────────────────
    year       = solicitud.fecha_inicio.year
    estado_txt = ESTADO_LABEL.get(solicitud.estado, solicitud.estado)
    fecha_pres = solicitud.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')

    left_items = []
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'escudo.gif')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.8 * cm, height=2.8 * cm)
        logo.hAlign = 'CENTER'
        left_items.append(logo)
        left_items.append(Spacer(1, 0.15 * cm))

    dpto = (solicitud.usuario.departamento if solicitud.usuario else None) \
        or solicitud.departamento_docente or '—'
    for linea in [
        'Ministerio de Cultura y Educación',
        'Universidad Nacional de San Luis',
        'Facultad de Ciencias Físico Matemáticas y Naturales',
        f'Departamento: {dpto}',
    ]:
        left_items.append(Paragraph(linea, s['inst_bold']))

    if solicitud.area:
        left_items.append(Paragraph(f'Area: {solicitud.area}', s['inst_bold']))

    right_items = [
        Spacer(1, 0.8 * cm),
        Paragraph(f'(Programa del año {year})', s['status']),
        Paragraph(f'(Programa {estado_txt})', s['status']),
        Paragraph(f'(Presentado el {fecha_pres})', s['status']),
    ]

    cab = Table(
        [[left_items, right_items]],
        colWidths=[CONTENT_W * 0.62, CONTENT_W * 0.38],
    )
    cab.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    E.append(cab)
    E.append(Spacer(1, 0.4 * cm))

    # ── I — Oferta Académica ────────────────────────────────────────────────────
    E.append(_sec_titulo('I - Oferta Académica', s))
    w = CONTENT_W
    E.append(_tabla(
        [
            [_p('Materia', s['th']), _p('Carrera', s['th']),
             _p('Plan', s['th']), _p('Año', s['th']), _p('Período', s['th'])],
            [
                _p(solicitud.nombre_curso, s['td']),
                _p(solicitud.carrera.nombre if solicitud.carrera else '', s['td']),
                _p(solicitud.plan_estudio.codigo if solicitud.plan_estudio else '', s['td']),
                _p(solicitud.anno_carrera or '', s['td']),
                _p(solicitud.get_periodo_display() if solicitud.periodo else '', s['td']),
            ],
        ],
        col_widths=[w * 0.28, w * 0.28, w * 0.14, w * 0.10, w * 0.20],
        extra_cmds=[('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)],
    ))

    # ── II — Equipo Docente ─────────────────────────────────────────────────────
    E.append(Spacer(1, 0.5 * cm))
    E.append(_sec_titulo('II - Equipo Docente', s))

    filas_ii = [[
        _p('Docente', s['th']),
        _p('Función', s['th']),
        _p('Cargo', s['th']),
        _p('Dedicación', s['th']),
    ]]
    for m in solicitud.equipo_docente.all():
        filas_ii.append([
            _p(m.nombre, s['td']),
            _p(m.get_funcion_display(), s['td']),
            _p(m.get_cargo_display() if m.cargo else '', s['td']),
            _p(m.get_dedicacion_display() if m.dedicacion else '', s['td']),
        ])
    if len(filas_ii) == 1:
        filas_ii.append([_p('', s['td'])] * 4)

    E.append(_tabla(
        filas_ii,
        col_widths=[w * 0.40, w * 0.28, w * 0.16, w * 0.16],
        extra_cmds=[('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)],
    ))

    # ── III — Características del Curso ────────────────────────────────────────
    E.append(Spacer(1, 0.5 * cm))
    E.append(_sec_titulo('III - Características del Curso', s))

    total_hs = solicitud.total_horas_semanales
    cant_hs  = solicitud.cantidad_semanas * total_hs

    # Tabla 1: Crédito Horario Semanal
    cw_hs = [w * 0.17, w * 0.13, w * 0.18, w * 0.35, w * 0.17]
    E.append(_tabla(
        [
            [_p('Crédito Horario Semanal', s['th_c']), '', '', '', ''],
            [
                _p('Teórico/Práctico', s['th_c']),
                _p('Teóricas', s['th_c']),
                _p('Prácticas de Aula', s['th_c']),
                _p('Práct. de lab/ camp/\nResid/ PIP, etc.', s['th_c']),
                _p('Total', s['th_c']),
            ],
            [
                _p('Hs', s['td_c']),
                _p(f'{solicitud.hs_teoricas} Hs', s['td_c']),
                _p(f'{solicitud.hs_practicas_aula} Hs', s['td_c']),
                _p(f'{solicitud.hs_lab_campo} Hs', s['td_c']),
                _p(f'{total_hs} Hs', s['td_c']),
            ],
        ],
        col_widths=cw_hs,
        extra_cmds=[
            ('SPAN', (0, 0), (4, 0)),
            ('BACKGROUND', (0, 0), (4, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (4, 1), colors.lightgrey),
        ],
    ))

    E.append(Spacer(1, 0.3 * cm))

    # Tabla 2: Tipificación / Período
    E.append(_tabla(
        [
            [_p('Tipificación', s['th_c']), _p('Período', s['th_c'])],
            [
                _p(solicitud.get_modalidad_cursado_display() if solicitud.modalidad_cursado else '', s['td']),
                _p(solicitud.get_periodo_display() if solicitud.periodo else '', s['td']),
            ],
        ],
        col_widths=[w * 0.50, w * 0.50],
        extra_cmds=[('BACKGROUND', (0, 0), (1, 0), colors.lightgrey)],
    ))

    E.append(Spacer(1, 0.3 * cm))

    # Tabla 3: Duración
    E.append(_tabla(
        [
            [_p('Duración', s['th_c']), '', '', ''],
            [
                _p('Desde', s['th_c']),
                _p('Hasta', s['th_c']),
                _p('Cantidad de Semanas', s['th_c']),
                _p('Cantidad de Horas', s['th_c']),
            ],
            [
                _p(solicitud.fecha_inicio.strftime('%d/%m/%Y'), s['td_c']),
                _p(solicitud.fecha_hasta.strftime('%d/%m/%Y'), s['td_c']),
                _p(str(solicitud.cantidad_semanas), s['td_c']),
                _p(str(cant_hs), s['td_c']),
            ],
        ],
        col_widths=[w * 0.25, w * 0.25, w * 0.25, w * 0.25],
        extra_cmds=[
            ('SPAN', (0, 0), (3, 0)),
            ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (3, 1), colors.lightgrey),
        ],
    ))

    # ── IV–XIV — Secciones de texto ─────────────────────────────────────────────
    def sec(num, titulo, texto):
        E.append(Spacer(1, 0.5 * cm))
        E.append(_sec_titulo(f'{num} - {titulo}', s))
        E.append(_caja(texto, s))

    sec('IV', 'Fundamentación', solicitud.fundamentacion)
    sec('V', 'Objetivos / Resultados de Aprendizaje', solicitud.objetivos)

    E.append(Spacer(1, 0.5 * cm))
    E.append(_sec_titulo('VI - Contenidos', s))
    cont_vi = ''
    if solicitud.contenidos_minimos:
        cont_vi += 'Contenidos Mínimos \n' + solicitud.contenidos_minimos + '\n\n'
    cont_vi += solicitud.unidades
    E.append(_caja(cont_vi, s))

    sec('VII', 'Plan de Trabajos Prácticos', solicitud.plan_trabajos_practicos or '')
    sec('VIII', 'Regimen de Aprobación', solicitud.regimen_aprobacion)
    sec('IX', 'Bibliografía Básica', solicitud.bibliografia_basica)
    sec('X', 'Bibliografia Complementaria', solicitud.bibliografia_complementaria or '')
    sec('XI', 'Resumen de Objetivos', solicitud.resumen_objetivos or '')
    sec('XII', 'Resumen del Programa', solicitud.resumen_programa or '')
    sec('XIII', 'Imprevistos', solicitud.imprevistos or '')
    sec('XIV', 'Otros', solicitud.contacto_otros or '')

    # ── ELEVACIÓN y APROBACIÓN ──────────────────────────────────────────────────
    E.append(PageBreak())

    ROW_H = 1.8 * cm
    E.append(_tabla(
        [
            [_p('ELEVACIÓN y APROBACIÓN DE ESTE PROGRAMA', s['th_c']), ''],
            ['', _p('Profesor Responsable', s['th_c'])],
            [_p('Firma:', s['td']), ''],
            [_p('Aclaración:', s['td']), ''],
            [_p('Fecha:', s['td']), ''],
        ],
        col_widths=[w * 0.30, w * 0.70],
        extra_cmds=[
            ('SPAN', (0, 0), (1, 0)),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (1, 1), 'CENTER'),
            ('BACKGROUND', (0, 0), (1, 0), colors.lightgrey),
            ('ROWHEIGHT', (0, 2), (-1, -1), ROW_H),
        ],
    ))

    doc.build(E, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buffer.seek(0)
    return buffer
