from __future__ import annotations

import html
import io
from datetime import datetime, timezone
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFReportError(Exception):
    """Error generando el informe PDF."""


def _safe(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and pd.isna(value):
            return ""
    except Exception:
        pass
    return html.escape(str(value))


def _fmt_date(value: Any) -> str:
    try:
        return value.strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except Exception:
        return "0.0%"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _truncate_label(value: Any, max_len: int = 44) -> str:
    text = str(value)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "qa_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17365D"),
            spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "qa_heading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "qa_body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
        ),
        "muted": ParagraphStyle(
            "qa_muted",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#666666"),
        ),
        "th": ParagraphStyle(
            "qa_th",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=colors.white,
        ),
        "td": ParagraphStyle(
            "qa_td",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
        ),
        "metric_label": ParagraphStyle(
            "qa_metric_label",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#666666"),
        ),
        "metric_value": ParagraphStyle(
            "qa_metric_value",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17365D"),
        ),
    }


def _fig_to_png(fig: plt.Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=155, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def _img(png: bytes, max_width: float) -> Image:
    image = Image(io.BytesIO(png))
    ratio = max_width / float(image.imageWidth)
    image.drawWidth = max_width
    image.drawHeight = float(image.imageHeight) * ratio
    return image


def _prep_df(df: pd.DataFrame | None, columns: Iterable[str] | None = None, max_rows: int = 50) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if columns is not None:
        existing = [c for c in columns if c in out.columns]
        out = out[existing]

    out = out.head(max_rows).copy()

    for col in out.columns:
        if col in {"share", "cumulative_share", "critical_pct"}:
            out[col] = out[col].map(_fmt_pct)
        elif col == "date":
            out[col] = out[col].map(_fmt_date)
        else:
            out[col] = out[col].fillna("").astype(str)

    rename = {
        "row_number": "Fila",
        "date": "Fecha",
        "agent": "Agente",
        "ticket_id": "Caso/Ticket",
        "reason": "Motivo",
        "notes": "Observaciones",
        "count": "Cantidad",
        "share": "%",
        "cumulative_share": "% acum.",
    }
    return out.rename(columns={c: rename.get(c, c) for c in out.columns})


def _critical_table(df: pd.DataFrame | None, st: dict[str, ParagraphStyle]) -> Table | Paragraph:
    pdf_df = _prep_df(df, ["row_number", "date", "agent", "ticket_id", "reason", "notes"], 50)
    if pdf_df.empty:
        return Paragraph("No hay errores críticos en el rango/filtros seleccionados.", st["muted"])

    data: list[list[Any]] = []
    data.append([Paragraph(_safe(col), st["th"]) for col in pdf_df.columns])
    for _, row in pdf_df.iterrows():
        data.append([Paragraph(_safe(row[col]), st["td"]) for col in pdf_df.columns])

    table = Table(data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E2F3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _recurrence_percent(kpis: Any) -> float:
    rec = getattr(kpis, "recurrence", {}) or {}
    pairs = rec.get("repeated_agent_reason")
    total = _safe_float(getattr(kpis, "total_errors", 0), 0.0)
    if total <= 0 or pairs is None or pairs.empty or "count" not in pairs.columns:
        return 0.0
    return float(pairs["count"].sum()) / total


def _empty_chart(title: str, subtitle: str = "") -> bytes:
    fig, ax = plt.subplots(figsize=(10.2, 3.8), facecolor="white")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", color="#111827", pad=16)
    if subtitle:
        ax.text(0, 0.92, subtitle, transform=ax.transAxes, fontsize=9.5, color="#6B7280")
    ax.text(0.5, 0.45, "Sin datos para mostrar", ha="center", va="center", fontsize=13, color="#6B7280")
    return _fig_to_png(fig)


def _modern_barh_png(
    df: pd.DataFrame | None,
    *,
    label_col: str,
    value_col: str = "count",
    pct_col: str | None = None,
    title: str,
    subtitle: str,
    color: str,
    max_items: int = 10,
    percent_denominator: float | None = None,
) -> bytes:
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        return _empty_chart(title, subtitle)

    data = df.head(max_items).copy().sort_values(value_col, ascending=True)
    labels = [_truncate_label(x) for x in data[label_col].tolist()]
    values = [_safe_float(v) for v in data[value_col].tolist()]

    if pct_col and pct_col in data.columns:
        percentages = [_safe_float(v) for v in data[pct_col].tolist()]
    else:
        denom = percent_denominator if percent_denominator and percent_denominator > 0 else sum(values)
        percentages = [(v / denom if denom else 0.0) for v in values]

    fig, ax = plt.subplots(figsize=(10.2, 4.65), facecolor="white")
    ypos = list(range(len(labels)))

    bars = ax.barh(ypos, values, color=color, alpha=0.93, height=0.58)
    ax.barh(ypos, values, color=color, alpha=0.16, height=0.84)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)

    max_value = max(values) if values else 1.0
    for bar, value, pct in zip(bars, values, percentages):
        ax.text(
            bar.get_width() + (max_value * 0.02),
            bar.get_y() + bar.get_height() / 2,
            f"{int(value)} ({pct:.1%})",
            va="center",
            ha="left",
            fontsize=9.5,
            fontweight="bold",
            color="#111827",
        )

    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", color="#111827", pad=18)
    ax.text(0, 1.035, subtitle, transform=ax.transAxes, fontsize=9.5, color="#6B7280")
    ax.set_xlabel("Cantidad", fontsize=9, color="#374151")
    ax.tick_params(axis="y", labelsize=9, colors="#374151")
    ax.tick_params(axis="x", labelsize=8, colors="#6B7280")
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E5E7EB")
    ax.set_xlim(0, max_value * 1.38 if max_value else 1)
    fig.tight_layout()
    return _fig_to_png(fig)


def _week_recurrence_metrics(wow_results: Any | None) -> dict[str, Any]:
    corrected = list(getattr(wow_results, "corrected_agents", []) or []) if wow_results is not None else []
    new_alert = list(getattr(wow_results, "new_alert_agents", []) or []) if wow_results is not None else []
    persistent = list(getattr(wow_results, "persistent_agents", []) or []) if wow_results is not None else []

    previous_count = len(corrected) + len(persistent)
    current_count = len(new_alert) + len(persistent)
    delta = current_count - previous_count
    delta_pct = (delta / previous_count) if previous_count else (1.0 if current_count else 0.0)
    current_agents = sorted(set(new_alert + persistent))

    return {
        "corrected": corrected,
        "new_alert": new_alert,
        "persistent": persistent,
        "previous_count": previous_count,
        "current_count": current_count,
        "delta": delta,
        "delta_pct": delta_pct,
        "current_agents": current_agents,
        "current_pct": current_count / max(previous_count, current_count, 1),
        "previous_pct": previous_count / max(previous_count, current_count, 1),
    }


def _wow_modern_png(wow_results: Any | None, *, title: str, subtitle: str) -> bytes:
    m = _week_recurrence_metrics(wow_results)
    correction_rate = _safe_float(getattr(wow_results, "correction_rate", 0.0), 0.0) if wow_results is not None else 0.0

    labels = ["Semana anterior", "Periodo analizado"]
    values = [m["previous_count"], m["current_count"]]
    palette = ["#94A3B8", "#EF4444"]

    fig = plt.figure(figsize=(10.2, 4.8), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.58])
    ax_donut = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[0, 1])

    fig.suptitle(title, x=0.02, y=0.99, ha="left", fontsize=16, fontweight="bold", color="#111827")
    fig.text(0.02, 0.925, subtitle, ha="left", fontsize=9.5, color="#6B7280")

    rate = max(0.0, min(1.0, correction_rate))
    ax_donut.pie(
        [rate, 1 - rate],
        startangle=90,
        counterclock=False,
        colors=["#10B981", "#E5E7EB"],
        wedgeprops={"width": 0.25, "edgecolor": "white"},
    )
    ax_donut.text(0, 0.10, f"{rate:.1%}", ha="center", va="center", fontsize=22, fontweight="bold", color="#111827")
    ax_donut.text(0, -0.14, "Tasa de\nsubsanación", ha="center", va="center", fontsize=9, color="#6B7280")
    ax_donut.axis("equal")

    ypos = list(range(len(labels)))
    ax_bar.barh(ypos, values, color=palette, alpha=0.93, height=0.55)
    ax_bar.barh(ypos, values, color=palette, alpha=0.16, height=0.82)
    ax_bar.set_yticks(ypos)
    ax_bar.set_yticklabels(labels)
    ax_bar.invert_yaxis()

    max_value = max(values) if max(values) > 0 else 1
    for i, value in enumerate(values):
        base = max_value if max_value else 1
        pct = value / base
        ax_bar.text(value + max_value * 0.045, i, f"{value} agentes ({pct:.1%})", va="center", ha="left", fontsize=11, fontweight="bold", color="#111827")

    ax_bar.set_xlabel("Agentes con reincidencia", fontsize=9, color="#374151")
    ax_bar.tick_params(axis="y", labelsize=10, colors="#374151")
    ax_bar.tick_params(axis="x", labelsize=8, colors="#6B7280")
    ax_bar.grid(axis="x", color="#E5E7EB", linewidth=0.8)
    ax_bar.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax_bar.spines[spine].set_visible(False)
    ax_bar.spines["bottom"].set_color("#E5E7EB")
    ax_bar.set_xlim(0, max_value * 1.45)
    fig.tight_layout(rect=[0, 0, 1, 0.83])
    return _fig_to_png(fig)


def _recurrent_agents_chart(wow_results: Any | None) -> bytes:
    m = _week_recurrence_metrics(wow_results)
    persistent = m["persistent"]
    new_alert = m["new_alert"]

    rows = []
    for agent in persistent:
        rows.append({"agent": agent, "count": 1, "type": "Reincidencia sostenida"})
    for agent in new_alert:
        rows.append({"agent": agent, "count": 1, "type": "Nuevo en alerta"})

    if not rows:
        return _empty_chart(
            "Agentes con reincidencia en el periodo analizado",
            "No hay agentes con reincidencia en el periodo analizado.",
        )

    df = pd.DataFrame(rows)
    df["label"] = df["agent"].astype(str) + " — " + df["type"].astype(str)
    denom = max(len(rows), 1)
    return _modern_barh_png(
        df,
        label_col="label",
        value_col="count",
        title="Agentes con reincidencia en el periodo analizado",
        subtitle="Comparación de cantidad de errores por agente reincidente: periodo anterior vs periodo analizado",
        color="#EF4444",
        max_items=20,
        percent_denominator=denom,
    )


def _recurrence_summary_png(kpis: Any) -> bytes:
    rec = getattr(kpis, "recurrence", {}) or {}
    total_errors = _safe_float(getattr(kpis, "total_errors", 0), 0.0)

    repeated_tickets = rec.get("repeated_tickets")
    repeated_pairs = rec.get("repeated_agent_reason")

    ticket_rows = float(repeated_tickets["count"].sum()) if repeated_tickets is not None and not repeated_tickets.empty and "count" in repeated_tickets.columns else 0.0
    pair_rows = float(repeated_pairs["count"].sum()) if repeated_pairs is not None and not repeated_pairs.empty and "count" in repeated_pairs.columns else 0.0

    ticket_pct = ticket_rows / total_errors if total_errors else 0.0
    pair_pct = pair_rows / total_errors if total_errors else 0.0

    labels = ["Errores en tickets repetidos", "Errores en patrón agente + motivo"]
    percentages = [ticket_pct, pair_pct]
    counts = [ticket_rows, pair_rows]
    palette = ["#0EA5E9", "#DB2777"]

    fig, ax = plt.subplots(figsize=(10.2, 3.7), facecolor="white")
    ax.set_title("Resumen porcentual de reincidencia", loc="left", fontsize=16, fontweight="bold", color="#111827", pad=18)
    ax.text(0, 1.04, "Porcentaje calculado sobre el total de errores del periodo analizado", transform=ax.transAxes, fontsize=9.5, color="#6B7280")

    ypos = list(range(len(labels)))
    ax.barh(ypos, percentages, color=palette, alpha=0.92, height=0.48)
    ax.barh(ypos, percentages, color=palette, alpha=0.15, height=0.74)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()

    max_pct = max(percentages) if max(percentages) > 0 else 0.1
    for i, (count, pct) in enumerate(zip(counts, percentages)):
        ax.text(pct + max_pct * 0.045, i, f"{int(count)} errores ({pct:.1%})", va="center", ha="left", fontsize=11, fontweight="bold", color="#111827")

    ax.set_xlim(0, min(1.0, max_pct * 1.4) if max_pct > 0.75 else max_pct * 1.4)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.tick_params(axis="y", labelsize=9, colors="#374151")
    ax.tick_params(axis="x", labelsize=8, colors="#6B7280")
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.8)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E5E7EB")
    fig.tight_layout()
    return _fig_to_png(fig)


def _recurrence_ticket_chart(kpis: Any) -> bytes:
    rec = getattr(kpis, "recurrence", {}) or {}
    df = rec.get("repeated_tickets")
    total = max(_safe_float(getattr(kpis, "total_errors", 0), 0.0), 1.0)
    return _modern_barh_png(
        df,
        label_col="ticket_id",
        value_col="count",
        title="Reincidencias por ticket",
        subtitle="Tickets que aparecen más de una vez. El porcentaje se calcula sobre el total de errores del periodo.",
        color="#0EA5E9",
        max_items=12,
        percent_denominator=total,
    )


def _recurrence_agent_reason_chart(kpis: Any) -> bytes:
    rec = getattr(kpis, "recurrence", {}) or {}
    df = rec.get("repeated_agent_reason")
    if df is not None and not df.empty:
        df = df.copy()
        df["agent_reason"] = df["agent"].astype(str) + " — " + df["reason"].astype(str)
    total = max(_safe_float(getattr(kpis, "total_errors", 0), 0.0), 1.0)
    return _modern_barh_png(
        df,
        label_col="agent_reason",
        value_col="count",
        title="Reincidencias por agente + motivo",
        subtitle="Patrones repetidos por agente y motivo. El porcentaje se calcula sobre el total de errores del periodo.",
        color="#DB2777",
        max_items=12,
        percent_denominator=total,
    )




def _recurrent_agents_comparison_chart(comparison_df: pd.DataFrame | None) -> bytes:
    """Compara errores totales SOLO de agentes reincidentes en ambas semanas."""
    title = "Agentes reincidentes — comparación de errores"
    subtitle = "Solo agentes que reincidieron en ambas semanas: errores del periodo anterior vs periodo analizado"

    if comparison_df is None or comparison_df.empty:
        return _empty_chart(title, "No hay agentes que hayan reincidido en ambas semanas.")

    required = {"agent", "previous_errors", "current_errors", "delta", "delta_pct"}
    if not required.issubset(set(comparison_df.columns)):
        return _empty_chart(title, "No se recibió la estructura esperada para la comparación de reincidentes.")

    data = comparison_df.copy().head(12).sort_values("current_errors", ascending=True)
    labels = [_truncate_label(agent, 30) for agent in data["agent"].astype(str).tolist()]
    prev_values = data["previous_errors"].astype(float).tolist()
    curr_values = data["current_errors"].astype(float).tolist()
    delta_values = data["delta"].astype(float).tolist()
    delta_pcts = data["delta_pct"].astype(float).tolist()

    fig = plt.figure(figsize=(12.8, 6.3), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[2.15, 0.85])
    ax = fig.add_subplot(gs[0, 0])
    ax_side = fig.add_subplot(gs[0, 1])

    fig.suptitle(title, x=0.02, y=0.990, ha="left", fontsize=18, fontweight="bold", color="#0F172A")
    fig.text(0.02, 0.895, subtitle, ha="left", fontsize=10, color="#64748B")

    y = list(range(len(labels)))
    height = 0.34
    ax.barh([i - height / 2 for i in y], prev_values, height=height, color="#CBD5E1", alpha=0.96, label="Periodo anterior")
    ax.barh([i + height / 2 for i in y], curr_values, height=height, color="#EF4444", alpha=0.94, label="Periodo analizado")

    max_value = max(prev_values + curr_values) if (prev_values + curr_values) else 1
    for i, (prev, curr, delta, pct) in enumerate(zip(prev_values, curr_values, delta_values, delta_pcts)):
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
        color = "#DC2626" if delta > 0 else ("#059669" if delta < 0 else "#64748B")
        ax.text(max(prev, curr) + max_value * 0.04, i, f"{int(curr)} vs {int(prev)}  {arrow} {pct:+.1%}", va="center", fontsize=9.5, fontweight="bold", color=color, clip_on=False)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Cantidad de errores", fontsize=9.5, color="#334155")
    ax.tick_params(axis="y", labelsize=9, colors="#334155")
    ax.tick_params(axis="x", labelsize=8.5, colors="#64748B")
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.set_xlim(0, max_value * 1.95 if max_value else 1)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)

    total_prev = int(sum(prev_values))
    total_curr = int(sum(curr_values))
    total_delta = total_curr - total_prev
    total_delta_pct = (total_delta / total_prev) if total_prev else (1.0 if total_curr else 0.0)
    recurrent_count = int(len(data))

    ax_side.axis("off")
    card_color = "#FEF2F2" if total_delta > 0 else "#ECFDF5"
    accent = "#EF4444" if total_delta > 0 else "#10B981"

    ax_side.add_patch(plt.Rectangle((0.02, 0.62), 0.96, 0.30, transform=ax_side.transAxes, color=card_color, ec="none"))
    ax_side.text(0.07, 0.84, "Diferencia total", transform=ax_side.transAxes, fontsize=9.5, color="#64748B", fontweight="bold")
    ax_side.text(0.07, 0.73, f"{total_delta:+d}", transform=ax_side.transAxes, fontsize=25, color=accent, fontweight="bold")
    ax_side.text(0.07, 0.66, f"{total_delta_pct:+.1%} vs periodo anterior", transform=ax_side.transAxes, fontsize=8.5, color="#334155")

    ax_side.add_patch(plt.Rectangle((0.02, 0.29), 0.96, 0.24, transform=ax_side.transAxes, color="#F8FAFC", ec="none"))
    ax_side.text(0.07, 0.46, "Agentes reincidentes", transform=ax_side.transAxes, fontsize=9.5, color="#64748B", fontweight="bold")
    ax_side.text(0.07, 0.36, str(recurrent_count), transform=ax_side.transAxes, fontsize=25, color="#0F172A", fontweight="bold")
    ax_side.text(0.07, 0.31, "reincidieron en ambas semanas", transform=ax_side.transAxes, fontsize=8.3, color="#334155")

    ax_side.add_patch(plt.Rectangle((0.02, 0.06), 0.96, 0.16, transform=ax_side.transAxes, color="#F8FAFC", ec="none"))
    ax_side.text(0.07, 0.16, "Errores actuales", transform=ax_side.transAxes, fontsize=9.5, color="#64748B", fontweight="bold")
    ax_side.text(0.07, 0.09, str(total_curr), transform=ax_side.transAxes, fontsize=19, color="#0F172A", fontweight="bold")

    fig.tight_layout(rect=[0, 0, 1, 0.84])
    return _fig_to_png(fig)


def _recurrent_agents_critical_comparison_chart(comparison_df: pd.DataFrame | None) -> bytes:
    """Compara errores críticos SOLO de agentes reincidentes en ambas semanas."""
    title = "Agentes reincidentes — comparación de errores críticos"
    subtitle = "Solo agentes reincidentes en ambas semanas: críticos del periodo anterior vs periodo analizado"

    if comparison_df is None or comparison_df.empty:
        return _empty_chart(title, "No hay agentes reincidentes en ambas semanas para comparar críticos.")

    required = {"agent", "previous_critical_errors", "current_critical_errors", "critical_delta", "critical_delta_pct"}
    if not required.issubset(set(comparison_df.columns)):
        return _empty_chart(title, "No se recibió la estructura esperada para comparar críticos.")

    data = comparison_df.copy()
    data = data[(data["previous_critical_errors"] > 0) | (data["current_critical_errors"] > 0)]
    if data.empty:
        return _empty_chart(title, "Los agentes reincidentes no tuvieron errores críticos en ninguno de los dos periodos.")

    data = data.head(12).sort_values("current_critical_errors", ascending=True)
    labels = [_truncate_label(agent, 30) for agent in data["agent"].astype(str).tolist()]
    prev_values = data["previous_critical_errors"].astype(float).tolist()
    curr_values = data["current_critical_errors"].astype(float).tolist()
    delta_values = data["critical_delta"].astype(float).tolist()
    delta_pcts = data["critical_delta_pct"].astype(float).tolist()

    fig, ax = plt.subplots(figsize=(12.2, 5.5), facecolor="white")
    fig.suptitle(title, x=0.02, y=0.990, ha="left", fontsize=17, fontweight="bold", color="#0F172A")
    fig.text(0.02, 0.885, subtitle, ha="left", fontsize=9.5, color="#64748B")

    y = list(range(len(labels)))
    height = 0.34
    ax.barh([i - height / 2 for i in y], prev_values, height=height, color="#CBD5E1", alpha=0.96, label="Críticos periodo anterior")
    ax.barh([i + height / 2 for i in y], curr_values, height=height, color="#B91C1C", alpha=0.94, label="Críticos periodo analizado")

    max_value = max(prev_values + curr_values) if (prev_values + curr_values) else 1
    for i, (prev, curr, delta, pct) in enumerate(zip(prev_values, curr_values, delta_values, delta_pcts)):
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
        color = "#B91C1C" if delta > 0 else ("#059669" if delta < 0 else "#64748B")
        ax.text(max(prev, curr) + max_value * 0.05, i, f"{int(curr)} vs {int(prev)}  {arrow} {pct:+.1%}", va="center", fontsize=9.5, fontweight="bold", color=color, clip_on=False)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Cantidad de errores críticos", fontsize=9.5, color="#334155")
    ax.tick_params(axis="y", labelsize=9, colors="#334155")
    ax.tick_params(axis="x", labelsize=8.5, colors="#64748B")
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.set_xlim(0, max_value * 1.9 if max_value else 1)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    fig.tight_layout(rect=[0, 0, 1, 0.83])
    return _fig_to_png(fig)

def _metric_table(st: dict[str, ParagraphStyle], metrics: list[tuple[str, str]]) -> Table:
    data = [
        [Paragraph(label, st["metric_label"]) for label, _ in metrics],
        [Paragraph(value, st["metric_value"]) for _, value in metrics],
    ]
    table = Table(data, colWidths=[6 * cm] * len(metrics), hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF4FB")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4C7E7")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E2F3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _add_wow_section(story: list[Any], st: dict[str, ParagraphStyle], wow_results: Any | None, comparison_label: str, recurrent_agents_comparison: pd.DataFrame | None = None) -> None:
    story.append(Paragraph("Evolución semanal de reincidencias", st["h"]))
    if comparison_label:
        story.append(Paragraph(_safe(comparison_label), st["body"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Enfoque de esta sección:</b> se muestran únicamente los agentes que reincidieron en la comparación de las dos semanas; es decir, agentes que tuvieron reincidencia en el periodo anterior y volvieron a reincidir en el periodo analizado. No incluye agentes nuevos en alerta.",
        st["body"],
    ))
    story.append(Spacer(1, 6))
    story.append(_img(_recurrent_agents_comparison_chart(recurrent_agents_comparison), 22.5 * cm))
    story.append(Paragraph(
        "<b>Lectura de diferencia total:</b> compara la suma de errores de los agentes reincidentes en el periodo analizado contra la suma de errores de esos mismos agentes en el periodo anterior. Por ejemplo, <b>+18</b> significa 18 errores más que antes; <b>+112.5%</b> significa que el aumento fue de 112.5% frente al periodo anterior.",
        st["muted"],
    ))
    story.append(Spacer(1, 8))
    story.append(_img(_recurrent_agents_critical_comparison_chart(recurrent_agents_comparison), 22.5 * cm))

def build_pdf_report(
    kpis: Any,
    *,
    title: str = "QA Weekly Analytics — Informe",
    generated_by: str = "",
    additional_note: str = "",
    wow_results: Any | None = None,
    comparison_label: str = "",
    recurrent_agents_comparison: pd.DataFrame | None = None,
) -> bytes:
    try:
        buffer = io.BytesIO()
        st = _styles()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.2 * cm,
            leftMargin=1.2 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm,
            title=title,
        )
        story: list[Any] = []
        recurrence_pct = _recurrence_percent(kpis)

        header_text = (
            f"Periodo analizado: <b>{_fmt_date(kpis.start_date)} - {_fmt_date(kpis.end_date)}</b>"
            + (f"<br/>Preparado por: {_safe(generated_by)}" if generated_by else "")
        )
        story.append(Paragraph(header_text, st["body"]))
        if str(additional_note or "").strip():
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>Nota:</b> {_safe(str(additional_note).strip())}", st["body"]))

        story.append(Spacer(1, 12))

        story.append(Paragraph("PARTE 1 — Informe de la semana", st["h"]))
        story.append(Paragraph("Resumen del periodo seleccionado: KPIs, rankings principales y detalle de errores críticos.", st["muted"]))
        story.append(Paragraph("Resumen ejecutivo", st["h"]))
        story.append(_metric_table(st, [
            ("Total de errores", str(int(getattr(kpis, "total_errors", 0) or 0))),
            ("Errores críticos", str(int(getattr(kpis, "critical_count", 0) or 0))),
            ("% críticos", _fmt_pct(getattr(kpis, "critical_pct", 0.0))),
            ("% reincidencia", _fmt_pct(recurrence_pct)),
        ]))

        story.append(Spacer(1, 8))
        story.append(_img(_modern_barh_png(
            getattr(kpis, "by_reason", None),
            label_col="reason",
            pct_col="share",
            title="Ranking por motivo",
            subtitle="Motivos con mayor cantidad de errores. Cada barra incluye participación porcentual.",
            color="#2563EB",
            max_items=10,
        ), 22.5 * cm))
        story.append(Spacer(1, 8))
        story.append(_img(_modern_barh_png(
            getattr(kpis, "by_agent", None),
            label_col="agent",
            pct_col="share",
            title="Ranking por agente",
            subtitle="Agentes con mayor cantidad de errores. Cada barra incluye participación porcentual.",
            color="#7C3AED",
            max_items=10,
        ), 22.5 * cm))



        story.append(PageBreak())
        story.append(Paragraph("Críticos — detalle", st["h"]))
        story.append(Paragraph("Se muestran hasta 50 registros críticos para trazabilidad operativa.", st["muted"]))
        story.append(_critical_table(getattr(kpis, "critical_table", None), st))
        try:
            if getattr(kpis, "critical_table", pd.DataFrame()).shape[0] > 50:
                story.append(Spacer(1, 6))
                story.append(Paragraph("Nota: se muestran los primeros 50 críticos.", st["muted"]))
        except Exception:
            pass


        story.append(PageBreak())
        story.append(Paragraph("PARTE 2 — Evolución semanal de reincidencias", st["h"]))
        story.append(Paragraph("Comparativo del periodo seleccionado contra el mismo rango de la semana anterior.", st["muted"]))
        _add_wow_section(story, st, wow_results, comparison_label, recurrent_agents_comparison)
        doc.build(story)
        pdf = buffer.getvalue()
        if not pdf:
            raise PDFReportError("El PDF generado está vacío")
        return pdf

    except PDFReportError:
        raise
    except Exception as exc:
        raise PDFReportError(f"No se pudo generar el PDF: {exc}") from exc
