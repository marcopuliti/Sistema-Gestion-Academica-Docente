import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_customuser_email_unsl_validator'),
    ]

    operations = [
        migrations.CreateModel(
            name='TokenVerificacionEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='token_verificacion',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
