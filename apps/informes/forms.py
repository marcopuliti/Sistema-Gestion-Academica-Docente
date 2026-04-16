from django import forms
from .models import InformeActividadAnual


class InformeActividadAnualForm(forms.ModelForm):
    # Campos para envío anónimo (requeridos solo si no está autenticado)
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
        model = InformeActividadAnual
        fields = [
            'anno_academico', 'categoria', 'dedicacion',
            'materias_dictadas', 'carga_horaria_docencia',
            'actividades_investigacion', 'actividades_extension',
            'actividades_gestion', 'actividades_formacion',
            'observaciones',
        ]
        widgets = {
            'materias_dictadas': forms.Textarea(attrs={'rows': 4}),
            'actividades_investigacion': forms.Textarea(attrs={'rows': 4}),
            'actividades_extension': forms.Textarea(attrs={'rows': 4}),
            'actividades_gestion': forms.Textarea(attrs={'rows': 4}),
            'actividades_formacion': forms.Textarea(attrs={'rows': 4}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, anonimo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.anonimo = anonimo
        if anonimo:
            self.fields['nombre_docente'].required = True
            self.fields['legajo_docente'].required = True
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.Select, forms.NumberInput)):
                field.widget.attrs.setdefault('class', 'form-control')
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'form-control')


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
