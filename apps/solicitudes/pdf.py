import os
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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


# ── Estilos ────────────────────────────────────────────────────────────────────
def _s():
    base = getSampleStyleSheet()
    return {
        'inst_bold': ParagraphStyle(
            'InstBold', parent=base['Normal'],
            fontName='Times-Bold', fontSize=11,
            alignment=TA_CENTER, leading=15, spaceAfter=0,
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
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'escudo.gif')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.8 * cm, height=2.8 * cm)
        logo.hAlign = 'CENTER'
        E.append(logo)
        E.append(Spacer(1, 0.15 * cm))

    for linea in [
        'Ministerio de Cultura y Educación',
        'Universidad Nacional de San Luis',
        'Facultad de Ciencias Físico Matemáticas y Naturales',
        f'Departamento: {(solicitud.usuario.departamento if solicitud.usuario else None) or solicitud.departamento_docente or "—"}',
    ]:
        E.append(Paragraph(linea, s['inst_bold']))

    if solicitud.area:
        E.append(Paragraph(f'Area: {solicitud.area}', s['inst_bold']))

    E.append(Spacer(1, 0.4 * cm))

    # ── I — Oferta Académica ────────────────────────────────────────────────────
    E.append(Paragraph('I - Oferta Académica', s['sec_titulo']))
    w = CONTENT_W
    E.append(_tabla(
        [
            [_p('Materia', s['th']), _p('Carrera', s['th']),
             _p('Plan', s['th']), _p('Año', s['th']), _p('Período', s['th'])],
            [
                _p(solicitud.nombre_curso, s['td']),
                _p(solicitud.carrera or '', s['td']),
                _p(solicitud.plan_estudio or '', s['td']),
                _p(solicitud.anno_carrera or '', s['td']),
                _p(solicitud.get_periodo_display() if solicitud.periodo else '', s['td']),
            ],
        ],
        col_widths=[w * 0.28, w * 0.28, w * 0.14, w * 0.10, w * 0.20],
    ))

    # ── II — Equipo Docente ─────────────────────────────────────────────────────
    E.append(Spacer(1, 0.5 * cm))
    E.append(Paragraph('II - Equipo Docente', s['sec_titulo']))

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

    E.append(_tabla(filas_ii, col_widths=[w * 0.40, w * 0.28, w * 0.16, w * 0.16]))

    # ── III — Características del Curso ────────────────────────────────────────
    E.append(Spacer(1, 0.5 * cm))
    E.append(Paragraph('III - Características del Curso', s['sec_titulo']))

    total_hs = solicitud.total_horas_semanales

    # Crédito Horario Semanal (tabla con fila de título fusionada)
    E.append(_tabla(
        [
            # fila fusionada: título
            [_p('Credito Horario Semanal', s['th_c']), '', '', '', ''],
            # cabeceras de columnas
            [
                _p('Teórico/Práctico', s['th_c']),
                _p('Teóricas', s['th_c']),
                _p('Prácticas de Aula', s['th_c']),
                _p('Práct. de lab/ camp/ Resid/ PIP, etc.', s['th_c']),
                _p('Total', s['th_c']),
            ],
            # datos
            [
                _p('Hs', s['td_c']),
                _p(f'{solicitud.hs_teoricas} Hs', s['td_c']),
                _p(f'{solicitud.hs_practicas_aula} Hs', s['td_c']),
                _p(f'{solicitud.hs_lab_campo} Hs', s['td_c']),
                _p(f'{total_hs} Hs', s['td_c']),
            ],
        ],
        col_widths=[w * 0.18, w * 0.14, w * 0.20, w * 0.34, w * 0.14],
        extra_cmds=[
            ('SPAN', (0, 0), (4, 0)),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ],
    ))

    E.append(Spacer(1, 0.15 * cm))

    # Tipificación | Periodo
    E.append(_tabla(
        [
            [_p('Tipificación', s['th_c']), _p('Periodo', s['th_c'])],
            [
                _p(solicitud.get_tipificacion_display() if solicitud.tipificacion else '', s['td']),
                _p(solicitud.get_periodo_display() if solicitud.periodo else '', s['td']),
            ],
        ],
        col_widths=[w * 0.50, w * 0.50],
        extra_cmds=[('ALIGN', (0, 0), (-1, 0), 'CENTER')],
    ))

    E.append(Spacer(1, 0.15 * cm))

    # Duración
    cant_hs = solicitud.cantidad_semanas * total_hs
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
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ],
    ))

    # ── IV — Fundamentación ─────────────────────────────────────────────────────
    def sec(num, titulo, texto):
        E.append(Spacer(1, 0.5 * cm))
        E.append(Paragraph(f'{num} - {titulo}', s['sec_titulo']))
        E.append(_caja(texto, s))

    sec('IV', 'Fundamentación', solicitud.fundamentacion)

    # ── V — Objetivos ───────────────────────────────────────────────────────────
    sec('V', 'Objetivos / Resultados de Aprendizaje', solicitud.objetivos)

    # ── VI — Contenidos ─────────────────────────────────────────────────────────
    E.append(Spacer(1, 0.5 * cm))
    E.append(Paragraph('VI - Contenidos', s['sec_titulo']))
    cont_vi = ''
    if solicitud.contenidos_minimos:
        cont_vi += 'Contenidos Mínimos \n' + solicitud.contenidos_minimos + '\n\n'
    cont_vi += solicitud.unidades
    E.append(_caja(cont_vi, s))

    # ── VII — Plan de Trabajos Prácticos ────────────────────────────────────────
    sec('VII', 'Plan de Trabajos Prácticos', solicitud.plan_trabajos_practicos or '')

    # ── VIII — Régimen de Aprobación ────────────────────────────────────────────
    sec('VIII', 'Regimen de Aprobación', solicitud.regimen_aprobacion)

    # ── IX — Bibliografía Básica ────────────────────────────────────────────────
    sec('IX', 'Bibliografía Básica', solicitud.bibliografia_basica)

    # ── X — Bibliografía Complementaria ────────────────────────────────────────
    sec('X', 'Bibliografia Complementaria', solicitud.bibliografia_complementaria or '')

    # ── XI — Resumen de Objetivos ───────────────────────────────────────────────
    sec('XI', 'Resumen de Objetivos', solicitud.resumen_objetivos or '')

    # ── XII — Resumen del Programa ──────────────────────────────────────────────
    sec('XII', 'Resumen del Programa', solicitud.resumen_programa or '')

    # ── XIII — Imprevistos ──────────────────────────────────────────────────────
    sec('XIII', 'Imprevistos', solicitud.imprevistos or '')

    # ── XIV — Otros ─────────────────────────────────────────────────────────────
    sec('XIV', 'Otros', solicitud.contacto_otros or '')

    # ── ELEVACIÓN y APROBACIÓN ──────────────────────────────────────────────────
    E.append(PageBreak())

    ROW_H = 1.8 * cm
    E.append(_tabla(
        [
            # fila 0: título fusionado
            [_p('ELEVACIÓN y APROBACIÓN DE ESTE PROGRAMA', s['th_c']), ''],
            # fila 1: col derecha "Profesor Responsable"
            ['', _p('Profesor Responsable', s['th_c'])],
            # filas de firma
            [_p('Firma:', s['td']), ''],
            [_p('Aclaración:', s['td']), ''],
            [_p('Fecha:', s['td']), ''],
        ],
        col_widths=[w * 0.30, w * 0.70],
        extra_cmds=[
            ('SPAN', (0, 0), (1, 0)),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (1, 1), 'CENTER'),
            ('ROWHEIGHT', (0, 2), (-1, -1), ROW_H),
        ],
    ))

    doc.build(E, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buffer.seek(0)
    return buffer
