from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Portada y Catálogo con IA
    path('', views.landing, name='landing'),
    path('explorar/', views.index, name='index'),
    path('lugar/<int:lugar_id>/', views.detalle_lugar, name='detalle_lugar'),
    path('mapa/', views.mapa_turistico, name='mapa'),

    # HU03: Búsqueda dinámica Fetch API (Sprint 3)
    path('api/buscar-lugares/', views.api_buscar_lugares, name='api_buscar_lugares'),

    # HU07: Agenda de Eventos Locales (Sprint 3)
    path('eventos/', views.eventos_publicos, name='eventos_publicos'),
    path('admin/eventos/crear/', views.evento_crear, name='evento_crear'),

    # HU09: Métrica al compartir en redes (Sprint 3)
    path('api/lugar/<int:lugar_id>/compartir/', views.registrar_compartido, name='registrar_compartido'),

    # Autenticación y Perfil de Usuario
    path('registro/', views.registro, name='registro'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('perfil/', views.perfil, name='perfil'),

    # Panel Administrativo y Dashboard
    path('dashboard/', views.dashboard_municipal, name='dashboard_municipal'),

    # HU10: Panel de Gestión Municipal (CRUD)
    path('gestion-municipal/lugares/', views.admin_lugares_lista, name='admin_lugares_lista'),
    path('gestion-municipal/lugares/crear/', views.admin_lugar_crear, name='admin_lugar_crear'),
    path('gestion-municipal/lugares/editar/<int:lugar_id>/', views.admin_lugar_editar, name='admin_lugar_editar'),
    path('gestion-municipal/lugares/eliminar/<int:lugar_id>/', views.admin_lugar_eliminar, name='admin_lugar_eliminar'),
    
    # Telemetría interna pasiva (Sin interacción de usuario)
    path('api/telemetria/lugar/<int:lugar_id>/', views.telemetria_visita_interna, name='telemetria_visita_interna'),

    # HU11: Dashboard Descriptivo Municipal
    path('gestion-municipal/dashboard/', views.dashboard_municipal, name='dashboard_municipal'),
    path('api/analytics/descriptivo/', views.api_analytics_descriptivo, name='api_analytics_descriptivo'),

    path('api/analytics/predictivo/', views.api_analytics_predictivo, name='api_analytics_predictivo'),

]
