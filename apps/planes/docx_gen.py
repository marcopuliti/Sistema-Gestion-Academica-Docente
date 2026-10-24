import datetime
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]
DIAS = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes'}

COLOR_AZUL     = '1A3A5C'
COLOR_AMARILLO = 'FFF3CD'
COLOR_GRIS     = 'F0F4F8'
COLOR_BLANCO   = 'FFFFFF'


def _set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def _cell_margins(cell, top=60, bottom=60, left=80, right=80):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for side, val in (('top', top), ('bottom', bottom), ('left', left), ('right', right)):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:w'), str(val))
        el.set(qn('w:type'), 'dxa')
        tcMar.append(el)
    tcPr.append(tcMar)


def _write_cell(cell, texto, bold=False, italic=False, size=9, color=None, center=False):
    cell.text = ''
    para = cell.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    run = para.add_run(str(texto) if texto else '—')
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    _cell_margins(cell)


def _p(doc_or_para, text, size=11, bold=False, italic=False, align=None):
    if hasattr(doc_or_para, 'add_paragraph'):
        para = doc_or_para.add_paragraph()
    else:
        para = doc_or_para
    run = para.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if align:
        para.alignment = align
    return para


def _diffs(t_dir, t_adm):
    if t_adm is None:
        return {k: True for k in ('presidente', 'vocal_1', 'vocal_2', 'dia', 'hora', 'modalidad')}
    return {
        'presidente': (t_dir.presidente_nombre != t_adm.presidente_nombre or
                       t_dir.presidente_dni != t_adm.presidente_dni),
        'vocal_1':    (t_dir.vocal_1_nombre != t_adm.vocal_1_nombre or
                       t_dir.vocal_1_dni != t_adm.vocal_1_dni),
        'vocal_2':    (t_dir.vocal_2_nombre != t_adm.vocal_2_nombre or
                       t_dir.vocal_2_dni != t_adm.vocal_2_dni),
        'dia':        t_dir.dia_semana != t_adm.dia_semana,
        'hora':       t_dir.hora != t_adm.hora,
        'modalidad':  t_dir.permite_libres != t_adm.permite_libres,
    }


def _add_tribunal_table(doc, mep, t_dir, t_adm):
    diff = _diffs(t_dir, t_adm)
    dia_str      = DIAS.get(t_dir.dia_semana, '—') if t_dir.dia_semana else '—'
    hora_str     = t_dir.hora.strftime('%H:%M') if t_dir.hora else '—'
    modalidad    = 'Libres y regulares' if t_dir.permite_libres else 'Solo regulares'
    hdr_text     = (
        f"{mep.materia.nombre} ({mep.materia.codigo}) — "
        f"Plan {mep.plan.codigo} — {mep.plan.carrera.nombre} — {mep.ano}° año"
    )

    # 3 columns: Campo | Nombre/Valor | DNI
    tbl = doc.add_table(rows=0, cols=3)
    tbl.style = 'Table Grid'
    col_widths = [Cm(3), Cm(10.5), Cm(3)]

    def set_widths(row):
        for i, w in enumerate(col_widths):
            row.cells[i].width = w

    # ── Header row ──
    hdr_row = tbl.add_row()
    set_widths(hdr_row)
    merged = hdr_row.cells[0].merge(hdr_row.cells[2])
    _set_cell_bg(merged, COLOR_AZUL)
    _write_cell(merged, hdr_text, bold=True, size=9, color='FFFFFF')

    # ── Sub-header ──
    sub_row = tbl.add_row()
    set_widths(sub_row)
    _set_cell_bg(sub_row.cells[0], COLOR_GRIS)
    _set_cell_bg(sub_row.cells[1], COLOR_GRIS)
    _set_cell_bg(sub_row.cells[2], COLOR_GRIS)
    _write_cell(sub_row.cells[0], 'Campo',  bold=True, size=9)
    _write_cell(sub_row.cells[1], 'Nombre', bold=True, size=9)
    _write_cell(sub_row.cells[2], 'DNI',    bold=True, size=9)

    # ── Data rows ──
    data = [
        ('presidente', 'Presidente', t_dir.presidente_nombre, t_dir.presidente_dni),
        ('vocal_1',    '1er. Vocal', t_dir.vocal_1_nombre,    t_dir.vocal_1_dni),
        ('vocal_2',    '2do. Vocal', t_dir.vocal_2_nombre,    t_dir.vocal_2_dni),
        ('dia',        'Día',        dia_str,                  ''),
        ('hora',       'Hora',       hora_str,                 ''),
        ('modalidad',  'Modalidad',  modalidad,                ''),
    ]
    for key, label, val1, val2 in data:
        row = tbl.add_row()
        set_widths(row)
        bg = COLOR_AMARILLO if diff[key] else COLOR_BLANCO
        for c in row.cells:
            _set_cell_bg(c, bg)
        _write_cell(row.cells[0], label, bold=True, size=9)
        _write_cell(row.cells[1], val1, size=9)
        if val2:
            _write_cell(row.cells[2], val2, size=9)
        else:
            merged_cell = row.cells[1].merge(row.cells[2])
            _set_cell_bg(merged_cell, bg)
            _write_cell(merged_cell, val1, size=9)

    doc.add_paragraph()


def generar_docx_solicitud_cambio(director, admin, meps, item_map, current_map):
    doc = Document()

    # Márgenes
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.5)

    hoy = datetime.date.today()
    fecha_str = f"San Luis, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

    # ── Carta ──
    p_fecha = _p(doc, fecha_str, size=11)
    p_fecha.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_paragraph()

    admin_nombre = admin.get_full_name() if admin else 'Secretario Académico'
    _p(doc, f"Sr. Secretario Académico de la FCFMyN", bold=True)
    _p(doc, admin_nombre)
    _p(doc, "S / D:")
    doc.add_paragraph()

    n = len([m for m in meps if item_map.get(m.id)])
    cuerpo = (
        f"Me dirijo a Ud., y por su intermedio a quien corresponda, para solicitar "
        f"la modificación de {n} Tribunal{'es' if n != 1 else ''} "
        f"Examinador{'es' if n != 1 else ''} para mesas de examen del Ciclo Lectivo "
        f"{hoy.year} de las materias del Departamento de {director.departamento}. "
        f"Las celdas resaltadas en amarillo indican los campos propuestos a modificar "
        f"respecto a los valores actuales."
    )
    p_cuerpo = _p(doc, cuerpo)
    p_cuerpo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph()
    _p(doc, "Sin otro particular, saludo a Ud. con atenta consideración.")
    doc.add_paragraph()
    doc.add_paragraph()

    firma = (
        f"{director.get_full_name()}\n"
        f"Director del Departamento de {director.departamento}\n"
        f"F.C.F.M.yN."
    )
    _p(doc, firma)

    # ── Salto de página + listado ──
    doc.add_page_break()

    titulo = f"Solicitud de Cambio de Tribunales — Dpto. {director.departamento} — {hoy.year}"
    _p(doc, titulo, size=12, bold=True)
    doc.add_paragraph()

    for mep in meps:
        t_dir = item_map.get(mep.id)
        if not t_dir:
            continue
        t_adm = current_map.get(mep.id)
        _add_tribunal_table(doc, mep, t_dir, t_adm)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ── Informe cuatrimestral de comisiones ──────────────────────────────────────

def _add_comision_table(doc, c):
    optativa = ' — Optativa' if c.es_optativa_bolsa else ''
    planes = ', '.join(f'Plan {pl.codigo}' for pl in c.planes.all()) or '—'
    credito = f'{c.credito_horario} hs' if c.credito_horario else '—'
    equipo = list(c.equipo.all())

    table = doc.add_table(rows=4 + max(len(equipo), 1), cols=5)
    table.style = 'Table Grid'

    hdr = table.rows[0].cells[0].merge(table.rows[0].cells[4])
    _write_cell(
        hdr, f'{c.nombre_materia} ({c.codigo_materia}){optativa} — {c.carrera.nombre} — {c.get_cuatrimestre_display()}',
        bold=True, color=COLOR_BLANCO,
    )
    _set_cell_bg(hdr, COLOR_AZUL)

    r = table.rows[1].cells
    _write_cell(r[0], 'Planes', bold=True)
    _write_cell(r[1].merge(r[4]), planes)
    r = table.rows[2].cells
    _write_cell(r[0], 'Condición', bold=True)
    _write_cell(r[1], c.get_condicion_display() or '—')
    _write_cell(r[2], 'Crédito horario', bold=True)
    _write_cell(r[3].merge(r[4]), credito)

    for cell, texto in zip(table.rows[3].cells, ('Apellido y nombre', 'DNI', 'Función', 'Cargo', 'Dedicación')):
        _write_cell(cell, texto, bold=True, size=8)
        _set_cell_bg(cell, COLOR_GRIS)

    if equipo:
        for row, m in zip(table.rows[4:], equipo):
            valores = (m.nombre, m.dni, m.get_funcion_display(), m.get_cargo_display(), m.get_dedicacion_display())
            for cell, texto in zip(row.cells, valores):
                _write_cell(cell, texto or '—')
    else:
        _write_cell(table.rows[4].cells[0].merge(table.rows[4].cells[4]), 'Sin equipo docente cargado', italic=True)
    doc.add_paragraph()


def generar_docx_informe_comisiones(departamento, director, admin, solicitud, comisiones):
    from .pdf import texto_periodo_informe

    doc = Document()
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Cm(2.5)
        section.left_margin = section.right_margin = Cm(2.5)

    hoy = datetime.date.today()
    p_fecha = _p(doc, f"San Luis, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}", size=11)
    p_fecha.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph()

    admin_nombre = admin.get_full_name() if admin else 'Secretario Académico'
    _p(doc, "Sr. Secretario Académico de la FCFMyN", bold=True)
    _p(doc, admin_nombre)
    _p(doc, "S / D:")
    doc.add_paragraph()

    n = len(comisiones)
    p_cuerpo = _p(doc, (
        f"Me dirijo a Ud., y por su intermedio a quien corresponda, para elevar el informe de "
        f"comisiones del {texto_periodo_informe(solicitud)} de las materias del Departamento de "
        f"{departamento}, que comprende {n} {'comisiones' if n != 1 else 'comisión'} con su "
        f"condición de cursada, crédito horario, planes de estudio asociados y equipo docente."
    ))
    p_cuerpo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    doc.add_paragraph()
    _p(doc, "Sin otro particular, saludo a Ud. con atenta consideración.")
    doc.add_paragraph()
    doc.add_paragraph()
    nombre_director = director.get_full_name() if director else ''
    _p(doc, f"{nombre_director}\nDirector del Departamento de {departamento}\nF.C.F.M.yN.")

    doc.add_page_break()
    _p(doc, f"Informe de Comisiones — Dpto. {departamento} — {solicitud.get_cuatrimestre_display()} {solicitud.anio}",
       size=12, bold=True)
    doc.add_paragraph()
    for c in comisiones:
        _add_comision_table(doc, c)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
