from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from .models import CustomUser
from .validators import DOMINIO_REQUERIDO
from apps.tramites.models import DEPARTAMENTO_CHOICES


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Email institucional',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'usuario (sin @unsl.edu.ar)',
        }),
        help_text='Ingresá la parte de tu email antes del @unsl.edu.ar',
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'}),
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            try:
                user = CustomUser.objects.get(username=username)
                if not user.is_active and user.check_password(password):
                    raise forms.ValidationError(
                        'Tu cuenta aún no fue verificada. '
                        'Revisá tu casilla de email y hacé clic en el enlace de verificación.'
                    )
            except CustomUser.DoesNotExist:
                pass
        return super().clean()


class UsuarioCreacionForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = (
            'username', 'first_name', 'last_name', 'email',
            'rol', 'departamento', 'legajo', 'telefono',
        )
        labels = {
            'username': 'Nombre de usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Email',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class UsuarioEdicionForm(UserChangeForm):
    password = None

    class Meta:
        model = CustomUser
        fields = (
            'username', 'first_name', 'last_name', 'email',
            'rol', 'departamento', 'legajo', 'telefono',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class RegistroForm(UserCreationForm):
    first_name = forms.CharField(
        label='Nombre', max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre'}),
    )
    last_name = forms.CharField(
        label='Apellido', max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu apellido'}),
    )
    email = forms.EmailField(
        label=f'Email institucional ({DOMINIO_REQUERIDO})',
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': f'usuario{DOMINIO_REQUERIDO}'}),
    )
    departamento = forms.ChoiceField(
        label='Departamento',
        choices=DEPARTAMENTO_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'departamento', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Quitar el campo username heredado de UserCreationForm
        self.fields.pop('username', None)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if not email.endswith(DOMINIO_REQUERIDO):
            raise forms.ValidationError(f'El email debe pertenecer al dominio {DOMINIO_REQUERIDO}.')
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este email.')
        return email

    def clean_departamento(self):
        dep = self.cleaned_data.get('departamento', '')
        if not dep:
            raise forms.ValidationError('Seleccioná tu departamento.')
        return dep

    def _generar_username(self, email):
        base = email.split('@')[0].lower()
        username = base
        n = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f'{base}{n}'
            n += 1
        return username

    def save(self, commit=True):
        usuario = super().save(commit=False)
        email = self.cleaned_data['email']
        usuario.username = self._generar_username(email)
        usuario.email = email
        usuario.departamento = self.cleaned_data['departamento']
        usuario.is_active = False
        usuario.rol = CustomUser.DOCENTE
        if commit:
            usuario.save()
        return usuario


class PerfilForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'departamento', 'telefono')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
