from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView

from .forms import LoginForm, UsuarioCreacionForm, UsuarioEdicionForm, PerfilForm
from .models import CustomUser
from apps.tramites.decorators import solo_administrador


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


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
    return render(request, 'accounts/perfil.html', {'form': form})


@login_required
@solo_administrador
def lista_usuarios(request):
    usuarios = CustomUser.objects.all().order_by('last_name', 'first_name')
    return render(request, 'accounts/lista_usuarios.html', {'usuarios': usuarios})


@login_required
@solo_administrador
def crear_usuario(request):
    if request.method == 'POST':
        form = UsuarioCreacionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('accounts:lista_usuarios')
    else:
        form = UsuarioCreacionForm()
    return render(request, 'accounts/form_usuario.html', {'form': form, 'titulo': 'Crear Usuario'})


@login_required
@solo_administrador
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
@solo_administrador
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
