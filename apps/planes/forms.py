from django import forms
from .models import DIA_SEMANA_CHOICES

_txt = {'class': 'form-control form-control-sm'}
_sel = {'class': 'form-select form-select-sm'}


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
