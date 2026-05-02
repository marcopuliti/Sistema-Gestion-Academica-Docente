from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0005_planestudio_activo'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnioDictado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ano', models.PositiveSmallIntegerField(verbose_name='Año')),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='anos_dictados',
                    to='planes.planestudio',
                    verbose_name='Plan de estudio',
                )),
            ],
            options={
                'verbose_name': 'Año dictado',
                'verbose_name_plural': 'Años dictados',
                'ordering': ['plan', 'ano'],
                'unique_together': {('plan', 'ano')},
            },
        ),
    ]
