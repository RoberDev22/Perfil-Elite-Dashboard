import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Perfil de Élite — Scouting Dashboard", layout="wide", page_icon=":material/sports_soccer:")

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
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; color: #14213D; }
div[data-testid="stMetricLabel"] { font-family: 'Inter', sans-serif; color: #6B7280; font-weight: 500; }

/* Contenedores con borde (tarjetas de validación empírica) */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important; border: 1px solid #E4E1D8 !important;
}

/* Cabeceras de st.table (nombres de jugadores en el comparador) */
[data-testid="stTable"] thead th {
    font-family: 'Space Grotesk', sans-serif !important; font-size: 1.05rem !important;
    color: #14213D !important; font-weight: 700 !important;
}
[data-testid="stTable"] tbody td, [data-testid="stTable"] tbody th {
    font-size: 0.95rem !important;
}
</style>
""", unsafe_allow_html=True)

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
    return rfef, laliga


rfef, laliga = cargar_datos()

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

tab_ranking, tab_ficha, tab_comparador, tab_validacion = st.tabs(
    [":material/leaderboard: Ranking", ":material/badge: Ficha de jugador",
     ":material/compare_arrows: Comparador", ":material/verified: Validación empírica"]
)

# ---------------------------------------------------------------------------
# TAB 1 — Ranking
# ---------------------------------------------------------------------------
with tab_ranking:
    st.subheader("Ranking de jugadores de 1ª RFEF proyectados sobre el espacio de LaLiga")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        grupos_sel = st.multiselect("Posición", sorted(rfef["grupo"].unique()),
                                     default=sorted(rfef["grupo"].unique()))
    with col2:
        arquetipos_disp = sorted(rfef[rfef["grupo"].isin(grupos_sel)]["arquetipo_proyectado"].unique()) if grupos_sel else []
        arquetipos_sel = st.multiselect("Arquetipo", arquetipos_disp, default=arquetipos_disp)
    with col3:
        temporadas_sel = st.multiselect("Temporada", sorted(rfef["Temporada"].unique()),
                                         default=sorted(rfef["Temporada"].unique()))
    with col4:
        score_min = st.slider("Score mínimo", 0, 100, 0)

    filtro = (
        rfef["grupo"].isin(grupos_sel)
        & rfef["arquetipo_proyectado"].isin(arquetipos_sel)
        & rfef["Temporada"].isin(temporadas_sel)
        & (rfef["score_final"] >= score_min)
    )
    tabla = rfef[filtro].sort_values("score_final", ascending=False)

    st.write(f"**{len(tabla)}** jugadores cumplen los filtros.")
    st.dataframe(
        tabla[["Jugador", "Equipo", "Edad", "Temporada", "grupo", "arquetipo_proyectado",
               "similitud_coseno", "score_final", "percentil_score"]]
        .rename(columns={"grupo": "Posición", "arquetipo_proyectado": "Arquetipo",
                          "similitud_coseno": "Similitud", "score_final": "Score",
                          "percentil_score": "Percentil (vs. su posición)"})
        .round({"Similitud": 3, "Score": 1, "Percentil (vs. su posición)": 0}),
        width='stretch',
        hide_index=True,
        height=520,
    )

# ---------------------------------------------------------------------------
# TAB 2 — Ficha de jugador
# ---------------------------------------------------------------------------
with tab_ficha:
    st.subheader("Ficha individual")
    rfef_validos = rfef.dropna(subset=["Jugador", "Equipo", "Temporada"]).copy()
    opciones = (rfef_validos["Jugador"] + " — " + rfef_validos["Equipo"] + " (" + rfef_validos["Temporada"] + ")").tolist()
    idx_map = dict(zip(opciones, rfef_validos.index))
    seleccion = st.selectbox("Selecciona un jugador", opciones,
                              index=opciones.index(opciones[0]) if opciones else 0)
    jugador = rfef.loc[idx_map[seleccion]]
    grupo = jugador["grupo"]

    st.markdown(
        f"""<div style="font-family:'Space Grotesk', sans-serif; font-weight:700;
             color:#14213D; font-size:1.6rem; margin:0.3rem 0 0.6rem 0;">
             {jugador['Jugador']}
             <span style="font-family:'Inter', sans-serif; font-weight:500; color:#6B7280; font-size:1rem;">
             — {jugador['Equipo']} ({jugador['Temporada']})</span></div>""",
        unsafe_allow_html=True,
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
        fig_dist.add_vline(x=jugador["score_final"], line_width=3, line_color="#1B4332",
                            annotation_text=jugador["Jugador"], annotation_position="top",
                            annotation_font=dict(family="Space Grotesk, sans-serif", color="#14213D", size=12))
        fig_dist.add_vline(x=media_grupo, line_width=1, line_dash="dot", line_color="#6B7280",
                            annotation_text="media", annotation_font=dict(size=10, color="#6B7280"))
        fig_dist.update_layout(
            height=140, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
            xaxis_title=f"Distribución de scores — {grupo}s (1ª RFEF)",
            yaxis_visible=False,
            font=dict(family="Inter, sans-serif", color="#14213D", size=11),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_dist, width='stretch')

        st.markdown(
            f"""<div style="background:#EAF2EC; border:1px solid #1B4332; border-left:5px solid #1B4332;
                 border-radius:10px; padding:0.55rem 1rem; margin:0.6rem 0 0.9rem 0;
                 font-family:'Space Grotesk', sans-serif; font-weight:600; color:#14213D; font-size:1.05rem;">
                 {jugador['arquetipo_proyectado']}
                 <span style="font-family:'Inter', sans-serif; font-weight:500; color:#6B7280; font-size:0.8rem;">
                 · arquetipo proyectado ({grupo})</span>
                 </div>""",
            unsafe_allow_html=True,
        )

        c2, c3 = st.columns(2)
        c2.metric("Edad", int(jugador["Edad"]))
        c3.metric("Similitud", f"{jugador['similitud_coseno']:.2f}")

        st.markdown("**Por qué tiene este score (SHAP):**")
        factores = jugador["shap_top_factores"].split(" | ")
        nombres = [f.split(" (")[0] for f in factores]
        valores = [float(f.split("(")[1].replace(")", "").replace("+", "").replace("−", "-")) for f in factores]
        colores = ["#1B4332" if v >= 0 else "#B33A3A" for v in valores]
        fig_shap = go.Figure(go.Bar(
            x=valores, y=nombres, orientation="h", marker_color=colores,
            text=[f"{v:+.1f}" for v in valores], textposition="outside",
        ))
        fig_shap.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                                xaxis_title="Contribución al score (SHAP)",
                                font=dict(family="Inter, sans-serif", color="#14213D"),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_shap, width='stretch')

    with colB:
        radar_vars = RADAR_VARS[grupo]
        valores_pct = [percentiles[grupo].loc[jugador.name, v] for v in radar_vars]
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=valores_pct + [valores_pct[0]],
            theta=radar_vars + [radar_vars[0]],
            fill="toself", name=jugador["Jugador"], line_color="#1B4332",
            fillcolor="rgba(27, 67, 50, 0.25)",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False, height=420,
            title=f"Percentil dentro de su posición ({grupo}, 1ª RFEF)",
            font=dict(family="Inter, sans-serif", color="#14213D"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_radar, width='stretch')

# ---------------------------------------------------------------------------
# TAB 3 — Comparador
# ---------------------------------------------------------------------------
with tab_comparador:
    st.subheader("Comparador de jugadores")
    grupo_comp = st.selectbox("Posición a comparar", sorted(rfef["grupo"].unique()), key="grupo_comp")
    pool = rfef[rfef["grupo"] == grupo_comp]
    pool = pool.dropna(subset=["Jugador", "Equipo", "Temporada"]).copy()
    opciones_comp = (pool["Jugador"] + " — " + pool["Equipo"] + " (" + pool["Temporada"] + ")").tolist()

    c1, c2 = st.columns(2)
    with c1:
        sel1 = st.selectbox("Jugador 1", opciones_comp, index=0)
    with c2:
        sel2 = st.selectbox("Jugador 2", opciones_comp, index=min(1, len(opciones_comp) - 1))

    idx_map_comp = dict(zip(opciones_comp, pool.index))
    j1, j2 = pool.loc[idx_map_comp[sel1]], pool.loc[idx_map_comp[sel2]]

    radar_vars = RADAR_VARS[grupo_comp]
    fig = go.Figure()
    for j, color in [(j1, "#14213D"), (j2, "#C9762C")]:
        vals = [percentiles[grupo_comp].loc[j.name, v] for v in radar_vars]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=radar_vars + [radar_vars[0]],
            fill="toself", name=f"{j['Jugador']} ({j['Temporada']})", line_color=color,
        ))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=500,
                       legend=dict(font=dict(size=15, family="Space Grotesk, sans-serif")),
                       font=dict(family="Inter, sans-serif", color="#14213D"),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
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

    for nombre in VALIDACION_EMPIRICA:
        fila = rfef[rfef["Jugador"] == nombre]
        if fila.empty:
            continue
        fila = fila.sort_values("score_final", ascending=False).iloc[0]
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(
                    f"""<div style="font-family:'Space Grotesk', sans-serif; font-weight:700;
                         color:#14213D; font-size:1.35rem; line-height:1.2; margin-bottom:0.2rem;">
                         {fila['Jugador']}</div>""",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""<div style="font-family:'JetBrains Mono', monospace; font-weight:700;
                         color:#1B4332; font-size:2rem; line-height:1.1;">
                         {fila['score_final']:.1f} <span style="font-size:1rem; font-weight:500; color:#6B7280;">pts</span></div>""",
                    unsafe_allow_html=True,
                )
                st.caption(f"{fila['arquetipo_proyectado']} · {fila['Temporada']} · {fila['Equipo']}")
            with c2:
                st.write(VALIDACION_TEXTO.get(nombre, ""))
