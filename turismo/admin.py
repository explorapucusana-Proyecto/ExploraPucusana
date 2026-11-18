from decimal import Decimal
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
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

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if len(nombre) < 3:
            raise ValidationError("El nombre de la categoría debe tener al menos 3 caracteres.")
        return nombre


class LugarAdminForm(forms.ModelForm):
    class Meta:
        model = Lugar
        fields = '__all__'

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if len(nombre) < 3:
            raise ValidationError("El nombre del atractivo debe tener al menos 3 caracteres.")
        return nombre

    def clean_descripcion(self):
        descripcion = (self.cleaned_data.get('descripcion') or '').strip()
        if len(descripcion) < 10:
            raise ValidationError("La descripción debe tener al menos 10 caracteres.")
        return descripcion

    def clean_latitud(self):
        lat = self.cleaned_data.get('latitud')
        if lat is not None and not (-12.65 <= lat <= -12.30):
            raise ValidationError("La latitud está fuera del perímetro de Pucusana (debe estar entre -12.65 y -12.30).")
        return lat

    def clean_longitud(self):
        lon = self.cleaned_data.get('longitud')
        if lon is not None and not (-77.00 <= lon <= -76.60):
            raise ValidationError("La longitud está fuera del perímetro de Pucusana (debe estar entre -77.00 y -76.60).")
        return lon

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio < Decimal('0.00'):
            raise ValidationError("El precio de entrada no puede ser negativo.")
        return precio


class EventoAdminForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = '__all__'

    def clean_titulo(self):
        titulo = (self.cleaned_data.get('titulo') or '').strip()
        if len(titulo) < 4:
            raise ValidationError("El título del evento debe tener al menos 4 caracteres.")
        return titulo

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        fin = cleaned_data.get('fecha_fin')
        if inicio and fin and fin <= inicio:
            raise ValidationError("La fecha y hora de finalización debe ser posterior a la fecha y hora de inicio.")
        return cleaned_data


class PerfilAdminForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = '__all__'

    def clean_edad(self):
        edad = self.cleaned_data.get('edad')
        if edad is not None and not (10 <= edad <= 100):
            raise ValidationError("La edad del turista debe estar entre 10 y 100 años.")
        return edad

    def clean_nacionalidad(self):
        nac = (self.cleaned_data.get('nacionalidad') or '').strip()
        if nac and (len(nac) < 3 or any(c.isdigit() for c in nac)):
            raise ValidationError("Ingresa una nacionalidad válida (solo letras, mínimo 3 caracteres).")
        return nac


class ResenaAdminForm(forms.ModelForm):
    class Meta:
        model = Resena
        fields = '__all__'

    def clean_calificacion(self):
        cal = self.cleaned_data.get('calificacion')
        if cal is not None and cal not in range(1, 6):
            raise ValidationError("La calificación debe estar entre 1 y 5 estrellas.")
        return cal

    def clean_comentario(self):
        com = (self.cleaned_data.get('comentario') or '').strip()
        if len(com) < 5:
            raise ValidationError("El comentario debe tener al menos 5 caracteres.")
        return com


class CategoriaAdmin(admin.ModelAdmin):
    form = CategoriaAdminForm
    list_display = ('nombre', 'vista_previa_icono')
    search_fields = ('nombre',)

    @admin.display(description='Ícono')
    def vista_previa_icono(self, obj):
        if obj.icono and 'fa-' in obj.icono:
            return format_html(
                '<span style="display:inline-flex; align-items:center; gap:8px;">'
                '<i class="{}" style="font-size:18px; color:#2563eb;"></i>'
                '<code style="font-size:11px; color:#64748b;">{}</code>'
                '</span>',
                obj.icono, obj.icono
            )
        return '-'

    class Media:
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',)
        }


# Configuraciones para que el admin se vea profesional
class LugarAdmin(admin.ModelAdmin):
    form = LugarAdminForm
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
    form = PerfilAdminForm
    list_display = ('usuario', 'nacionalidad', 'edad')


class EventoAdmin(admin.ModelAdmin):
    form = EventoAdminForm
    list_display = ('titulo', 'categoria', 'fecha_inicio', 'fecha_fin', 'estado', 'ubicacion')
    list_filter = ('estado', 'categoria', 'fecha_inicio')
    search_fields = ('titulo', 'descripcion', 'ubicacion')


class ResenaAdmin(admin.ModelAdmin):
    form = ResenaAdminForm
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