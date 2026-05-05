import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0034_solicitudinformetribunal_cuatrimestre_anio_depts'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudservicio',
            name='carrera',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='solicitudes_servicio',
                to='planes.carrera',
                verbose_name='Carrera',
            ),
        ),
    ]
