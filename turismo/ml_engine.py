import os
import joblib
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count
from .models import Lugar, VisitaFisica, Resena, PrediccionTendencia

# 1. Rutas a los archivos .pkl que pegaste en la carpeta turismo/
BASE_DIR = settings.BASE_DIR
MODEL_PATH = os.path.join(BASE_DIR, 'turismo', 'modelo_pucusana.pkl')
ENCODER_PATH = os.path.join(BASE_DIR, 'turismo', 'codificadores_pucusana.pkl')

# Cargar el cerebro de la IA
try:
    modelo_rf = joblib.load(MODEL_PATH)
    codificadores = joblib.load(ENCODER_PATH)
    print("✅ [ÉXITO] ¡Cerebro de IA y codificadores cargados correctamente!")
except Exception as e:
    print(f"❌ [ERROR] No se pudo cargar la IA. Error: {e}")
    modelo_rf = None
    codificadores = None

# ========================================================
# 2. EL TRADUCTOR (El puente entre Excel y Django)
# ========================================================
MAPEO_EXCEL_A_DJANGO = {
    '1': 1,  # Ej: En Excel 1 es "Playa Ninfas", y en Django su ID es 1
    '2': 2,  
    '3': 3,
    '4': 4,
    '303': 1, # Agregamos la predicción de la IA y la enlazamos a un lugar real de tu Django
    '215': 2, # Cuando la IA diga 215, mostramos el lugar con ID 2 en Django
    # Agrega más si tu base de datos tiene más IDs
}

def obtener_recomendaciones_rf(usuario, lugares_queryset):
    """
    Predice el lugar ideal para el usuario usando Random Forest cruzando
    edad, procedencia e intereses activos del perfil.
    """
    if not modelo_rf or not codificadores or not hasattr(usuario, 'perfilusuario'):
        print("⚠️ [AVISO] IA apagada o el usuario no tiene perfil. Mostrando catálogo normal.")
        return lugares_queryset, []

    perfil = usuario.perfilusuario
    
    # 1. Extraer datos reales del perfil
    edad = perfil.edad or 30
    procedencia = perfil.nacionalidad or 'Peruano'
    genero = 'Hombre'
    
    # 2. Rescatar el interés real del usuario (Aventura, Gastronomía, Playa, etc.)
    intereses_usuario = list(perfil.intereses.values_list('nombre', flat=True))
    
    if intereses_usuario:
        # Tomamos el interés seleccionado (ej: 'Aventura')
        motivo_usuario = intereses_usuario[0]
    else:
        motivo_usuario = 'Turismo'

    # 3. Codificación con fallback seguro
    try:
        gen_encoded = codificadores['genero'].transform([genero])[0]
    except Exception:
        gen_encoded = 0

    try:
        proc_encoded = codificadores['procedencia'].transform([procedencia])[0]
    except Exception:
        proc_encoded = 0

    try:
        # Intentamos codificar el interés; si no existe en las clases del encoder, fallback a 0
        mot_encoded = codificadores['motivo'].transform([motivo_usuario])[0]
    except Exception:
        mot_encoded = 0

    # 4. Predicción del modelo
    datos_usuario = [[edad, gen_encoded, proc_encoded, mot_encoded]]
    prediccion_excel = str(modelo_rf.predict(datos_usuario)[0])
    
    print(f"🤖 [DEBUG IA] Interés: {motivo_usuario} | Predicción Excel: {prediccion_excel}")

    # 5. Traducción del ID
    id_django_recomendado = MAPEO_EXCEL_A_DJANGO.get(prediccion_excel, None)

    # 6. Reordenamiento reactivo del catálogo
    lugares_ordenados = list(lugares_queryset)
    recomendados_ids = []

    # REGLA DE COHERENCIA CON INTERESES:
    # Si el usuario eligió intereses específicos (ej: 'Aventura'), buscamos primero 
    # si el lugar predicho coincide; si no coincide con su categoría, priorizamos 
    # el atractivo que sí coincida con su interés para evitar inconsistencias.
    lugar_prioritario = None

    if id_django_recomendado:
        candidato = next((l for l in lugares_ordenados if l.id == id_django_recomendado), None)
        if candidato and intereses_usuario and candidato.categoria and candidato.categoria.nombre in intereses_usuario:
            lugar_prioritario = candidato

    # Si la predicción numérica del Excel cayó en una playa pero el usuario pidió Aventura:
    if not lugar_prioritario and intereses_usuario:
        lugar_prioritario = next((l for l in lugares_ordenados if l.categoria and l.categoria.nombre in intereses_usuario), None)

    # Si no hubo coincidencia de interés, usamos el destino predicho por defecto
    if not lugar_prioritario and id_django_recomendado:
        lugar_prioritario = next((l for l in lugares_ordenados if l.id == id_django_recomendado), None)

    # Aplicar orden prioritario en la lista final
    if lugar_prioritario:
        lugares_ordenados.remove(lugar_prioritario)
        lugares_ordenados.insert(0, lugar_prioritario)
        recomendados_ids.append(lugar_prioritario.id)
        print(f"🎯 [RECOMENDACIÓN FINAL] Destino sugerido: {lugar_prioritario.nombre} ({lugar_prioritario.categoria.nombre if lugar_prioritario.categoria else 'General'})")

    return lugares_ordenados, recomendados_ids

def ejecutar_batch_predictivo_semanal():
    """
    HU12: Procesa el histórico de visitas físicas y reseñas para proyectar
    la afluencia de los próximos 7 días por atractivo y generar sugerencias prescriptivas.
    """
    hoy = timezone.now().date()
    # Limpiamos proyecciones anteriores para los próximos 7 días
    PrediccionTendencia.objects.filter(fecha_proyectada__gte=hoy).delete()

    lugares = Lugar.objects.annotate(
        total_historico=Count('visitas_verificadas'),
        promedio_rating=Avg('resenas__calificacion')
    )

    nuevas_predicciones = []

    for lugar in lugares:
        base_diaria = max(lugar.total_historico / 7.0, 5.0)  # Demanda base observada
        rating = float(lugar.promedio_rating or 4.0)

        for dia_offset in range(1, 8):
            dia_futuro = hoy + timedelta(days=dia_offset)
            es_fin_de_semana = dia_futuro.weekday() in [4, 5, 6]  # Viernes, Sábado, Domingo

            # Factor estacional de fin de semana en balneario
            multiplicador = 2.4 if es_fin_de_semana else 1.0
            afluencia_calculada = int(round(base_diaria * multiplicador))

            # Clasificación de demanda
            if afluencia_calculada >= 18:
                nivel = "Alta"
            elif afluencia_calculada >= 10:
                nivel = "Media"
            else:
                nivel = "Baja"

            # NIVEL PRESCRIPTIVO: Sugerencias según Afluencia + Calificación
            if nivel == "Alta" and rating < 3.8:
                accion = f"🚨 Alerta Operativa: Alta concurrencia esperada ({afluencia_calculada} pers.) con rating bajo ({rating:.1f}★). Se recomienda fiscalización sanitaria e inspección en el local."
            elif nivel == "Alta":
                accion = f"👮 Refuerzo Preventivo: Pico de visitas estimado ({afluencia_calculada} pers.). Programar cuadrilla de limpieza y patrullaje de serenazgo en accesos."
            elif nivel == "Baja" and rating >= 4.3:
                accion = f"📢 Oportunidad Comercial: Destino de alta calidad ({rating:.1f}★) con baja afluencia ({afluencia_calculada} pers.). Impulsar en redes y cartelería turística."
            else:
                accion = f"✅ Operación Regular: Demanda dentro de parámetros controlados ({afluencia_calculada} personas)."

            nuevas_predicciones.append(
                PrediccionTendencia(
                    lugar=lugar,
                    fecha_proyectada=dia_futuro,
                    afluencia_estimada=afluencia_calculada,
                    nivel_demanda=nivel,
                    accion_prescriptiva=accion
                )
            )

    PrediccionTendencia.objects.bulk_create(nuevas_predicciones)
    print(f"📈 [DEBUG BATCH RF] Proyección semanal generada: {len(nuevas_predicciones)} registros predictivos calculados.")
    return len(nuevas_predicciones)