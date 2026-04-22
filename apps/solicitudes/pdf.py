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


def _caja(texto, s, content_w=None):
    """Sección de texto libre dentro de un recuadro con borde."""
    w = content_w if content_w is not None else CONTENT_W
    t = Table([[_p(texto or '', s['caja'])]], colWidths=[w])
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
                _p(f'{solicitud.hs_teorico_practico} Hs', s['td_c']),
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


# ── Nota de Comisión (Secretario Académico) ────────────────────────────────────
def generar_pdf_nota_comision(solicitud):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=3 * cm, leftMargin=3 * cm,
        topMargin=2.5 * cm, bottomMargin=2.5 * cm,
    )
    s = _s()
    base = getSampleStyleSheet()

    nota = ParagraphStyle('Nota2', parent=base['Normal'],
                          fontName='Times-Roman', fontSize=12, leading=18)
    nota_right = ParagraphStyle('Nota2R', parent=nota, alignment=TA_RIGHT)

    E = []

    # Destinatario
    for linea in [
        'Secretario/a Académico/a',
        'Fac. Cs. Físico Matemáticas y Naturales',
    ]:
        E.append(Paragraph(linea, nota))
    E.append(Spacer(1, 0.6 * cm))

    # Cuerpo
    E.append(Paragraph('De mi mayor consideración:', nota))
    E.append(Spacer(1, 0.3 * cm))

    periodo_txt = solicitud.get_periodo_display() if solicitud.periodo else '—'
    anno = solicitud.fecha_inicio.year if solicitud.fecha_inicio else '—'
    cuerpo = (
        f'Me dirijo a Ud., a fin de enviarle la comisión de la materia '
        f'<b>{solicitud.nombre_curso}</b> del {periodo_txt} del año {anno}.'
    )
    E.append(Paragraph(cuerpo, nota))
    E.append(Spacer(1, 0.3 * cm))
    E.append(Paragraph('Sin otro particular, me despido de Ud. muy atentamente.', nota))
    E.append(Spacer(1, 0.5 * cm))

    # Tabla de comisión  (7 columnas: Materia | Función | Nombre | Periodo | Condición | Crédito | Plan)
    w = PAGE_W - 6 * cm  # ancho útil con márgenes de 3cm
    cw = [w * 0.18, w * 0.20, w * 0.18, w * 0.11, w * 0.11, w * 0.11, w * 0.11]

    dpto = (solicitud.usuario.departamento if solicitud.usuario else None) \
        or solicitud.departamento_docente or '—'
    plan_txt = solicitud.plan_estudio.codigo if solicitud.plan_estudio else '—'
    credito_txt = f'{solicitud.cantidad_semanas * solicitud.total_horas_semanales} hs'
    condicion_txt = solicitud.get_condicion_display() if solicitud.condicion else '—'

    miembros = list(solicitud.equipo_docente.all())
    n = max(len(miembros), 1)
    # índices de filas: 0=dept, 1=col-headers, 2=sub-headers, 3..3+n-1=datos
    R0, R1, R2, R3 = 0, 1, 2, 3
    last_data = R3 + n - 1

    # Fila 0: "Departamento de ..." (abarca las 7 columnas)
    filas = [
        [_p(f'Departamento de {dpto}', s['th_c']), '', '', '', '', '', ''],
    ]
    # Fila 1: headers — "Comisión" abarca cols 1-2; las otras cols se fusionarán con fila 2
    filas.append([
        _p('Materia',          s['th_c']),
        _p('Comisión',         s['th_c']),
        _p('',                 s['th_c']),
        _p('Periodo',          s['th_c']),
        _p('Condición',        s['th_c']),
        _p('Crédito\nHorario', s['th_c']),
        _p('Plan de\nEstudio', s['th_c']),
    ])
    # Fila 2: sub-headers de Comisión + valores de las cols 3-6
    filas.append([
        _p('',           s['th_c']),
        _p('Función',    s['th_c']),
        _p('Nombre',     s['th_c']),
        _p(periodo_txt,   s['td_c']),
        _p(condicion_txt, s['td_c']),
        _p(credito_txt,   s['td_c']),
        _p(plan_txt,      s['td_c']),
    ])

    # Filas de datos: solo cols 0-2; cols 3-6 están fusionadas desde fila 2
    for i, m in enumerate(miembros):
        if i == 0:
            mat_cell = _p(solicitud.nombre_curso, s['td_c'])
        elif i == 1:
            codigo = f'Código: {solicitud.codigo_materia}' if solicitud.codigo_materia else 'Código: _______________'
            mat_cell = _p(codigo, s['td'])
        else:
            mat_cell = _p('', s['td'])
        nombre_dni = m.nombre + (f'\nDNI: {m.dni}' if m.dni else '')
        filas.append([
            mat_cell,
            _p(m.get_funcion_display(), s['td']),
            _p(nombre_dni, s['td']),
            _p('', s['td_c']),
            _p('', s['td_c']),
            _p('', s['td_c']),
            _p('', s['td_c']),
        ])

    cmds_extra = [
        # Fila 0: dept
        ('SPAN',       (0, R0), (6, R0)),
        ('BACKGROUND', (0, R0), (6, R0), colors.lightgrey),
        ('ALIGN',      (0, R0), (6, R0), 'CENTER'),
        # Fila 1: headers — "Comisión" fusiona cols 1-2; col 0 fusiona con fila 2
        ('SPAN',       (1, R1), (2, R1)),
        ('BACKGROUND', (0, R1), (6, R1), colors.lightgrey),
        ('SPAN',       (0, R1), (0, R2)),
        # Fila 2: sub-headers de Comisión
        ('BACKGROUND', (0, R2), (2, R2), colors.lightgrey),
        # Cols 3-6: el valor ocupa fila 2 + todas las filas de datos (header queda en fila 1)
        ('SPAN',       (3, R2), (3, last_data)),
        ('SPAN',       (4, R2), (4, last_data)),
        ('SPAN',       (5, R2), (5, last_data)),
        ('SPAN',       (6, R2), (6, last_data)),
        ('VALIGN',     (3, R2), (6, last_data), 'MIDDLE'),
        ('ALIGN',      (3, R2), (6, last_data), 'CENTER'),
    ]

    t = Table(filas, colWidths=cw)
    t.setStyle(TableStyle(list(_TABLA_BASE) + cmds_extra))
    E.append(t)
    E.append(Spacer(1, 0.8 * cm))

    # Firma del departamento
    linea_firma = Table([['']], colWidths=[6 * cm])
    linea_firma.setStyle(TableStyle([('LINEABOVE', (0, 0), (0, 0), 0.5, NEGRO)]))
    linea_firma.hAlign = 'LEFT'
    E.append(linea_firma)
    E.append(Paragraph(f'Departamento de {dpto}', nota))

    doc.build(E, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buffer.seek(0)
    return buffer


# ── Nota de Elevación ──────────────────────────────────────────────────────────
def generar_pdf_nota_elevacion(solicitud):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=3 * cm, leftMargin=3 * cm,
        topMargin=2.5 * cm, bottomMargin=2.5 * cm,
    )
    s = _s()
    base = getSampleStyleSheet()

    nota = ParagraphStyle(
        'Nota', parent=base['Normal'],
        fontName='Times-Roman', fontSize=12, leading=18, spaceAfter=0,
    )
    nota_bold = ParagraphStyle(
        'NotaBold', parent=nota, fontName='Times-Bold',
    )
    nota_right = ParagraphStyle(
        'NotaRight', parent=nota, alignment=TA_RIGHT,
    )
    nota_center = ParagraphStyle(
        'NotaCenter', parent=nota, alignment=TA_CENTER,
    )

    E = []

    # Encabezado institucional
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'escudo.gif')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.2 * cm, height=2.2 * cm)
        logo.hAlign = 'CENTER'
        E.append(logo)
        E.append(Spacer(1, 0.2 * cm))

    for linea in [
        'Universidad Nacional de San Luis',
        'Facultad de Ciencias Físico Matemáticas y Naturales',
    ]:
        E.append(Paragraph(linea, nota_center))
    E.append(Spacer(1, 0.8 * cm))

    # Lugar y fecha
    fecha = solicitud.fecha_creacion.strftime('%d de %B de %Y').replace(
        'January', 'enero').replace('February', 'febrero').replace(
        'March', 'marzo').replace('April', 'abril').replace(
        'May', 'mayo').replace('June', 'junio').replace(
        'July', 'julio').replace('August', 'agosto').replace(
        'September', 'septiembre').replace('October', 'octubre').replace(
        'November', 'noviembre').replace('December', 'diciembre')
    E.append(Paragraph(f'San Luis, {fecha}', nota_right))
    E.append(Spacer(1, 0.8 * cm))

    # Destinatario
    for linea in [
        'Señor/a Secretario/a Académico/a',
        'Facultad de Ciencias Físico Matemáticas y Naturales',
        'S / D',
    ]:
        E.append(Paragraph(linea, nota))
    E.append(Spacer(1, 0.8 * cm))

    # Saludo inicial
    E.append(Paragraph('De mi mayor consideración:', nota))
    E.append(Spacer(1, 0.5 * cm))

    # Cuerpo
    carrera_txt = solicitud.carrera.nombre if solicitud.carrera else '(carrera)'
    plan_txt = solicitud.plan_estudio.codigo if solicitud.plan_estudio else ''
    plan_ref = f', Plan {plan_txt}' if plan_txt else ''
    nombre_curso = solicitud.nombre_curso or '(denominación del curso)'

    cuerpo = (
        f'Tengo el agrado de dirigirme a Ud. a fin de solicitar se <b>protocolice</b> '
        f'el curso optativo de la carrera de <b>{carrera_txt}</b>{plan_ref}, '
        f'denominado <b>"{nombre_curso}"</b>, cuyo programa adjunto a la presente.'
    )
    E.append(Paragraph(cuerpo, nota))
    E.append(Spacer(1, 0.5 * cm))

    # Despedida
    E.append(Paragraph('Sin otro particular, saludo a Ud. muy atentamente.', nota))
    E.append(Spacer(1, 2.0 * cm))

    # Firma
    responsable = None
    for m in solicitud.equipo_docente.filter(funcion='responsable'):
        responsable = m
        break
    if responsable is None:
        for m in solicitud.equipo_docente.all():
            responsable = m
            break

    nombre_resp = responsable.nombre if responsable else solicitud.get_nombre_docente
    cargo_resp = responsable.get_cargo_display() if (responsable and responsable.cargo) else ''

    ancho_firma = 8 * cm
    linea_firma = Table(
        [['']],
        colWidths=[ancho_firma],
    )
    linea_firma.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 0.5, NEGRO),
    ]))
    linea_firma.hAlign = 'LEFT'
    E.append(linea_firma)
    E.append(Paragraph(nombre_resp or '', nota))
    if cargo_resp:
        E.append(Paragraph(cargo_resp, nota))
    E.append(Paragraph('Profesor/a Responsable', nota))

    doc.build(E)
    buffer.seek(0)
    return buffer


# ── Documento completo: Nota de Elevación + Programa ──────────────────────────
def generar_pdf_solicitud_completa(solicitud):
    """Nota de elevación (página 1) seguida del programa completo."""
    COMB_MARGIN = 3 * cm
    cw = PAGE_W - 2 * COMB_MARGIN

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=COMB_MARGIN, leftMargin=COMB_MARGIN,
        topMargin=2.5 * cm, bottomMargin=2.5 * cm,
    )
    s = _s()
    base = getSampleStyleSheet()
    E = []

    # ── PÁGINA 1: NOTA DE ELEVACIÓN ────────────────────────────────────────────
    nota = ParagraphStyle(
        'NotaC', parent=base['Normal'],
        fontName='Times-Roman', fontSize=12, leading=18, spaceAfter=0,
    )
    nota_right = ParagraphStyle('NotaCRight', parent=nota, alignment=TA_RIGHT)
    nota_center = ParagraphStyle('NotaCCenter', parent=nota, alignment=TA_CENTER)

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'escudo.gif')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.2 * cm, height=2.2 * cm)
        logo.hAlign = 'CENTER'
        E.append(logo)
        E.append(Spacer(1, 0.2 * cm))

    for linea in [
        'Universidad Nacional de San Luis',
        'Facultad de Ciencias Físico Matemáticas y Naturales',
    ]:
        E.append(Paragraph(linea, nota_center))
    E.append(Spacer(1, 0.8 * cm))

    fecha = solicitud.fecha_creacion.strftime('%d de %B de %Y').replace(
        'January', 'enero').replace('February', 'febrero').replace(
        'March', 'marzo').replace('April', 'abril').replace(
        'May', 'mayo').replace('June', 'junio').replace(
        'July', 'julio').replace('August', 'agosto').replace(
        'September', 'septiembre').replace('October', 'octubre').replace(
        'November', 'noviembre').replace('December', 'diciembre')
    E.append(Paragraph(f'San Luis, {fecha}', nota_right))
    E.append(Spacer(1, 0.8 * cm))

    for linea in [
        'Señor/a Secretario/a Académico/a',
        'Facultad de Ciencias Físico Matemáticas y Naturales',
        'S / D',
    ]:
        E.append(Paragraph(linea, nota))
    E.append(Spacer(1, 0.8 * cm))

    E.append(Paragraph('De mi mayor consideración:', nota))
    E.append(Spacer(1, 0.5 * cm))

    carrera_txt = solicitud.carrera.nombre if solicitud.carrera else '(carrera)'
    plan_txt = solicitud.plan_estudio.codigo if solicitud.plan_estudio else ''
    plan_ref = f', Plan {plan_txt}' if plan_txt else ''
    nombre_curso = solicitud.nombre_curso or '(denominación del curso)'

    cuerpo = (
        f'Tengo el agrado de dirigirme a Ud. a fin de solicitar se <b>protocolice</b> '
        f'el curso optativo de la carrera de <b>{carrera_txt}</b>{plan_ref}, '
        f'denominado <b>"{nombre_curso}"</b>, cuyo programa adjunto a la presente.'
    )
    E.append(Paragraph(cuerpo, nota))
    E.append(Spacer(1, 0.5 * cm))
    E.append(Paragraph('Sin otro particular, saludo a Ud. muy atentamente.', nota))
    E.append(Spacer(1, 2.0 * cm))

    responsable = None
    for m in solicitud.equipo_docente.filter(funcion='responsable'):
        responsable = m
        break
    if responsable is None:
        for m in solicitud.equipo_docente.all():
            responsable = m
            break

    nombre_resp = responsable.nombre if responsable else solicitud.get_nombre_docente
    cargo_resp = responsable.get_cargo_display() if (responsable and responsable.cargo) else ''

    lf = Table([['']], colWidths=[8 * cm])
    lf.setStyle(TableStyle([('LINEABOVE', (0, 0), (0, 0), 0.5, NEGRO)]))
    lf.hAlign = 'LEFT'
    E.append(lf)
    E.append(Paragraph(nombre_resp or '', nota))
    if cargo_resp:
        E.append(Paragraph(cargo_resp, nota))
    E.append(Paragraph('Profesor/a Responsable', nota))

    # ── SALTO DE PÁGINA → PROGRAMA ─────────────────────────────────────────────
    E.append(PageBreak())

    # ── ENCABEZADO DEL PROGRAMA ────────────────────────────────────────────────
    year = solicitud.fecha_inicio.year
    estado_txt = ESTADO_LABEL.get(solicitud.estado, solicitud.estado)
    fecha_pres = solicitud.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')

    left_items = []
    if os.path.exists(logo_path):
        logo2 = Image(logo_path, width=2.8 * cm, height=2.8 * cm)
        logo2.hAlign = 'CENTER'
        left_items.append(logo2)
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
        colWidths=[cw * 0.62, cw * 0.38],
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
        col_widths=[cw * 0.28, cw * 0.28, cw * 0.14, cw * 0.10, cw * 0.20],
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
        col_widths=[cw * 0.40, cw * 0.28, cw * 0.16, cw * 0.16],
        extra_cmds=[('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)],
    ))

    # ── III — Características del Curso ────────────────────────────────────────
    E.append(Spacer(1, 0.5 * cm))
    E.append(_sec_titulo('III - Características del Curso', s))

    total_hs = solicitud.total_horas_semanales
    cant_hs  = solicitud.cantidad_semanas * total_hs

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
                _p(f'{solicitud.hs_teorico_practico} Hs', s['td_c']),
                _p(f'{solicitud.hs_teoricas} Hs', s['td_c']),
                _p(f'{solicitud.hs_practicas_aula} Hs', s['td_c']),
                _p(f'{solicitud.hs_lab_campo} Hs', s['td_c']),
                _p(f'{total_hs} Hs', s['td_c']),
            ],
        ],
        col_widths=[cw * 0.17, cw * 0.13, cw * 0.18, cw * 0.35, cw * 0.17],
        extra_cmds=[
            ('SPAN', (0, 0), (4, 0)),
            ('BACKGROUND', (0, 0), (4, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (4, 1), colors.lightgrey),
        ],
    ))
    E.append(Spacer(1, 0.3 * cm))

    E.append(_tabla(
        [
            [_p('Tipificación', s['th_c']), _p('Período', s['th_c'])],
            [
                _p(solicitud.get_modalidad_cursado_display() if solicitud.modalidad_cursado else '', s['td']),
                _p(solicitud.get_periodo_display() if solicitud.periodo else '', s['td']),
            ],
        ],
        col_widths=[cw * 0.50, cw * 0.50],
        extra_cmds=[('BACKGROUND', (0, 0), (1, 0), colors.lightgrey)],
    ))
    E.append(Spacer(1, 0.3 * cm))

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
        col_widths=[cw * 0.25, cw * 0.25, cw * 0.25, cw * 0.25],
        extra_cmds=[
            ('SPAN', (0, 0), (3, 0)),
            ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (3, 1), colors.lightgrey),
        ],
    ))

    def sec(num, titulo, texto):
        E.append(Spacer(1, 0.5 * cm))
        E.append(_sec_titulo(f'{num} - {titulo}', s))
        E.append(_caja(texto, s, content_w=cw))

    sec('IV', 'Fundamentación', solicitud.fundamentacion)
    sec('V', 'Objetivos / Resultados de Aprendizaje', solicitud.objetivos)

    E.append(Spacer(1, 0.5 * cm))
    E.append(_sec_titulo('VI - Contenidos', s))
    cont_vi = ''
    if solicitud.contenidos_minimos:
        cont_vi += 'Contenidos Mínimos \n' + solicitud.contenidos_minimos + '\n\n'
    cont_vi += solicitud.unidades
    E.append(_caja(cont_vi, s, content_w=cw))

    sec('VII', 'Plan de Trabajos Prácticos', solicitud.plan_trabajos_practicos or '')
    sec('VIII', 'Regimen de Aprobación', solicitud.regimen_aprobacion)
    sec('IX', 'Bibliografía Básica', solicitud.bibliografia_basica)
    sec('X', 'Bibliografia Complementaria', solicitud.bibliografia_complementaria or '')
    sec('XI', 'Resumen de Objetivos', solicitud.resumen_objetivos or '')
    sec('XII', 'Resumen del Programa', solicitud.resumen_programa or '')
    sec('XIII', 'Imprevistos', solicitud.imprevistos or '')
    sec('XIV', 'Otros', solicitud.contacto_otros or '')

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
        col_widths=[cw * 0.30, cw * 0.70],
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
