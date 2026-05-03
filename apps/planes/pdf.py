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
        # Sin baseline externo: resaltar todo campo con datos (es todo nuevo)
        return {
            'presidente': bool(t_dir.presidente_nombre or t_dir.presidente_dni),
            'vocal_1':    bool(t_dir.vocal_1_nombre    or t_dir.vocal_1_dni),
            'vocal_2':    bool(t_dir.vocal_2_nombre    or t_dir.vocal_2_dni),
            'dia_hora':   bool(t_dir.dia_semana        or t_dir.hora),
            'modalidad':  True,
        }
    return {
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
        [p('Día y hora', s['campo']),
         p(f'{dia_str} {hora_str}', s['valor']),
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
        # span dia/hora and modalidad value cells
        ('SPAN', (1, 5), (2, 5)),
        ('SPAN', (1, 6), (2, 6)),
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

    # Yellow for changed rows (rows 2–6 = data rows)
    row_map = [
        ('presidente', 2),
        ('vocal_1', 3),
        ('vocal_2', 4),
        ('dia_hora', 5),
        ('modalidad', 6),
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


def generar_pdf_modificaciones_tribunales(director, admin, meps, dir_map, adm_map):
    hoy = datetime.date.today()
    n = len([m for m in meps if dir_map.get(m.id)])
    cuerpo = (
        f"Me dirijo a Ud., y por su intermedio a quien corresponda, para informar "
        f"las modificaciones realizadas a {n} Tribunal{'es' if n != 1 else ''} "
        f"Examinador{'es' if n != 1 else ''} para mesas de examen del Ciclo Lectivo "
        f"{hoy.year} de las materias del Departamento de {director.departamento}. "
        f"Las celdas resaltadas en amarillo indican los campos modificados respecto "
        f"a los datos registrados en el sistema externo."
    )
    titulo = f"Modificaciones a Tribunales Examinadores — Dpto. {director.departamento} — {hoy.year}"
    return _build_pdf(director, admin, meps, dir_map, adm_map, cuerpo, titulo)
