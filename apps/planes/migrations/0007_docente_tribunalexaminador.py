from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0006_aniodictado'),
    ]

    operations = [
        migrations.CreateModel(
            name='Docente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=250, verbose_name='Nombre completo')),
                ('dni', models.CharField(max_length=15, unique=True, verbose_name='DNI')),
            ],
            options={
                'verbose_name': 'Docente',
                'verbose_name_plural': 'Docentes',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='TribunalExaminador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_hora', models.DateTimeField(blank=True, null=True, verbose_name='Día y hora del examen')),
                ('permite_libres', models.BooleanField(
                    default=True,
                    verbose_name='Pueden rendir libres',
                    help_text='Si está desmarcado, solo pueden rendir alumnos regulares.',
                )),
                ('materia_en_plan', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tribunal',
                    to='planes.materiaenplan',
                    verbose_name='Materia en plan',
                )),
                ('presidente', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tribunales_como_presidente',
                    to='planes.docente',
                    verbose_name='Presidente',
                )),
                ('vocal_1', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tribunales_como_vocal_1',
                    to='planes.docente',
                    verbose_name='1er. Vocal',
                )),
                ('vocal_2', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tribunales_como_vocal_2',
                    to='planes.docente',
                    verbose_name='2do. Vocal',
                )),
            ],
            options={
                'verbose_name': 'Tribunal Examinador',
                'verbose_name_plural': 'Tribunales Examinadores',
            },
        ),
    ]
