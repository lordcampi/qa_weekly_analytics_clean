from __future__ import annotations

import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from qa_weekly_analytics.app.dashboard_logic import (  # noqa: E402
    compute_default_range,
    get_filter_options,
    map_critical_choice,
    quincena_preset_labels,
    resolve_selected_weeks,
    week_options_for_ui,
)
from qa_weekly_analytics.app.kpi_cards import KpiCardsError, build_kpi_cards  # noqa: E402
from qa_weekly_analytics.connectors.google_auth import GoogleAuthError, clear_cached_token, get_credentials  # noqa: E402
from qa_weekly_analytics.connectors.sheets_reader import SheetsReadError, read_range  # noqa: E402
from qa_weekly_analytics.domain.date_ranges import DateRange, list_monday_friday_weeks, merge_week_ranges, previous_week_monday_friday  # noqa: E402
from qa_weekly_analytics.domain.period_comparison import comparison_label, comparison_ranges_for_period  # noqa: E402
from qa_weekly_analytics.domain.validation import DataValidationError, clean_and_validate_rows  # noqa: E402
from qa_weekly_analytics.jobs.scheduler import start_scheduler  # noqa: E402
from qa_weekly_analytics.kpis.weekly_summary import compute_kpis  # noqa: E402
from qa_weekly_analytics.kpis.wow_recurrence import WoWRecurrenceResult, analyze_wow_recurrence  # noqa: E402
from qa_weekly_analytics.reporting.pdf_report import PDFReportError, build_pdf_report  # noqa: E402
from qa_weekly_analytics.storage.publish_weekly_snapshot import PublishSnapshotError, publish_weekly_snapshot  # noqa: E402
from qa_weekly_analytics.storage.settings import Settings, SettingsError  # noqa: E402
from qa_weekly_analytics.viz.dashboard_charts import critical_vs_non_critical_stacked, pareto_agents_chart, top_agents_bar, top_reasons_bar, trend_lv_bar  # noqa: E402
from qa_weekly_analytics.viz.table_styles import style_critical_table, style_ranking_table, style_recurrence_table  # noqa: E402

logger = logging.getLogger(__name__)

APP_GOOGLE_SCOPES: list[str] = ["https://www.googleapis.com/auth/spreadsheets"]


def _setup_logging() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s - %(message)s")


@st.cache_data(show_spinner=True)
def _load_and_clean_data(sheet_id: str, sheet_tab: str, sheet_range: str) -> tuple[pd.DataFrame, object]:
    credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")).resolve()
    token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", ".secrets/token.json")).resolve()
    try:
        creds = get_credentials(scopes=APP_GOOGLE_SCOPES, credentials_path=credentials_path, token_path=token_path)
        sheet_data = read_range(credentials=creds, sheet_id=sheet_id, sheet_tab=sheet_tab, sheet_range=sheet_range)
        valid_df, report = clean_and_validate_rows(sheet_data.df, source_row_start=2, max_examples=10)
        return valid_df, report
    except (GoogleAuthError, SheetsReadError, DataValidationError) as exc:
        logger.exception("Error cargando o limpiando datos")
        raise RuntimeError(str(exc)) from exc


def _apply_week_selection_to_dates(
    df: pd.DataFrame,
    *,
    use_week_picker: bool,
    selected_week_labels: list[str],
    week_options: dict[str, DateRange],
) -> tuple[date, date]:
    if use_week_picker and selected_week_labels:
        weeks = resolve_selected_weeks(selected_week_labels, week_options)
        if weeks:
            merged = merge_week_ranges(weeks)
            return merged.start_date, merged.end_date
    return st.session_state["start_date"], st.session_state["end_date"]


def _render_publish_section(df: pd.DataFrame, settings: Settings) -> None:
    st.subheader("Publicar semana cerrada")
    st.caption("Congela KPIs de la semana anterior L–V en Google Sheets y Excel histórico.")
    week_to_publish = previous_week_monday_friday(tz_name=settings.TIMEZONE)
    st.text(f"Semana: {week_to_publish.start_date} → {week_to_publish.end_date}")
    credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", ".secrets/credentials.json")).resolve()
    token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", ".secrets/token.json")).resolve()

    if st.button("Re-autorizar Google (lectura + escritura)", use_container_width=True):
        clear_cached_token(token_path)
        st.cache_data.clear()
        try:
            get_credentials(scopes=APP_GOOGLE_SCOPES, credentials_path=credentials_path, token_path=token_path, force_reauth=True)
            st.success("Google re-autorizado. Aceptá permisos de edición en Sheets si el navegador lo pide.")
        except GoogleAuthError as exc:
            st.error(str(exc))

    col_a, col_b = st.columns(2)
    with col_a:
        to_sheets = st.checkbox("Publicar en Google Sheets", value=True)
    with col_b:
        to_excel = st.checkbox("Publicar en Excel local", value=True)
    if st.button("Publicar semana cerrada", type="primary", use_container_width=True):
        write_creds = None
        if to_sheets:
            try:
                write_creds = get_credentials(
                    scopes=APP_GOOGLE_SCOPES,
                    credentials_path=credentials_path,
                    token_path=token_path,
                )
            except GoogleAuthError as exc:
                st.error(f"No se pudo autenticar para escritura: {exc}")
                st.info("Usá el botón «Re-autorizar Google» arriba y aceptá permiso para editar hojas de cálculo.")
                return
        try:
            result = publish_weekly_snapshot(
                df,
                week_range=week_to_publish,
                settings=settings,
                credentials=write_creds,
                to_sheets=to_sheets,
                to_excel=to_excel,
            )
            if result.skipped:
                st.warning(f"La semana {result.week_id} ya estaba publicada.")
            else:
                st.success(f"Semana {result.week_id} publicada correctamente.")
                if result.excel_path:
                    st.caption(f"Excel: {result.excel_path}")
        except PublishSnapshotError as exc:
            st.error(str(exc))
            if "insufficient authentication scopes" in str(exc).lower() or "scope" in str(exc).lower():
                st.info("Usá «Re-autorizar Google» y volvé a publicar.")


def _render_one_on_one_tab(
    df: pd.DataFrame,
    *,
    start_date: date,
    end_date: date,
    agents: list[str],
    reasons: list[str],
    critical: bool | None,
    wow_results: WoWRecurrenceResult,
    comparison_lbl: str,
    recurrent_agents_comparison: pd.DataFrame,
) -> None:
    st.subheader("Modo 1:1 — Revisión por agente")
    st.caption("Selecciona un agente y el periodo (semanas o fechas) para preparar la reunión.")
    one_agent = st.selectbox("Agente para 1:1", options=[""] + agents, index=0)
    if not one_agent:
        st.info("Elige un agente para ver su detalle en el periodo seleccionado.")
        return

    agent_filter = [one_agent]
    kpis_1a1 = compute_kpis(
        df,
        start_date=start_date,
        end_date=end_date,
        agents=agent_filter,
        reasons=reasons or None,
        critical=critical,
    )
    st.metric("Errores del agente", kpis_1a1.total_errors)
    st.metric("Críticos", kpis_1a1.critical_count)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Motivos")
        if kpis_1a1.by_reason.empty:
            st.caption("Sin errores en el periodo.")
        else:
            st.dataframe(style_ranking_table(kpis_1a1.by_reason), use_container_width=True)
    with col2:
        st.subheader("Reincidencias agente + motivo")
        st.dataframe(style_recurrence_table(kpis_1a1.recurrence["repeated_agent_reason"]), use_container_width=True)

    st.subheader("Evolución en el periodo")
    st.info(comparison_lbl)
    full_agent_df = df[df["agent"] == one_agent]
    current_range, previous_range = comparison_ranges_for_period(start_date, end_date)
    agent_wow = analyze_wow_recurrence(full_agent_df, current_week=current_range, previous_week=previous_range)

    status = "—"
    if one_agent in wow_results.persistent_agents:
        status = "Persistente"
    elif one_agent in wow_results.new_alert_agents:
        status = "Nuevo en alerta"
    elif one_agent in wow_results.corrected_agents:
        status = "Subsanado"
    st.metric("Estado evolutivo (periodo global)", status)

    if not kpis_1a1.critical_table.empty:
        st.subheader("Detalle críticos")
        st.dataframe(style_critical_table(kpis_1a1.critical_table), use_container_width=True)

    if not recurrent_agents_comparison.empty and one_agent in recurrent_agents_comparison["agent"].values:
        st.subheader("Comparación reincidentes")
        row = recurrent_agents_comparison[recurrent_agents_comparison["agent"] == one_agent]
        st.dataframe(row, use_container_width=True)

    if st.button("Generar PDF 1:1", use_container_width=True):
        try:
            pdf_bytes = build_pdf_report(
                kpis_1a1,
                title=f"QA 1:1 — {one_agent}",
                wow_results=agent_wow,
                comparison_label=comparison_lbl,
                recurrent_agents_comparison=recurrent_agents_comparison[
                    recurrent_agents_comparison["agent"] == one_agent
                ] if not recurrent_agents_comparison.empty else recurrent_agents_comparison,
            )
            st.download_button(
                "Descargar PDF 1:1",
                data=pdf_bytes,
                file_name=f"qa_1a1_{one_agent}_{start_date}_{end_date}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except PDFReportError as exc:
            st.error(str(exc))


def _build_recurrent_agents_comparison(df: pd.DataFrame, *, current_range: DateRange, previous_range: DateRange, wow_results: WoWRecurrenceResult) -> pd.DataFrame:
    """Compara SOLO agentes reincidentes reales entre las dos semanas.

    Reincidente real = agente que aparece como persistente en el análisis WoW,
    es decir, tuvo reincidencia en el periodo anterior y volvió a reincidir
    en el periodo analizado. No incluye nuevos en alerta.
    """
    recurrent_agents = sorted(set(wow_results.persistent_agents or []))
    columns = [
        "agent",
        "previous_errors",
        "current_errors",
        "delta",
        "delta_pct",
        "previous_critical_errors",
        "current_critical_errors",
        "critical_delta",
        "critical_delta_pct",
    ]
    if not recurrent_agents:
        return pd.DataFrame(columns=columns)

    previous_df = df[
        (df["date"] >= previous_range.start_date)
        & (df["date"] <= previous_range.end_date)
        & (df["agent"].isin(recurrent_agents))
    ]
    current_df = df[
        (df["date"] >= current_range.start_date)
        & (df["date"] <= current_range.end_date)
        & (df["agent"].isin(recurrent_agents))
    ]

    previous_counts = previous_df.groupby("agent").size().to_dict()
    current_counts = current_df.groupby("agent").size().to_dict()

    previous_critical_counts = previous_df[previous_df["is_critical"]].groupby("agent").size().to_dict() if "is_critical" in previous_df.columns else {}
    current_critical_counts = current_df[current_df["is_critical"]].groupby("agent").size().to_dict() if "is_critical" in current_df.columns else {}

    rows = []
    for agent in recurrent_agents:
        prev = int(previous_counts.get(agent, 0))
        curr = int(current_counts.get(agent, 0))
        delta = curr - prev
        delta_pct = (delta / prev) if prev else (1.0 if curr else 0.0)

        prev_critical = int(previous_critical_counts.get(agent, 0))
        curr_critical = int(current_critical_counts.get(agent, 0))
        critical_delta = curr_critical - prev_critical
        critical_delta_pct = (critical_delta / prev_critical) if prev_critical else (1.0 if curr_critical else 0.0)

        rows.append(
            {
                "agent": agent,
                "previous_errors": prev,
                "current_errors": curr,
                "delta": delta,
                "delta_pct": delta_pct,
                "previous_critical_errors": prev_critical,
                "current_critical_errors": curr_critical,
                "critical_delta": critical_delta,
                "critical_delta_pct": critical_delta_pct,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["current_errors", "previous_errors", "agent"], ascending=[False, False, True]
    )

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


def _render_wow_recurrence_tab(wow_results: WoWRecurrenceResult, comparison_label: str) -> None:
    st.subheader("Evolución de Reincidencias")
    st.caption("Compara el periodo seleccionado contra el periodo anterior de igual duración.")
    st.info(comparison_label)
    st.metric(label="Tasa de Subsanación", value=f"{wow_results.correction_rate:.1%}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Agentes Subsanados")
        if wow_results.corrected_agents:
            st.dataframe(pd.DataFrame(wow_results.corrected_agents, columns=["Agente"]), use_container_width=True)
        else:
            st.caption("No hay agentes en esta categoría.")
    with col2:
        st.subheader("Nuevos en Alerta")
        if wow_results.new_alert_agents:
            st.dataframe(pd.DataFrame(wow_results.new_alert_agents, columns=["Agente"]), use_container_width=True)
        else:
            st.caption("No hay agentes en esta categoría.")
    with col3:
        st.subheader("Agentes Persistentes")
        if wow_results.persistent_agents:
            st.dataframe(pd.DataFrame(wow_results.persistent_agents, columns=["Agente"]), use_container_width=True)
        else:
            st.caption("No hay agentes en esta categoría.")


def _render_pdf_tab(kpis: object, wow_results: WoWRecurrenceResult, comparison_label: str, recurrent_agents_comparison: pd.DataFrame) -> None:
    st.subheader("Exportar informe en PDF")
    st.caption("El PDF incluye resumen, gráficos, evolución semanal, rankings, reincidencias y detalle de críticos.")
    title = st.text_input("Título del informe", value="QA Weekly Analytics — Informe")
    generated_by = st.text_input("Preparado por (opcional)", value="")
    additional_note = st.text_area("Nota adicional para el PDF (opcional)", value="", height=100)
    default_name = f"qa_weekly_report_{kpis.start_date}_{kpis.end_date}.pdf"
    if st.button("Generar PDF", type="primary", use_container_width=True):
        try:
            pdf_bytes = build_pdf_report(
                kpis,
                title=title,
                generated_by=generated_by,
                additional_note=additional_note,
                wow_results=wow_results,
                comparison_label=comparison_label,
                recurrent_agents_comparison=recurrent_agents_comparison,
            )
            st.success("PDF generado correctamente ✅")
            st.download_button("Descargar informe PDF", data=pdf_bytes, file_name=default_name, mime="application/pdf", use_container_width=True)
        except PDFReportError as exc:
            logger.exception("No se pudo generar PDF")
            st.error(str(exc))


def main() -> None:
    _setup_logging()
    st.set_page_config(page_title="QA Weekly Analytics", layout="wide")
    st.title("QA Weekly Analytics — Dashboard")

    try:
        settings = Settings.from_env()
    except SettingsError as exc:
        st.error(f"Configuración inválida: {exc}")
        st.stop()

    start_scheduler(settings)

    with st.sidebar:
        st.header("Controles")
        st.caption("Fuente: Google Sheets")
        st.code(f"Tab: {settings.SHEET_TAB}\nRango: {settings.SHEET_RANGE}", language="text")
        if st.button("Refrescar datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        df, quality_report = _load_and_clean_data(settings.SHEET_ID, settings.SHEET_TAB, settings.SHEET_RANGE)
    except RuntimeError as exc:
        st.error("No se pudo cargar/limpiar la hoja. Verifica credenciales y permisos de Sheets.")
        st.exception(exc)
        st.stop()

    _render_quality_report(quality_report)
    if df.empty:
        st.warning("No hay filas válidas tras QA-005.")
        st.stop()

    opts = get_filter_options(df)
    available_weeks = list_monday_friday_weeks(df)
    week_options = week_options_for_ui(available_weeks)

    if "start_date" not in st.session_state or "end_date" not in st.session_state:
        start_default, end_default = compute_default_range(settings.TIMEZONE)
        st.session_state["start_date"] = start_default
        st.session_state["end_date"] = end_default

    with st.sidebar:
        st.subheader("Rango de fechas")
        use_week_picker = st.toggle("Seleccionar por semanas", value=False)
        selected_week_labels: list[str] = []
        if use_week_picker and week_options:
            if st.button("Preset: Quincena (2 semanas)", use_container_width=True):
                st.session_state["selected_weeks"] = quincena_preset_labels(week_options, 2)
            selected_week_labels = st.multiselect(
                "Semanas L–V",
                options=list(week_options.keys()),
                default=st.session_state.get("selected_weeks", quincena_preset_labels(week_options, 1)),
                key="week_multiselect",
            )
            st.session_state["selected_weeks"] = selected_week_labels
        else:
            if st.button("Semana anterior (L–V)", use_container_width=True):
                start_default, end_default = compute_default_range(settings.TIMEZONE)
                st.session_state["start_date"] = start_default
                st.session_state["end_date"] = end_default
            start_date = st.date_input("Desde", value=st.session_state["start_date"])
            end_date = st.date_input("Hasta", value=st.session_state["end_date"])
            st.session_state["start_date"] = start_date
            st.session_state["end_date"] = end_date

        st.subheader("Filtros")
        agents = st.multiselect("Agente", options=opts.agents, default=[])
        reasons = st.multiselect("Motivo", options=opts.reasons, default=[])
        critical_choice = st.selectbox("Crítico", ["Todos", "Sólo críticos", "Sólo no críticos"], index=0)

    effective_start, effective_end = _apply_week_selection_to_dates(
        df,
        use_week_picker=use_week_picker,
        selected_week_labels=selected_week_labels,
        week_options=week_options,
    )

    if effective_start > effective_end:
        st.error("Rango inválido: 'Desde' no puede ser mayor que 'Hasta'.")
        st.stop()

    critical = map_critical_choice(critical_choice)
    kpis = compute_kpis(
        df,
        start_date=effective_start,
        end_date=effective_end,
        agents=agents or None,
        reasons=reasons or None,
        critical=critical,
    )

    current_range, previous_range = comparison_ranges_for_period(effective_start, effective_end)
    wow_recurrence_kpis = analyze_wow_recurrence(df, current_week=current_range, previous_week=previous_range)
    comparison_lbl = comparison_label(current_range, previous_range)
    recurrent_agents_comparison = _build_recurrent_agents_comparison(
        df,
        current_range=current_range,
        previous_range=previous_range,
        wow_results=wow_recurrence_kpis,
    )

    st.caption(f"Rango: {kpis.start_date} → {kpis.end_date} | Filas tras filtros: {kpis.filtered_rows}")
    _render_kpi_cards(kpis)
    st.divider()

    tabs = st.tabs(["Resumen", "Agentes", "Motivos", "Tendencia", "Críticos", "Evolución Semanal", "Modo 1:1", "Histórico", "PDF"])

    with tabs[0]:
        st.subheader("Resumen visual")
        st.plotly_chart(trend_lv_bar(kpis), use_container_width=True, key="plot_resumen_trend_lv")
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Top agentes")
            st.plotly_chart(top_agents_bar(kpis), use_container_width=True, key="plot_resumen_top_agents")
        with col_right:
            st.subheader("Top motivos")
            st.plotly_chart(top_reasons_bar(kpis), use_container_width=True, key="plot_resumen_top_reasons")
        st.subheader("Reincidencias")
        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("Tickets repetidos (ticket_id)")
            st.dataframe(style_recurrence_table(kpis.recurrence["repeated_tickets"]), use_container_width=True)
        with col_b:
            st.caption("Patrón repetido (agente + motivo)")
            st.dataframe(style_recurrence_table(kpis.recurrence["repeated_agent_reason"]), use_container_width=True)

    with tabs[1]:
        st.subheader("Ranking por agente")
        st.plotly_chart(top_agents_bar(kpis), use_container_width=True, key="plot_agentes_top_agents")
        st.subheader("Pareto 80/20 — Agentes")
        st.plotly_chart(pareto_agents_chart(kpis), use_container_width=True, key="plot_agentes_pareto_agents")
        st.dataframe(style_ranking_table(kpis.by_agent), use_container_width=True)

    with tabs[2]:
        st.subheader("Ranking por motivo")
        st.plotly_chart(top_reasons_bar(kpis), use_container_width=True, key="plot_motivos_top_reasons")
        st.dataframe(style_ranking_table(kpis.by_reason), use_container_width=True)

    with tabs[3]:
        st.subheader("Tendencia diaria L–V")
        st.plotly_chart(trend_lv_bar(kpis), use_container_width=True, key="plot_tendencia_trend_lv")
        st.subheader("Críticos vs no críticos")
        st.plotly_chart(critical_vs_non_critical_stacked(df, start_date=effective_start, end_date=effective_end, agents=agents or None, reasons=reasons or None), use_container_width=True, key="plot_tendencia_critical_vs_non_critical")

    with tabs[4]:
        st.subheader("Detalle de críticos")
        if kpis.critical_table.empty:
            st.info("No hay errores críticos en el rango/filtros seleccionados.")
        else:
            st.dataframe(style_critical_table(kpis.critical_table), use_container_width=True)

    with tabs[5]:
        _render_wow_recurrence_tab(wow_recurrence_kpis, comparison_lbl)

    with tabs[6]:
        _render_one_on_one_tab(
            df,
            start_date=effective_start,
            end_date=effective_end,
            agents=opts.agents,
            reasons=reasons,
            critical=critical,
            wow_results=wow_recurrence_kpis,
            comparison_lbl=comparison_lbl,
            recurrent_agents_comparison=recurrent_agents_comparison,
        )

    with tabs[7]:
        _render_publish_section(df, settings)
        excel_path = settings.historic_excel_path_resolved(_REPO_ROOT)
        st.caption(f"Excel histórico: {excel_path}")
        if excel_path.exists():
            st.download_button(
                "Descargar Excel histórico",
                data=excel_path.read_bytes(),
                file_name=excel_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with tabs[8]:
        _render_pdf_tab(kpis, wow_recurrence_kpis, comparison_lbl, recurrent_agents_comparison)


if __name__ == "__main__":
    main()
