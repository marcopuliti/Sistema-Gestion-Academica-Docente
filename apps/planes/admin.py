from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Carrera, PlanEstudio, Materia, MateriaEnPlan, AnioDictado, Docente, TribunalExaminador, SolicitudInformeTribunal, InformeTribunalesEnviado, SolicitudCambioTribunal, SolicitudCambioItem
from .management.commands.importar_materias import PlanParser, fetch_html




class AnioDictadoInline(admin.TabularInline):
    model = AnioDictado
    extra = 1
    fields = ('ano',)
    verbose_name = 'Año dictado'
    verbose_name_plural = 'Años que se están dictando'


class MateriaEnPlanInline(admin.TabularInline):
    model = MateriaEnPlan
    extra = 1
    fields = ('materia', 'ano', 'cuatrimestre', 'es_optativa', 'es_servicio', 'hs_totales', 'tope_hs')
    autocomplete_fields = ['materia']
    ordering = ('ano', 'cuatrimestre')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('materia')


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'departamento', 'duracion_anos', 'cantidad_planes')
    list_filter = ('departamento',)
    list_editable = ('departamento',)
    search_fields = ('codigo', 'nombre')
    ordering = ('nombre',)

    @admin.display(description='Planes')
    def cantidad_planes(self, obj):
        return obj.planes.count()


@admin.register(PlanEstudio)
class PlanEstudioAdmin(admin.ModelAdmin):
    list_display = ('carrera', 'codigo', 'vigente', 'activo', 'anos_dictados_display', 'cantidad_materias')
    list_display_links = ('codigo',)
    list_filter = ('vigente', 'activo', 'carrera')
    list_editable = ('vigente', 'activo')
    search_fields = ('codigo', 'carrera__nombre', 'carrera__codigo')
    autocomplete_fields = ['carrera']
    inlines = [AnioDictadoInline, MateriaEnPlanInline]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/importar-desde-url/',
                self.admin_site.admin_view(self.importar_desde_url_view),
                name='planes_planestudio_importar_desde_url',
            ),
        ]
        return custom + urls

    def importar_desde_url_view(self, request, pk):
        redirect_url = reverse('admin:planes_planestudio_change', args=[pk])

        try:
            plan = PlanEstudio.objects.select_related('carrera').get(pk=pk)
        except PlanEstudio.DoesNotExist:
            self.message_user(request, f'Plan con id={pk} no encontrado.', messages.ERROR)
            return HttpResponseRedirect(reverse('admin:planes_planestudio_changelist'))

        url = request.POST.get('url_plan', '').strip()
        if not url:
            self.message_user(request, 'Ingresá un URL antes de importar.', messages.WARNING)
            return HttpResponseRedirect(redirect_url)

        try:
            html = fetch_html(url)
        except Exception as e:
            self.message_user(request, f'No se pudo descargar la página: {e}', messages.ERROR)
            return HttpResponseRedirect(redirect_url)

        parser = PlanParser()
        parser.feed(html)

        if not parser.materias:
            self.message_user(request, 'No se encontraron materias en esa página.', messages.WARNING)
            return HttpResponseRedirect(redirect_url)

        creadas = 0
        existentes = 0
        for m in parser.materias:
            materia, _ = Materia.objects.get_or_create(
                codigo=m['codigo'],
                defaults={'nombre': m['nombre'].title()},
            )
            _, rel_creada = MateriaEnPlan.objects.get_or_create(
                materia=materia,
                plan=plan,
                defaults={'ano': m['ano'], 'cuatrimestre': m['cuatrimestre']},
            )
            if rel_creada:
                creadas += 1
            else:
                existentes += 1

        self.message_user(
            request,
            f'Plan {plan.codigo} ({plan.carrera.nombre}): {creadas} materias importadas, {existentes} ya existían.',
            messages.SUCCESS,
        )
        return HttpResponseRedirect(redirect_url)

    @admin.display(description='Años dictados')
    def anos_dictados_display(self, obj):
        return obj.get_anos_dictados_display()

    @admin.display(description='Materias')
    def cantidad_materias(self, obj):
        return obj.materias_en_plan.count()

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('carrera').prefetch_related('materias_en_plan', 'anos_dictados')


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'departamento', 'en_cuantos_planes')
    list_filter = ('departamento',)
    list_editable = ('departamento',)
    search_fields = ('codigo', 'nombre')
    ordering = ('nombre',)

    @admin.display(description='Planes')
    def en_cuantos_planes(self, obj):
        return obj.en_planes.count()

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('en_planes')


class TribunalInline(admin.StackedInline):
    model = TribunalExaminador
    extra = 0
    max_num = 1
    can_delete = True
    fields = (
        ('presidente_nombre', 'presidente_dni'),
        ('vocal_1_nombre', 'vocal_1_dni'),
        ('vocal_2_nombre', 'vocal_2_dni'),
        ('dia_semana', 'hora', 'permite_libres'),
    )
    verbose_name_plural = 'Tribunal Examinador'


@admin.register(MateriaEnPlan)
class MateriaEnPlanAdmin(admin.ModelAdmin):
    list_display = ('get_nombre_display', 'materia', 'plan', 'ano', 'cuatrimestre', 'es_optativa', 'es_servicio', 'hs_totales', 'tope_hs_display', 'tiene_tribunal')
    list_display_links = ('get_nombre_display',)
    list_filter = ('es_optativa', 'es_servicio', 'ano', 'cuatrimestre', 'plan__vigente', 'plan__activo', 'plan__carrera', 'plan')
    list_editable = ('hs_totales',)
    search_fields = ('materia__nombre', 'materia__codigo', 'plan__carrera__nombre')
    autocomplete_fields = ['materia', 'plan']
    ordering = ('plan__carrera__nombre', 'plan__codigo', 'ano', 'cuatrimestre')
    inlines = [TribunalInline]

    fieldsets = (
        ('Ubicación en el plan', {
            'fields': ('plan', 'materia', 'ano', 'cuatrimestre'),
        }),
        ('Datos académicos', {
            'fields': ('es_optativa', 'es_servicio', 'departamento_dictante', 'hs_totales', 'tope_hs'),
        }),
    )

    @admin.display(description='Nombre en el plan')
    def get_nombre_display(self, obj):
        return obj.get_nombre()

    @admin.display(description='Tope hs')
    def tope_hs_display(self, obj):
        if obj.tope_hs:
            return obj.tope_hs
        return format_html('<span style="color:#aaa">—</span>')

    @admin.display(description='Tribunal', boolean=True)
    def tiene_tribunal(self, obj):
        return hasattr(obj, 'tribunal')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('materia', 'plan__carrera').prefetch_related('tribunal')


@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dni')
    search_fields = ('nombre', 'dni')
    ordering = ('nombre',)


@admin.register(TribunalExaminador)
class TribunalExaminadorAdmin(admin.ModelAdmin):
    list_display = ('materia_en_plan', 'get_plan', 'get_ano', 'presidente_nombre', 'vocal_1_nombre', 'vocal_2_nombre', 'dia_semana', 'hora', 'permite_libres')
    list_filter = ('permite_libres', 'materia_en_plan__plan__vigente', 'materia_en_plan__plan__activo', 'materia_en_plan__plan__carrera', 'materia_en_plan__ano')
    search_fields = ('materia_en_plan__materia__nombre', 'presidente_nombre', 'vocal_1_nombre', 'vocal_2_nombre')
    autocomplete_fields = ['materia_en_plan']
    ordering = ('materia_en_plan__plan__carrera__nombre', 'materia_en_plan__plan__codigo', 'materia_en_plan__ano')

    @admin.display(description='Plan', ordering='materia_en_plan__plan__codigo')
    def get_plan(self, obj):
        return obj.materia_en_plan.plan

    @admin.display(description='Año', ordering='materia_en_plan__ano')
    def get_ano(self, obj):
        return f'{obj.materia_en_plan.ano}°'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'materia_en_plan__materia',
            'materia_en_plan__plan__carrera',
        )


@admin.register(SolicitudInformeTribunal)
class SolicitudInformeTribunalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'solicitante', 'activa')
    list_filter = ('activa',)
    readonly_fields = ('fecha', 'solicitante')
    ordering = ('-fecha',)


@admin.register(InformeTribunalesEnviado)
class InformeTribunalesEnviadoAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'departamento', 'director', 'fecha_envio')
    list_filter = ('departamento', 'solicitud')
    readonly_fields = ('fecha_envio',)
    ordering = ('-fecha_envio',)


class SolicitudCambioItemInline(admin.TabularInline):
    model = SolicitudCambioItem
    extra = 0
    can_delete = False
    fields = ('tribunal', 'presidente_nombre', 'vocal_1_nombre', 'vocal_2_nombre', 'dia_semana', 'hora', 'permite_libres')
    readonly_fields = ('tribunal',)


@admin.register(SolicitudCambioTribunal)
class SolicitudCambioTribunalAdmin(admin.ModelAdmin):
    list_display = ('fecha_creacion', 'departamento', 'director', 'estado', 'cantidad_items')
    list_filter = ('departamento', 'estado')
    readonly_fields = ('fecha_creacion', 'fecha_envio', 'director', 'departamento', 'estado')
    ordering = ('-fecha_creacion',)
    inlines = [SolicitudCambioItemInline]

    @admin.display(description='Items')
    def cantidad_items(self, obj):
        return obj.items.count()
