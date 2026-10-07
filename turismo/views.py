import os
import math
import json

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Q, F
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Lugar, Categoria, PerfilUsuario, Resena, Evento, VisitaFisica
from .ml_engine import obtener_recomendaciones_rf

from .models import PrediccionTendencia
from .ml_engine import ejecutar_batch_predictivo_semanal

RADIO_TOLERANCIA_METROS = 300.0  # Perímetro de presencia física en el atractivo en metros


# ==============================================================
# UTILIDADES MATEMÁTICAS (HAVERSINE)
# ==============================================================
def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia geodésica exacta en metros usando la fórmula de Haversine.
    """
    R = 6371000.0  # Radio medio terrestre en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# ==============================================================
# TELEMETRÍA Y ANALÍTICA (HU10 Y HU11)
# ==============================================================
@require_POST
def telemetria_visita_interna(request, lugar_id):
    """
    HU10: Procesamiento interno y silencioso en segundo plano.
    Evalúa coordenadas emitidas por el navegador sin interferir en la UI.
    Si la distancia es <= 300 m, certifica la visita física real.
    """
    try:
        data = json.loads(request.body)
        lat_usr = float(data.get('lat'))
        lon_usr = float(data.get('lon'))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'ignored'}, status=200)

    try:
        lugar = Lugar.objects.get(id=lugar_id)
    except Lugar.DoesNotExist:
        return JsonResponse({'status': 'ignored'}, status=200)

    distancia = calcular_distancia_metros(lat_usr, lon_usr, lugar.latitud, lugar.longitud)

    if distancia <= RADIO_TOLERANCIA_METROS:
        hoy = timezone.now().date()
        usuario_actual = request.user if request.user.is_authenticated else None

        ya_registrado = VisitaFisica.objects.filter(
            lugar=lugar,
            usuario=usuario_actual,
            fecha_visita=hoy
        ).exists()

        if not ya_registrado:
            VisitaFisica.objects.create(
                lugar=lugar,
                usuario=usuario_actual,
                latitud_turista=lat_usr,
                longitud_turista=lon_usr,
                distancia_metros=round(distancia, 2),
                fecha_visita=hoy
            )
            Lugar.objects.filter(id=lugar.id).update(visitas=F('visitas') + 1)

    return JsonResponse({'status': 'ok'})


@staff_member_required
def api_analytics_descriptivo(request):
    """
    HU11: Endpoint analítico que consolida indicadores descriptivos 
    de visitas físicas reales y satisfacción para alimentar Chart.js.
    """
    total_lugares = Lugar.objects.count()
    total_visitas_fisicas = VisitaFisica.objects.count()
    total_resenas = Resena.objects.count()
    promedio_general = Resena.objects.aggregate(prom=Avg('calificacion'))['prom'] or 0.0

    categorias_visitas = Categoria.objects.annotate(
        total_visitas=Count('lugares__visitas_verificadas')
    ).values('nombre', 'total_visitas')

    labels_cat = [c['nombre'] for c in categorias_visitas]
    data_cat = [c['total_visitas'] for c in categorias_visitas]

    distribucion_estrellas = [
        Resena.objects.filter(calificacion=i).count() for i in range(1, 6)
    ]

    resenas_positivas = Resena.objects.filter(calificacion__gte=4).count()
    indice_satisfaccion = round((resenas_positivas / total_resenas * 100), 2) if total_resenas > 0 else 0.0

    top_lugares = Lugar.objects.annotate(
        conteo_visitas=Count('visitas_verificadas'),
        rating_prom=Avg('resenas__calificacion')
    ).order_by('-conteo_visitas')[:5]

    top_nombres = [l.nombre for l in top_lugares]
    top_visitas = [l.conteo_visitas for l in top_lugares]
    top_ratings = [round(l.rating_prom or 0.0, 2) for l in top_lugares]

    return JsonResponse({
        'status': 'ok',
        'kpis': {
            'total_lugares': total_lugares,
            'total_visitas_fisicas': total_visitas_fisicas,
            'total_resenas': total_resenas,
            'calificacion_promedio': round(promedio_general, 2),
            'indice_satisfaccion': indice_satisfaccion
        },
        'grafico_categorias': {
            'labels': labels_cat,
            'series': data_cat
        },
        'grafico_satisfaccion': {
            'labels': ['1 Estrella', '2 Estrellas', '3 Estrellas', '4 Estrellas', '5 Estrellas'],
            'series': distribucion_estrellas
        },
        'grafico_top_atractivos': {
            'labels': top_nombres,
            'visitas': top_visitas,
            'ratings': top_ratings
        }
    })


# ==============================================================
# GESTIÓN MUNICIPAL ADMINISTRATIVA (CRUD HU10)
# ==============================================================
@staff_member_required
def admin_lugares_lista(request):
    lugares = Lugar.objects.select_related('categoria').annotate(
        total_resenas=Count('resenas'),
        promedio_rating=Avg('resenas__calificacion'),
        total_visitas_reales=Count('visitas_verificadas')
    ).order_by('-id')
    return render(request, 'admin_lugares_lista.html', {'lugares': lugares})


@staff_member_required
def admin_lugar_crear(request):
    categorias = Categoria.objects.all()
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        categoria_id = request.POST.get('categoria')
        latitud = request.POST.get('latitud')
        longitud = request.POST.get('longitud')
        precio = request.POST.get('precio', '0.00')
        horario = request.POST.get('horario', '08:00 AM - 06:00 PM')
        direccion = request.POST.get('direccion', '')
        telefono = request.POST.get('telefono', '')
        imagen = request.FILES.get('imagen')

        if not nombre or not descripcion:
            messages.error(request, "El nombre y la descripción son requeridos.")
            return render(request, 'admin_lugar_form.html', {'categorias': categorias})

        nuevo_lugar = Lugar.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            categoria_id=categoria_id if categoria_id else None,
            latitud=float(latitud) if latitud else -12.4830,
            longitud=float(longitud) if longitud else -76.7960,
            precio=precio if precio else 0.00,
            horario=horario,
            direccion=direccion,
            telefono=telefono,
            imagen=imagen
        )
        messages.success(request, f"Atractivo turístico '{nuevo_lugar.nombre}' registrado con éxito.")
        return redirect('admin_lugares_lista')

    return render(request, 'admin_lugar_form.html', {'categorias': categorias})


@staff_member_required
def admin_lugar_editar(request, lugar_id):
    lugar = get_object_or_404(Lugar, id=lugar_id)
    categorias = Categoria.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        if not nombre or not descripcion:
            messages.error(request, "El nombre y la descripción no pueden estar vacíos.")
            return render(request, 'admin_lugar_form.html', {'lugar': lugar, 'categorias': categorias})

        lugar.nombre = nombre
        lugar.descripcion = descripcion
        lugar.categoria_id = request.POST.get('categoria') or None

        if request.POST.get('latitud'):
            lugar.latitud = float(request.POST.get('latitud'))
        if request.POST.get('longitud'):
            lugar.longitud = float(request.POST.get('longitud'))

        lugar.precio = request.POST.get('precio', lugar.precio)
        lugar.horario = request.POST.get('horario', lugar.horario)
        lugar.direccion = request.POST.get('direccion', lugar.direccion)
        lugar.telefono = request.POST.get('telefono', lugar.telefono)

        if 'imagen' in request.FILES:
            lugar.imagen = request.FILES['imagen']

        lugar.save()
        messages.success(request, f"Atractivo '{lugar.nombre}' actualizado correctamente.")
        return redirect('admin_lugares_lista')

    return render(request, 'admin_lugar_form.html', {'lugar': lugar, 'categorias': categorias})


@staff_member_required
def admin_lugar_eliminar(request, lugar_id):
    lugar = get_object_or_404(Lugar, id=lugar_id)
    if request.method == 'POST':
        nombre = lugar.nombre
        lugar.delete()
        messages.success(request, f"Atractivo '{nombre}' eliminado correctamente.")
        return redirect('admin_lugares_lista')
    return render(request, 'admin_lugar_confirmar_eliminar.html', {'lugar': lugar})


# ==============================================================
# VISTAS PÚBLICAS Y TURISMO GENERAL
# ==============================================================
def landing(request):
    if request.user.is_authenticated:
        return redirect('index')
    return render(request, 'landing.html')


def index(request):
    lugares_lista = Lugar.objects.select_related('categoria').all()
    categorias_lista = Categoria.objects.all()

    busqueda = request.GET.get('buscar', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()

    if busqueda:
        lugares_lista = lugares_lista.filter(nombre__icontains=busqueda)

    if categoria_id and categoria_id.isdigit():
        lugares_lista = lugares_lista.filter(categoria_id=int(categoria_id))

    recomendados_ids = []
    if request.user.is_authenticated and not request.user.is_staff:
        lugares_lista, recomendados_ids = obtener_recomendaciones_rf(request.user, lugares_lista)

    contexto = {
        'lugares': lugares_lista,
        'categorias': categorias_lista,
        'recomendados_ids': recomendados_ids,
        'busqueda_actual': busqueda,
        'categoria_actual': int(categoria_id) if categoria_id.isdigit() else None
    }
    return render(request, 'index.html', contexto)


def api_buscar_lugares(request):
    busqueda = request.GET.get('buscar', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()

    lugares = Lugar.objects.select_related('categoria').all()
    if busqueda:
        lugares = lugares.filter(nombre__icontains=busqueda)
    if categoria_id and categoria_id.isdigit():
        lugares = lugares.filter(categoria_id=int(categoria_id))

    data = [{
        'id': l.id,
        'nombre': l.nombre,
        'descripcion': l.descripcion[:120] + '...',
        'categoria': l.categoria.nombre if l.categoria else 'General',
        'latitud': l.latitud,
        'longitud': l.longitud,
        'precio': float(l.precio),
        'imagen_url': l.imagen.url if l.imagen else ''
    } for l in lugares]

    return JsonResponse({'lugares': data, 'total': len(data)})


def detalle_lugar(request, lugar_id):
    lugar = get_object_or_404(Lugar, id=lugar_id)
    resenas = lugar.resenas.all().order_by('-fecha')

    if request.method == 'POST' and request.user.is_authenticated:
        comentario_texto = request.POST.get('comentario', '').strip()
        calificacion_num = request.POST.get('calificacion', '').strip()

        if comentario_texto and calificacion_num:
            palabras_prohibidas = ['insulto1', 'obsceno2']
            if any(palabra in comentario_texto.lower() for palabra in palabras_prohibidas):
                messages.error(request, "Tu comentario contiene palabras inapropiadas no permitidas en la plataforma.")
                return redirect('detalle_lugar', lugar_id=lugar.id)

            Resena.objects.create(
                lugar=lugar,
                usuario=request.user,
                calificacion=int(calificacion_num),
                comentario=comentario_texto
            )
            messages.success(request, "¡Tu reseña ha sido publicada exitosamente!")
            return redirect('detalle_lugar', lugar_id=lugar.id)

    contexto = {
        'lugar': lugar,
        'resenas': resenas
    }
    return render(request, 'detalle.html', contexto)


def registrar_compartido(request, lugar_id):
    if request.method == 'POST':
        lugar = get_object_or_404(Lugar, id=lugar_id)
        Lugar.objects.filter(id=lugar.id).update(compartidos=F('compartidos') + 1)
        lugar.refresh_from_db()
        return JsonResponse({'status': 'ok', 'compartidos': lugar.compartidos})
    return JsonResponse({'status': 'invalid'}, status=400)


def eventos_publicos(request):
    ahora = timezone.now()
    eventos = Evento.objects.filter(estado='publicado', fecha_fin__gte=ahora).order_by('fecha_inicio')
    return render(request, 'eventos.html', {'eventos': eventos})


@staff_member_required
def evento_crear(request):
    categorias = Categoria.objects.all()
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descripcion = request.POST.get('descripcion')
        categoria_id = request.POST.get('categoria')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        ubicacion = request.POST.get('ubicacion')

        if titulo and fecha_inicio and fecha_fin:
            Evento.objects.create(
                titulo=titulo,
                descripcion=descripcion,
                categoria_id=categoria_id if categoria_id else None,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                ubicacion=ubicacion,
                creado_por=request.user
            )
            messages.success(request, "Evento registrado con éxito en la agenda municipal.")
            return redirect('eventos_publicos')

    return render(request, 'admin_evento_form.html', {'categorias': categorias})


def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        correo_ingresado = request.POST.get('email', '').strip()

        if correo_ingresado and User.objects.filter(email__iexact=correo_ingresado).exists():
            messages.error(request, "⚠️ El correo electrónico ya se encuentra registrado en Explora Pucusana.")
            return render(request, 'registro.html', {'form': form})

        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.email = correo_ingresado
            usuario.save()
            PerfilUsuario.objects.create(usuario=usuario)
            login(request, usuario)
            messages.success(request, f"¡Registro completado con éxito! Bienvenido(a), {usuario.username}.")
            return redirect('perfil')
    else:
        form = UserCreationForm()

    return render(request, 'registro.html', {'form': form})


@login_required
def perfil(request):
    perfil_obj, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    todas_categorias = Categoria.objects.all()

    if request.method == 'POST':
        perfil_obj.edad = request.POST.get('edad') or None
        perfil_obj.nacionalidad = request.POST.get('nacionalidad', 'Peruano')
        intereses_seleccionados = request.POST.getlist('intereses')
        perfil_obj.intereses.set(intereses_seleccionados)
        perfil_obj.save()
        messages.success(request, "🎯 Preferencias actualizadas. El motor de Inteligencia Artificial ha reestructurado tu catálogo.")
        return redirect('index')

    contexto = {
        'perfil': perfil_obj,
        'categorias': todas_categorias,
        'intereses_actuales': perfil_obj.intereses.values_list('id', flat=True)
    }
    return render(request, 'perfil.html', contexto)


# ==============================================================
# DASHBOARD MUNICIPAL (HU11)
# ==============================================================
@staff_member_required
def dashboard_municipal(request):
    """
    Controlador principal del Dashboard Municipal.
    Pasa las variables consolidadas directamente al template para renderizado nativo
    y mantiene compatibilidad con los llamados asíncronos de Chart.js.
    """
    # 1. Datos para el gráfico de torta de categorías (ordenadas de mayor a menor)
    categorias = Categoria.objects.annotate(total=Count('lugares')).order_by('-total')
    nombres_categorias = [c.nombre for c in categorias]
    totales_categorias = [c.total for c in categorias]

    # 2. Métricas de cabecera (KPIs descriptivos)
    total_lugares = Lugar.objects.count()
    total_visitas = VisitaFisica.objects.count()
    total_resenas = Resena.objects.count()
    promedio_general = Resena.objects.aggregate(prom=Avg('calificacion'))['prom'] or 0.0

    # 3. Top 5 de atractivos mejor calificados
    lugares_top = Lugar.objects.annotate(
        promedio=Avg('resenas__calificacion')
    ).exclude(promedio__isnull=True).order_by('-promedio')[:5]

    nombres_lugares = [l.nombre for l in lugares_top]
    promedios_lugares = [round(float(l.promedio or 0.0), 2) for l in lugares_top]

    contexto = {
        # Serializado seguro para Chart.js
        'nombres_categorias': json.dumps(nombres_categorias),
        'totales_categorias': json.dumps(totales_categorias),
        'nombres_lugares': json.dumps(nombres_lugares),
        'promedios_lugares': json.dumps(promedios_lugares),
        # Variables numéricas para tarjetas de cabecera
        'total_lugares': total_lugares,
        'total_visitas': total_visitas,
        'total_resenas': total_resenas,
        'promedio_gral': round(promedio_general, 2),
    }
    return render(request, 'dashboard.html', contexto)


def mapa_turistico(request):
    lugares = Lugar.objects.all()
    return render(request, 'mapa.html', {'lugares': lugares})

@staff_member_required
def api_analytics_predictivo(request):
    """
    HU12: Devuelve la serie temporal de proyecciones para los próximos 7 días
    y las recomendaciones prescriptivas generadas por el batch.
    """
    hoy = timezone.now().date()
    # Si no hay predicciones vigentes, ejecutamos el batch automáticamente
    if not PrediccionTendencia.objects.filter(fecha_proyectada__gte=hoy).exists():
        ejecutar_batch_predictivo_semanal()

    predicciones = PrediccionTendencia.objects.filter(
        fecha_proyectada__gte=hoy
    ).select_related('lugar').order_by('fecha_proyectada')

    # Agrupación por fecha para el gráfico de línea temporal
    fechas_dict = {}
    for p in predicciones:
        f_str = p.fecha_proyectada.strftime('%a %d/%m')
        fechas_dict[f_str] = fechas_dict.get(f_str, 0) + p.afluencia_estimada

    # Prescripciones destacadas (alertas y oportunidades)
    alertas_prescriptivas = [{
        'lugar': p.lugar.nombre,
        'fecha': p.fecha_proyectada.strftime('%d/%m/%Y'),
        'demanda': p.nivel_demanda,
        'afluencia': p.afluencia_estimada,
        'accion': p.accion_prescriptiva
    } for p in predicciones.filter(nivel_demanda__in=["Alta", "Baja"])[:6]]

    return JsonResponse({
        'status': 'ok',
        'grafico_tendencia': {
            'fechas': list(fechas_dict.keys()),
            'afluencia_total': list(fechas_dict.values())
        },
        'alertas_prescriptivas': alertas_prescriptivas
    })
# turismo/views.py

# HU02 / HU03 / HU05: Catálogo y Búsqueda (PROTEGIDO)
@login_required
def index(request):
    lugares_lista = Lugar.objects.select_related('categoria').all()
    categorias_lista = Categoria.objects.all()
    
    busqueda = request.GET.get('buscar', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()
    
    if busqueda:
        lugares_lista = lugares_lista.filter(nombre__icontains=busqueda)
        
    if categoria_id and categoria_id.isdigit():
        lugares_lista = lugares_lista.filter(categoria_id=int(categoria_id))
        
    recomendados_ids = [] 
    if request.user.is_authenticated and not request.user.is_staff:
        lugares_lista, recomendados_ids = obtener_recomendaciones_rf(request.user, lugares_lista)
        
    contexto = {
        'lugares': lugares_lista,
        'categorias': categorias_lista, 
        'recomendados_ids': recomendados_ids,
        'busqueda_actual': busqueda,
        'categoria_actual': int(categoria_id) if categoria_id.isdigit() else None
    }
    return render(request, 'index.html', contexto)