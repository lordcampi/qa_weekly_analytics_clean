from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class KpiCardsError(Exception):
    """Error construyendo tarjetas KPI para dashboard."""


@dataclass(frozen=True, slots=True)
class KpiCard:
    """Representa una tarjeta KPI visual.

    Args:
        label: Etiqueta visible.
        value: Valor principal formateado.
        help_text: Texto de ayuda opcional.
    """

    label: str
    value: str
    help_text: str | None = None


def _format_pct(value: float) -> str:
    """Formatea una proporción 0..1 como porcentaje.

    Args:
        value: Proporción.

    Returns:
        Porcentaje con 1 decimal.
    """
    return f"{value:.1%}"


def build_kpi_cards(kpis: Any) -> tuple[KpiCard, KpiCard, KpiCard]:
    """Construye las tarjetas KPI principales.

    Args:
        kpis: Objeto KPIResult con total_errors, critical_count y critical_pct.

    Returns:
        Tupla con tarjetas: Total, Críticos, % críticos.

    Raises:
        KpiCardsError: Si el objeto no contiene los atributos requeridos.
    """
    required_attrs = ("total_errors", "critical_count", "critical_pct")
    missing = [attr for attr in required_attrs if not hasattr(kpis, attr)]
    if missing:
        raise KpiCardsError(f"Faltan atributos requeridos para tarjetas KPI: {missing}")

    try:
        total_errors = int(kpis.total_errors)
        critical_count = int(kpis.critical_count)
        critical_pct = float(kpis.critical_pct)

        cards = (
            KpiCard(
                label="Total de errores",
                value=str(total_errors),
                help_text="Total de hallazgos en el rango y filtros seleccionados.",
            ),
            KpiCard(
                label="Errores críticos",
                value=str(critical_count),
                help_text="Cantidad de hallazgos marcados como críticos.",
            ),
            KpiCard(
                label="% críticos",
                value=_format_pct(critical_pct),
                help_text="Proporción de errores críticos sobre el total filtrado.",
            ),
        )

        logger.debug(
            "Tarjetas KPI construidas",
            extra={
                "total_errors": total_errors,
                "critical_count": critical_count,
                "critical_pct": critical_pct,
            },
        )
        return cards
    except Exception as exc:
        logger.exception("Error construyendo tarjetas KPI")
        raise KpiCardsError("No se pudieron construir las tarjetas KPI") from exc