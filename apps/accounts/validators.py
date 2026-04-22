from django.core.exceptions import ValidationError

DOMINIO_REQUERIDO = '@unsl.edu.ar'


def validate_unsl_email(value):
    if value and not value.lower().endswith(DOMINIO_REQUERIDO):
        raise ValidationError(
            f'El email debe pertenecer al dominio {DOMINIO_REQUERIDO}.'
        )
