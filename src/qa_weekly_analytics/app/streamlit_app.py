from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from qa_weekly_analytics.app.dashboard_logic import (  # noqa: E402
    FilterOptions,
    get_available_weeks,
    get_filter_options,
    resolve_selected_weeks,
)
from qa_weekly_analytics.app.kpi_cards import KpiCardsError, build_kpi_cards  # noqa: E402
from qa_weekly_analytics.domain.date_ranges import (  # noqa: E402
    DateRange,
    available_years,
    iso_week_label,
    merge_week_ranges,
)
from qa_weekly_analytics.domain.validation import DataValidationError, clean_and_validate_rows  # noqa: E402
from qa_weekly_analytics.kpis.weekly_comparison import compare_weeks  # noqa: E402
from qa_weekly_analytics.kpis.weekly_summary import compute_kpis  # noqa: E402
from qa_weekly_analytics.reporting.pdf_report import PDFReportError, build_pdf_report  # noqa: E402
from qa_weekly_analytics.storage.settings import Settings, SettingsError  # noqa: E402
from qa_weekly_analytics.viz.dashboard_charts import (  # noqa: E402
    agent_trend_line,
    agents_errors_heatmap,
    comparison_side_by_side,
    top_agents_bar,
    top_reasons_bar,
    weekly_trend_bar,
)
from qa_weekly_analytics.viz.table_styles import style_critical_table, style_ranking_table, style_recurrence_table  # noqa: E402

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


@st.cache_data(show_spinner=True)
def _load_and_clean_data(data_url: str) -> tuple[pd.DataFrame, object]:
    """Carga datos desde CSV público de Google Sheets."""
    try:
        raw_df = pd.read_csv(data_url)
        valid_df, report = clean_and_validate_rows(raw_df, source_row_start=2, max_examples=10)
        return valid_df, report
    except DataValidationError as exc:
        logger.exception("Error validando datos")
        raise RuntimeError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Error cargando CSV desde URL")
        raise RuntimeError(f"No se pudo cargar la fuente de datos: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers de renderizado
# ---------------------------------------------------------------------------


def _render_quality_report(report: object) -> None:
    with st.expander("Calidad de datos (QA-005)", expanded=False):
        st.write(report)


def _render_kpi_cards(kpis: object) -> None:
    try:
        cards = build_kpi_cards(kpis)
    except KpiCardsError as exc:
        st.warning(f"No se pudieron renderizar las tarjetas KPI: {exc}")
        return
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards, strict=True):
        col.metric(label=card.label, value=card.value, help=card.help_text)


def _render_pdf_export(kpis: object) -> None:
    with st.expander("📄 Exportar informe PDF", expanded=False):
        st.subheader("Exportar informe en PDF")
        st.caption("El PDF incluye resumen, gráficos, rankings y detalle de críticos.")
        title = st.text_input("Título del informe", value="QA Weekly Analytics — Informe", key="pdf_title")
        generated_by = st.text_input("Preparado por (opcional)", value="", key="pdf_author")
        additional_note = st.text_area("Nota adicional para el PDF (opcional)", value="", height=80, key="pdf_note")
        default_name = f"qa_weekly_report_{kpis.start_date}_{kpis.end_date}.pdf"
        if st.button("Generar PDF", type="primary", use_container_width=True, key="pdf_button"):
            try:
                pdf_bytes = build_pdf_report(
                    kpis,
                    title=title,
                    generated_by=generated_by,
                    additional_note=additional_note,
                )
                st.success("PDF generado correctamente ✅")
                st.download_button(
                    "Descargar informe PDF",
                    data=pdf_bytes,
                    file_name=default_name,
                    mime="application/pdf",
                    use_container_width=True,
                )
            except PDFReportError as exc:
                logger.exception("No se pudo generar PDF")
                st.error(str(exc))


# ---------------------------------------------------------------------------
# Tab 1: Explorar Semanas
# ---------------------------------------------------------------------------


def _render_explore_tab(
    df: pd.DataFrame,
    all_weeks: dict[str, DateRange],
    agents: list[str] | None,
    critical_only: bool,
) -> None:
    st.subheader("📊 Explorar Semanas")
    st.caption("Selecciona una o más semanas para ver KPIs agregados y tendencia histórica.")

    if not all_weeks:
        st.info("No hay semanas con datos para el año seleccionado.")
        return

    default_weeks = [list(all_weeks.keys())[-1]] if all_weeks else []
    selected = st.multiselect(
        "Semanas a consultar",
        options=list(all_weeks.keys()),
        default=default_weeks,
        key="explore_weeks",
    )

    if not selected:
        st.info("Selecciona al menos una semana para ver los KPIs.")
        return

    weeks = resolve_selected_weeks(selected, all_weeks)
    if not weeks:
        return

    merged = merge_week_ranges(weeks)
    critical_filter: bool | None = True if critical_only else None

    kpis = compute_kpis(
        df,
        start_date=merged.start_date,
        end_date=merged.end_date,
        agents=agents,
        critical=critical_filter,
    )

    st.caption(
        f"Rango: {kpis.start_date} → {kpis.end_date} | Filas: {kpis.filtered_rows}  |  Semanas: {len(weeks)}"
    )
    _render_kpi_cards(kpis)

    # Tendencia semanal (una barra por semana)
    st.subheader("Tendencia semanal")
    weekly_data: list[tuple[str, int, int]] = []
    weekly_agent_counts: list[dict[str, int]] = []
    week_labels: list[str] = []
    for w in weeks:
        label = iso_week_label(w)
        wk = compute_kpis(
            df,
            start_date=w.start_date,
            end_date=w.end_date,
            agents=agents,
            critical=critical_filter,
        )
        weekly_data.append((label, wk.total_errors, wk.critical_count))
        week_labels.append(label)
        if wk.by_agent.empty:
            weekly_agent_counts.append({})
        else:
            weekly_agent_counts.append(
                {str(row["agent"]): int(row["count"]) for _, row in wk.by_agent.iterrows()}
            )

    st.plotly_chart(weekly_trend_bar(weekly_data, title="Errores por semana"), use_container_width=True)

    # Rankings
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Top agentes")
        st.plotly_chart(top_agents_bar(kpis), use_container_width=True, key="explore_top_agents")
        st.dataframe(style_ranking_table(kpis.by_agent), use_container_width=True)
    with col_b:
        st.subheader("Top motivos")
        st.plotly_chart(top_reasons_bar(kpis), use_container_width=True, key="explore_top_reasons")
        st.dataframe(style_ranking_table(kpis.by_reason), use_container_width=True)

    # Reincidencias
    st.subheader("Reincidencias")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.caption("Tickets repetidos")
        st.dataframe(style_recurrence_table(kpis.recurrence["repeated_tickets"]), use_container_width=True)
    with col_r2:
        st.caption("Patrón repetido (agente + motivo)")
        st.dataframe(style_recurrence_table(kpis.recurrence["repeated_agent_reason"]), use_container_width=True)

    # Críticos
    st.subheader("Detalle de críticos")
    if kpis.critical_table.empty:
        st.info("No hay errores críticos en el rango seleccionado.")
    else:
        st.dataframe(style_critical_table(kpis.critical_table), use_container_width=True)

    # Errores por agente (heatmap)
    st.subheader("Errores por agente")
    top_agents = (
        []
        if kpis.by_agent.empty
        else [str(a) for a in kpis.by_agent["agent"].head(10).tolist()]
    )
    agent_series = {
        agent: [week_counts.get(agent, 0) for week_counts in weekly_agent_counts]
        for agent in top_agents
    }
    st.plotly_chart(
        agents_errors_heatmap(week_labels, agent_series),
        use_container_width=True,
        key="explore_agents_heatmap",
    )


# ---------------------------------------------------------------------------
# Tab 2: Comparar Semanas
# ---------------------------------------------------------------------------


def _render_compare_tab(
    df: pd.DataFrame,
    all_weeks: dict[str, DateRange],
    agents: list[str] | None,
    critical_only: bool,
) -> None:
    st.subheader("⚖️ Comparar Semanas")
    st.caption("Compara dos semanas lado a lado para ver evolución.")

    week_labels = list(all_weeks.keys())
    if len(week_labels) < 2:
        st.info("Se necesitan al menos 2 semanas con datos para comparar.")
        return

    col_a, col_b = st.columns(2)
    with col_a:
        week_a_label = st.selectbox(
            "Semana A (base)", options=week_labels, index=max(0, len(week_labels) - 2), key="cmp_week_a"
        )
    with col_b:
        week_b_label = st.selectbox(
            "Semana B (comparar)", options=week_labels, index=len(week_labels) - 1, key="cmp_week_b"
        )

    if week_a_label == week_b_label:
        st.warning("Selecciona dos semanas diferentes para comparar.")
        return

    week_a = all_weeks[week_a_label]
    week_b = all_weeks[week_b_label]

    if week_a.start_date > week_b.start_date:
        week_a, week_b = week_b, week_a
        week_a_label, week_b_label = week_b_label, week_a_label

    comparison = compare_weeks(df, week_a=week_a, week_b=week_b, agents=agents, critical_only=critical_only)

    # KPI Cards comparativos
    st.subheader("Resumen comparativo")
    kcol1, kcol2, kcol3 = st.columns(3)
    delta_arrow = "↑" if comparison.delta_errors > 0 else ("↓" if comparison.delta_errors < 0 else "—")
    delta_color = "inverse" if comparison.delta_errors > 0 else ("inverse" if comparison.delta_errors < 0 else "off")

    with kcol1:
        st.metric(comparison.week_a_label, comparison.kpis_a.total_errors)
    with kcol2:
        st.metric(
            comparison.week_b_label,
            comparison.kpis_b.total_errors,
            delta=f"{delta_arrow} {abs(comparison.delta_errors)}",
            delta_color=delta_color,
        )
    with kcol3:
        st.metric("Variación %", f"{comparison.delta_pct:+.1%}")

    ccol1, ccol2 = st.columns(2)
    with ccol1:
        st.metric("Críticos — A", comparison.kpis_a.critical_count)
    with ccol2:
        st.metric("Críticos — B", comparison.kpis_b.critical_count, delta=f"{comparison.delta_critical:+d}")

    # Gráfico side-by-side
    st.subheader("Comparación por agente")
    st.plotly_chart(
        comparison_side_by_side(
            comparison.week_a_label,
            comparison.week_b_label,
            comparison.kpis_a,
            comparison.kpis_b,
        ),
        use_container_width=True,
    )

    # Movimiento de agentes
    st.subheader("Movimiento de agentes")
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("🟢 Mejoraron", len(comparison.agents_improved))
        if comparison.agents_improved:
            st.caption(", ".join(comparison.agents_improved[:5]))
    with mc2:
        st.metric("🔴 Empeoraron", len(comparison.agents_declined))
        if comparison.agents_declined:
            st.caption(", ".join(comparison.agents_declined[:5]))
    with mc3:
        st.metric("🟡 Nuevos", len(comparison.agents_new))
        if comparison.agents_new:
            st.caption(", ".join(comparison.agents_new[:5]))
    with mc4:
        st.metric("⚪ Resueltos", len(comparison.agents_resolved))
        if comparison.agents_resolved:
            st.caption(", ".join(comparison.agents_resolved[:5]))


# ---------------------------------------------------------------------------
# Tab 3: Detalle por Agente
# ---------------------------------------------------------------------------


def _render_agent_tab(
    df: pd.DataFrame,
    agent: str,
    all_weeks: dict[str, DateRange],
    critical_only: bool,
) -> None:
    st.subheader(f"👤 Detalle — {agent}")
    st.caption("Comportamiento del agente a lo largo de las semanas seleccionadas.")

    if not all_weeks:
        st.info("No hay semanas con datos.")
        return

    week_labels = list(all_weeks.keys())
    selected_labels = st.multiselect(
        "Semanas a analizar",
        options=week_labels,
        default=week_labels[-4:] if len(week_labels) >= 4 else week_labels,
        key="agent_detail_weeks",
    )

    if not selected_labels:
        st.info("Selecciona al menos una semana.")
        return

    weeks = resolve_selected_weeks(selected_labels, all_weeks)
    critical_filter: bool | None = True if critical_only else None

    merged = merge_week_ranges(weeks)
    kpis = compute_kpis(
        df,
        start_date=merged.start_date,
        end_date=merged.end_date,
        agents=[agent],
        critical=critical_filter,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total errores", kpis.total_errors)
    with col2:
        st.metric("Críticos", kpis.critical_count)
    with col3:
        st.metric("Tasa criticidad", f"{kpis.critical_pct:.1%}")

    st.subheader("Tendencia semanal")
    agent_weekly: list[tuple[str, int]] = []
    for w in weeks:
        label = iso_week_label(w)
        wk = compute_kpis(
            df, start_date=w.start_date, end_date=w.end_date, agents=[agent], critical=critical_filter
        )
        agent_weekly.append((label, wk.total_errors))

    st.plotly_chart(agent_trend_line(agent_weekly, agent), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Motivos")
        if kpis.by_reason.empty:
            st.caption("Sin errores en el periodo.")
        else:
            st.dataframe(style_ranking_table(kpis.by_reason), use_container_width=True)
    with col_b:
        st.subheader("Reincidencias agente + motivo")
        st.dataframe(style_recurrence_table(kpis.recurrence["repeated_agent_reason"]), use_container_width=True)

    if not kpis.critical_table.empty:
        st.subheader("Detalle críticos")
        st.dataframe(style_critical_table(kpis.critical_table), use_container_width=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _setup_logging()
    st.set_page_config(page_title="QA Weekly Analytics", layout="wide")
    st.title("QA Weekly Analytics — Dashboard")

    # Settings: Streamlit Cloud (st.secrets) o local (.env)
    try:
        settings = Settings.from_streamlit_secrets()
    except SettingsError:
        try:
            settings = Settings.from_env()
        except SettingsError as exc:
            st.error(f"Configuración inválida: {exc}")
            return

    # Carga de datos (CSV público)
    with st.sidebar:
        st.header("🔧 Controles")
        st.caption("Fuente: Google Sheets (CSV público)")
        if st.button("🔄 Refrescar datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        df, quality_report = _load_and_clean_data(settings.DATA_URL)
    except RuntimeError as exc:
        st.error("No se pudo cargar/limpiar los datos desde la URL configurada.")
        st.exception(exc)
        return

    _render_quality_report(quality_report)

    if df.empty:
        st.warning("No hay filas válidas tras QA-005.")
        return

    opts: FilterOptions = get_filter_options(df)
    years: list[int] = available_years(df)

    # Sidebar
    with st.sidebar:
        st.subheader("📅 Periodo")
        selected_year = st.selectbox("Año", options=years, index=0 if years else 0, key="sidebar_year")
        st.subheader("👥 Filtros")
        agent_choice = st.selectbox("Agente", options=["Todos"] + opts.agents, index=0, key="sidebar_agent")
        critical_only = st.toggle("Solo críticos", value=False, key="sidebar_critical")

    all_weeks = get_available_weeks(df, selected_year)

    if not all_weeks:
        st.warning(f"No hay semanas con datos para el año {selected_year}.")
        st.stop()

    agents_filter: list[str] | None = None
    selected_agent: str | None = None
    if agent_choice != "Todos":
        agents_filter = [agent_choice]
        selected_agent = agent_choice

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Explorar", "⚖️ Comparar", "👤 Detalle Agente"])

    with tab1:
        _render_explore_tab(df, all_weeks=all_weeks, agents=agents_filter, critical_only=critical_only)

    with tab2:
        _render_compare_tab(df, all_weeks=all_weeks, agents=agents_filter, critical_only=critical_only)

    with tab3:
        if selected_agent:
            _render_agent_tab(df, agent=selected_agent, all_weeks=all_weeks, critical_only=critical_only)
        else:
            st.info("👈 Selecciona un agente en el panel lateral para ver su detalle.")

    # PDF Export
    if all_weeks:
        latest_week = all_weeks[list(all_weeks.keys())[-1]]
        kpis_pdf = compute_kpis(
            df,
            start_date=latest_week.start_date,
            end_date=latest_week.end_date,
            agents=agents_filter,
            critical=True if critical_only else None,
        )
        _render_pdf_export(kpis_pdf)


if __name__ == "__main__":
    main()