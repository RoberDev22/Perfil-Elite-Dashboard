import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import re
import unicodedata
import base64
import urllib.request

st.set_page_config(page_title="Perfil de Élite — Scouting Dashboard", layout="wide", page_icon=":material/sports_soccer:")


def normaliza_nombre(nombre):
    """'Fer López' -> 'fer_lopez' ; 'Real Madrid Castilla' -> 'real_madrid_castilla'"""
    nfkd = unicodedata.normalize("NFKD", str(nombre))
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpio = sin_tildes.lower()
    limpio = re.sub(r"[^a-z0-9]+", "_", limpio).strip("_")
    return limpio


def _ruta_imagenes_urls():
    candidatos = [
        "data/imagenes_urls.csv", "dashboard/data/imagenes_urls.csv",
        "imagenes_urls.csv", "./imagenes_urls.csv",
    ]
    for ruta in candidatos:
        if os.path.exists(ruta):
            return ruta, candidatos
    return None, candidatos


@st.cache_data
def _cargar_urls_imagenes_cache(_ruta, _mtime):
    """Cache real, invalidada automáticamente cuando cambia el archivo en disco
    (la mtime forma parte de la clave de caché), no solo cuando cambia el código.
    Esto evita servir imágenes desactualizadas tras un redeploy que no reinicia
    del todo el proceso de Streamlit."""
    df_urls = pd.read_csv(_ruta)
    df_urls["clave"] = df_urls["tipo"] + "::" + df_urls["nombre"].apply(normaliza_nombre)
    return dict(zip(df_urls["clave"], df_urls["url"]))


def cargar_urls_imagenes():
    ruta, candidatos = _ruta_imagenes_urls()
    if ruta is None:
        return {}, None, candidatos
    mtime = os.path.getmtime(ruta)
    return _cargar_urls_imagenes_cache(ruta, mtime), ruta, candidatos


@st.cache_data(show_spinner=False)
def url_a_data_uri_remota(url):
    """Descarga una imagen remota UNA VEZ (cacheada en el servidor) y la convierte en
    data URI. Los escudos de Sofascore a veces responden 503 (rate limiting) si muchos
    usuarios piden la imagen directamente al CDN a la vez (p.ej. al cargar la tabla de
    Ranking, que pide decenas de escudos de golpe). Descargándola en el servidor y
    cacheándola evitamos que cada visitante dispare su propia petición al CDN externo."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "image/png")
        ext = "jpeg" if "jpeg" in content_type else ("svg+xml" if "svg" in content_type else "png")
        b64 = base64.b64encode(data).decode()
        return f"data:image/{ext};base64,{b64}"
    except Exception:
        return url  # si falla la descarga, devolvemos la URL tal cual (mismo comportamiento que antes)


def buscar_imagen(carpeta, nombre):
    """Busca primero en el mapeo de URLs externas; si no, en assets/<carpeta>/<nombre>.<ext> local."""
    tipo = "jugador" if carpeta == "jugadores" else "escudo"
    urls, _, _ = cargar_urls_imagenes()
    clave = f"{tipo}::{normaliza_nombre(nombre)}"
    if clave in urls and pd.notna(urls[clave]) and str(urls[clave]).strip():
        url = urls[clave]
        if tipo == "escudo" and str(url).startswith("http"):
            return url_a_data_uri_remota(url)
        return url  # URL externa, se usa tal cual

    base = normaliza_nombre(nombre)
    for candidatos_dir in [f"assets/{carpeta}", f"dashboard/assets/{carpeta}"]:
        for ext in ["jpg", "jpeg", "png", "webp"]:
            ruta = f"{candidatos_dir}/{base}.{ext}"
            if os.path.exists(ruta):
                return ruta
    return None


@st.cache_data
def imagen_a_data_uri(ruta):
    """Convierte una imagen local a data URI para poder incrustarla en HTML (<img src=...>)."""
    ext = ruta.split(".")[-1].lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    with open(ruta, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def silueta_svg(size=48):
    """Icono neutro de 'sin foto disponible', igual que usan Transfermarkt/Sofascore."""
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"
        style="border-radius:50%; background:#E4E1D8; flex-shrink:0;">
        <circle cx="50" cy="38" r="18" fill="#AFA99A"/>
        <path d="M50 58 C25 58 12 76 12 100 L88 100 C88 76 75 58 50 58 Z" fill="#AFA99A"/>
        </svg>"""


def img_html(ruta, size=48, radius="50%", border=None, con_silueta=False):
    """HTML <img> listo para insertar en un f-string de markdown. Acepta rutas locales, URLs http(s)
    y data URIs (data:image/...;base64,...) ya listas para usar tal cual.
    Si con_silueta=True y no hay ruta, devuelve un icono neutro de 'sin foto' en vez de nada."""
    if ruta is None:
        return silueta_svg(size) if con_silueta else ""
    ruta_str = str(ruta)
    if ruta_str.startswith("http") or ruta_str.startswith("data:"):
        src = ruta_str
    else:
        src = imagen_a_data_uri(ruta)
    borde = f"border:2px solid {border};" if border else ""
    return (f'<img src="{src}" style="width:{size}px; height:{size}px; object-fit:cover; '
            f'border-radius:{radius}; {borde}" referrerpolicy="no-referrer" loading="lazy">')


def render_html(html, container=None):
    """st.markdown con HTML, pero quitando la indentación de cada línea antes de renderizar.
    Si no se hace esto, Markdown interpreta las líneas con 4+ espacios de sangría como
    bloque de código y muestra el HTML como texto en vez de interpretarlo."""
    destino = container if container is not None else st
    limpio = " ".join(line.strip() for line in html.strip().split("\n"))
    destino.markdown(limpio, unsafe_allow_html=True)


def render_label_icono(icono, texto, container=None, color_icono="#6B7280"):
    """Label pequeño con icono Material Symbols delante, para usar justo encima de
    un widget con label_visibility='collapsed' (los shortcodes :material/icono: no
    se procesan dentro de labels de multiselect/selectbox, así que se monta a mano)."""
    render_html(
        f"""<div style="display:flex; align-items:center; gap:0.35rem; margin:0 0 0.35rem 0;
             font-family:'Inter', sans-serif; font-weight:600; color:#14213D; font-size:0.875rem;">
             <span style="font-family:'Material Symbols Rounded'; font-weight:400; font-size:1.05rem;
             color:{color_icono}; line-height:1;">{icono}</span>{texto}</div>""",
        container=container,
    )

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.01em; }

/* Cabecera */
.pe-header {
    background: linear-gradient(135deg, #14213D 0%, #1B4332 100%);
    padding: 1.6rem 2rem; border-radius: 14px; margin-bottom: 1.2rem;
}
.pe-header h1 { color: #F6F5F0 !important; margin: 0; font-size: 1.9rem; }
.pe-header p { color: #C9D3C5; margin: 0.3rem 0 0 0; font-size: 0.95rem; }

/* Pestañas */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    background-color: #FFFFFF; border-radius: 8px 8px 0 0; padding: 8px 18px;
    font-family: 'Space Grotesk', sans-serif; font-weight: 600; color: #6B7280;
}
.stTabs [aria-selected="true"] { color: #14213D !important; border-bottom: 3px solid #1B4332 !important; }

/* Métricas -> estilo "ficha de scouting" */
div[data-testid="stMetric"] {
    background-color: #FFFFFF; border: 1px solid #E4E1D8; border-left: 5px solid #1B4332;
    border-radius: 10px; padding: 0.9rem 1.1rem;
}
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; color: #14213D !important; }
div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p {
    font-family: 'Inter', sans-serif; color: #6B7280 !important; font-weight: 500;
}

/* Forzar el color del texto dentro de los gráficos Plotly (títulos, ejes, etiquetas),
   que Streamlit Cloud en modo oscuro puede aclarar por encima del color fijado en Python */
.js-plotly-plot text, .js-plotly-plot .gtitle, .js-plotly-plot .xtitle, .js-plotly-plot .ytitle,
.js-plotly-plot .legendtext, .js-plotly-plot tspan {
    fill: #14213D !important;
}

/* Tarjetas con borde: contenedores st.container(border=True) detectados por JS
   (el testid de Streamlit para esto ha cambiado entre versiones, así que se marcan
   dinámicamente más abajo) y tarjetas montadas a mano en HTML. */
.pe-hover-card {
    border-radius: 12px;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.pe-hover-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 24px rgba(20, 33, 61, 0.10);
    border-color: #C9C4B4 !important;
}

/* Cabeceras de st.table (nombres de jugadores en el comparador) */
[data-testid="stTable"] {
    background: #FFFFFF !important; border-radius: 8px; padding: 0.4rem;
}
[data-testid="stTable"] table, [data-testid="stTable"] thead, [data-testid="stTable"] tbody {
    background: #FFFFFF !important;
}
[data-testid="stTable"] thead th {
    font-family: 'Space Grotesk', sans-serif !important; font-size: 1.05rem !important;
    color: #14213D !important; font-weight: 700 !important; background: #FFFFFF !important;
}
[data-testid="stTable"] tbody td, [data-testid="stTable"] tbody th {
    font-size: 0.95rem !important; color: #14213D !important; background: #FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

# Recolorea las "chips" seleccionadas de los multiselect de Posición (Ranking,
# Comparador) para que usen el mismo color por grupo que el resto de la app
# (scatter, Top 10, Ficha de jugador), en vez del verde único del tema global.
import streamlit.components.v1 as components
components.html("""
<script>
const GRUPO_COLOR_TAG = {"Extremo": "#2E9E5B", "Mediapunta": "#2563EB", "Delantero": "#C9762C"};
function recolorTags() {
    const doc = window.parent.document;
    const tags = doc.querySelectorAll('div[data-baseweb="tag"], span[data-baseweb="tag"]');
    tags.forEach(function (t) {
        const label = (t.innerText || "").trim();
        const match = Object.keys(GRUPO_COLOR_TAG).find(function (k) { return label === k || label.startsWith(k); });
        if (match) {
            t.style.setProperty("background-color", GRUPO_COLOR_TAG[match], "important");
        }
    });
}
// Marca con la clase .pe-hover-card los contenedores st.container(border=True):
// el data-testid de Streamlit para esto ha cambiado de versión a versión, así
// que se detectan por su borde ya calculado en vez de por un nombre fijo.
function marcarTarjetasConBorde() {
    const doc = window.parent.document;
    const bloques = doc.querySelectorAll('div[data-testid="stVerticalBlock"]');
    bloques.forEach(function (b) {
        if (b.classList.contains('pe-hover-card')) return;
        const cs = doc.defaultView.getComputedStyle(b);
        if (cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none') {
            b.classList.add('pe-hover-card');
        }
    });
}
// Streamlit no permite acotar st.sidebar a una sola pestaña de forma nativa:
// la sidebar es global. Cada grupo de filtros (Ranking, Comparador) vive en su
// propio st.container(border=True) dentro de la sidebar; se identifica cada
// grupo por el texto de su cabecera y se le añade una clase propia para poder
// mostrarlo/ocultarlo por separado según la pestaña activa.
function marcarGruposSidebar() {
    const doc = window.parent.document;
    const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
    if (!sidebar) return;
    const cabeceras = sidebar.querySelectorAll('[data-testid="stMarkdownContainer"]');
    cabeceras.forEach(function (h) {
        const txt = h.innerText || '';
        let cls = null;
        if (txt.indexOf('Filtros del Ranking') !== -1) cls = 'pe-sidebar-group-ranking';
        else if (txt.indexOf('Filtros del Comparador') !== -1) cls = 'pe-sidebar-group-comparador';
        if (!cls) return;
        let el = h.closest('div[data-testid="stVerticalBlock"]');
        while (el) {
            const cs = doc.defaultView.getComputedStyle(el);
            if (cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none') {
                el.classList.add(cls);
                break;
            }
            const padre = el.parentElement;
            el = padre ? padre.closest('div[data-testid="stVerticalBlock"]') : null;
        }
    });
}
// Oculta/muestra la sidebar y, dentro de ella, el grupo de filtros que
// corresponda según qué pestaña esté activa (aria-selected).
function toggleSidebarPorTab() {
    const doc = window.parent.document;
    const tabs = doc.querySelectorAll('button[data-testid="stTab"]');
    let activa = null;
    tabs.forEach(function (t) {
        if (t.getAttribute('aria-selected') === 'true') {
            const txt = t.innerText || '';
            if (txt.indexOf('Ranking') !== -1) activa = 'ranking';
            else if (txt.indexOf('Comparador') !== -1) activa = 'comparador';
            else activa = 'otra';
        }
    });
    if (activa === null) return;
    const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
    const control = doc.querySelector('[data-testid="stSidebarCollapsedControl"]');
    const mostrarSidebar = activa === 'ranking' || activa === 'comparador';
    if (sidebar) {
        sidebar.style.setProperty('display', mostrarSidebar ? '' : 'none', 'important');
        const grupoRanking = sidebar.querySelector('.pe-sidebar-group-ranking');
        const grupoComparador = sidebar.querySelector('.pe-sidebar-group-comparador');
        if (grupoRanking) grupoRanking.style.setProperty('display', activa === 'ranking' ? '' : 'none', 'important');
        if (grupoComparador) grupoComparador.style.setProperty('display', activa === 'comparador' ? '' : 'none', 'important');
    }
    if (control) {
        control.style.setProperty('display', mostrarSidebar ? '' : 'none', 'important');
    }
}
function refrescarTodo() {
    recolorTags();
    marcarTarjetasConBorde();
    marcarGruposSidebar();
    toggleSidebarPorTab();
}
const target = window.parent.document.body;
if (target && !window.__peTagObserverAttached) {
    window.__peTagObserverAttached = true;
    new MutationObserver(refrescarTodo).observe(target, {childList: true, subtree: true});
}
refrescarTodo();
setInterval(refrescarTodo, 800);
</script>
""", height=0)

# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
VARS = {
    'Extremo': ['Goles/90', 'xG/90', 'Remates/90', 'Toques en el área de penalti/90',
                'Regates/90', 'Regates realizados, %', 'Carreras en progresión/90', 'Aceleraciones/90',
                'xA/90', 'Jugadas claves/90', 'Centros/90', 'Pases al área de penalti/90',
                'Interceptaciones/90', 'Duelos defensivos/90'],
    'Mediapunta': ['Jugadas claves/90', 'xA/90', 'Asistencias/90', 'Pases en el último tercio/90',
                   'Goles/90', 'xG/90', 'Remates/90', 'Toques en el área de penalti/90',
                   'Pases progresivos/90', 'Pases recibidos /90'],
    'Delantero': ['Goles, excepto los penaltis/90', 'xG/90', 'Remates/90', 'Goles hechos, %',
                  'Toques en el área de penalti/90', 'Carreras en progresión/90', 'Pases recibidos /90',
                  'Duelos defensivos/90', 'Interceptaciones/90', 'Aceleraciones/90'],
}

# Un pequeño subconjunto de variables "clave" por grupo, usadas para el radar
# (demasiadas puntas hacen el radar ilegible)
RADAR_VARS = {
    'Extremo': ['Goles/90', 'xA/90', 'Regates/90', 'Carreras en progresión/90',
                'Jugadas claves/90', 'Duelos defensivos/90'],
    'Mediapunta': ['Goles/90', 'xA/90', 'Jugadas claves/90', 'Pases progresivos/90',
                   'Pases en el último tercio/90', 'Pases recibidos /90'],
    'Delantero': ['Goles, excepto los penaltis/90', 'xG/90', 'Remates/90',
                  'Toques en el área de penalti/90', 'Carreras en progresión/90', 'Duelos defensivos/90'],
}

GRUPO_COLOR = {"Extremo": "#2E9E5B", "Mediapunta": "#2563EB", "Delantero": "#C9762C"}
GRUPO_COLOR_LIGHT = {"Extremo": "#EAF6EF", "Mediapunta": "#EAF1FE", "Delantero": "#FDF1E7"}


def hex_to_rgba(hex_color, alpha=0.25):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


VALIDACION_EMPIRICA = [
    "Fer López", "A. Ezzalzouli", "Pablo Torre", "Jan Virgili",
    "Pau Víctor", "Fermín López", "Victor Muñoz",
]

VALIDACION_TEXTO = {
    'Fer López': "Debutó con el primer equipo del Celta y fue internacional sub-21. El sistema lo puntuó como el perfil más alto de todo el dataset (96.8).",
    'A. Ezzalzouli': "Saltó del filial del Real Betis al primer equipo y después al FC Barcelona, consolidándose en LaLiga como extremo de banda.",
    'Pablo Torre': "Del filial del Mallorca al primer equipo del FC Barcelona con apenas 19 años.",
    'Jan Virgili': "Progresó en la cantera del Barcelona hasta el primer equipo, confirmando el perfil de extremo desbordador detectado.",
    'Pau Víctor': "De la Primera Federación al FC Barcelona, donde debutó en LaLiga como delantero.",
    'Fermín López': "De la Primera Federación (Barça Atlètic) al once titular del FC Barcelona en apenas una temporada.",
    'Victor Muñoz': "Detectado en su temporada de consolidación 2024-25 con el Real Madrid Castilla. Fichó por el Osasuna, fue elegido mejor sub-23 de LaLiga en dos ocasiones, debutó con España y fue convocado al Mundial 2026, antes de ser traspasado al Liverpool F.C. por su cláusula de 40M€.",
}

# Club en el que juega cada jugador HOY (no el de su etapa en 1ª RFEF). Dato mantenido a mano,
# igual que VALIDACION_TEXTO, porque el mercado de fichajes cambia y no está en ningún CSV del dataset.
EQUIPO_ACTUAL_ACTUALIZADO = "6 de julio de 2026"
EQUIPO_ACTUAL = {
    'Fer López': "Wolverhampton Wanderers",
    'A. Ezzalzouli': "Real Betis Balompié",
    'Pablo Torre': "RCD Mallorca",
    'Jan Virgili': "RCD Mallorca",
    'Pau Víctor': "Sporting de Braga",
    'Fermín López': "FC Barcelona",
    'Victor Muñoz': "Liverpool FC",
}
EQUIPO_ACTUAL_NOTA = {
    'Fer López': "de vuelta de su cesión en el Celta; su destino para 2026-27 aún se decide este verano.",
    'Jan Virgili': "el FC Barcelona negocia su recompra y una cesión inmediata al Real Betis (operación en curso, no oficializada).",
}


@st.cache_data
def cargar_datos():
    import os

    def buscar(nombre):
        candidatos = [f"data/{nombre}", nombre, f"./{nombre}"]
        for c in candidatos:
            if os.path.exists(c):
                return c
        raise FileNotFoundError(
            f"No se encontró '{nombre}'. Colócalo en la raíz del repositorio "
            f"o dentro de una carpeta 'data/'. Rutas probadas: {candidatos}"
        )

    rfef = pd.read_csv(buscar("rfef_final_con_shap.csv"))
    laliga = pd.read_csv(buscar("laliga_arquetipos_fase_a.csv"))
    destacados_extra = pd.read_csv(buscar("destacados_perfil_extra.csv"))
    return rfef, laliga, destacados_extra


rfef, laliga, destacados_extra = cargar_datos()

# percentiles dentro de cada grupo (para el radar), calculados una vez
percentiles = {}
stats_score = {}
for grupo, varlist in VARS.items():
    sub = rfef[rfef["grupo"] == grupo]
    percentiles[grupo] = sub[varlist].rank(pct=True) * 100
    stats_score[grupo] = {
        "percentil_score": sub["score_final"].rank(pct=True) * 100,
        "media": sub["score_final"].mean(),
        "mediana": sub["score_final"].median(),
        "p90": sub["score_final"].quantile(0.90),
        "valores": sub["score_final"].values,
    }

rfef["percentil_score"] = pd.concat([stats_score[g]["percentil_score"] for g in VARS]).reindex(rfef.index)
rfef = rfef.copy()

# Variables comunes a las tres posiciones, para poder comparar jugadores de
# distinta posición en el mismo radar (percentil calculado sobre todo el pool ofensivo)
CROSS_VARS = ["Goles/90", "xG/90", "xA/90", "Remates/90",
              "Carreras en progresión/90", "Duelos defensivos/90"]
percentiles_cross = rfef[CROSS_VARS].rank(pct=True) * 100

# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
st.markdown("""
<div class="pe-header">
    <h1><span style="font-family:'Material Symbols Rounded'; font-weight:400; vertical-align:-4px; font-size:1.6rem;">radar</span> Perfil de Élite</h1>
    <p>Sistema de detección de talento cross-liga (1ª RFEF → LaLiga) · PCA + K-Means + LightGBM + SHAP
    · TFM Big Data Aplicado al Scouting en Fútbol</p>
</div>
""", unsafe_allow_html=True)

tab_ranking, tab_ficha, tab_comparador, tab_validacion, tab_destacados, tab_trayectoria = st.tabs(
    [":material/leaderboard: Ranking", ":material/badge: Ficha de jugador",
     ":material/compare_arrows: Comparador", ":material/verified: Validación empírica",
     ":material/star: Jugadores destacados", ":material/timeline: Trayectoria"]
)
# Pestaña "Fuera de RFEF" (caso Lamine Yamal) retirada temporalmente: el
# laliga_arquetipos_fase_a.csv del pipeline v1.3 ya no trae las columnas
# biográficas ni las estadísticas por temporada (Altura, Pie, Pasaporte,
# Vencimiento contrato, Edad, Goles, xG, Asistencias, xA, Partidos/Minutos
# jugados) que esta pestaña necesitaba. Se reactivará en cuanto lleguen esos datos.

# ---------------------------------------------------------------------------
# Barra lateral — filtros de Ranking y de Comparador, cada uno en su propio
# grupo. Cada grupo solo debe verse en su pestaña correspondiente: el bloque
# de JS más abajo (toggleSidebarPorTab / marcarGruposSidebar) oculta/muestra
# la sidebar y el grupo activo según la pestaña seleccionada, porque Streamlit
# no ofrece forma nativa de acotar st.sidebar a una sola pestaña.
# ---------------------------------------------------------------------------
with st.sidebar:
    with st.container(border=True):
        render_html(
            """<div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:1rem;
                 font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D; font-size:1.15rem;">
                 <span style="font-family:'Material Symbols Rounded'; font-weight:400; font-size:1.5rem;
                 color:#1B4332; line-height:1;">tune</span>Filtros del Ranking</div>"""
        )

        render_label_icono("sports_soccer", "Posición")
        grupos_sel = st.multiselect(" ", sorted(rfef["grupo"].unique()),
                                     default=sorted(rfef["grupo"].unique()),
                                     placeholder="Elige una o varias opciones", label_visibility="collapsed")

        render_label_icono("auto_awesome", "Arquetipo")
        arquetipos_disp = sorted(rfef[rfef["grupo"].isin(grupos_sel)]["arquetipo_proyectado"].unique()) if grupos_sel else []
        arquetipos_sel = st.multiselect(" ", arquetipos_disp, default=arquetipos_disp,
                                         placeholder="Elige una o varias opciones", label_visibility="collapsed")

        render_label_icono("calendar_month", "Temporada")
        temporadas_sel = st.multiselect(" ", sorted(rfef["Temporada"].unique()),
                                         default=sorted(rfef["Temporada"].unique()),
                                         placeholder="Elige una o varias opciones", label_visibility="collapsed")

        render_label_icono("shield", "Equipo")
        equipos_sel_rank = st.multiselect(" ", sorted(rfef["Equipo"].dropna().unique()),
                                           default=[], placeholder="Todos los equipos", label_visibility="collapsed")

        # Filtro de Nacionalidad retirado temporalmente: el CSV del pipeline v1.3
        # (rfef_final_con_shap.csv) ya no incluye la columna "País de nacimiento".
        # Se reactivará en cuanto se disponga de ese dato para todo el pool de jugadores.

        st.divider()

        render_label_icono("speed", "Score mínimo")
        score_min = st.slider(" ", 0, 100, 0, label_visibility="collapsed")

        edad_min_data, edad_max_data = int(rfef["Edad"].min()), int(rfef["Edad"].max())
        render_label_icono("cake", "Edad")
        edad_rango = st.slider(" ", edad_min_data, edad_max_data,
                                (edad_min_data, edad_max_data), label_visibility="collapsed")

        min_min_data, min_max_data = int(rfef["Minutos jugados"].min()), int(rfef["Minutos jugados"].max())
        render_label_icono("timer", "Minutos jugados (mínimo)")
        minutos_min = st.slider(" ", min_min_data, min_max_data, min_min_data, label_visibility="collapsed")

    with st.container(border=True):
        render_html(
            """<div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:1rem;
                 font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D; font-size:1.15rem;">
                 <span style="font-family:'Material Symbols Rounded'; font-weight:400; font-size:1.5rem;
                 color:#1B4332; line-height:1;">tune</span>Filtros del Comparador</div>"""
        )

        rfef_validos_comp = rfef.dropna(subset=["Jugador", "Equipo", "Temporada"]).copy()

        def _selector_comp_sidebar(etiqueta, key_prefix, index_default):
            render_label_icono("sports_soccer", f"Posición ({etiqueta})")
            pos_sel = st.multiselect(" ", sorted(rfef_validos_comp["grupo"].unique()),
                                      default=sorted(rfef_validos_comp["grupo"].unique()),
                                      key=f"{key_prefix}_pos", label_visibility="collapsed")
            sub = rfef_validos_comp[rfef_validos_comp["grupo"].isin(pos_sel)] if pos_sel else rfef_validos_comp
            render_label_icono("shield", f"Equipo ({etiqueta})")
            eq_sel = st.multiselect(" ", sorted(sub["Equipo"].unique()), default=[], key=f"{key_prefix}_eq",
                                     placeholder="Elige una o varias opciones", label_visibility="collapsed")
            if eq_sel:
                sub = sub[sub["Equipo"].isin(eq_sel)]
            if sub.empty:
                sub = rfef_validos_comp
            opciones = (sub["Jugador"] + " — " + sub["Equipo"] + " (" + sub["Temporada"] + ")").tolist()
            idx_map = dict(zip(opciones, sub.index))
            render_label_icono("person", f"Jugador ({etiqueta})")
            sel = st.selectbox(" ", opciones, index=min(index_default, len(opciones) - 1),
                                key=f"{key_prefix}_sel", label_visibility="collapsed")
            return sub.loc[idx_map[sel]]

        j1 = _selector_comp_sidebar("Jugador 1", "j1", 0)
        st.divider()
        j2 = _selector_comp_sidebar("Jugador 2", "j2", 1)

# ---------------------------------------------------------------------------
# TAB 1 — Ranking
# ---------------------------------------------------------------------------
with tab_ranking:
    st.subheader("Ranking de jugadores de 1ª RFEF proyectados sobre el espacio de LaLiga")
    st.caption("Los filtros están en la barra lateral izquierda.")

    filtro = (
        rfef["grupo"].isin(grupos_sel)
        & rfef["arquetipo_proyectado"].isin(arquetipos_sel)
        & rfef["Temporada"].isin(temporadas_sel)
        & (rfef["score_final"] >= score_min)
        & rfef["Edad"].between(edad_rango[0], edad_rango[1])
        & (rfef["Minutos jugados"] >= minutos_min)
    )
    if equipos_sel_rank:
        filtro &= rfef["Equipo"].isin(equipos_sel_rank)
    tabla = rfef[filtro].sort_values("score_final", ascending=False)

    st.write(f"**{len(tabla)}** jugadores cumplen los filtros.")
    st.caption(
        "ℹ️ La columna \"Equipo\" refleja el club actual del jugador registrado en Wyscout en el "
        "momento de exportación de los datos, que puede no coincidir con su club durante la "
        "temporada de 1ª RFEF analizada (ver nota metodológica del TFM, sección 19.1)."
    )

    tabla_display = tabla[["Jugador", "Equipo", "Edad", "Temporada", "grupo", "arquetipo_proyectado",
                            "similitud_coseno", "score_final", "percentil_score"]].copy()
    tabla_display.insert(0, "Foto", tabla["Jugador"].apply(lambda n: buscar_imagen("jugadores", n)))
    tabla_display.insert(2, "Escudo", tabla["Equipo"].apply(lambda n: buscar_imagen("escudos", n)))
    tabla_display = tabla_display.rename(columns={
        "grupo": "Posición", "arquetipo_proyectado": "Arquetipo",
        "similitud_coseno": "Similitud", "score_final": "Score",
        "percentil_score": "Percentil",
    }).round({"Similitud": 3, "Score": 1, "Percentil": 0})

    st.dataframe(
        tabla_display,
        width='stretch',
        hide_index=True,
        height=640,
        row_height=44,
        column_config={
            "Foto": st.column_config.ImageColumn("Foto", width="small"),
            "Jugador": st.column_config.TextColumn("Jugador", width=150),
            "Escudo": st.column_config.ImageColumn("Escudo", width="small"),
            "Equipo": st.column_config.TextColumn("Equipo", width=150),
            "Edad": st.column_config.NumberColumn("Edad", width=55),
            "Temporada": st.column_config.TextColumn("Temporada", width=85),
            "Posición": st.column_config.TextColumn("Posición", width=95),
            "Arquetipo": st.column_config.TextColumn("Arquetipo", width=130),
            "Similitud": st.column_config.NumberColumn("Similitud", width=80),
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f", width=110),
            "Percentil": st.column_config.ProgressColumn("Percentil (vs. su posición)", min_value=0, max_value=100, format="%.0f", width=145),
        },
    )

    with st.container(border=True):
        st.markdown("#### Edad vs. Score — dónde están los perfiles jóvenes con puntuación alta")
        st.caption(
            "El **Score** combina tres componentes: similitud con los arquetipos de LaLiga (similitud coseno), "
            "sobre-rendimiento contextual (Z-score dentro de su grupo comparable) y un ajuste por edad que valora "
            "más el margen de progresión de los perfiles jóvenes. No es una nota de nivel absoluto, sino una señal "
            "relativa para priorizar el seguimiento dentro de cada posición."
        )
        fig_scatter = go.Figure()
        for grupo_s in sorted(tabla["grupo"].unique()):
            sub = tabla[tabla["grupo"] == grupo_s]
            fig_scatter.add_trace(go.Scatter(
                x=sub["Edad"], y=sub["score_final"], mode="markers", name=grupo_s,
                marker=dict(color=GRUPO_COLOR.get(grupo_s, "#2E9E5B"), size=9, opacity=0.75,
                            line=dict(width=1, color="#FFFFFF")),
                customdata=sub[["Jugador", "Equipo", "Temporada", "arquetipo_proyectado"]],
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} (%{customdata[2]})<br>"
                              "Arquetipo: %{customdata[3]}<br>Edad: %{x} · Score: %{y:.1f}<extra></extra>",
            ))
        fig_scatter.update_layout(
            height=460, margin=dict(l=50, r=30, t=20, b=50),
            xaxis_title="Edad", yaxis_title="Score final",
            font=dict(family="Inter, sans-serif", color="#14213D"),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            legend=dict(font=dict(family="Space Grotesk, sans-serif", size=13)),
        )
        fig_scatter.update_xaxes(gridcolor="#EDEBE4")
        fig_scatter.update_yaxes(gridcolor="#EDEBE4")
        st.plotly_chart(fig_scatter, width='stretch')

    with st.container(border=True):
        st.markdown("#### Top 10 según los filtros actuales")
        top10 = tabla.head(10).sort_values("score_final")
        etiquetas_top10 = (top10["Jugador"] + " (" + top10["Equipo"] + " · " + top10["Temporada"] + ")")
        fig_bar = go.Figure(go.Bar(
            x=top10["score_final"], y=etiquetas_top10,
            orientation="h",
            marker_color=[GRUPO_COLOR.get(g, "#2E9E5B") for g in top10["grupo"]],
            text=top10["score_final"].round(1), textposition="outside",
        ))
        fig_bar.update_layout(
            height=420, margin=dict(l=10, r=30, t=10, b=40),
            xaxis_title="Score final",
            font=dict(family="Inter, sans-serif", color="#14213D"),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        )
        fig_bar.update_xaxes(gridcolor="#EDEBE4")
        st.plotly_chart(fig_bar, width='stretch')

# ---------------------------------------------------------------------------
# TAB 2 — Ficha de jugador
# ---------------------------------------------------------------------------
with tab_ficha:
    st.subheader("Ficha individual")
    rfef_validos = rfef.dropna(subset=["Jugador", "Equipo", "Temporada"]).copy()

    col_eq_f, col_temp_f = st.columns(2)
    with col_eq_f:
        eq_filtro_f = st.multiselect("Filtrar por equipo", sorted(rfef_validos["Equipo"].unique()),
                                      default=[], key="ficha_eq_filtro", placeholder="Elige una o varias opciones")
    with col_temp_f:
        temp_filtro_f = st.multiselect("Filtrar por temporada", sorted(rfef_validos["Temporada"].unique()),
                                        default=[], key="ficha_temp_filtro", placeholder="Elige una o varias opciones")

    rfef_filtrado_f = rfef_validos
    if eq_filtro_f:
        rfef_filtrado_f = rfef_filtrado_f[rfef_filtrado_f["Equipo"].isin(eq_filtro_f)]
    if temp_filtro_f:
        rfef_filtrado_f = rfef_filtrado_f[rfef_filtrado_f["Temporada"].isin(temp_filtro_f)]

    if rfef_filtrado_f.empty:
        st.warning("Sin resultados para esos filtros.")
        st.stop()

    opciones = (rfef_filtrado_f["Jugador"] + " — " + rfef_filtrado_f["Equipo"] + " (" + rfef_filtrado_f["Temporada"] + ")").tolist()
    idx_map = dict(zip(opciones, rfef_filtrado_f.index))
    seleccion = st.selectbox("Selecciona un jugador", opciones,
                              index=opciones.index(opciones[0]) if opciones else 0)
    jugador = rfef.loc[idx_map[seleccion]]
    grupo = jugador["grupo"]
    color_ficha = GRUPO_COLOR.get(grupo, "#2E9E5B")
    color_ficha_light = GRUPO_COLOR_LIGHT.get(grupo, "#EAF6EF")

    foto_jugador = buscar_imagen("jugadores", jugador["Jugador"])
    escudo_equipo = buscar_imagen("escudos", jugador["Equipo"])

    render_html(
        f"""<div style="background:#FFFFFF; border:1px solid #E4E1D8; border-radius:10px;
             padding:0.7rem 1.1rem; margin:0.3rem 0 0.9rem 0; display:flex; align-items:center; gap:0.9rem;">
             {img_html(foto_jugador, size=56, radius="50%", border="#E4E1D8", con_silueta=True)}
             <div>
             <div style="font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D; font-size:1.6rem;
                  display:flex; align-items:center; gap:0.5rem;">
             {jugador['Jugador']} {img_html(escudo_equipo, size=26, radius="4px")}
             </div>
             <span style="font-family:'Inter', sans-serif; font-weight:500; color:#6B7280; font-size:1rem;">
             {jugador['Equipo']} ({jugador['Temporada']})</span>
             </div></div>"""
    )

    colA, colB = st.columns([1, 1.3])

    with colA:
        st.metric("Score final", f"{jugador['score_final']:.1f}")

        pct_score = stats_score[grupo]["percentil_score"].loc[jugador.name]
        media_grupo = stats_score[grupo]["media"]
        diff_media = jugador["score_final"] - media_grupo
        st.caption(
            f"Percentil **{pct_score:.0f}** entre los {grupo.lower()}s de 1ª RFEF analizados "
            f"({'+' if diff_media >= 0 else ''}{diff_media:.1f} vs. media del grupo, {media_grupo:.1f})"
        )

        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=stats_score[grupo]["valores"], nbinsx=30,
            marker_color="#D8D4C8", name="Resto del grupo", opacity=0.9,
        ))
        fig_dist.add_vline(x=jugador["score_final"], line_width=3, line_color=color_ficha,
                            annotation_text=jugador["Jugador"], annotation_position="top",
                            annotation_font=dict(family="Space Grotesk, sans-serif", color="#14213D", size=12))
        fig_dist.add_vline(x=media_grupo, line_width=1, line_dash="dot", line_color="#6B7280",
                            annotation_text="media", annotation_font=dict(size=10, color="#6B7280"))
        fig_dist.update_layout(
            height=140, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
            xaxis_title=f"Distribución de scores — {grupo}s (1ª RFEF)",
            yaxis_visible=False,
            font=dict(family="Inter, sans-serif", color="#14213D", size=11),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_dist, width='stretch')

        render_html(
            f"""<div style="background:{color_ficha_light}; border:1px solid {color_ficha}; border-left:5px solid {color_ficha};
                 border-radius:10px; padding:0.55rem 1rem; margin:0.6rem 0 0.9rem 0;
                 font-family:'Space Grotesk', sans-serif; font-weight:600; color:#14213D; font-size:1.05rem;">
                 {jugador['arquetipo_proyectado']}
                 <span style="font-family:'Inter', sans-serif; font-weight:500; color:#6B7280; font-size:0.8rem;">
                 · arquetipo proyectado ({grupo})</span>
                 </div>"""
        )

        c2, c3 = st.columns(2)
        c2.metric("Edad", int(jugador["Edad"]))
        c3.metric("Similitud", f"{jugador['similitud_coseno']:.2f}")

        st.markdown("**Por qué tiene este score (SHAP):**")
        factores = jugador["shap_top_factores"].split(" | ")
        nombres = [f.split(" (")[0] for f in factores]
        valores = [float(f.split("(")[1].replace(")", "").replace("+", "").replace("−", "-")) for f in factores]
        colores = ["#2E9E5B" if v >= 0 else "#B33A3A" for v in valores]
        fig_shap = go.Figure(go.Bar(
            x=valores, y=nombres, orientation="h", marker_color=colores,
            text=[f"{v:+.1f}" for v in valores], textposition="outside",
        ))
        fig_shap.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                                xaxis_title="Contribución al score (SHAP)",
                                font=dict(family="Inter, sans-serif", color="#14213D"),
                                paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig_shap, width='stretch')

    with colB:
        radar_vars = RADAR_VARS[grupo]
        valores_pct = [percentiles[grupo].loc[jugador.name, v] for v in radar_vars]
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=valores_pct + [valores_pct[0]],
            theta=radar_vars + [radar_vars[0]],
            fill="toself", name=jugador["Jugador"], line_color=color_ficha,
            fillcolor=hex_to_rgba(color_ficha, 0.25),
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False, height=420,
            title=f"Percentil dentro de su posición ({grupo}, 1ª RFEF)",
            font=dict(family="Inter, sans-serif", color="#14213D"),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_radar, width='stretch')

# ---------------------------------------------------------------------------
# TAB 3 — Comparador
# ---------------------------------------------------------------------------
with tab_comparador:
    st.subheader("Comparador de jugadores")
    st.caption("Puedes comparar jugadores de la misma posición (radar con métricas específicas) "
               "o de posiciones distintas (radar con métricas comunes de ataque). Los filtros están "
               "en la barra lateral izquierda.")

    def render_tarjeta_comp(jugador_sel):
        escudo_sel = buscar_imagen("escudos", jugador_sel["Equipo"])
        foto_sel = buscar_imagen("jugadores", jugador_sel["Jugador"])
        render_html(
            f"""<div class="pe-hover-card" style="display:flex; align-items:center; gap:0.7rem; margin:0.5rem 0 0.7rem 0;
                 background:#FFFFFF; border:1px solid #E4E1D8; border-radius:10px; padding:0.5rem 0.8rem;">
                 {img_html(foto_sel, size=52, radius="50%", border="#E4E1D8", con_silueta=True)}
                 <div>
                 <div style="font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D; font-size:1.1rem;">
                 {jugador_sel['Jugador']}</div>
                 <div style="font-family:'Inter', sans-serif; font-weight:500; color:#6B7280; font-size:0.85rem;
                      display:flex; align-items:center; gap:0.35rem; margin-top:0.1rem;">
                 {img_html(escudo_sel, size=18, radius="3px")} {jugador_sel['Equipo']} ({jugador_sel['Temporada']})
                 </div></div></div>"""
        )

    c1, c2 = st.columns(2)
    with c1:
        render_tarjeta_comp(j1)
    with c2:
        render_tarjeta_comp(j2)

    misma_posicion = j1["grupo"] == j2["grupo"]
    if misma_posicion:
        radar_vars = RADAR_VARS[j1["grupo"]]
        tabla_percentiles = percentiles[j1["grupo"]]
        st.caption(f"Misma posición ({j1['grupo']}) — radar con las métricas específicas de esa posición.")
    else:
        radar_vars = CROSS_VARS
        tabla_percentiles = percentiles_cross
        st.caption(f"Posiciones distintas ({j1['grupo']} vs. {j2['grupo']}) — radar con métricas comunes de ataque, "
                   "percentil calculado sobre el conjunto completo de jugadores ofensivos de 1ª RFEF.")

    fig = go.Figure()
    for j, color in [(j1, "#14213D"), (j2, "#C9762C")]:
        vals = [tabla_percentiles.loc[j.name, v] for v in radar_vars]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=radar_vars + [radar_vars[0]],
            fill="toself", name=f"{j['Jugador']} ({j['grupo']}, {j['Temporada']})", line_color=color,
        ))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=500,
                       margin=dict(l=60, r=260, t=40, b=40),
                       legend=dict(font=dict(size=14, family="Space Grotesk, sans-serif"),
                                   x=1.0, xanchor="left", y=0.5, yanchor="middle"),
                       font=dict(family="Inter, sans-serif", color="#14213D"),
                       paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    st.plotly_chart(fig, width='stretch')

    comp_tabla = pd.DataFrame({
        j1["Jugador"]: [str(j1["arquetipo_proyectado"]), str(int(j1["Edad"])), f"{j1['score_final']:.1f}"],
        j2["Jugador"]: [str(j2["arquetipo_proyectado"]), str(int(j2["Edad"])), f"{j2['score_final']:.1f}"],
    }, index=["Arquetipo", "Edad", "Score final"])
    st.table(comp_tabla)

# ---------------------------------------------------------------------------
# TAB 4 — Validación empírica
# ---------------------------------------------------------------------------
with tab_validacion:
    st.subheader("Validación empírica: casos reales detectados por el sistema")
    st.caption("Jugadores que el modelo puntuó alto en 1ª RFEF y que después confirmaron su proyección en LaLiga o en clubes de mayor nivel.")

    # ordenar por score final (de mayor a menor) antes de numerar
    orden_validacion = []
    for nombre in VALIDACION_EMPIRICA:
        fila_tmp = rfef[rfef["Jugador"] == nombre]
        if fila_tmp.empty:
            continue
        orden_validacion.append((nombre, fila_tmp["score_final"].max()))
    orden_validacion = [n for n, _ in sorted(orden_validacion, key=lambda t: t[1], reverse=True)]

    for i, nombre in enumerate(orden_validacion, start=1):
        fila = rfef[rfef["Jugador"] == nombre]
        if fila.empty:
            continue
        fila = fila.sort_values("score_final", ascending=False).iloc[0]
        color = GRUPO_COLOR.get(fila["grupo"], "#2E9E5B")
        foto_v = buscar_imagen("jugadores", fila["Jugador"])
        escudo_v = buscar_imagen("escudos", fila["Equipo"])
        render_html(
            f"""<div class="pe-hover-card" style="border:1px solid #E4E1D8; border-left:6px solid {color}; border-radius:10px;
                 padding:1.1rem 1.4rem; margin-bottom:0.9rem; display:flex; gap:1.4rem; align-items:flex-start;
                 background:#FFFFFF;">
                <div style="font-family:'JetBrains Mono', monospace; font-weight:700; color:{color};
                     font-size:1.7rem; min-width:2.4rem; line-height:1.4;">{i:02d}</div>
                {img_html(foto_v, size=64, radius="50%", border="#E4E1D8", con_silueta=True)}
                <div style="flex:0 0 230px;">
                    <div style="font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D;
                         font-size:1.35rem; line-height:1.2;">{fila['Jugador']}</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-weight:700; color:{color};
                         font-size:1.9rem; line-height:1.3; margin-top:0.2rem;">
                         {fila['score_final']:.1f} <span style="font-size:0.9rem; font-weight:500; color:#6B7280;">pts</span></div>
                    <div style="font-family:'Inter', sans-serif; color:#6B7280; font-size:0.82rem; margin-top:0.3rem;">
                         {fila['arquetipo_proyectado']} · {fila['Temporada']}</div>
                    <div style="font-family:'Inter', sans-serif; color:#6B7280; font-size:0.82rem; margin-top:0.15rem;
                         display:flex; align-items:center; gap:0.35rem;">
                         {img_html(escudo_v, size=24, radius="3px")}
                         <span>{fila['Equipo']}</span></div>
                </div>
                <div style="flex:1; font-family:'Inter', sans-serif; color:#14213D; font-size:0.95rem;
                     line-height:1.5; padding-top:0.2rem;">{VALIDACION_TEXTO.get(nombre, "")}</div>
                </div>"""
        )

# ---------------------------------------------------------------------------
# TAB 5 — Jugadores destacados
# ---------------------------------------------------------------------------

with tab_destacados:
    st.subheader("Jugadores destacados: ficha ampliada de los casos de validación")
    st.caption("Perfil físico, contractual y evolución del score a lo largo de las temporadas disponibles, "
               "para los mismos 7 casos de la pestaña de Validación empírica.")

    for nombre in VALIDACION_EMPIRICA:
        historial = rfef[rfef["Jugador"] == nombre].sort_values("Temporada")
        if historial.empty:
            continue
        ultima = historial.sort_values("score_final", ascending=False).iloc[0]
        extra_row = destacados_extra[destacados_extra["Jugador"] == nombre]
        color = GRUPO_COLOR.get(ultima["grupo"], "#2E9E5B")
        grupo_hist = ultima["grupo"]
        foto_d = buscar_imagen("jugadores", ultima["Jugador"])
        escudo_d = buscar_imagen("escudos", ultima["Equipo"])
        equipo_actual = EQUIPO_ACTUAL.get(nombre)
        escudo_actual = buscar_imagen("escudos", equipo_actual) if equipo_actual else None
        nota_actual = EQUIPO_ACTUAL_NOTA.get(nombre)

        with st.container(border=True):
            col_side, col_main = st.columns([1, 2.6])

            with col_side:
                render_html(
                    f"""<div style="text-align:center;">
                         {img_html(foto_d, size=100, radius="50%", border="#E4E1D8", con_silueta=True)}
                         </div>""",
                    container=col_side,
                )
                render_html(
                    f"""<div style="text-align:center; font-family:'Space Grotesk', sans-serif; font-weight:700;
                         color:#14213D; font-size:1.2rem; margin-top:0.5rem;">{ultima['Jugador']}</div>
                         <div style="text-align:center; font-family:'Inter', sans-serif; color:#6B7280; font-size:0.85rem;
                         display:flex; align-items:center; justify-content:center; gap:0.35rem; margin:0.15rem 0;">
                         {img_html(escudo_d, size=20, radius="3px")} {ultima['Equipo']}</div>
                         <div style="text-align:center; font-family:'Inter', sans-serif; color:#9AA0A6; font-size:0.75rem;
                         margin-bottom:0.7rem;">temporada destacada: {ultima['Temporada']}</div>""",
                    container=col_side,
                )
                render_html(
                    f"""<div style="background:#FFFFFF; border:1px solid {color}; border-left:5px solid {color};
                         border-radius:8px; padding:0.4rem 0.6rem; font-family:'Space Grotesk', sans-serif;
                         font-weight:600; color:#14213D; font-size:0.85rem; text-align:center; margin-bottom:0.4rem;">
                         {ultima['arquetipo_proyectado']} · {ultima['grupo']}</div>""",
                    container=col_side,
                )

                if equipo_actual:
                    render_html(
                        f"""<div style="background:#FFF8EC; border:1px solid #E8A33D; border-left:5px solid #E8A33D;
                             border-radius:8px; padding:0.4rem 0.6rem; display:flex; align-items:center;
                             justify-content:center; gap:0.35rem; font-family:'Space Grotesk', sans-serif;
                             font-weight:600; color:#14213D; font-size:0.82rem; margin-bottom:0.3rem;">
                             {img_html(escudo_actual, size=20, radius="3px")} Actualmente: {equipo_actual}</div>""",
                        container=col_side,
                    )
                    if nota_actual:
                        col_side.caption(f"📌 {nota_actual}")
                    col_side.caption(f"Verificado a {EQUIPO_ACTUAL_ACTUALIZADO}.")

                if not extra_row.empty:
                    e = extra_row.iloc[0]
                    datos_bio = [
                        ("Altura", f"{int(e['Altura'])} cm" if pd.notna(e["Altura"]) and e["Altura"] > 0 else "N/D"),
                        ("Pie", str(e["Pie"]).capitalize() if pd.notna(e["Pie"]) else "N/D"),
                        ("Nacionalidad", str(e["Pasaporte"]) if pd.notna(e["Pasaporte"]) else "N/D"),
                        ("Minutos (mejor temp.)", f"{int(ultima['Minutos jugados'])} min"),
                        ("Vencimiento contrato", str(e["Vencimiento contrato"]) if pd.notna(e["Vencimiento contrato"]) else "N/D"),
                    ]
                    filas_bio = "".join(
                        f"""<div style="display:flex; justify-content:space-between; padding:0.32rem 0;
                             border-bottom:1px solid #F0EEE7; font-family:'Inter', sans-serif; font-size:0.8rem;">
                             <span style="color:#6B7280;">{label}</span>
                             <span style="color:#14213D; font-weight:600; text-align:right;">{val}</span></div>"""
                        for label, val in datos_bio
                    )
                    render_html(
                        f"""<div style="background:#FFFFFF; border:1px solid #E4E1D8; border-radius:8px;
                             padding:0.3rem 0.7rem; margin-top:0.5rem;">{filas_bio}</div>""",
                        container=col_side,
                    )
                    col_side.caption("El vencimiento de contrato es el dato más reciente disponible, no necesariamente "
                                      "el de su etapa en 1ª RFEF.")

            with col_main:
                render_html(
                    f"""<div style="background:#FFFFFF; border:1px solid #E4E1D8; border-radius:10px;
                         padding:0.8rem 1rem; font-family:'Inter', sans-serif; color:#14213D;
                         font-size:0.95rem; line-height:1.5; margin-bottom:0.9rem;">
                         {VALIDACION_TEXTO.get(nombre, '')}</div>""",
                    container=col_main,
                )

                colG, colH = col_main.columns(2)
                with colG:
                    st.markdown("**Por qué tiene este score (SHAP):**")
                    factores = ultima["shap_top_factores"].split(" | ")
                    nombres_shap = [f.split(" (")[0] for f in factores]
                    valores_shap = [float(f.split("(")[1].replace(")", "").replace("+", "").replace("−", "-"))
                                    for f in factores]
                    colores_shap = ["#2E9E5B" if v >= 0 else "#B33A3A" for v in valores_shap]
                    fig_shap_d = go.Figure(go.Bar(
                        x=valores_shap, y=nombres_shap, orientation="h", marker_color=colores_shap,
                        text=[f"{v:+.1f}" for v in valores_shap], textposition="outside",
                    ))
                    fig_shap_d.update_layout(
                        height=260, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title="Contribución al score (SHAP)",
                        font=dict(family="Inter, sans-serif", color="#14213D"),
                        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                    )
                    st.plotly_chart(fig_shap_d, width='stretch')

                with colH:
                    radar_vars_d = RADAR_VARS[grupo_hist]
                    valores_pct_d = [percentiles[grupo_hist].loc[ultima.name, v] for v in radar_vars_d]
                    fig_radar_d = go.Figure()
                    fig_radar_d.add_trace(go.Scatterpolar(
                        r=valores_pct_d + [valores_pct_d[0]],
                        theta=radar_vars_d + [radar_vars_d[0]],
                        fill="toself", name=nombre, line_color=color,
                        fillcolor=hex_to_rgba(color, 0.25),
                    ))
                    fig_radar_d.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                        showlegend=False, height=260, margin=dict(l=30, r=30, t=30, b=20),
                        title=dict(text=f"Percentil en su grupo ({grupo_hist})", font=dict(size=12)),
                        font=dict(family="Inter, sans-serif", color="#14213D", size=10),
                        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                    )
                    st.plotly_chart(fig_radar_d, width='stretch')

                st.markdown("##### Evolución del score por temporada")
                media_grupo_hist = stats_score[grupo_hist]["media"]
                valores_grupo = stats_score[grupo_hist]["valores"]

                rng = np.random.default_rng(abs(hash(grupo_hist)) % (2**32))
                jitter = rng.uniform(-0.42, 0.42, size=len(valores_grupo))

                fig_evo = go.Figure()
                fig_evo.add_trace(go.Scatter(
                    x=valores_grupo, y=jitter, mode="markers", name="Resto del grupo",
                    marker=dict(size=7, color="#8A93A6", opacity=0.8, line=dict(width=0)),
                    hoverinfo="skip",
                ))
                fig_evo.add_vline(x=media_grupo_hist, line_width=1, line_dash="dot", line_color="#6B7280",
                                   annotation_text="media", annotation_font=dict(size=10, color="#6B7280"))

                for i_temp, (_, fila_t) in enumerate(historial.iterrows()):
                    y_off = 0 if len(historial) == 1 else (0.55 if i_temp % 2 == 0 else -0.55)
                    # Halo debajo del punto del jugador, para que destaque con claridad
                    # sobre el resto del grupo.
                    fig_evo.add_trace(go.Scatter(
                        x=[fila_t["score_final"]], y=[y_off], mode="markers",
                        marker=dict(size=28, color=hex_to_rgba(color, 0.25), line=dict(width=0)),
                        showlegend=False, hoverinfo="skip",
                    ))
                    fig_evo.add_trace(go.Scatter(
                        x=[fila_t["score_final"]], y=[y_off], mode="markers+text",
                        marker=dict(size=18, color=color, line=dict(width=3, color="#FFFFFF")),
                        text=[f"{fila_t['Temporada']}: {fila_t['score_final']:.1f}"],
                        textposition="top center" if y_off >= 0 else "bottom center",
                        textfont=dict(size=11, color=color, family="Space Grotesk, sans-serif"),
                        showlegend=False, hoverinfo="skip",
                    ))

                fig_evo.update_layout(
                    height=230, margin=dict(l=20, r=20, t=30, b=30), showlegend=False,
                    title=dict(text=f"Su score frente al resto de {grupo_hist.lower()}s analizados en 1ª RFEF",
                               font=dict(size=12, family="Space Grotesk, sans-serif")),
                    font=dict(family="Inter, sans-serif", color="#14213D", size=11),
                    paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                    yaxis=dict(visible=False, range=[-1.3, 1.3]),
                    xaxis=dict(gridcolor="#EDEBE4", title="Score final"),
                )
                st.plotly_chart(fig_evo, width='stretch')

                percentil_pico = ultima.get("percentil_score", float("nan"))
                if pd.notna(percentil_pico):
                    explicacion = (f"En la temporada {ultima['Temporada']} destacó con un score de {ultima['score_final']:.1f} pts, "
                                    f"situándose en el percentil {percentil_pico:.0f} entre los {grupo_hist.lower()}s de 1ª RFEF "
                                    f"analizados por el modelo (por encima del {percentil_pico:.0f}% del grupo esa temporada).")
                else:
                    explicacion = (f"En la temporada {ultima['Temporada']} destacó con un score de {ultima['score_final']:.1f} pts "
                                    f"dentro del grupo de {grupo_hist.lower()}s de 1ª RFEF analizados por el modelo.")

                if len(historial) > 1:
                    delta = historial["score_final"].iloc[-1] - historial["score_final"].iloc[0]
                    signo = "subió" if delta > 0 else "bajó"
                    explicacion += (f" Entre {historial['Temporada'].iloc[0]} y {historial['Temporada'].iloc[-1]} el score {signo} "
                                    f"{abs(delta):.1f} puntos — recuerda que el score es relativo al resto del grupo de esa "
                                    f"temporada, así que también refleja cambios en el nivel general del grupo, no solo en el jugador.")

                st.caption(explicacion)

# ---------------------------------------------------------------------------
# TAB 6 — Trayectoria (estilo Transfermarkt)
# ---------------------------------------------------------------------------
with tab_trayectoria:
    st.subheader("Trayectoria del jugador")
    st.caption(
        "Recorrido cronológico por club y temporada, con el arquetipo y el score que le asignó el "
        "modelo en cada una. Incluye todos los clubes presentes en el dataset (también los de fuera "
        "de 1ª RFEF), útil para ver el camino completo de un jugador, incluida su etapa posterior a "
        "la RFEF."
    )

    jugadores_trayectoria = sorted(rfef["Jugador"].dropna().unique())
    jugador_tray_sel = st.selectbox(
        "Selecciona un jugador", jugadores_trayectoria,
        index=jugadores_trayectoria.index("Fer López") if "Fer López" in jugadores_trayectoria else 0,
        key="trayectoria_sel",
    )

    historial_tray = rfef[rfef["Jugador"] == jugador_tray_sel].sort_values("Temporada").reset_index(drop=True)

    if historial_tray.empty:
        st.info("Sin datos de trayectoria para este jugador.")
    else:
        foto_tray = buscar_imagen("jugadores", jugador_tray_sel)
        render_html(
            f"""<div style="display:flex; align-items:center; gap:0.9rem; margin:0.3rem 0 1.1rem 0;">
                 {img_html(foto_tray, size=64, radius="50%", border="#E4E1D8", con_silueta=True)}
                 <div>
                 <div style="font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D; font-size:1.4rem;">
                 {jugador_tray_sel}</div>
                 <div style="font-family:'Inter', sans-serif; color:#6B7280; font-size:0.85rem;">
                 {len(historial_tray)} temporada(s) registrada(s) en el dataset</div>
                 </div></div>"""
        )

        filas_timeline = []
        for _, fila_t in historial_tray.iterrows():
            color_t = GRUPO_COLOR.get(fila_t.get("grupo"), "#2E9E5B")
            escudo_t = buscar_imagen("escudos", fila_t["Equipo"])
            score_txt = f"{fila_t['score_final']:.1f} pts" if pd.notna(fila_t.get("score_final")) else "—"
            arquetipo_txt = fila_t.get("arquetipo_proyectado", "—")
            filas_timeline.append(f"""
                <div style="display:flex; gap:1rem; align-items:flex-start; position:relative; padding-bottom:1.6rem;">
                    <div style="display:flex; flex-direction:column; align-items:center; width:14px;">
                        <div style="width:14px; height:14px; border-radius:50%; background:{color_t};
                             border:2px solid #FFFFFF; box-shadow:0 0 0 2px {color_t}; margin-top:0.35rem; flex-shrink:0;"></div>
                        <div style="width:2px; flex:1; background:#E4E1D8; margin-top:0.2rem;"></div>
                    </div>
                    <div style="flex:1; background:#FFFFFF; border:1px solid #E4E1D8; border-left:4px solid {color_t};
                         border-radius:10px; padding:0.7rem 1rem; display:flex; align-items:center; justify-content:space-between; gap:1rem;">
                        <div style="display:flex; align-items:center; gap:0.6rem;">
                            {img_html(escudo_t, size=32, radius="4px")}
                            <div>
                                <div style="font-family:'Space Grotesk', sans-serif; font-weight:700; color:#14213D; font-size:1rem;">
                                {fila_t['Equipo']}</div>
                                <div style="font-family:'Inter', sans-serif; color:#6B7280; font-size:0.8rem;">
                                {fila_t['Temporada']} · {arquetipo_txt}</div>
                            </div>
                        </div>
                        <div style="font-family:'JetBrains Mono', monospace; font-weight:700; color:{color_t}; font-size:1.05rem;
                             white-space:nowrap;">{score_txt}</div>
                    </div>
                </div>""")
        # el último punto de la línea no necesita continuar hacia abajo
        filas_timeline[-1] = filas_timeline[-1].replace(
            'background:#E4E1D8; margin-top:0.2rem;', 'background:transparent; margin-top:0.2rem;'
        )
        render_html("<div>" + "".join(filas_timeline) + "</div>")

        tabla_tray = historial_tray[["Temporada", "Equipo", "grupo", "arquetipo_proyectado", "score_final"]].rename(
            columns={"grupo": "Posición", "arquetipo_proyectado": "Arquetipo", "score_final": "Score"}
        ).round({"Score": 1})
        with st.expander("Ver como tabla"):
            st.dataframe(tabla_tray, hide_index=True, width='stretch')
