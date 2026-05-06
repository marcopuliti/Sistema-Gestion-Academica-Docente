from django import forms
from django.forms import inlineformset_factory

from .models import (
    SolicitudProtocolizacion, MiembroEquipoDocente, CorrelativaRequerida,
    CONDICION_CHOICES, CONDICION_CORRELATIVA_CHOICES, TIPO_CORRELATIVA_CHOICES,
    SolicitudTaller, MiembroEquipoTaller,
)
from apps.planes.models import PlanEstudio, MateriaEnPlan, Materia
from apps.tramites.models import DEPARTAMENTO_CHOICES


# Tipificaciones que requieren datos curriculares (carrera, plan, crédito horario)
# electiva/extracurricular kept for backward compat with existing records
TIPIFICACIONES_CURRICULARES = {'optativa', 'electiva'}


class SolicitudProtocolizacionForm(forms.ModelForm):
    # Campos para envío anónimo
    nombre_docente = forms.CharField(
        label='Nombre y apellido', max_length=200, required=False,
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
        model = SolicitudProtocolizacion
        fields = [
            # I - Oferta Académica
            'nombre_curso', 'carrera', 'plan_estudio', 'optativa_vinculada',
            'anno_carrera', 'periodo',
            # III - Características
            'hs_teorico_practico', 'hs_teoricas', 'hs_practicas_aula', 'hs_lab_campo',
            'modalidad_cursado', 'tipificacion', 'fecha_inicio', 'fecha_hasta', 'cantidad_semanas',
            # IV-XIV
            'fundamentacion', 'objetivos',
            'contenidos_minimos', 'unidades',
            'plan_trabajos_practicos', 'regimen_aprobacion',
            'bibliografia_basica', 'bibliografia_complementaria',
            'resumen_objetivos', 'resumen_programa',
            'imprevistos', 'contacto_otros',
            'condicion',
        ]
        widgets = {
            'anno_carrera': forms.TextInput(attrs={'readonly': True}),
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
            'condicion': forms.Select(choices=[('', '---------')] + list(CONDICION_CHOICES)),
        }

    def __init__(self, *args, tipificacion=None, anonimo=False, carrera_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.anonimo = anonimo
        if anonimo:
            self.fields['nombre_docente'].required = True

        # Pre-fijar tipificación y ocultarla si viene del URL
        if tipificacion:
            self.fields['tipificacion'].initial = tipificacion
            self.fields['tipificacion'].widget = forms.HiddenInput()

        # Para extracurricular: carrera/plan/optativa/periodo no son obligatorios
        if tipificacion not in TIPIFICACIONES_CURRICULARES:
            for f in ('carrera', 'plan_estudio', 'optativa_vinculada', 'anno_carrera', 'periodo'):
                self.fields[f].required = False

        # Restringir carreras disponibles si se especifica
        if carrera_qs is not None:
            self.fields['carrera'].queryset = carrera_qs

        # Filtrar planes según carrera seleccionada
        carrera_id = self._resolver_id('carrera')
        if carrera_id:
            self.fields['plan_estudio'].queryset = PlanEstudio.objects.filter(
                carrera_id=carrera_id, vigente=True
            )
        else:
            self.fields['plan_estudio'].queryset = PlanEstudio.objects.none()

        # Filtrar optativas según plan seleccionado
        plan_id = self._resolver_id('plan_estudio')
        if plan_id:
            self.fields['optativa_vinculada'].queryset = MateriaEnPlan.objects.filter(
                plan_id=plan_id, es_optativa=True
            ).select_related('materia').order_by('ano', 'materia__nombre')
        else:
            self.fields['optativa_vinculada'].queryset = MateriaEnPlan.objects.none()

        # Label custom para optativa: "Nombre (codigo)"
        self.fields['optativa_vinculada'].label_from_instance = (
            lambda obj: f'{obj.get_nombre()} ({obj.materia.codigo})'
        )

        # IDs para JS dinámico
        self.fields['carrera'].widget.attrs['id'] = 'id_carrera'
        self.fields['plan_estudio'].widget.attrs['id'] = 'id_plan_estudio'
        self.fields['optativa_vinculada'].widget.attrs['id'] = 'id_optativa_vinculada'

        # Aplicar clases Bootstrap
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.HiddenInput):
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def _resolver_id(self, campo):
        """Devuelve el id del campo desde la instancia (edición) o del POST."""
        if self.instance.pk:
            val = getattr(self.instance, f'{campo}_id', None)
            if val:
                return val
        raw = self.data.get(campo)
        if raw:
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
        return None

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
        fields = ['nombre', 'dni', 'funcion', 'cargo', 'dedicacion']
        widgets = {
            'nombre':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido, Nombre'}),
            'dni':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DNI'}),
            'funcion':    forms.Select(attrs={'class': 'form-select'}),
            'cargo':      forms.Select(attrs={'class': 'form-select'}),
            'dedicacion': forms.Select(attrs={'class': 'form-select'}),
        }


class EquipoDocenteFormSetBase(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        tiene_responsable = any(
            f.cleaned_data.get('funcion') == 'prof_responsable'
            for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
        )
        if not tiene_responsable:
            raise forms.ValidationError(
                'Debe asignar al menos un docente como "Prof. Responsable".'
            )


EquipoDocenteFormSet = inlineformset_factory(
    SolicitudProtocolizacion,
    MiembroEquipoDocente,
    form=MiembroEquipoDocenteForm,
    formset=EquipoDocenteFormSetBase,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class CorrelativaForm(forms.ModelForm):
    materia = forms.ModelChoiceField(
        queryset=Materia.objects.none(),
        label='Materia',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm correlativa-materia-select'}),
    )

    class Meta:
        model = CorrelativaRequerida
        fields = ['materia', 'condicion', 'tipo']
        widgets = {
            'condicion': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'tipo':      forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }


CorrelativaFormSet = inlineformset_factory(
    SolicitudProtocolizacion,
    CorrelativaRequerida,
    form=CorrelativaForm,
    extra=0,
    can_delete=True,
)


class ActasAvalForm(forms.Form):
    acta_comision_carrera = forms.FileField(
        label='Acta Comisión de Carrera (PDF)',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
    )
    acta_consejo_departamental = forms.FileField(
        label='Acta Consejo Departamental (PDF)',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
    )

    def _validar_pdf(self, f):
        if f and not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Solo se aceptan archivos PDF.')
        return f

    def clean_acta_comision_carrera(self):
        return self._validar_pdf(self.cleaned_data.get('acta_comision_carrera'))

    def clean_acta_consejo_departamental(self):
        return self._validar_pdf(self.cleaned_data.get('acta_consejo_departamental'))


class RevisionDirectorForm(forms.Form):
    """Formulario de revisión para el Director de Departamento."""
    accion = forms.ChoiceField(
        choices=[
            ('devuelta', 'Devolver al docente con observaciones'),
            ('elevada',  'Elevar al Administrador'),
        ],
        label='Acción',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comentarios = forms.CharField(
        label='Observaciones / Comentarios',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=False,
    )


class RevisionAdminForm(forms.Form):
    """Formulario de revisión para el Administrador (solicitud ya elevada)."""
    accion = forms.ChoiceField(
        choices=[
            ('aprobado',  'Aprobar'),
            ('observada', 'Devolver con observaciones'),
        ],
        label='Decisión',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    numero_resolucion = forms.CharField(
        label='Número de resolución',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 01-24'}),
    )
    comentarios = forms.CharField(
        label='Comentarios',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('accion') == 'aprobado' and not cleaned.get('numero_resolucion'):
            raise forms.ValidationError('Debe ingresar el número de resolución para aprobar.')
        return cleaned


_T  = {'class': 'form-control'}
_TA = lambda r: {'class': 'form-control', 'rows': r}
_TN = {'class': 'form-control', 'min': 0}


class SolicitudTallerForm(forms.ModelForm):
    class Meta:
        model = SolicitudTaller
        fields = [
            'denominacion_curso',
            'credito_horario_total', 'destinatarios', 'cupo',
            'calendario_actividades', 'fecha_elevar_nomina',
            'objetivos', 'contenidos_minimos', 'programa',
            'sistema_evaluacion', 'bibliografia', 'costos_financiamiento',
        ]
        widgets = {
            'denominacion_curso':     forms.TextInput(attrs=_T),
            'credito_horario_total':  forms.NumberInput(attrs=_TN),
            'destinatarios':          forms.Textarea(attrs=_TA(3)),
            'cupo':                   forms.NumberInput(attrs=_TN),
            'calendario_actividades': forms.Textarea(attrs=_TA(6)),
            'fecha_elevar_nomina':    forms.DateInput(attrs={**_T, 'type': 'date'}),
            'objetivos':              forms.Textarea(attrs=_TA(5)),
            'contenidos_minimos':     forms.Textarea(attrs=_TA(4)),
            'programa':               forms.Textarea(attrs=_TA(8)),
            'sistema_evaluacion':     forms.Textarea(attrs=_TA(4)),
            'bibliografia':           forms.Textarea(attrs=_TA(5)),
            'costos_financiamiento':  forms.Textarea(attrs=_TA(4)),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True


_DETALLE_TALLER = {'titulo', 'documento', 'institucion', 'email', 'telefono'}


class MiembroEquipoTallerForm(forms.ModelForm):
    class Meta:
        model = MiembroEquipoTaller
        fields = ['rol', 'nombre', 'titulo', 'documento', 'institucion', 'email', 'telefono']
        widgets = {
            'rol':        forms.Select(attrs={'class': 'form-select equipo-taller-rol'}),
            'nombre':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido, Nombre'}),
            'titulo':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Lic., Dr., Prof.'}),
            'documento':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DNI'}),
            'institucion': forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono / FAX'}),
        }

    def clean(self):
        cleaned = super().clean()
        from .models import ROL_TALLER_CON_DETALLE
        if cleaned.get('rol') in ROL_TALLER_CON_DETALLE and not cleaned.get('DELETE'):
            for f in _DETALLE_TALLER:
                if not cleaned.get(f):
                    self.add_error(f, 'Requerido para este rol.')
        return cleaned


class EquipoTallerFormSetBase(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        activos = [
            f.cleaned_data for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
        ]
        roles = {d.get('rol') for d in activos}
        tiene_responsable  = bool(roles & {'responsable', 'responsable_coordinador'})
        tiene_coordinador  = bool(roles & {'coordinador', 'responsable_coordinador'})
        if not tiene_responsable:
            raise forms.ValidationError('Debe haber al menos un Responsable en el equipo.')
        if not tiene_coordinador:
            raise forms.ValidationError('Debe haber al menos un Coordinador en el equipo.')


EquipoTallerFormSet = inlineformset_factory(
    SolicitudTaller,
    MiembroEquipoTaller,
    form=MiembroEquipoTallerForm,
    formset=EquipoTallerFormSetBase,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ActaConsejoTallerForm(forms.Form):
    acta_consejo_departamental = forms.FileField(
        label='Acta Consejo Departamental (PDF)',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
    )

    def clean_acta_consejo_departamental(self):
        f = self.cleaned_data.get('acta_consejo_departamental')
        if f and not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Solo se aceptan archivos PDF.')
        return f
