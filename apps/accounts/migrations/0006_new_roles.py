from django.db import migrations, models


def migrar_administrador_a_secretario(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(rol='administrador').update(rol='secretario')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_remove_unsl_email_validator'),
    ]

    operations = [
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
                ],
                default='docente',
                max_length=30,
                verbose_name='Rol',
            ),
        ),
        migrations.RunPython(
            migrar_administrador_a_secretario,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
