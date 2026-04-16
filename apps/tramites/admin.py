from django import forms
from django.contrib import admin
from django.db import models as db_models
from .models import CalendarioAcademico


class CalendarioAcademicoForm(forms.ModelForm):
    """Usa inputs HTML5 date para evitar el widget JS del admin (incompatible con Python 3.14)."""
    fecha_inicio_1c = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    fecha_fin_1c    = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    fecha_inicio_2c = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    fecha_fin_2c    = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    class Meta:
        model = CalendarioAcademico
        fields = '__all__'


@admin.register(CalendarioAcademico)
class CalendarioAcademicoAdmin(admin.ModelAdmin):
    form = CalendarioAcademicoForm
    list_display = ('anno', 'fecha_inicio_1c', 'fecha_fin_1c', 'fecha_inicio_2c', 'fecha_fin_2c', 'semanas_cuatrimestre', 'semanas_anual')
    ordering = ('-anno',)
