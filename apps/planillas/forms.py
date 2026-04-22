from django import forms
from .models import PlanificacionActividades
from apps.tramites.models import DEPARTAMENTO_CHOICES


class PlanificacionActividadesForm(forms.ModelForm):
    # Campos para envío anónimo
    nombre_docente = forms.CharField(
        label='Nombre y apellido', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    legajo_docente = forms.CharField(
        label='Legajo', max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    departamento_docente = forms.ChoiceField(
        label='Departamento', choices=DEPARTAMENTO_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    email_docente = forms.EmailField(
        label='Email', required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = PlanificacionActividades
        fields = [
            'anno', 'fecha_desde', 'fecha_hasta',
            'cargo', 'dedicacion', 'designacion', 'area',
            'a1_descripcion', 'a1_hs_1c', 'a1_hs_2c',
            'a2_descripcion', 'a2_hs_1c', 'a2_hs_2c',
            'a3_descripcion', 'a3_hs_1c', 'a3_hs_2c',
            'a4_descripcion', 'a4_hs_1c', 'a4_hs_2c',
            'b_descripcion',  'b_hs_1c',  'b_hs_2c',
            'c_descripcion',  'c_hs_1c',  'c_hs_2c',
            'd_descripcion',  'd_hs_1c',  'd_hs_2c',
            'e_descripcion',  'e_hs_1c',  'e_hs_2c',
            'f_descripcion',  'f_hs_1c',  'f_hs_2c',
            'g_descripcion',  'g_hs_1c',  'g_hs_2c',
        ]
        widgets = {
            'fecha_desde': forms.DateInput(attrs={'type': 'date'}),
            'fecha_hasta': forms.DateInput(attrs={'type': 'date'}),
            'a1_descripcion': forms.Textarea(attrs={'rows': 3}),
            'a2_descripcion': forms.Textarea(attrs={'rows': 3}),
            'a3_descripcion': forms.Textarea(attrs={'rows': 3}),
            'a4_descripcion': forms.Textarea(attrs={'rows': 3}),
            'b_descripcion':  forms.Textarea(attrs={'rows': 3}),
            'c_descripcion':  forms.Textarea(attrs={'rows': 3}),
            'd_descripcion':  forms.Textarea(attrs={'rows': 3}),
            'e_descripcion':  forms.Textarea(attrs={'rows': 3}),
            'f_descripcion':  forms.Textarea(attrs={'rows': 3}),
            'g_descripcion':  forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, anonimo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.anonimo = anonimo
        if anonimo:
            self.fields['nombre_docente'].required = True
            self.fields['legajo_docente'].required = True
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        desde = cleaned.get('fecha_desde')
        hasta = cleaned.get('fecha_hasta')
        if desde and hasta and hasta < desde:
            raise forms.ValidationError('Fecha hasta no puede ser anterior a fecha desde.')
        return cleaned


class RevisionForm(forms.Form):
    estado = forms.ChoiceField(
        choices=[
            ('aprobado', 'Aprobar'),
            ('rechazado', 'Rechazar'),
            ('en_revision', 'Marcar en revisión'),
        ],
        label='Decisión',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comentarios = forms.CharField(
        label='Comentarios',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=False,
    )
