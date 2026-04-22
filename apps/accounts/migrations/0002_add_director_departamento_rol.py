from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='rol',
            field=models.CharField(
                choices=[
                    ('docente', 'Docente'),
                    ('administrador', 'Administrador'),
                    ('director_departamento', 'Director de Departamento'),
                ],
                default='docente',
                max_length=30,
                verbose_name='Rol',
            ),
        ),
    ]
