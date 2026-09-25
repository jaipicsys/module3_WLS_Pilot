import React, { useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";
import LayersOutlinedIcon from "@mui/icons-material/LayersOutlined";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const fmt = (s) => {
    const hh = String(Math.floor(s / 3600)).padStart(2, "0");
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const ss = String(s % 60).padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
};

/*
 * Props:
 *   status      badge text (default "Productive")
 *   statusColor badge colour
 *   activity, product, cycleCount   info rows
 *   startSeconds  initial timer value
 *   running     whether the timer ticks (default true)
 */
export default function CurrentActivity({
    status = "Productive",
    statusColor,
    activity = "Folding & Stacking",
    product = "Towel – Standard",
    cycleCount = "12 (this minute)",
    startSeconds = 24,
    running = true,
}) {
    const c = useDashboardColors();
    const [seconds, setSeconds] = useState(startSeconds);
    const ref = useRef(null);

    useEffect(() => {
        if (!running) return undefined;
        ref.current = setInterval(() => setSeconds((s) => s + 1), 1000);
        return () => clearInterval(ref.current);
    }, [running]);

    const rows = [
        { k: "Activity", v: activity },
        { k: "Product", v: product },
        { k: "Cycle Count", v: cycleCount },
    ];

    const headerRight = (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Box
                sx={{
                    px: 1,
                    py: 0.3,
                    borderRadius: "6px",
                    bgcolor: statusColor || c.green,
                    color: "#fff",
                    fontSize: 11,
                    fontWeight: 700,
                }}
            >
                {status}
            </Box>
            <Typography
                sx={{
                    fontSize: 13,
                    fontWeight: 700,
                    fontVariantNumeric: "tabular-nums",
                    color: c.title,
                }}
            >
                {fmt(seconds)}
            </Typography>
        </Box>
    );

    return (
        <Panel title="Current Activity" headerRight={headerRight}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                <Box
                    sx={{
                        width: 56,
                        height: 56,
                        borderRadius: "12px",
                        bgcolor: c.accentSoft,
                        color: c.accent,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                    }}
                >
                    <LayersOutlinedIcon sx={{ fontSize: 26 }} />
                </Box>

                <Box sx={{ flex: 1 }}>
                    {rows.map((r) => (
                        <Box
                            key={r.k}
                            sx={{
                                display: "flex",
                                justifyContent: "space-between",
                                gap: 2,
                                py: 0.4,
                            }}
                        >
                            <Typography sx={{ fontSize: 12.5, color: c.muted }}>
                                {r.k}
                            </Typography>
                            <Typography
                                sx={{
                                    fontSize: 12.5,
                                    fontWeight: 600,
                                    color: c.title,
                                    textAlign: "right",
                                }}
                            >
                                {r.v}
                            </Typography>
                        </Box>
                    ))}
                </Box>
            </Box>
        </Panel>
    );
}