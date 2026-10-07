from django.contrib import admin
from django.urls import path, include
from django.conf import settings # NUEVO
from django.conf.urls.static import static # NUEVO

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),  # 👈 Endpoint nativo para set_language
    path('accounts/', include('allauth.urls')),  # 👈 Endpoints OAuth de Google, Facebook, MS
    path('', include('turismo.urls')),
]

# NUEVO: Esto permite que Django sirva las imágenes subidas durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)