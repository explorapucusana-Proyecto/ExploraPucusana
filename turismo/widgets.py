from django import forms
from django.utils.safestring import mark_safe

ICONOS_DISPONIBLES = [
    # Playas, Naturaleza y Aventura
    ('fa-solid fa-umbrella-beach', 'Playa / Balneario'),
    ('fa-solid fa-water', 'Mar / Bahía'),
    ('fa-solid fa-sun', 'Sol / Verano'),
    ('fa-solid fa-mountain-sun', 'Mirador / Acantilado'),
    ('fa-solid fa-tree', 'Parque / Naturaleza'),
    ('fa-solid fa-person-hiking', 'Caminata / Trekking'),
    ('fa-solid fa-campground', 'Camping / Aire libre'),
    ('fa-solid fa-binoculars', 'Avistamiento / Fauna'),
    ('fa-solid fa-fish', 'Pesca / Fauna marina'),
    ('fa-solid fa-feather', 'Aves / Isla'),

    # Náutica y Transporte
    ('fa-solid fa-ship', 'Paseo en bote / Yate'),
    ('fa-solid fa-sailboat', 'Velero / Deportes náuticos'),
    ('fa-solid fa-anchor', 'Muelle / Puerto'),
    ('fa-solid fa-life-ring', 'Seguridad / Salvavidas'),
    ('fa-solid fa-bus', 'Transporte / Paradero'),
    ('fa-solid fa-car', 'Estacionamiento / Acceso'),

    # Gastronomía
    ('fa-solid fa-utensils', 'Restaurante / Gastronomía'),
    ('fa-solid fa-shrimp', 'Cevichería / Mariscos'),
    ('fa-solid fa-mug-hot', 'Cafetería / Jugos'),
    ('fa-solid fa-ice-cream', 'Heladería / Postres'),
    ('fa-solid fa-martini-glass-citrus', 'Bar / Bebidas'),
    ('fa-solid fa-burger', 'Comida rápida / Snacks'),

    # Cultura, Historia y Eventos
    ('fa-solid fa-landmark', 'Patrimonio / Monumento'),
    ('fa-solid fa-church', 'Iglesia / Capilla'),
    ('fa-solid fa-masks-theater', 'Cultura / Teatro'),
    ('fa-solid fa-music', 'Música / Festivales'),
    ('fa-solid fa-calendar-days', 'Eventos / Agenda'),
    ('fa-solid fa-camera-retro', 'Punto fotográfico'),
    ('fa-solid fa-palette', 'Artesanía / Arte'),

    # Servicios, Alojamiento y Deportes
    ('fa-solid fa-hotel', 'Hotel / Hospedaje'),
    ('fa-solid fa-bed', 'Bungalows / Alojamiento'),
    ('fa-solid fa-store', 'Comercio / Mercado'),
    ('fa-solid fa-person-swimming', 'Natación'),
    ('fa-solid fa-bicycle', 'Ciclismo'),
    ('fa-solid fa-futbol', 'Deportes / Recreación'),
    ('fa-solid fa-heart', 'Favoritos / Destacados'),
    ('fa-solid fa-star', 'Imperdible / Top'),
    ('fa-solid fa-map-pin', 'Ubicación general'),
]


class IconPickerWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        value = value or 'fa-solid fa-map-pin'
        botones_html = []

        for clase_icono, etiqueta in ICONOS_DISPONIBLES:
            activo = 'border: 2px solid #2563eb; background-color: #eff6ff; color: #1d4ed8;' if value == clase_icono else 'border: 1px solid #cbd5e1; background-color: #ffffff; color: #334155;'
            botones_html.append(f"""
                <button type="button"
                        class="icon-picker-btn"
                        data-icon="{clase_icono}"
                        title="{etiqueta} ({clase_icono})"
                        onclick="seleccionarIcono_{name}(this)"
                        style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:8px 4px; border-radius:8px; cursor:pointer; transition:all 0.15s; {activo}">
                    <i class="{clase_icono}" style="font-size:18px; margin-bottom:4px;"></i>
                    <span style="font-size:10px; line-height:1.1; text-align:center; max-width:72px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{etiqueta.split('/')[0].strip()}</span>
                </button>
            """)

        html = f"""
        <div style="max-width: 680px;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <span style="display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px; border-radius:8px; background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;">
                    <i id="preview_{name}" class="{value}" style="font-size:18px;"></i>
                </span>
                <input type="text" name="{name}" id="id_{name}" value="{value}"
                       placeholder="Clase FontAwesome (ej. fa-solid fa-umbrella-beach)"
                       oninput="document.getElementById('preview_{name}').className = this.value"
                       style="flex:1; padding:6px 10px; border:1px solid #cbd5e1; border-radius:6px; font-family:monospace;">
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(82px, 1fr)); gap:6px; max-height:240px; overflow-y:auto; padding:8px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;">
                {''.join(botones_html)}
            </div>
        </div>
        <script>
            function seleccionarIcono_{name}(btn) {{
                const iconClass = btn.getAttribute('data-icon');
                document.getElementById('id_{name}').value = iconClass;
                document.getElementById('preview_{name}').className = iconClass;
                btn.parentElement.querySelectorAll('.icon-picker-btn').forEach(b => {{
                    b.style.border = '1px solid #cbd5e1';
                    b.style.backgroundColor = '#ffffff';
                    b.style.color = '#334155';
                }});
                btn.style.border = '2px solid #2563eb';
                btn.style.backgroundColor = '#eff6ff';
                btn.style.color = '#1d4ed8';
            }}
        </script>
        """
        return mark_safe(html)