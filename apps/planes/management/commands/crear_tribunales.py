from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.planes.models import MateriaEnPlan, TribunalExaminador


def crear_tribunales_faltantes():
    """
    Crea un TribunalExaminador vacío para cada MateriaEnPlan de planes
    vigentes o activos que todavía no tenga uno.
    Devuelve (creados, ya_existian).
    """
    meps_con_tribunal = TribunalExaminador.objects.values_list('materia_en_plan_id', flat=True)

    meps = (
        MateriaEnPlan.objects
        .filter(Q(plan__vigente=True) | Q(plan__activo=True))
        .exclude(id__in=meps_con_tribunal)
        .select_related('materia', 'plan__carrera')
        .order_by('plan__carrera__nombre', 'plan__codigo', 'ano', 'materia__nombre')
    )

    tribunales = [TribunalExaminador(materia_en_plan=mep) for mep in meps]
    TribunalExaminador.objects.bulk_create(tribunales)

    ya_existian = TribunalExaminador.objects.count() - len(tribunales)
    return len(tribunales), ya_existian


class Command(BaseCommand):
    help = 'Crea tribunales examinadores vacíos para materias sin tribunal en planes vigentes o activos'

    def handle(self, *args, **kwargs):
        creados, ya_existian = crear_tribunales_faltantes()
        self.stdout.write(f'Tribunales ya existentes: {ya_existian}')
        self.stdout.write(self.style.SUCCESS(f'Tribunales creados: {creados}'))
