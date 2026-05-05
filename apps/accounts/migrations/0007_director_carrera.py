import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_new_roles'),
        ('planes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='carrera',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='directores',
                to='planes.carrera',
                verbose_name='Carrera',
            ),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='rol',
            field=models.CharField(
                choices=[
                    ('docente', 'Docente'),
                    ('secretario', 'Secretario'),
                    ('direccion_academica', 'Dirección Académica'),
                    ('dpto_estudiantes', 'Departamento de Estudiantes'),
                    ('director_departamento', 'Director de Departamento'),
                    ('director_carrera', 'Director de Carrera'),
                ],
                default='docente',
                max_length=30,
                verbose_name='Rol',
            ),
        ),
    ]
