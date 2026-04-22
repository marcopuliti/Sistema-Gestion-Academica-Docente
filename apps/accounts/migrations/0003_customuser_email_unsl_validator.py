import apps.accounts.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_director_departamento_rol'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='email',
            field=models.EmailField(
                blank=True,
                max_length=254,
                validators=[apps.accounts.validators.validate_unsl_email],
                verbose_name='Correo electrónico',
            ),
        ),
    ]
