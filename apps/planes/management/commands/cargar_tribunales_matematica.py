"""
Carga los tribunales examinadores del Departamento de Matemática
a partir de los datos extraídos del archivo de tribunales (Lunes).

Para cada TribunalExaminador y TribunalAdmin se aplican los mismos datos,
ya que este comando carga el estado actual del sistema externo.
pendiente_sincronizacion queda en False (ya sincronizado).
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.planes.models import MateriaEnPlan, TribunalExaminador, TribunalAdmin

LUNES = 1
MARTES = 2
H8 = datetime.time(8, 0)

# Tribunales uniformes: mismo tribunal para todos los planes de esa materia.
# (codigo_materia, pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni, dia, hora, libres)
UNIFORMES = [
    ('03MA00014',    'BLOIS Maria Ines',       '17625176', 'SCHVAGER Betsabe',       '26450804', 'CANCELA ELIAS D.',       '32500878', LUNES,  H8, True),
    ('03MA00972',    'BLOIS Maria Ines',       '17625176', 'SCHVAGER Betsabe',       '26450804', 'CANCELA ELIAS D.',       '32500878', LUNES,  H8, True),
    ('03064MA00010', 'BLOIS Maria Ines',       '17625176', 'SCHVAGER Betsabe',       '26450804', 'CANCELA ELIAS D.',       '32500878', LUNES,  H8, True),
    ('03MA00529',    'BLOIS Maria Ines',       '17625176', 'SCHVAGER Betsabe',       '26450804', 'CANCELA ELIAS D.',       '32500878', LUNES,  H8, True),
    ('03MA00279',    'PANELO Cristian',        '32915835', 'JAUME Daniel A.',        '22693282', 'PASTINE Adrian G.',      '33219586', LUNES,  H8, True),
    ('03003MA00006', 'PANELO Cristian',        '32915835', 'JAUME Daniel A.',        '22693282', 'PASTINE Adrian G.',      '33219586', LUNES,  H8, True),
    ('03MA00881',    'MARTINEZ Federico',      '27624328', 'ARRIBILLAGA Pablo R.',   '30896847', 'PASTINE Adrian Gabriel', '33219586', LUNES,  H8, True),
    ('03MA00884',    'JAUME Daniel A.',        '22693282', 'PASTINE Adrian G.',      '33219586', 'NEME Pablo A.',          '27376238', MARTES, H8, True),
    ('03MA00880',    'SPEDALETTI Juan',        '27932507', 'SILVA Analia',           '29668948', 'RIDOLFI Claudia',        '25259776', MARTES, H8, True),
    ('03MA00173',    'NEME Alejandro J.',      '10945376', 'JAUME Daniel Alejandro', '22693282', 'PASTINE Adrian G.',      '33219586', LUNES,  H8, True),
    ('03MA00882',    'SILVA Analia',           '29668948', 'BENAVENTE Ana',          '22011871', 'FAVIER Sergio Jose',     '14888081', MARTES, H8, True),
    ('03003MA00002', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'MOLINA MUNAFO Gonzalo', '31717035', 'JAUME Daniel Alejandro', '22693282', LUNES, H8, True),
    ('03003MA00007', 'NEME Pablo A.',          '27376238', 'MANASERO Paola',         '33153111', 'BENAVENTE Ana',          '22011871', LUNES,  H8, True),
    ('16001MA0004',  'ZAKOWICZ Maria I.',      '17949441', 'BORTOLUSSI Noelia Belen', '',        'GALDEANO Patricia',      '16984428', LUNES,  H8, False),
]

# Cálculo I (03MA00001): tribunal varía según el plan.
# {plan.codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni)}
# Día y hora es siempre Lunes 08:00, libres=True.
CALCULO_I_POR_PLAN = {
    '13/08': ('CORTES NICOLAS E.',    '27496755', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'BENAVENTE Ana',  '22011871'),
    '5/09':  ('CORTES NICOLAS E.',    '27496755', 'MANASERO Paola',           '33153111', 'LOPEZ ORTIZ Juan Ignacio', '33702529'),
    '6/15':  ('CORTES NICOLAS E.',    '27496755', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'BENAVENTE Ana',  '22011871'),
    '28/12': ('CORTES NICOLAS E.',    '27496755', 'MANASERO Paola',           '33153111', 'LOPEZ ORTIZ Juan Ignacio', '33702529'),
    '26/12': ('NEME Pablo Alejandro', '11901073', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'BENAVENTE Ana',  '22011871'),
    '2/25':  ('NEME Pablo Alejandro', '11901073', 'LOPEZ ORTIZ Juan Ignacio', '33702529', 'BENAVENTE Ana',  '22011871'),
    '09/17': ('BENAVENTE Ana',        '22011871', 'NEME Pablo A.',            '27376238', 'MARTINEZ Federico', '27624328'),
    '15/06': ('BENAVENTE Ana',        '22011871', 'NEME Pablo A.',            '27376238', 'MARTINEZ Federico', '27624328'),
    '16/06': ('BENAVENTE Ana',        '22011871', 'NEME Pablo A.',            '27376238', 'MARTINEZ Federico', '27624328'),
    '21/13': ('NEME Pablo A.',        '27376238', 'MANASERO Paola',           '33153111', 'BENAVENTE Ana',  '22011871'),
    '32/12': ('NEME Pablo A.',        '27376238', 'MANASERO Paola',           '33153111', 'BENAVENTE Ana',  '22011871'),
}

# Cálculo Numérico (03MA00012): mismo tribunal, día varía según el plan.
# {plan.codigo: (pres_nombre, pres_dni, voc1_nombre, voc1_dni, voc2_nombre, voc2_dni, dia)}
CALCULO_NUMERICO_POR_PLAN = {
    '09/17': ('LEDEZMA Agustina V.', '39395104', 'SPEDALETTI Juan', '27932507', 'NEME Pablo A.', '27376238', LUNES),
    '26/12': ('LEDEZMA Agustina V.', '39395104', 'SPEDALETTI Juan', '27932507', 'NEME Pablo A.', '27376238', MARTES),
    '28/12': ('LEDEZMA Agustina V.', '39395104', 'SPEDALETTI Juan', '27932507', 'NEME Pablo A.', '27376238', MARTES),
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
    help = 'Carga tribunales del Departamento de Matemática desde los datos del sistema externo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se haría sin guardar cambios.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        actualizados = 0
        sin_mep = []
        ahora = timezone.now()

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

        # ── Cálculo I ─────────────────────────────────────────────────────────
        for plan_codigo, datos in CALCULO_I_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00001', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00001 / plan {plan_codigo}')
                continue
            label = f'Calculo I / Plan {plan_codigo} ({mep.plan.carrera if hasattr(mep.plan, "carrera") else ""})'
            if dry:
                self.stdout.write(f'  [dry] {label}')
                continue
            t_dir, _ = TribunalExaminador.objects.get_or_create(materia_en_plan=mep)
            t_adm, _ = TribunalAdmin.objects.get_or_create(materia_en_plan=mep)
            _aplicar_tribunal(t_dir, t_adm, pn, pd, v1n, v1d, v2n, v2d, LUNES, H8, True)
            actualizados += 1
            self.stdout.write(f'  OK  {label}')

        # ── Cálculo Numérico ──────────────────────────────────────────────────
        for plan_codigo, datos in CALCULO_NUMERICO_POR_PLAN.items():
            pn, pd, v1n, v1d, v2n, v2d, dia = datos
            mep = (
                MateriaEnPlan.objects
                .filter(materia__codigo='03MA00012', plan__codigo=plan_codigo)
                .select_related('materia', 'plan')
                .first()
            )
            if not mep:
                sin_mep.append(f'03MA00012 / plan {plan_codigo}')
                continue
            label = f'Calculo Numerico / Plan {plan_codigo}'
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
