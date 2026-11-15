from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),  # 👈 Endpoint nativo para set_language
    path('accounts/', include('allauth.urls')),  # 👈 Endpoints OAuth de Google, Facebook, MS
    path('', include('turismo.urls')),

    # Servir archivos multimedia (lugares/ y eventos/) en local y producción (DEBUG=False)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]