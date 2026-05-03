from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0025_rebuild_solicitudcambiotribunal'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Drop TribunalAdmin
        migrations.DeleteModel(name='TribunalAdmin'),

        # Remove pendiente_sincronizacion from TribunalExaminador
        migrations.RemoveField(
            model_name='tribunalexaminador',
            name='pendiente_sincronizacion',
        ),

        # Update TribunalExaminador verbose_names
        migrations.AlterModelOptions(
            name='tribunalexaminador',
            options={
                'verbose_name': 'Tribunal Examinador',
                'verbose_name_plural': 'Tribunales Examinadores',
            },
        ),

        # Drop old SolicitudCambioTribunal (had M2M 'tribunales')
        migrations.DeleteModel(name='SolicitudCambioTribunal'),

        # Recreate SolicitudCambioTribunal with new schema
        migrations.CreateModel(
            name='SolicitudCambioTribunal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('departamento', models.CharField(
                    choices=[
                        ('', '---------'),
                        ('Matemática', 'Matemática'),
                        ('Física', 'Física'),
                        ('Geología', 'Geología'),
                        ('Electrónica', 'Electrónica'),
                        ('Informática', 'Informática'),
                        ('Minería', 'Minería'),
                    ],
                    max_length=50,
                    verbose_name='Departamento',
                )),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('fecha_envio', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de envío')),
                ('estado', models.CharField(
                    choices=[('borrador', 'Borrador'), ('enviada', 'Enviada'), ('aplicada', 'Aplicada')],
                    default='borrador',
                    max_length=20,
                    verbose_name='Estado',
                )),
                ('director', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='solicitudes_cambio_tribunal',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Director',
                )),
            ],
            options={
                'verbose_name': 'Solicitud de cambio de tribunal',
                'verbose_name_plural': 'Solicitudes de cambio de tribunal',
                'ordering': ['-fecha_creacion'],
            },
        ),

        # Create SolicitudCambioItem
        migrations.CreateModel(
            name='SolicitudCambioItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
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
                ('solicitud', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='planes.solicitudcambiotribunal',
                    verbose_name='Solicitud',
                )),
                ('tribunal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='solicitud_items',
                    to='planes.tribunalexaminador',
                    verbose_name='Tribunal',
                )),
            ],
            options={
                'verbose_name': 'Item de solicitud de cambio',
                'verbose_name_plural': 'Items de solicitud de cambio',
                'unique_together': {('solicitud', 'tribunal')},
            },
        ),
    ]
