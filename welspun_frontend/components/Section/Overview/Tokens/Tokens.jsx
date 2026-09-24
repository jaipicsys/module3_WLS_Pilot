import { useTheme } from "@mui/material";

/*
 * Central, theme-aware colour tokens for every dashboard panel.
 * Import and call inside a component:  const c = useDashboardColors();
 */
export default function useDashboardColors() {
    const isDark = useTheme().palette.mode === "dark";

    return {
        isDark,

        // surfaces
        pageBg: isDark ? "#0e0e14" : "#f5f6fa",
        cardBg: isDark ? "#15151f" : "#ffffff",
        cardBorder: isDark ? "#26263a" : "#ececf2",
        track: isDark ? "#23232f" : "#eef1f6",

        // text
        title: isDark ? "#e8e8f2" : "#1f2430",
        text: isDark ? "#d0d0e0" : "#2a2f3a",
        muted: isDark ? "#8a8aa0" : "#8a90a0",

        // brand + status
        accent: "#12b79c",
        accentSoft: isDark ? "#3a2016" : "#fdeee7",
        green: "#12b76a",
        orange: "#f59e0b",
        red: "#ef4444",
        gray: "#9ca3af",
    };
}

/* Ordered orange->coral shade scale for ranked bars (Others handled separately) */
export const barShades = ["#e0491d", "#ef5323", "#f47a4e", "#f89b78", "#f9b79c"];