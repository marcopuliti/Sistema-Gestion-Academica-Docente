from django.db import migrations


def eliminar_tribunales_de_slots(apps, schema_editor):
    """Los slots 'Optativa I/II…' no se rinden: los tribunales ahora son de las materias
    de la bolsa. Solo se borran los vacíos y sin cambios propuestos ni agrupaciones."""
    TribunalExaminador = apps.get_model('planes', 'TribunalExaminador')
    qs = (
        TribunalExaminador.objects
        .filter(materia_en_plan__es_optativa=True)
        .filter(presidente_nombre='', vocal_1_nombre='', vocal_2_nombre='', dia_semana__isnull=True, hora__isnull=True)
        .filter(solicitud_items__isnull=True, agrupaciones__isnull=True)
    )
    TribunalExaminador.objects.filter(pk__in=list(qs.values_list('pk', flat=True))).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0041_bolsa_optativas'),
    ]

    operations = [
        migrations.RunPython(eliminar_tribunales_de_slots, migrations.RunPython.noop),
    ]
