from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import Categoria, Lugar, PerfilUsuario, Resena, Evento, VisitaFisica
from .widgets import IconPickerWidget


class CategoriaAdminForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = '__all__'
        widgets = {
            'icono': IconPickerWidget(),
        }


class CategoriaAdmin(admin.ModelAdmin):
    form = CategoriaAdminForm
    list_display = ('nombre', 'vista_previa_icono', 'icono')
    search_fields = ('nombre',)

    @admin.display(description='Ícono')
    def vista_previa_icono(self, obj):
        if obj.icono:
            return format_html('<i class="{}" style="font-size: 18px; color: #2563eb;"></i>', obj.icono)
        return '-'

    class Media:
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',)
        }


# Configuraciones para que el admin se vea profesional
class LugarAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'visitas', 'compartidos', 'latitud', 'longitud')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('categoria',)
    readonly_fields = ('visitas', 'compartidos')  # Para que no se alteren manualmente


class VisitaFisicaAdmin(admin.ModelAdmin):
    list_display = ('lugar', 'usuario', 'distancia_metros', 'fecha_visita', 'fecha_hora')
    list_filter = ('fecha_visita', 'lugar__categoria')
    search_fields = ('lugar__nombre', 'usuario__username')
    readonly_fields = ('lugar', 'usuario', 'latitud_turista', 'longitud_turista', 'distancia_metros', 'fecha_visita', 'fecha_hora')


class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nacionalidad', 'edad')


class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'fecha_inicio', 'fecha_fin', 'estado', 'ubicacion')
    list_filter = ('estado', 'categoria', 'fecha_inicio')
    search_fields = ('titulo', 'descripcion', 'ubicacion')


class ResenaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'lugar', 'calificacion', 'fecha')
    list_filter = ('calificacion', 'fecha')
    search_fields = ('usuario__username', 'lugar__nombre')


admin.site.register(Categoria, CategoriaAdmin)
admin.site.register(Lugar, LugarAdmin)
admin.site.register(VisitaFisica, VisitaFisicaAdmin)  # Auditoría de presencia física
admin.site.register(PerfilUsuario, PerfilAdmin)
admin.site.register(Resena, ResenaAdmin)
admin.site.register(Evento, EventoAdmin)

# Personalización institucional del panel
admin.site.site_header = "Administración de Explora Pucusana"
admin.site.site_title = "Explora Pucusana Admin"
admin.site.index_title = "Panel de Gestión Municipal"