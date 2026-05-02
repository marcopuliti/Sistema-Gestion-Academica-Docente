import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0020_alter_solicitudcambiotribunal_dia_semana_propuesto_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tribunalexaminador',
            name='pendiente_sincronizacion',
            field=models.BooleanField(default=False, verbose_name='Pendiente de sincronización'),
        ),
        migrations.CreateModel(
            name='TribunalAdmin',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('materia_en_plan', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tribunal_admin_obj',
                    to='planes.materiaenplan',
                    verbose_name='Materia en plan',
                )),
                ('presidente_nombre', models.CharField(blank=True, max_length=250, verbose_name='Presidente (nombre)')),
                ('presidente_dni', models.CharField(blank=True, max_length=15, verbose_name='Presidente (DNI)')),
                ('vocal_1_nombre', models.CharField(blank=True, max_length=250, verbose_name='1er. Vocal (nombre)')),
                ('vocal_1_dni', models.CharField(blank=True, max_length=15, verbose_name='1er. Vocal (DNI)')),
                ('vocal_2_nombre', models.CharField(blank=True, max_length=250, verbose_name='2do. Vocal (nombre)')),
                ('vocal_2_dni', models.CharField(blank=True, max_length=15, verbose_name='2do. Vocal (DNI)')),
                ('dia_semana', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes')],
                    verbose_name='Día de la semana',
                )),
                ('hora', models.TimeField(blank=True, null=True, verbose_name='Hora del examen')),
                ('permite_libres', models.BooleanField(default=True, verbose_name='Pueden rendir libres')),
                ('ultima_sincronizacion', models.DateTimeField(blank=True, null=True, verbose_name='Última sincronización')),
            ],
            options={
                'verbose_name': 'Tribunal (Administración)',
                'verbose_name_plural': 'Tribunales (Administración)',
            },
        ),
        migrations.DeleteModel(name='SolicitudCambioTribunal'),
    ]
