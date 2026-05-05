from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def solo_administrador(view_func):
    """Secretario, Dirección Académica o Departamento de Estudiantes."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.es_administrador:
            messages.error(request, 'No tenés permisos para acceder a esta sección.')
            return redirect('tramites:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_admin_general(view_func):
    """Solo Secretario o Dirección Académica (no Departamento de Estudiantes)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.puede_admin_general:
            messages.error(request, 'No tenés permisos para acceder a esta sección.')
            return redirect('tramites:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_secretario(view_func):
    """Solo Secretario (gestión de usuarios)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.puede_gestionar_usuarios:
            messages.error(request, 'No tenés permisos para acceder a esta sección.')
            return redirect('tramites:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def puede_revisar(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.puede_revisar:
            messages.error(request, 'No tenés permisos para revisar trámites.')
            return redirect('tramites:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_director_departamento(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.es_director_departamento:
            messages.error(request, 'No tenés permisos para acceder a esta sección.')
            return redirect('tramites:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_director_carrera(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.es_director_carrera:
            messages.error(request, 'No tenés permisos para acceder a esta sección.')
            return redirect('tramites:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
