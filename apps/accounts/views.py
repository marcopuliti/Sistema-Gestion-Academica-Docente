from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .emails import enviar_bienvenida
from .forms import LoginForm, RegistroForm, UsuarioCreacionForm, UsuarioEdicionForm, PerfilForm
from .models import CustomUser, TokenVerificacionEmail
from apps.tramites.decorators import solo_secretario


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


def _enviar_verificacion(request, usuario, token):
    url = request.build_absolute_uri(
        f'/cuentas/verificar/{token.token}/'
    )
    cuerpo = render_to_string('accounts/emails/verificacion.txt', {
        'nombre': usuario.get_full_name() or usuario.username,
        'url_verificacion': url,
    })
    try:
        send_mail(
            subject='Verificá tu cuenta — DELTA UNSL',
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('Error enviando verificación: %s', exc)


def registro(request):
    if request.user.is_authenticated:
        return redirect('tramites:dashboard')
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            token = TokenVerificacionEmail.objects.create(usuario=usuario)
            _enviar_verificacion(request, usuario, token)
            messages.success(
                request,
                f'Cuenta creada. Revisá tu email ({usuario.email}) para activarla.'
            )
            return redirect('accounts:login')
    else:
        form = RegistroForm()
    return render(request, 'accounts/registro.html', {'form': form})


def verificar_email(request, token):
    try:
        tok = TokenVerificacionEmail.objects.select_related('usuario').get(token=token)
    except TokenVerificacionEmail.DoesNotExist:
        messages.error(request, 'El enlace de verificación es inválido.')
        return redirect('accounts:login')

    if tok.esta_expirado():
        tok.usuario.delete()  # elimina también el token por CASCADE
        messages.error(request, 'El enlace expiró (24 h). Registrate nuevamente.')
        return redirect('accounts:registro')

    usuario = tok.usuario
    usuario.is_active = True
    usuario.save(update_fields=['is_active'])
    tok.delete()
    messages.success(request, '¡Cuenta verificada! Ya podés iniciar sesión.')
    return redirect('accounts:login')


@login_required
def perfil(request):
    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('accounts:perfil')
    else:
        form = PerfilForm(instance=request.user)
    pw_form = PasswordChangeForm(user=request.user)
    for field in pw_form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    return render(request, 'accounts/perfil.html', {'form': form, 'pw_form': pw_form})


@login_required
def cambiar_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('accounts:perfil')
        else:
            messages.error(request, 'Corregí los errores antes de continuar.')
    else:
        form = PasswordChangeForm(user=request.user)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    return render(request, 'accounts/perfil.html', {'form': PerfilForm(instance=request.user), 'pw_form': form})


@login_required
@solo_secretario
def lista_usuarios(request):
    usuarios = CustomUser.objects.all().order_by('last_name', 'first_name')
    return render(request, 'accounts/lista_usuarios.html', {'usuarios': usuarios})


@login_required
@solo_secretario
def crear_usuario(request):
    if request.method == 'POST':
        form = UsuarioCreacionForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password1']
            usuario = form.save()
            enviar_bienvenida(usuario, password)
            messages.success(request, f'Usuario creado. Se envió email de bienvenida a {usuario.email or "—"}.')
            return redirect('accounts:lista_usuarios')
    else:
        form = UsuarioCreacionForm()
    return render(request, 'accounts/form_usuario.html', {'form': form, 'titulo': 'Crear Usuario'})


@login_required
@solo_secretario
def editar_usuario(request, pk):
    usuario = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = UsuarioEdicionForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('accounts:lista_usuarios')
    else:
        form = UsuarioEdicionForm(instance=usuario)
    return render(request, 'accounts/form_usuario.html', {'form': form, 'titulo': 'Editar Usuario', 'usuario': usuario})


@login_required
@solo_secretario
def toggle_activo_usuario(request, pk):
    usuario = get_object_or_404(CustomUser, pk=pk)
    if usuario == request.user:
        messages.error(request, 'No podés desactivar tu propia cuenta.')
    else:
        usuario.is_active = not usuario.is_active
        usuario.save()
        estado = 'activado' if usuario.is_active else 'desactivado'
        messages.success(request, f'Usuario {estado} correctamente.')
    return redirect('accounts:lista_usuarios')
