"""
Carga los tribunales examinadores del Departamento de Matemática
correspondientes a los días Martes, Miércoles, Jueves y Viernes.

pendiente_sincronizacion queda en False (ya sincronizado).
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.planes.models import MateriaEnPlan, TribunalExaminador, TribunalAdmin

LUNES     = 1
MARTES    = 2
MIERCOLES = 3
JUEVES    = 4
VIERNES   = 5
H8 = datetime.time(8, 0)
H9 = datetime.time(9, 0)

# Tribunales uniformes: mismo tribunal para todos los planes de esa materia.
# (codigo_materia, pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni, dia, hora, libres)
UNIFORMES = [
    # ── Martes ───────────────────────────────────────────────────────────────
    ('03MA00879',   'SPEDALETTI Juan',           '27932507', 'NEME Pablo A.',            '27376238', 'PASTINE Adrian G.',       '33219586', MARTES,    H8, True),
    ('03MA04002',   'ALLENDES',                  '25092120', 'GALDEANO Patricia',        '16984428', 'SOSA',                    '25166655', MARTES,    H8, True),
    ('03MA04001',   'PEPA RISMA Eliana',         '30345610', 'GALDEANO Patricia',        '16984428', 'AMIEVA RODRIGUEZ',        '35767014', MARTES,    H8, False),
    ('03MA00020',   'CORTES NICOLAS E.',         '27496755', 'JUAREZ',                   '32515074', 'BARROZO M. Fernanda',     '27698232', MARTES,    H8, True),
    ('03MA00528',   'BARROZO M. Fernanda',       '27698232', 'CORTES NICOLAS E.',        '27496755', 'JUAREZ',                  '32515074', MARTES,    H8, True),
    # ── Miércoles ────────────────────────────────────────────────────────────
    ('03MA00074',   'PASTINE Adrian G.',         '33219586', 'MANASERO Paola',           '33153111', 'GARCIA ALVAREZ Pablo',    '34488931', MIERCOLES, H8, True),
    ('03MA04005',   'ARRIBILLAGA Pablo R.',      '30896847', 'BARROZO M. Fernanda',      '27698232', 'GALDEANO Patricia',       '16984428', MIERCOLES, H8, True),
    ('03MA00532',   'ALCALA',                    '22445295', 'PASTINE Adrian G.',        '33219586', 'NEME Pablo A.',           '27376238', MIERCOLES, H8, True),
    ('03MA00531',   'PEPA RISMA Luciana',        '30345609', 'MOLINA MUNAFO Gonzalo',    '31717035', 'GALDEANO Patricia',       '16984428', MIERCOLES, H8, True),
    ('03MA00533',   'MOLINA MUNAFO Gonzalo',     '31717035', 'JAUME Daniel A.',          '22693282', 'ALCALA',                  '22445295', MIERCOLES, H8, True),
    ('03MA04000',   'JAUME Daniel A.',           '22693282', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'PEPA RISMA Eliana',       '30345610', MIERCOLES, H8, True),
    ('03MA00883',   'LORENZO',                   '26082377', 'FAVIER Sergio Jose',       '14888081', 'BENAVENTE Ana',           '22011871', MIERCOLES, H8, False),
    ('03MA00885',   'MARTINEZ Federico',         '27624328', 'ARRIBILLAGA Pablo R.',     '30896847', 'SILVA Analia',            '29668948', MIERCOLES, H8, True),
    ('03MA04003',   'RANZUGLIA',                 '17088918', 'GALDEANO Patricia',        '16984428', 'BARROZO M. Fernanda',     '27698232', MIERCOLES, H8, True),
    ('03MA04034',   'RIDOLFI Claudia',           '25259776', 'PEPA RISMA Eliana',        '30345610', 'ALCALA',                  '22445295', MIERCOLES, H8, True),
    ('03MA04006',   'CHIARANI',                  '17123160', 'GALDEANO Patricia',        '16984428', 'BARROZO M. Fernanda',     '27698232', MIERCOLES, H8, True),
    ('16001MA0003', 'ZAKOWICZ Maria I.',         '17949441', 'GARCIARENA',              '',          'PENNA',                   '',         LUNES,     H8, False),
    # ── Jueves ───────────────────────────────────────────────────────────────
    ('03MA00878',   'NEME Pablo A.',             '27376238', 'GARCIA ALVAREZ Pablo',     '34488931', 'SOTA Rodrigo',            '23547481', JUEVES,    H8, True),
    ('03MA00886',   'FAVIER Sergio Jose',        '14888081', 'BENAVENTE Ana',            '22011871', 'LORENZO',                 '26082377', JUEVES,    H8, True),
    ('03MA04007',   'AMIEVA RODRIGUEZ',          '35767014', 'BARROZO M. Fernanda',      '27698232', 'CORTES NICOLAS E.',       '27496755', JUEVES,    H9, False),
    ('16001MA0002', 'BORTOLUSSI Noelia Belen',   '',         'ZAKOWICZ Maria I.',        '17949441', 'GALDEANO Patricia',       '16984428', JUEVES,    H8, False),
    # ── Viernes ──────────────────────────────────────────────────────────────
    ('03MA04004',   'RANZUGLIA',                 '17088918', 'GALDEANO Patricia',        '16984428', 'BARROZO M. Fernanda',     '27698232', VIERNES,   H8, False),
    ('03MA04036',   'RIDOLFI Claudia',           '25259776', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'ALCALA',                  '22445295', VIERNES,   H8, True),
]

# Álgebra II (03MA00158): tribunal varía según el plan. Siempre Martes 08:00, libres=True.
# {plan_codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni)}
ALGEBRA_II_POR_PLAN = {
    '12/13': ('GUIÑAZU',          '35766976', 'PANELO Cristian',        '32915835', 'MOLINA MUNAFO Gonzalo', '31717035'),
    '12/15': ('GUIÑAZU',          '35766976', 'PANELO Cristian',        '32915835', 'MOLINA MUNAFO Gonzalo', '31717035'),
    '16/13': ('GUIÑAZU',          '35766976', 'PANELO Cristian',        '32915835', 'MOLINA MUNAFO Gonzalo', '31717035'),
    '5/13':  ('GUIÑAZU',          '35766976', 'PANELO Cristian',        '32915835', 'MOLINA MUNAFO Gonzalo', '31717035'),
    '15/13': ('GUIÑAZU',          '35766976', 'PANELO Cristian',        '32915835', 'MOLINA MUNAFO Gonzalo', '31717035'),
    '9/13':  ('GUIÑAZU',          '35766976', 'PANELO Cristian',        '32915835', 'MOLINA MUNAFO Gonzalo', '31717035'),
    '13/08': ('FAVIER Sergio Jose', '14888081', 'SILVA Analia',         '29668948', 'LORENZO',               '26082377'),
    '26/12': ('FAVIER Sergio Jose', '14888081', 'SILVA Analia',         '29668948', 'LORENZO',               '26082377'),
    '28/12': ('FAVIER Sergio Jose', '14888081', 'SILVA Analia',         '29668948', 'LORENZO',               '26082377'),
}

# Álgebra I (03MA00016): tribunal varía según el plan. Siempre Martes 08:00, libres=True.
# {plan_codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni)}
ALGEBRA_I_POR_PLAN = {
    '13/08': ('MANASERO Paola', '33153111', 'GARCIA ALVAREZ Pablo',   '34488931', 'RIDOLFI Claudia',      '25259776'),
    '2/25':  ('MANASERO Paola', '33153111', 'GARCIA ALVAREZ Pablo',   '34488931', 'RIDOLFI Claudia',      '25259776'),
    '26/12': ('MANASERO Paola', '33153111', 'GARCIA ALVAREZ Pablo',   '34488931', 'RIDOLFI Claudia',      '25259776'),
    '28/12': ('MANASERO Paola', '33153111', 'GARCIA ALVAREZ Pablo',   '34488931', 'RIDOLFI Claudia',      '25259776'),
    '32/12': ('MANASERO Paola', '33153111', 'GARCIA ALVAREZ Pablo',   '34488931', 'RIDOLFI Claudia',      '25259776'),
    '09/17': ('JUAREZ',         '32515074', 'MANASERO Paola',         '33153111', 'GARCIA ALVAREZ Pablo', '34488931'),
    '12/14': ('JUAREZ',         '32515074', 'MANASERO Paola',         '33153111', 'PASTINE Adrian G.',    '33219586'),
    '21/13': ('JUAREZ',         '32515074', 'MANASERO Paola',         '33153111', 'PASTINE Adrian G.',    '33219586'),
    '15/06': ('JUAREZ',         '32515074', 'MANASERO Paola',         '33153111', 'PASTINE Adrian G.',    '33219586'),
    '16/06': ('JUAREZ',         '32515074', 'MANASERO Paola',         '33153111', 'PASTINE Adrian G.',    '33219586'),
}

# Cálculo II (03MA00004): tribunal varía según el plan. Siempre Miércoles 08:00, libres=True.
# {plan_codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni)}
CALCULO_II_POR_PLAN = {
    '6/15':  ('MARTINEZ Federico', '27624328', 'JUAREZ',             '32515074', 'PEPA RISMA Luciana',  '30345609'),
    '13/08': ('MARTINEZ Federico', '27624328', 'JUAREZ',             '32515074', 'PEPA RISMA Luciana',  '30345609'),
    '28/12': ('MARTINEZ Federico', '27624328', 'JUAREZ',             '32515074', 'PEPA RISMA Luciana',  '30345609'),
    '26/12': ('MARTINEZ Federico', '27624328', 'JUAREZ',             '32515074', 'PEPA RISMA Luciana',  '30345609'),
    '15/06': ('JUAREZ',            '32515074', 'MARTINEZ Federico',  '27624328', 'SILVA Analia',        '29668948'),
    '16/06': ('JUAREZ',            '32515074', 'SILVA Analia',       '29668948', 'MARTINEZ Federico',   '27624328'),
    '09/17': ('JUAREZ',            '32515074', 'SILVA Analia',       '29668948', 'MARTINEZ Federico',   '27624328'),
    '12/14': ('JUAREZ',            '32515074', 'SILVA Analia',       '29668948', 'MARTINEZ Federico',   '27624328'),
    '21/13': ('JUAREZ',            '32515074', 'SILVA Analia',       '29668948', 'MARTINEZ Federico',   '27624328'),
}

# Cálculo III (03MA00010): tribunal varía según el plan. Siempre Miércoles 08:00, libres=True.
# {plan_codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni)}
CALCULO_III_POR_PLAN = {
    '28/12': ('PEPA RISMA Eliana',   '30345610', 'PEPA RISMA Luciana', '30345609', 'ALCALA',             '22445295'),
    '2/25':  ('PEPA RISMA Eliana',   '30345610', 'PEPA RISMA Luciana', '30345609', 'ALCALA',             '22445295'),
    '32/12': ('ALCALA',              '22445295', 'PEPA RISMA Eliana',  '30345610', 'PEPA RISMA Luciana', '30345609'),
    '13/08': ('RIDOLFI Claudia',     '25259776', 'PEPA RISMA Luciana', '30345609', 'ALCALA',             '22445295'),
    '5/09':  ('ALCALA',              '22445295', 'PEPA RISMA Eliana',  '30345610', 'RIDOLFI Claudia',    '25259776'),
    '09/17': ('ALCALA',              '22445295', 'PEPA RISMA Eliana',  '30345610', 'PEPA RISMA Luciana', '30345609'),
    '12/14': ('ALCALA',              '22445295', 'RIDOLFI Claudia',    '25259776', 'PEPA RISMA Eliana',  '30345610'),
    '21/13': ('ALCALA',              '22445295', 'RIDOLFI Claudia',    '25259776', 'PEPA RISMA Eliana',  '30345610'),
    '16/06': ('ALCALA',              '22445295', 'PEPA RISMA Eliana',  '30345610', 'RIDOLFI Claudia',    '25259776'),
    '15/06': ('ALCALA',              '22445295', 'PEPA RISMA Luciana', '30345609', 'RIDOLFI Claudia',    '25259776'),
}

# Seminario (03MA00024): tribunal varía según el plan. Siempre Miércoles 08:00, libres=True.
# {plan_codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni)}
SEMINARIO_POR_PLAN = {
    '09/17': ('LORENZO',             '26082377', 'BENAVENTE Ana',        '22011871', 'BARROZO M. Fernanda', '27698232'),
    '21/13': ('BARROZO M. Fernanda', '27698232', 'ARRIBILLAGA Pablo R.', '30896847', 'ORTIZ ROMINA E.',     '33428098'),
}

# Matemática Aplicada (03MA00009): tribunal y día varían según el plan. Hora 08:00, libres=True.
# {plan_codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni, dia)}
MAT_APLICADA_POR_PLAN = {
    '15/06': ('FAVIER Sergio Jose', '14888081', 'SILVA Analia', '29668948', 'LORENZO',     '26082377', MARTES),
    '12/14': ('FAVIER Sergio Jose', '14888081', 'LORENZO',      '26082377', 'SILVA Analia', '29668948', MARTES),
    '09/17': ('BENAVENTE Ana',      '22011871', 'LORENZO',      '26082377', 'SILVA Analia', '29668948', VIERNES),
}


def _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, dia, hora, libres):
    for obj in (t_dir, t_adm):
        obj.presidente_nombre = pn
        obj.presidente_dni = pd
        obj.vocal_1_nombre = v1n
        obj.vocal_1_dni = v1d
        obj.vocal_2_nombre = v2n
        obj.vocal_2_dni = v2d
        obj.dia_semana = dia
        obj.hora = hora
        obj.permite_libres = libres
    t_dir.pendiente_sincronizacion = False
    t_adm.ultima_sincronizacion = timezone.now()
    t_dir.save()
    t_adm.save()


class Command(BaseCommand):
    help = 'Carga tribunales de Matemática (Martes–Viernes) desde los datos del sistema externo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se haría sin guardar cambios.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        actualizados = 0
        sin_mep = []

        # ── Tribunales uniformes ──────────────────────────────────────────────
        for codigo, pn, pd, v1n, v1d, v2n, v2d, dia, hora, libres in UNIFORMES:
            meps = list(
                MateriaEnPlan.objects
                .filter(materia__codigo=codigo)
                .filter(
                    __import__('django.db.models', fromlist=['Q']).Q(plan__vigente=True) |
                    __import__('django.db.models', fromlist=['Q']).Q(plan__activo=True)
                )
                .select_related('materia', 'plan')
            )
            if not meps:
                sin_mep.append(codigo)
                continue
            for mep in meps:
                label = f'{mep.materia.nombre} / Plan {mep.plan.codigo}'
                if dry:
                    self.stdout.write(f'  [dry] {label}')
                    continue
                t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
                t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
                _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, dia, hora, libres)
                actualizados += 1
                self.stdout.write(f'  OK  {label}')

        # ── Álgebra II ────────────────────────────────────────────────────────
        for plan_codigo, datos in ALGEBRA_II_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00158', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00158 / plan {plan_codigo}')
                continue
            label = f'Algebra II / Plan {plan_codigo}'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, MARTES, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Álgebra I ─────────────────────────────────────────────────────────
        for plan_codigo, datos in ALGEBRA_I_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00016', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00016 / plan {plan_codigo}')
                continue
            label = f'Algebra I / Plan {plan_codigo}'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, MARTES, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Cálculo II ────────────────────────────────────────────────────────
        for plan_codigo, datos in CALCULO_II_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00004', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00004 / plan {plan_codigo}')
                continue
            label = f'Calculo II / Plan {plan_codigo}'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, MIERCOLES, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Cálculo III ───────────────────────────────────────────────────────
        for plan_codigo, datos in CALCULO_III_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00010', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00010 / plan {plan_codigo}')
                continue
            label = f'Calculo III / Plan {plan_codigo}'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, MIERCOLES, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Seminario ─────────────────────────────────────────────────────────
        for plan_codigo, datos in SEMINARIO_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00024', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00024 / plan {plan_codigo}')
                continue
            label = f'Seminario / Plan {plan_codigo}'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, MIERCOLES, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Matemática Aplicada ───────────────────────────────────────────────
        for plan_codigo, datos in MAT_APLICADA_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d, dia = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00009', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00009 / plan {plan_codigo}')
                continue
            label = f'Matematica Aplicada / Plan {plan_codigo}'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, dia, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Resumen ───────────────────────────────────────────────────────────
        self.stdout.write('')
        if dry:
            self.stdout.write(self.style.WARNING('Dry-run: ningún cambio guardado.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Tribunales cargados: {actualizados}'))
        if sin_mep:
            self.stdout.write(self.style.WARNING('Sin MateriaEnPlan activa/vigente:'))
            for s in sin_mep:
                self.stdout.write(f'  - {s}')
