from django import forms
from django.db.models import Q
from .models import (
    DIA_SEMANA_CHOICES, Comision, Materia, MateriaEnPlan, MateriaOptativa,
    MiembroComision, PlanEstudio,
)

_txt = {'class': 'form-control form-control-sm'}
_sel = {'class': 'form-select form-select-sm'}
_PLAN_EN_USO = Q(plan__vigente=True) | Q(plan__activo=True)


class MateriaOptativaForm(forms.ModelForm):
    class Meta:
        model = MateriaOptativa
        fields = ['codigo', 'nombre', 'departamento', 'hs_totales', 'cuatrimestre',
                  'numero_resolucion', 'vigente', 'optativas']
        widgets = {
            'codigo': forms.TextInput(attrs=_txt),
            'nombre': forms.TextInput(attrs=_txt),
            'departamento': forms.Select(attrs=_sel),
            'hs_totales': forms.NumberInput(attrs={'min': 1, **_txt}),
            'cuatrimestre': forms.Select(attrs=_sel),
            'numero_resolucion': forms.TextInput(attrs=_txt),
            'vigente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'optativas': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Slots optativos de planes en uso (más los ya vinculados, aunque el plan no esté en uso)
        vinculados = self.instance.optativas.values('pk') if self.instance.pk else MateriaEnPlan.objects.none()
        self.fields['optativas'].queryset = (
            MateriaEnPlan.objects
            .filter(es_optativa=True)
            .filter(_PLAN_EN_USO | Q(pk__in=vinculados))
            .select_related('materia', 'plan__carrera')
            .order_by('plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre', 'materia__nombre')
        )

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].strip()
        if Materia.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError('Ese código ya corresponde a una materia de plan.')
        return codigo


class ComisionForm(forms.ModelForm):
    class Meta:
        model = Comision
        fields = ['condicion', 'credito_horario', 'planes']
        widgets = {
            'condicion': forms.Select(attrs=_sel),
            'credito_horario': forms.NumberInput(attrs={'min': 1, **_txt}),
            'planes': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['planes'].queryset = (
            PlanEstudio.objects
            .filter(carrera=self.instance.carrera)
            .filter(Q(vigente=True) | Q(activo=True) | Q(pk__in=self.instance.planes.values('pk')))
            .order_by('codigo')
        )
        self.fields['planes'].label_from_instance = lambda p: f'Plan {p.codigo}'


MiembroComisionFormSet = forms.inlineformset_factory(
    Comision, MiembroComision,
    fields=['nombre', 'dni', 'funcion', 'cargo', 'dedicacion'],
    widgets={
        'nombre': forms.TextInput(attrs=_txt),
        'dni': forms.TextInput(attrs=_txt),
        'funcion': forms.Select(attrs=_sel),
        'cargo': forms.Select(attrs=_sel),
        'dedicacion': forms.Select(attrs=_sel),
    },
    extra=1, can_delete=True,
)


class TribunalForm(forms.Form):
    presidente_nombre = forms.CharField(
        label='Presidente — Nombre completo', required=False,
        widget=forms.TextInput(attrs=_txt),
    )
    presidente_dni = forms.CharField(
        label='Presidente — DNI', required=False,
        widget=forms.TextInput(attrs=_txt),
    )
    vocal_1_nombre = forms.CharField(
        label='1er. Vocal — Nombre completo', required=False,
        widget=forms.TextInput(attrs=_txt),
    )
    vocal_1_dni = forms.CharField(
        label='1er. Vocal — DNI', required=False,
        widget=forms.TextInput(attrs=_txt),
    )
    vocal_2_nombre = forms.CharField(
        label='2do. Vocal — Nombre completo', required=False,
        widget=forms.TextInput(attrs=_txt),
    )
    vocal_2_dni = forms.CharField(
        label='2do. Vocal — DNI', required=False,
        widget=forms.TextInput(attrs=_txt),
    )
    dia_semana = forms.ChoiceField(
        choices=[('', '— Seleccionar —')] + [(v, l) for v, l in DIA_SEMANA_CHOICES],
        required=False,
        label='Día de la semana',
        widget=forms.Select(attrs=_sel),
    )
    hora = forms.TimeField(
        label='Hora del examen',
        required=False,
        input_formats=['%H:%M'],
        widget=forms.TimeInput(attrs={'type': 'time', **_txt}, format='%H:%M'),
    )
    permite_libres = forms.BooleanField(required=False, label='Pueden rendir libres')
