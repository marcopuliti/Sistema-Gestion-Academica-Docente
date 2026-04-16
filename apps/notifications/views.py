from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from .models import Notificacion


@login_required
def lista_notificaciones(request):
    notificaciones = Notificacion.objects.filter(destinatario=request.user)
    notificaciones.filter(leida=False).update(leida=True)
    return render(request, 'notifications/lista.html', {'notificaciones': notificaciones})


@login_required
def marcar_todas_leidas(request):
    Notificacion.objects.filter(destinatario=request.user, leida=False).update(leida=True)
    return redirect('notifications:lista')
