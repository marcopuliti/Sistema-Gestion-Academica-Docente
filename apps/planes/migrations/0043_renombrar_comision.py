from django.db import migrations


class Migration(migrations.Migration):
    """Las comisiones dejan de ser solo de optativas: se renombran los modelos y el campo
    del item de servicio (sin pérdida de datos)."""

    dependencies = [
        ('planes', '0042_eliminar_tribunales_slots_optativos'),
    ]

    operations = [
        # Las constraints que nombran el campo se recrean en 0044 con el nombre nuevo
        migrations.RemoveConstraint('SolicitudServicioItem', 'servicio_item_materia_o_comision'),
        migrations.RemoveConstraint('SolicitudServicioItem', 'servicio_item_unico_comision'),
        migrations.RenameModel('ComisionOptativa', 'Comision'),
        migrations.RenameModel('MiembroComisionOptativa', 'MiembroComision'),
        migrations.RenameField('SolicitudServicioItem', 'comision_optativa', 'comision'),
    ]
