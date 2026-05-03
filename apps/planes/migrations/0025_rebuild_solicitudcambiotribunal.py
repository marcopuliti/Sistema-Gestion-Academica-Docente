from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0024_informetribunalesenviado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
                ('fecha', models.DateTimeField(auto_now_add=True, verbose_name='Fecha')),
                ('director', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='solicitudes_cambio_tribunal',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Director',
                )),
                ('tribunales', models.ManyToManyField(
                    blank=True,
                    related_name='solicitudes_cambio',
                    to='planes.tribunalexaminador',
                    verbose_name='Tribunales incluidos',
                )),
            ],
            options={
                'verbose_name': 'Solicitud de cambio de tribunal',
                'verbose_name_plural': 'Solicitudes de cambio de tribunal',
                'ordering': ['-fecha'],
            },
        ),
    ]
