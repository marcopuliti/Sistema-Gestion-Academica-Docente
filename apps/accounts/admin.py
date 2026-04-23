from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from .models import CustomUser

admin.site.unregister(Group)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'email', 'rol', 'departamento', 'is_active')
    list_filter = ('rol', 'departamento', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'legajo')

    fieldsets = UserAdmin.fieldsets + (
        ('Información Docente', {
            'fields': ('rol', 'departamento', 'legajo', 'telefono'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Docente', {
            'fields': ('rol', 'departamento', 'legajo', 'telefono'),
        }),
    )
