from django import forms
from django.forms import inlineformset_factory

from .models import SolicitudProtocolizacion, MiembroEquipoDocente


# Tipificaciones que requieren datos curriculares (carrera, plan, crédito horario)
TIPIFICACIONES_CURRICULARES = {'optativa', 'electiva'}


class SolicitudProtocolizacionForm(forms.ModelForm):
    # Campos para envío anónimo
    nombre_docente = forms.CharField(
        label='Nombre y apellido', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    legajo_docente = forms.CharField(
        label='Legajo', max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    departamento_docente = forms.CharField(
        label='Departamento', max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email_docente = forms.EmailField(
        label='Email', required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = SolicitudProtocolizacion
        fields = [
            # I - Oferta Académica
            'nombre_curso', 'area', 'carrera', 'plan_estudio', 'anno_carrera', 'periodo',
            # III - Características
            'hs_teoricas', 'hs_practicas_aula', 'hs_lab_campo',
            'tipificacion', 'fecha_inicio', 'fecha_hasta', 'cantidad_semanas',
            # IV-XIV
            'fundamentacion', 'objetivos',
            'contenidos_minimos', 'unidades',
            'plan_trabajos_practicos', 'regimen_aprobacion',
            'bibliografia_basica', 'bibliografia_complementaria',
            'resumen_objetivos', 'resumen_programa',
            'imprevistos', 'contacto_otros',
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_hasta': forms.DateInput(attrs={'type': 'date'}),
            'fundamentacion': forms.Textarea(attrs={'rows': 5}),
            'objetivos': forms.Textarea(attrs={'rows': 5}),
            'contenidos_minimos': forms.Textarea(attrs={'rows': 3}),
            'unidades': forms.Textarea(attrs={'rows': 8}),
            'plan_trabajos_practicos': forms.Textarea(attrs={'rows': 5}),
            'regimen_aprobacion': forms.Textarea(attrs={'rows': 4}),
            'bibliografia_basica': forms.Textarea(attrs={'rows': 5}),
            'bibliografia_complementaria': forms.Textarea(attrs={'rows': 4}),
            'resumen_objetivos': forms.Textarea(attrs={'rows': 4}),
            'resumen_programa': forms.Textarea(attrs={'rows': 4}),
            'imprevistos': forms.Textarea(attrs={'rows': 3}),
            'contacto_otros': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, tipificacion=None, anonimo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.anonimo = anonimo
        if anonimo:
            self.fields['nombre_docente'].required = True
            self.fields['legajo_docente'].required = True

        # Pre-fijar tipificación y ocultarla si viene del URL
        if tipificacion:
            self.fields['tipificacion'].initial = tipificacion
            self.fields['tipificacion'].widget = forms.HiddenInput()

        # Para extracurricular: carrera/plan/periodo/horas no son obligatorios
        if tipificacion not in TIPIFICACIONES_CURRICULARES:
            for f in ('carrera', 'plan_estudio', 'anno_carrera', 'periodo'):
                self.fields[f].required = False

        # Aplicar clases Bootstrap
        for field in self.fields.values():
            if isinstance(field.widget, forms.HiddenInput):
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        hasta = cleaned_data.get('fecha_hasta')
        if inicio and hasta and hasta < inicio:
            raise forms.ValidationError('La fecha hasta no puede ser anterior a la fecha de inicio.')
        return cleaned_data


class MiembroEquipoDocenteForm(forms.ModelForm):
    class Meta:
        model = MiembroEquipoDocente
        fields = ['nombre', 'funcion', 'cargo', 'dedicacion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido, Nombre'}),
            'funcion': forms.Select(attrs={'class': 'form-select'}),
            'cargo': forms.Select(attrs={'class': 'form-select'}),
            'dedicacion': forms.Select(attrs={'class': 'form-select'}),
        }


EquipoDocenteFormSet = inlineformset_factory(
    SolicitudProtocolizacion,
    MiembroEquipoDocente,
    form=MiembroEquipoDocenteForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class RevisionForm(forms.Form):
    estado = forms.ChoiceField(
        choices=[('aprobado', 'Aprobar'), ('rechazado', 'Rechazar'), ('en_revision', 'Marcar en revisión')],
        label='Decisión',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comentarios = forms.CharField(
        label='Comentarios',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=False,
    )
