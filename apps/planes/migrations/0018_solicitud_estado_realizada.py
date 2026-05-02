from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0017_tribunal_docentes_texto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='solicitudcambiotribunal',
            name='estado',
            field=models.CharField(
                choices=[('pendiente', 'Pendiente'), ('realizada', 'Realizada')],
                default='pendiente',
                max_length=20,
                verbose_name='Estado',
            ),
        ),
    ]
