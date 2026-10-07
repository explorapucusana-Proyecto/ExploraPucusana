import math
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# 1. Categorías (Para HU03 - Filtrado)
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    icono = models.CharField(max_length=50, default="📍", help_text="Emoji o clase de icono")

    def __str__(self):
        return self.nombre

# 2. Atractivos Turísticos (Para HU02, HU04, HU09)
class Lugar(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, related_name="lugares")
    imagen = models.ImageField(upload_to='lugares/', null=True, blank=True)
    
    # Geolocalización para el mapa interactivo (Leaflet.js)
    latitud = models.FloatField(default=-12.4830, help_text="Latitud decimal")
    longitud = models.FloatField(default=-76.7960, help_text="Longitud decimal")
    
    direccion = models.CharField(max_length=255, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="0 para gratis")
    horario = models.CharField(max_length=100, default="08:00 AM - 06:00 PM", blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    # HU09: Métrica de interacción al compartir
    compartidos = models.PositiveIntegerField(default=0)
    visitas = models.PositiveIntegerField(default=0)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lugar"
        verbose_name_plural = "Lugares"

    def __str__(self):
        return self.nombre

# 3. Perfil de Usuario (Para HU01, HU06 - Intereses)
class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfilusuario")
    intereses = models.ManyToManyField(Categoria, blank=True, related_name="interesados")
    edad = models.PositiveIntegerField(null=True, blank=True)
    nacionalidad = models.CharField(max_length=100, default="Peruano")

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# 4. Reseñas (Para HU08 - Feedback)
class Resena(models.Model):
    lugar = models.ForeignKey(Lugar, on_delete=models.CASCADE, related_name="resenas")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    calificacion = models.IntegerField(choices=[(i, i) for i in range(1, 6)]) # 1 a 5 estrellas
    comentario = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.lugar.nombre}"

# 5. Eventos Locales (Para HU07 - Agenda Municipal)
class Evento(models.Model):
    ESTADOS = [
        ('publicado', 'Publicado'),
        ('pendiente', 'Pendiente'),
    ]

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, related_name="eventos")
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    ubicacion = models.CharField(max_length=255)
    organizador = models.CharField(max_length=150, default="Municipalidad Distrital de Pucusana")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='publicado')
    imagen = models.ImageField(upload_to='eventos/', null=True, blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering = ['fecha_inicio']

    def __str__(self):
        return f"{self.titulo} ({self.fecha_inicio.strftime('%d/%m/%Y')})"

class VisitaFisica(models.Model):
    """
    Registro interno y silencioso de presencia física verificado por geofencing.
    Alimenta los módulos de Business Analytics (Chart.js y Random Forest Batch).
    """
    lugar = models.ForeignKey(Lugar, on_delete=models.CASCADE, related_name="visitas_verificadas")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    latitud_turista = models.FloatField()
    longitud_turista = models.FloatField()
    distancia_metros = models.FloatField(help_text="Distancia geodésica calculada en metros")
    fecha_visita = models.DateField(default=timezone.now)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Visita Física Verificada"
        verbose_name_plural = "Visitas Físicas Verificadas"
        unique_together = ('lugar', 'usuario', 'fecha_visita')

    def __str__(self):
        nombre_usr = self.usuario.username if self.usuario else "Anónimo"
        return f"Visita física [{nombre_usr}] en {self.lugar.nombre} ({self.fecha_visita})"

class PrediccionTendencia(models.Model):
    """
    HU12: Almacena las proyecciones de afluencia generadas por el 
    modelo Random Forest en modo Batch Semanal y la sugerencia prescriptiva.
    """
    lugar = models.ForeignKey(Lugar, on_delete=models.CASCADE, related_name="predicciones")
    fecha_proyectada = models.DateField()
    afluencia_estimada = models.PositiveIntegerField(help_text="Estimación de visitantes proyectados")
    nivel_demanda = models.CharField(max_length=20, default="Media")  # Baja, Media, Alta
    accion_prescriptiva = models.TextField(blank=True, help_text="Sugerencia de gestión para la municipalidad")
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Predicción de Tendencia"
        verbose_name_plural = "Predicciones de Tendencias"
        ordering = ['fecha_proyectada', '-afluencia_estimada']

    def __str__(self):
        return f"{self.lugar.nombre} - {self.fecha_proyectada}: {self.afluencia_estimada} visitas ({self.nivel_demanda})"

