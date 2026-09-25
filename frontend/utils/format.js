/* =========================================================
   SHARED FORMATTERS

   Replaces the four duplicate copies of formatMinutes that
   lived in LossTree, LossTreeChart, LossSummaryCards and
   LossesByStation.
========================================================= */

/**
 * 141.3833  -> "2h 21m"
 * 15.3333   -> "15m"
 * 0         -> "0m"
 *
 * Rounds to whole minutes FIRST so we never produce "2h 60m".
 */
export const formatMinutes = (minutes = 0) => {
    const value = Number(minutes);

    if (!Number.isFinite(value) || value <= 0) {
        return "0m";
    }

    const total = Math.round(value);

    const hours = Math.floor(total / 60);
    const mins = total % 60;

    if (hours > 0) {
        return `${hours}h ${mins}m`;
    }

    return `${mins}m`;
};

/**
 * 57599 -> "15h 59m"
 * 3540  -> "59m"
 */
export const formatSeconds = (seconds = 0) => {
    const value = Number(seconds);

    if (!Number.isFinite(value) || value <= 0) {
        return "0m";
    }

    return formatMinutes(value / 60);
};

/**
 * 13.4423 -> "13.4%"
 */
export const formatPercent = (pct = 0, digits = 1) => {
    const value = Number(pct);

    if (!Number.isFinite(value)) {
        return `${(0).toFixed(digits)}%`;
    }

    return `${value.toFixed(digits)}%`;
};

/**
 * Safe division for derived percentages.
 * ratioPercent(206.55, 2789.95) -> 7.4033...
 */
export const ratioPercent = (part = 0, whole = 0) => {
    const p = Number(part) || 0;
    const w = Number(whole) || 0;

    if (w <= 0) {
        return 0;
    }

    return (p / w) * 100;
};