import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

PAGE_W, PAGE_H = A4
MARGIN_H = 2.5 * cm
MARGIN_V = 2.5 * cm
CONTENT_W = PAGE_W - 2 * MARGIN_H

AZUL = colors.HexColor('#1a3a5c')
AMARILLO = colors.HexColor('#FFF3CD')
GRIS = colors.HexColor('#f0f4f8')

MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

DIAS = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes'}

CUATRIMESTRE_LABEL = {1: 'primer cuatrimestre', 2: 'segundo cuatrimestre', 3: 'anual'}


def _styles():
    base = getSampleStyleSheet()
    return {
        'fecha': ParagraphStyle('fecha', parent=base['Normal'],
            fontName='Times-Roman', fontSize=11,
            alignment=TA_RIGHT, leading=14),
        'dest': ParagraphStyle('dest', parent=base['Normal'],
            fontName='Times-Roman', fontSize=11,
            alignment=TA_LEFT, leading=18),
        'cuerpo': ParagraphStyle('cuerpo', parent=base['Normal'],
            fontName='Times-Roman', fontSize=11,
            alignment=TA_JUSTIFY, leading=18, firstLineIndent=1.2 * cm),
        'firma': ParagraphStyle('firma', parent=base['Normal'],
            fontName='Times-Roman', fontSize=11,
            alignment=TA_RIGHT, leading=18),
        'titulo_seccion': ParagraphStyle('tit_sec', parent=base['Normal'],
            fontName='Times-Bold', fontSize=12,
            alignment=TA_CENTER, leading=16, spaceAfter=10),
        'mat_hdr': ParagraphStyle('mat_hdr', parent=base['Normal'],
            fontName='Times-Bold', fontSize=9,
            leading=12, textColor=colors.white),
        'subhdr': ParagraphStyle('subhdr', parent=base['Normal'],
            fontName='Times-Bold', fontSize=8,
            leading=11, textColor=colors.HexColor('#333333')),
        'campo': ParagraphStyle('campo', parent=base['Normal'],
            fontName='Times-Bold', fontSize=9, leading=12),
        'valor': ParagraphStyle('valor', parent=base['Normal'],
            fontName='Times-Roman', fontSize=9, leading=12),
    }


def _diffs(t_dir, t_adm):
    if t_adm is None:
        return {
            'presidente': bool(t_dir.presidente_nombre or t_dir.presidente_dni),
            'vocal_1':    bool(t_dir.vocal_1_nombre    or t_dir.vocal_1_dni),
            'vocal_2':    bool(t_dir.vocal_2_nombre    or t_dir.vocal_2_dni),
            'dia':        bool(t_dir.dia_semana),
            'hora':       bool(t_dir.hora),
            'modalidad':  True,
        }
    return {
        'presidente': (t_dir.presidente_nombre != t_adm.presidente_nombre
                       or t_dir.presidente_dni != t_adm.presidente_dni),
        'vocal_1': (t_dir.vocal_1_nombre != t_adm.vocal_1_nombre
                    or t_dir.vocal_1_dni != t_adm.vocal_1_dni),
        'vocal_2': (t_dir.vocal_2_nombre != t_adm.vocal_2_nombre
                    or t_dir.vocal_2_dni != t_adm.vocal_2_dni),
        'dia':      t_dir.dia_semana != t_adm.dia_semana,
        'hora':     t_dir.hora != t_adm.hora,
        'modalidad': t_dir.permite_libres != t_adm.permite_libres,
    }


def _tribunal_table(mep, t_dir, t_adm, s):
    diff = _diffs(t_dir, t_adm)

    dia_str = DIAS.get(t_dir.dia_semana, '—') if t_dir.dia_semana else '—'
    hora_str = t_dir.hora.strftime('%H:%M') if t_dir.hora else '—'
    modalidad_str = 'Libres y regulares' if t_dir.permite_libres else 'Solo regulares'

    hdr_text = (
        f"{mep.materia.nombre} ({mep.materia.codigo}) — "
        f"Plan {mep.plan.codigo} — {mep.plan.carrera.nombre} — {mep.ano}° año"
    )

    C1 = 2.8 * cm
    C2 = CONTENT_W - C1 - 2.8 * cm
    C3 = 2.8 * cm
    col_widths = [C1, C2, C3]

    def p(text, style):
        return Paragraph(text or '—', style)

    rows = [
        # header spanning all cols
        [p(hdr_text, s['mat_hdr']), '', ''],
        # subheader
        [p('Campo', s['subhdr']), p('Nombre', s['subhdr']), p('DNI', s['subhdr'])],
        # data rows
        [p('Presidente', s['campo']),
         p(t_dir.presidente_nombre, s['valor']),
         p(t_dir.presidente_dni, s['valor'])],
        [p('1er. Vocal', s['campo']),
         p(t_dir.vocal_1_nombre, s['valor']),
         p(t_dir.vocal_1_dni, s['valor'])],
        [p('2do. Vocal', s['campo']),
         p(t_dir.vocal_2_nombre, s['valor']),
         p(t_dir.vocal_2_dni, s['valor'])],
        [p('Día', s['campo']),
         p(dia_str, s['valor']),
         ''],
        [p('Hora', s['campo']),
         p(hora_str, s['valor']),
         ''],
        [p('Modalidad', s['campo']),
         p(modalidad_str, s['valor']),
         ''],
    ]

    style_cmds = [
        # header row
        ('SPAN', (0, 0), (2, 0)),
        ('BACKGROUND', (0, 0), (2, 0), AZUL),
        # subheader
        ('BACKGROUND', (0, 1), (2, 1), GRIS),
        # span value cells for día, hora and modalidad
        ('SPAN', (1, 5), (2, 5)),
        ('SPAN', (1, 6), (2, 6)),
        ('SPAN', (1, 7), (2, 7)),
        # borders
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#cccccc')),
        # padding
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]

    # Yellow for changed rows (rows 2–7 = data rows)
    row_map = [
        ('presidente', 2),
        ('vocal_1', 3),
        ('vocal_2', 4),
        ('dia', 5),
        ('hora', 6),
        ('modalidad', 7),
    ]
    for key, row_idx in row_map:
        if diff[key]:
            style_cmds.append(('BACKGROUND', (0, row_idx), (2, row_idx), AMARILLO))

    tbl = Table(rows, colWidths=col_widths, repeatRows=0)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _build_pdf(director, admin, meps, dir_map, adm_map, cuerpo_carta, titulo_listado):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_H,
        rightMargin=MARGIN_H,
        topMargin=MARGIN_V,
        bottomMargin=MARGIN_V,
    )
    s = _styles()
    story = []

    hoy = datetime.date.today()
    fecha_str = f"San Luis, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

    story.append(Paragraph(fecha_str, s['fecha']))
    story.append(Spacer(1, 0.9 * cm))

    admin_nombre = admin.get_full_name() if admin else 'Secretario Académico'
    story.append(Paragraph(
        f"Sr. Secretario Académico de la FCFMyN<br/>{admin_nombre}<br/>S / D:",
        s['dest'],
    ))
    story.append(Spacer(1, 0.7 * cm))
    story.append(Paragraph(cuerpo_carta, s['cuerpo']))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Sin otro particular, saludo a Ud. con atenta consideración.", s['cuerpo']))
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(
        f"{director.get_full_name()}<br/>"
        f"Director del Departamento<br/>"
        f"de {director.departamento}<br/>"
        f"F.C.F.M.yN.",
        s['firma'],
    ))

    story.append(PageBreak())
    story.append(Paragraph(titulo_listado, s['titulo_seccion']))
    story.append(Spacer(1, 0.3 * cm))

    for mep in meps:
        t_dir = dir_map.get(mep.id)
        if not t_dir:
            continue
        t_adm = adm_map.get(mep.id)
        story.append(_tribunal_table(mep, t_dir, t_adm, s))
        story.append(Spacer(1, 0.35 * cm))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generar_pdf_informe_tribunales(director, admin, meps, dir_map, adm_map):
    hoy = datetime.date.today()
    cuerpo = (
        f"Me dirijo a Ud., y por su intermedio a quien corresponda, para elevar "
        f"el listado de Tribunales Examinadores para mesas de examen del Ciclo "
        f"Lectivo {hoy.year} de las materias del Departamento de "
        f"{director.departamento}, informando los cambios y agregados realizados "
        f"a los mismos."
    )
    titulo = f"Listado de Tribunales Examinadores — Dpto. {director.departamento} — Ciclo {hoy.year}"
    return _build_pdf(director, admin, meps, dir_map, adm_map, cuerpo, titulo)


def generar_pdf_solicitud_cambio(director, admin, meps, item_map, current_map):
    """PDF de solicitud de cambio: item_map contiene los valores propuestos,
    current_map contiene el TribunalExaminador actual (baseline para diffs)."""
    hoy = datetime.date.today()
    n = len([m for m in meps if item_map.get(m.id)])
    cuerpo = (
        f"Me dirijo a Ud., y por su intermedio a quien corresponda, para solicitar "
        f"la modificación de {n} Tribunal{'es' if n != 1 else ''} "
        f"Examinador{'es' if n != 1 else ''} para mesas de examen del Ciclo Lectivo "
        f"{hoy.year} de las materias del Departamento de {director.departamento}. "
        f"Las celdas resaltadas en amarillo indican los campos propuestos a modificar "
        f"respecto a los valores actuales."
    )
    titulo = f"Solicitud de Cambio de Tribunales — Dpto. {director.departamento} — {hoy.year}"
    return _build_pdf(director, admin, meps, item_map, current_map, cuerpo, titulo)


def generar_pdf_solicitud_servicio(solicitud, admin_user, items):
    """
    Genera la nota formal de solicitud de dictado por servicio.
    items: lista de SolicitudServicioItem con select_related cargado.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN_H, rightMargin=MARGIN_H,
        topMargin=MARGIN_V, bottomMargin=MARGIN_V,
    )
    s = _styles()
    story = []

    from collections import defaultdict, OrderedDict

    es_externo = solicitud.departamento_dictante == 'Externo'
    director = solicitud.director
    if director:
        firma_txt = (
            f"{director.get_full_name()}<br/>"
            f"Director del Departamento<br/>"
            f"de {solicitud.departamento_solicitante}<br/>"
            f"F.C.F.M.yN."
        )
    else:
        firma_txt = f"Director del Departamento de {solicitud.departamento_solicitante}<br/>F.C.F.M.yN."

    _cuat_item = {1: '1° Cuatrimestre', 2: '2° Cuatrimestre', 3: 'Anual'}

    # Agrupar items por destinatario (preservando orden de aparición)
    por_destinatario = OrderedDict()
    for it in items:
        dest = it.destinatario or solicitud.dictante_externo_nombre or ''
        por_destinatario.setdefault(dest, []).append(it)

    admin_nombre = admin_user.get_full_name() if admin_user else 'Secretario Académico'

    hoy = datetime.date.today()
    fecha_str = f"San Luis, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

    first = True
    for dest, dest_items in por_destinatario.items():
        if not first:
            story.append(PageBreak())
        first = False

        story.append(Paragraph(fecha_str, s['fecha']))
        story.append(Spacer(1, 0.9 * cm))

        if dest:
            story.append(Paragraph(f"{dest}<br/>S / D:", s['dest']))
        else:
            story.append(Paragraph(
                f"Sr. Secretario Académico de la FCFMyN<br/>{admin_nombre}<br/>S / D:",
                s['dest'],
            ))
        story.append(Spacer(1, 0.7 * cm))

        # Agrupar por (carrera, plan) dentro de este destinatario
        grupos = defaultdict(list)
        for it in dest_items:
            mep = it.fila
            key = (mep.plan.carrera.nombre, mep.plan.codigo, mep.plan_id)
            grupos[key].append(it)

        for (carrera_nombre, plan_codigo, _), grupo_items in sorted(grupos.items()):
            if es_externo:
                intro = (
                    f"Me dirijo a Ud. a fin de solicitar el dictado de las siguientes asignaturas "
                    f"de la carrera {carrera_nombre} plan {plan_codigo}."
                )
            else:
                intro = (
                    f"Me dirijo a Ud., y por su intermedio a quien corresponda, a fin de solicitar se disponga "
                    f"el dictado por servicio de las siguientes asignaturas de la carrera "
                    f"{carrera_nombre} plan {plan_codigo}."
                )
            story.append(Paragraph(intro, s['cuerpo']))
            story.append(Spacer(1, 0.3 * cm))

            for it in sorted(
                grupo_items,
                key=lambda x: (x.fila.cuatrimestre, x.fila.materia.nombre),
            ):
                mep = it.fila
                cuat_label = _cuat_item.get(mep.cuatrimestre, '')
                optativa = ' — Optativa' if getattr(mep, 'es_optativa_bolsa', False) else ''
                linea = f"{mep.materia.nombre}{optativa} ({cuat_label}) – Crédito horario total: {it.hs_totales} hs"
                story.append(Paragraph(linea, ParagraphStyle(
                    'item_servicio', parent=s['cuerpo'],
                    firstLineIndent=0, leftIndent=2 * cm,
                )))
            story.append(Spacer(1, 0.4 * cm))

        story.append(Paragraph("Sin otro particular, saludo a Ud. con atenta consideración.", s['cuerpo']))
        story.append(Spacer(1, 2 * cm))
        story.append(Paragraph(firma_txt, s['firma']))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ── Informe cuatrimestral de comisiones ──────────────────────────────────────
# Las tablas replican el formato de las notas de "Comisiones de Cursada" de los departamentos:
# encabezado "DEPARTAMENTO DE …", columnas MATERIA | COMISIÓN (rol + docente) | PERIODO |
# CONDICIÓN | CRÉDITO HORARIO | PLAN DE ESTUDIOS, y páginas apaisadas.

FUNCION_ABREVIADA = {
    'prof_responsable': 'Prof. Resp.',
    'prof_colaborador': 'Prof. Colab.',
    'resp_practico':    'Resp. T.P',
    'aux_practico':     'Aux. Práctico',
    'aux_laboratorio':  'Aux. Lab',
}
PERIODO_ABREVIADO = {1: '1° Cuat.', 2: '2° Cuat.', 3: 'ANUAL'}
FILAS_MINIMAS_COMISION = 5


def texto_periodo_informe(solicitud):
    if solicitud.cuatrimestre == 1:
        return f'1° cuatrimestre y materias anuales del Ciclo Lectivo {solicitud.anio}'
    return f'2° cuatrimestre del Ciclo Lectivo {solicitud.anio}'


def datos_tabla_comision(c):
    """Contenido de la tabla de una comisión, compartido por el PDF y el DOCX."""
    nombre = f'Optat. ({c.nombre_materia})' if c.es_optativa_bolsa else c.nombre_materia
    equipo = [
        (FUNCION_ABREVIADA.get(m.funcion, m.get_funcion_display()),
         f'{m.nombre} DNI {m.dni}' if m.dni else m.nombre)
        for m in c.equipo.all()
    ]
    filas = max(FILAS_MINIMAS_COMISION, len(equipo))
    materia = [nombre, f'Cod. ({c.codigo_materia})', c.carrera.nombre]
    return {
        'materia': materia + [''] * (filas - len(materia)),
        'equipo': equipo + [('', '')] * (filas - len(equipo)),
        'periodo': PERIODO_ABREVIADO.get(c.cuatrimestre, ''),
        'condicion': c.get_condicion_display(),
        'credito': f'{c.credito_horario} hs' if c.credito_horario else '',
        'plan': ' '.join(p.codigo for p in sorted(c.planes.all(), key=lambda p: p.codigo)),
    }


# Proporciones de columnas de la nota original
_COLS_COMISION = (0.185, 0.095, 0.355, 0.087, 0.098, 0.087, 0.093)


def _comision_table(c, departamento, ancho):
    base = getSampleStyleSheet()['Normal']
    def st(nombre, **kw):
        return ParagraphStyle(nombre, parent=base, **{
            'fontName': 'Helvetica', 'fontSize': 7.5, 'leading': 9, 'alignment': TA_CENTER, **kw,
        })
    s_titulo = st('c_tit', fontName='Helvetica-Bold', fontSize=8)
    s_hdr = st('c_hdr', fontName='Helvetica-Bold', fontSize=8)
    s_hdr2 = st('c_hdr2', fontSize=7)
    s_txt = st('c_txt')
    s_rol = st('c_rol', alignment=TA_LEFT, fontSize=8)
    s_carrera = st('c_car', fontName='Helvetica-Bold')
    # Las celdas vacías llevan un espacio para conservar el alto de fila de la nota original
    p = lambda texto, estilo: Paragraph(texto or '&nbsp;', estilo)

    d = datos_tabla_comision(c)
    rows = [
        [p(f'DEPARTAMENTO DE {departamento.upper()}', s_titulo), '', '', '', '', '', ''],
        [p('MATERIA', s_hdr), p('COMISIÓN', s_hdr), '', p('PERIODO', s_hdr2), p('CONDICIÓN', s_hdr2),
         p('CRÉDITO<br/>HORARIO', s_hdr2), p('PLAN DE<br/>ESTUDIOS', s_hdr2)],
    ]
    for i, (materia, (rol, docente)) in enumerate(zip(d['materia'], d['equipo'])):
        rows.append([
            p(materia, s_carrera if i == 2 else s_txt), p(rol, s_rol), p(docente, s_txt),
            p(d['periodo'], s_txt) if i == 0 else '',
            p(d['condicion'], s_txt) if i == 0 else '',
            p(d['credito'], s_txt) if i == 0 else '',
            p(d['plan'], s_txt) if i == 0 else '',
        ])
    ultima = len(rows) - 1
    estilo = [
        ('SPAN', (0, 0), (6, 0)),
        ('SPAN', (1, 1), (2, 1)),
        *[('SPAN', (col, 2), (col, ultima)) for col in range(3, 7)],
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, 0), 1.2, colors.black),
        ('BOX', (0, 1), (-1, ultima), 1.2, colors.black),
        ('LINEAFTER', (2, 1), (2, ultima), 1, colors.black),
        ('LINEAFTER', (5, 1), (5, ultima), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    tbl = Table(rows, colWidths=[ancho * f for f in _COLS_COMISION])
    tbl.setStyle(TableStyle(estilo))
    return tbl


def generar_pdf_informe_comisiones(departamento, director, admin, solicitud, comisiones):
    from reportlab.lib.pagesizes import landscape
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageTemplate

    buffer = BytesIO()
    apaisada = landscape(A4)
    doc = BaseDocTemplate(buffer, pagesize=A4)
    doc.addPageTemplates([
        PageTemplate(id='carta', pagesize=A4, frames=[
            Frame(MARGIN_H, MARGIN_V, PAGE_W - 2 * MARGIN_H, PAGE_H - 2 * MARGIN_V, id='f_carta'),
        ]),
        PageTemplate(id='tablas', pagesize=apaisada, frames=[
            Frame(2 * cm, 1.5 * cm, apaisada[0] - 4 * cm, apaisada[1] - 3 * cm, id='f_tablas'),
        ]),
    ])
    s = _styles()
    story = []

    hoy = datetime.date.today()
    story.append(Paragraph(f"San Luis, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}", s['fecha']))
    story.append(Spacer(1, 0.9 * cm))
    admin_nombre = admin.get_full_name() if admin else 'Secretario Académico'
    story.append(Paragraph(f"Sr. Secretario Académico de la FCFMyN<br/>{admin_nombre}<br/>S / D:", s['dest']))
    story.append(Spacer(1, 0.7 * cm))
    n = len(comisiones)
    story.append(Paragraph(
        f"Me dirijo a Ud., y por su intermedio a quien corresponda, para elevar el informe de "
        f"comisiones del {texto_periodo_informe(solicitud)} de las materias del Departamento de "
        f"{departamento}, que comprende {n} {'comisiones' if n != 1 else 'comisión'} con su "
        f"condición de cursada, crédito horario, planes de estudio asociados y equipo docente.",
        s['cuerpo'],
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Sin otro particular, saludo a Ud. con atenta consideración.", s['cuerpo']))
    story.append(Spacer(1, 2 * cm))
    nombre_director = director.get_full_name() if director else ''
    story.append(Paragraph(
        f"{nombre_director}<br/>Director del Departamento<br/>de {departamento}<br/>F.C.F.M.yN.",
        s['firma'],
    ))

    story.append(NextPageTemplate('tablas'))
    story.append(PageBreak())
    ancho = 23 * cm
    for c in comisiones:
        story.append(KeepTogether([_comision_table(c, departamento, ancho), Spacer(1, 0.6 * cm)]))

    doc.build(story)
    buffer.seek(0)
    return buffer
