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

from .models import Lugar, Categoria, PerfilUsuario, Resena, Evento, VisitaFisica, PrediccionTendencia
from .ml_engine import obtener_recomendaciones_rf, ejecutar_batch_predictivo_semanal
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.utils.dateparse import parse_datetime
from django.db import IntegrityError

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

    # Validar rango geográfico real y evitar NaN / Inf
    if not (-90.0 <= lat_usr <= 90.0) or not (-180.0 <= lon_usr <= 180.0):
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
            try:
                VisitaFisica.objects.create(
                    lugar=lugar,
                    usuario=usuario_actual,
                    latitud_turista=round(lat_usr, 6),
                    longitud_turista=round(lon_usr, 6),
                    distancia_metros=round(distancia, 2),
                    fecha_visita=hoy
                )
                Lugar.objects.filter(id=lugar.id).update(visitas=F('visitas') + 1)
            except IntegrityError:
                pass

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
        datos, error = _validar_datos_lugar(request)
        if error:
            messages.error(request, error)
            return render(request, 'admin_lugar_form.html', {'categorias': categorias})

        nuevo_lugar = Lugar.objects.create(**datos)
        messages.success(request, f"✅ Atractivo turístico '{nuevo_lugar.nombre}' registrado con éxito.")
        return redirect('admin_lugares_lista')

    return render(request, 'admin_lugar_form.html', {'categorias': categorias})


@staff_member_required
def admin_lugar_editar(request, lugar_id):
    lugar = get_object_or_404(Lugar, id=lugar_id)
    categorias = Categoria.objects.all()

    if request.method == 'POST':
        datos, error = _validar_datos_lugar(request, lugar_actual=lugar)
        if error:
            messages.error(request, error)
            return render(request, 'admin_lugar_form.html', {'lugar': lugar, 'categorias': categorias})

        lugar.nombre = datos['nombre']
        lugar.descripcion = datos['descripcion']
        lugar.categoria_id = datos['categoria_id']
        lugar.latitud = datos['latitud']
        lugar.longitud = datos['longitud']
        lugar.precio = datos['precio']
        lugar.horario = datos['horario']
        lugar.direccion = datos['direccion']
        lugar.telefono = datos['telefono']

        if datos['imagen']:
            lugar.imagen = datos['imagen']

        lugar.save()
        messages.success(request, f"✅ Atractivo '{lugar.nombre}' actualizado correctamente.")
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


# HU02 / HU03 / HU05: Catálogo y Búsqueda (PROTEGIDO)
@login_required
def index(request):
    if request.user.is_authenticated:
        perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
        if not perfil.intereses.exists() or perfil.edad is None:
            return redirect('perfil')
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
        'categoria_icono': l.categoria.icono if (l.categoria and l.categoria.icono) else 'fa-solid fa-map-pin',
        'latitud': l.latitud,
        'longitud': l.longitud,
        'precio': float(l.precio),
        'imagen_url': l.imagen.url if l.imagen else ''
    } for l in lugares]

    return JsonResponse({'lugares': data, 'total': len(data)})


def detalle_lugar(request, lugar_id):
    lugar = get_object_or_404(Lugar, id=lugar_id)
    resenas = lugar.resenas.all().order_by('-fecha')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "⚠️ Debes iniciar sesión para publicar una reseña.")
            return redirect('login')

        comentario_texto = request.POST.get('comentario', '').strip()
        calificacion_raw = request.POST.get('calificacion', '').strip()

        # 1. Validar calificación numérica estricta (1 a 5 estrellas)
        if not calificacion_raw.isdigit() or int(calificacion_raw) not in range(1, 6):
            messages.error(request, "⚠️ Selecciona una calificación válida entre 1 y 5 estrellas.")
            return redirect('detalle_lugar', lugar_id=lugar.id)

        # 2. Validar longitud del comentario (evitar vacíos, puntos sueltos o textos excesivos)
        if len(comentario_texto) < 5:
            messages.error(request, "⚠️ Tu comentario es muy corto (mínimo 5 caracteres).")
            return redirect('detalle_lugar', lugar_id=lugar.id)

        if len(comentario_texto) > 600:
            messages.error(request, "⚠️ Tu comentario excede el límite permitido de 600 caracteres.")
            return redirect('detalle_lugar', lugar_id=lugar.id)

        # 3. Filtro de palabras inapropiadas ampliado
        palabras_prohibidas = [
            'insulto1', 'obsceno2', 'idiota', 'estupido', 'estúpido',
            'imbecil', 'imbécil', 'mierda', 'puta', 'carajo', 'basura'
        ]
        if any(palabra in comentario_texto.lower() for palabra in palabras_prohibidas):
            messages.error(request, "⚠️ Tu comentario contiene lenguaje inapropiado no permitido en la plataforma.")
            return redirect('detalle_lugar', lugar_id=lugar.id)

        # 4. Evitar doble reseña idéntica consecutiva del mismo usuario
        if Resena.objects.filter(lugar=lugar, usuario=request.user, comentario__iexact=comentario_texto).exists():
            messages.warning(request, "ℹ️ Ya habías publicado exactamente esta misma reseña para este atractivo.")
            return redirect('detalle_lugar', lugar_id=lugar.id)

        Resena.objects.create(
            lugar=lugar,
            usuario=request.user,
            calificacion=int(calificacion_raw),
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

def _validar_datos_lugar(request, lugar_actual=None):
    """Helper centralizado para validar creación y edición de atractivos turísticos."""
    nombre = request.POST.get('nombre', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    categoria_id = request.POST.get('categoria', '').strip()
    lat_raw = request.POST.get('latitud', '').strip().replace(',', '.')
    lon_raw = request.POST.get('longitud', '').strip().replace(',', '.')
    precio_raw = request.POST.get('precio', '0.00').strip().replace(',', '.')
    horario = request.POST.get('horario', '08:00 AM - 06:00 PM').strip()
    direccion = request.POST.get('direccion', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    imagen = request.FILES.get('imagen')

    if not nombre or len(nombre) < 3 or len(nombre) > 200:
        return None, "⚠️ El nombre del atractivo es obligatorio (entre 3 y 200 caracteres)."

    if not descripcion or len(descripcion) < 10:
        return None, "⚠️ La descripción debe tener al menos 10 caracteres."

    if categoria_id and (not categoria_id.isdigit() or not Categoria.objects.filter(id=int(categoria_id)).exists()):
        return None, "⚠️ La categoría seleccionada no es válida."

    # Validar coordenadas dentro del perímetro de Pucusana / Lima Sur para Leaflet.js
    try:
        latitud = float(lat_raw) if lat_raw else (lugar_actual.latitud if lugar_actual else -12.4830)
        longitud = float(lon_raw) if lon_raw else (lugar_actual.longitud if lugar_actual else -76.7960)
    except ValueError:
        return None, "⚠️ Latitud y longitud deben ser valores numéricos decimales válidos."

    if not (-12.65 <= latitud <= -12.30) or not (-77.00 <= longitud <= -76.60):
        return None, "⚠️ Las coordenadas están fuera del distrito de Pucusana (Lat: -12.48 aprox., Lon: -76.79 aprox.)."

    # Validar precio >= 0
    try:
        precio = Decimal(precio_raw) if precio_raw else Decimal('0.00')
    except InvalidOperation:
        return None, "⚠️ El precio debe ser un monto numérico válido (ej. 0.00 o 15.50)."

    if precio < Decimal('0.00') or precio > Decimal('9999.99'):
        return None, "⚠️ El precio debe estar entre S/ 0.00 y S/ 9999.99."

    # Validar teléfono opcional (solo dígitos, espacios, +, - y paréntesis)
    if telefono and not all(c.isdigit() or c in ' +-()' for c in telefono):
        return None, "⚠️ El teléfono contiene caracteres no válidos."

    # Validar imagen (tipo MIME y tamaño máximo 5 MB)
    if imagen:
        tipos_permitidos = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
        if imagen.content_type not in tipos_permitidos:
            return None, "⚠️ Formato de imagen no permitido. Usa JPG, PNG o WEBP."
        if imagen.size > 5 * 1024 * 1024:
            return None, "⚠️ La imagen supera el tamaño máximo permitido de 5 MB."

    datos = {
        'nombre': nombre,
        'descripcion': descripcion,
        'categoria_id': int(categoria_id) if categoria_id else None,
        'latitud': round(latitud, 6),
        'longitud': round(longitud, 6),
        'precio': precio,
        'horario': horario[:100] if horario else "08:00 AM - 06:00 PM",
        'direccion': direccion[:255],
        'telefono': telefono[:20],
        'imagen': imagen,
    }
    return datos, None

@staff_member_required
def evento_crear(request):
    categorias = Categoria.objects.all()
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        categoria_id = request.POST.get('categoria', '').strip()
        fecha_inicio_raw = request.POST.get('fecha_inicio', '').strip()
        fecha_fin_raw = request.POST.get('fecha_fin', '').strip()
        ubicacion = request.POST.get('ubicacion', '').strip()
        imagen = request.FILES.get('imagen')

        if not titulo or len(titulo) < 4:
            messages.error(request, "⚠️ El título del evento es obligatorio (mínimo 4 caracteres).")
            return render(request, 'admin_evento_form.html', {'categorias': categorias})

        if not descripcion or len(descripcion) < 10:
            messages.error(request, "⚠️ Ingresa una descripción detallada del evento (mínimo 10 caracteres).")
            return render(request, 'admin_evento_form.html', {'categorias': categorias})

        if not ubicacion or len(ubicacion) < 3:
            messages.error(request, "⚠️ La ubicación del evento en Pucusana es obligatoria.")
            return render(request, 'admin_evento_form.html', {'categorias': categorias})

        fecha_inicio = parse_datetime(fecha_inicio_raw)
        fecha_fin = parse_datetime(fecha_fin_raw)

        if not fecha_inicio or not fecha_fin:
            messages.error(request, "⚠️ Debes ingresar fechas y horas de inicio y fin válidas.")
            return render(request, 'admin_evento_form.html', {'categorias': categorias})

        if fecha_fin <= fecha_inicio:
            messages.error(request, "⚠️ La fecha y hora de finalización debe ser posterior a la de inicio.")
            return render(request, 'admin_evento_form.html', {'categorias': categorias})

        if imagen:
            if imagen.content_type not in ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']:
                messages.error(request, "⚠️ El flyer del evento debe ser una imagen JPG, PNG o WEBP.")
                return render(request, 'admin_evento_form.html', {'categorias': categorias})
            if imagen.size > 5 * 1024 * 1024:
                messages.error(request, "⚠️ El flyer supera el límite máximo de 5 MB.")
                return render(request, 'admin_evento_form.html', {'categorias': categorias})

        Evento.objects.create(
            titulo=titulo[:200],
            descripcion=descripcion,
            categoria_id=int(categoria_id) if categoria_id.isdigit() else None,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            ubicacion=ubicacion[:255],
            imagen=imagen,
            creado_por=request.user
        )
        messages.success(request, "✅ Evento registrado con éxito en la agenda municipal.")
        return redirect('eventos_publicos')

    return render(request, 'admin_evento_form.html', {'categorias': categorias})


def registro(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        correo_ingresado = request.POST.get('email', '').strip().lower()

        # 1. Validar correo obligatorio y formato válido
        if not correo_ingresado:
            messages.error(request, "⚠️ El correo electrónico es obligatorio.")
            return render(request, 'registro.html', {'form': form})

        try:
            validate_email(correo_ingresado)
        except ValidationError:
            messages.error(request, "⚠️ Ingresa un correo electrónico con formato válido (ej. usuario@dominio.com).")
            return render(request, 'registro.html', {'form': form})

        # 2. Validar unicidad de correo
        if User.objects.filter(email__iexact=correo_ingresado).exists():
            messages.error(request, "⚠️ El correo electrónico ya se encuentra registrado en Explora Pucusana.")
            return render(request, 'registro.html', {'form': form})

        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.email = correo_ingresado
            usuario.save()
            PerfilUsuario.objects.get_or_create(usuario=usuario)
            login(request, usuario, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"¡Registro completado con éxito! Bienvenido(a), {usuario.username}.")
            return redirect('perfil')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"⚠️ {error}")
    else:
        form = UserCreationForm()

    return render(request, 'registro.html', {'form': form})


@login_required
def perfil(request):
    perfil_obj, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    todas_categorias = Categoria.objects.all()

    if request.method == 'POST':
        edad_raw = request.POST.get('edad', '').strip()
        nacionalidad_raw = request.POST.get('nacionalidad', '').strip()
        intereses_raw = request.POST.getlist('intereses')

        # 1. Validar edad (numérica y rango realista 10 - 100 años)
        if not edad_raw or not edad_raw.isdigit():
            messages.error(request, "⚠️ Debes ingresar una edad válida en números enteros.")
            return redirect('perfil')

        edad_val = int(edad_raw)
        if edad_val < 10 or edad_val > 100:
            messages.error(request, "⚠️ La edad debe estar comprendida entre 10 y 100 años.")
            return redirect('perfil')

        # 2. Validar nacionalidad (obligatoria, longitud y sin solo números/símbolos)
        if not nacionalidad_raw or len(nacionalidad_raw) < 3 or len(nacionalidad_raw) > 60:
            messages.error(request, "⚠️ Ingresa una nacionalidad válida (entre 3 y 60 caracteres).")
            return redirect('perfil')

        if any(char.isdigit() for char in nacionalidad_raw):
            messages.error(request, "⚠️ La nacionalidad no puede contener números.")
            return redirect('perfil')

        # 3. Validar selección de intereses válida para el modelo Random Forest
        ids_validos = list(
            Categoria.objects.filter(id__in=[i for i in intereses_raw if i.isdigit()]).values_list('id', flat=True)
        )
        if not ids_validos:
            messages.error(request, "⚠️ Selecciona al menos una categoría de interés para personalizar tus recomendaciones con IA.")
            return redirect('perfil')

        perfil_obj.edad = edad_val
        perfil_obj.nacionalidad = nacionalidad_raw
        perfil_obj.intereses.set(ids_validos)
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
    categorias = Categoria.objects.annotate(total=Count('lugares')).order_by('-total')
    nombres_categorias = [c.nombre for c in categorias]
    totales_categorias = [c.total for c in categorias]

    total_lugares = Lugar.objects.count()
    total_visitas = VisitaFisica.objects.count()
    total_resenas = Resena.objects.count()
    promedio_general = Resena.objects.aggregate(prom=Avg('calificacion'))['prom'] or 0.0

    lugares_top = Lugar.objects.annotate(
        promedio=Avg('resenas__calificacion')
    ).exclude(promedio__isnull=True).order_by('-promedio')[:5]

    nombres_lugares = [l.nombre for l in lugares_top]
    promedios_lugares = [round(float(l.promedio or 0.0), 2) for l in lugares_top]

    contexto = {
        'nombres_categorias': json.dumps(nombres_categorias),
        'totales_categorias': json.dumps(totales_categorias),
        'nombres_lugares': json.dumps(nombres_lugares),
        'promedios_lugares': json.dumps(promedios_lugares),
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
    if not PrediccionTendencia.objects.filter(fecha_proyectada__gte=hoy).exists():
        ejecutar_batch_predictivo_semanal()

    predicciones = PrediccionTendencia.objects.filter(
        fecha_proyectada__gte=hoy
    ).select_related('lugar').order_by('fecha_proyectada')

    fechas_dict = {}
    for p in predicciones:
        f_str = p.fecha_proyectada.strftime('%a %d/%m')
        fechas_dict[f_str] = fechas_dict.get(f_str, 0) + p.afluencia_estimada

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