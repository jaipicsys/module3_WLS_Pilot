import React from "react";
import { Box, Typography } from "@mui/material";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

/*
 * data rows: { label, value (for arc size), amount (display), pct }
 */
const buildDefault = (c) => [
    { label: "Productive", value: 78, amount: "6h 12m", pct: 78, color: c.green },
    { label: "Idle / Waiting", value: 16, amount: "1h 18m", pct: 16, color: c.orange },
    { label: "Changeover", value: 4, amount: "18m", pct: 4, color: c.red },
    { label: "Others", value: 2, amount: "12m", pct: 2, color: c.gray },
];

export default function TimeDistribution({
    title = "Time Distribution",
    data,
    centerValue = "8h",
    centerLabel = "Available Time",
    height = 300,
}) {
    const c = useDashboardColors();
    const rows = data || buildDefault(c);

    return (
        <Panel title={title} sx={{ minHeight: height }}>
            <Box
                sx={{
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 2,
                    flexWrap: "wrap",
                }}
            >
                {/* Donut */}
                <Box sx={{ position: "relative", width: 170, height: 170 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={rows}
                                dataKey="value"
                                nameKey="label"
                                innerRadius={55}
                                outerRadius={80}
                                paddingAngle={2}
                                startAngle={90}
                                endAngle={-270}
                                stroke="none"
                            >
                                {rows.map((r) => (
                                    <Cell key={r.label} fill={r.color} />
                                ))}
                            </Pie>
                        </PieChart>
                    </ResponsiveContainer>

                    <Box
                        sx={{
                            position: "absolute",
                            inset: 0,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            pointerEvents: "none",
                        }}
                    >
                        <Typography
                            sx={{ fontSize: 24, fontWeight: 800, color: c.title }}
                        >
                            {centerValue}
                        </Typography>
                        <Typography sx={{ fontSize: 11, color: c.muted }}>
                            {centerLabel}
                        </Typography>
                    </Box>
                </Box>

                {/* Legend */}
                <Box
                    sx={{
                        flex: 1,
                        minWidth: 150,
                        display: "flex",
                        flexDirection: "column",
                        gap: 1.25,
                    }}
                >
                    {rows.map((r) => (
                        <Box
                            key={r.label}
                            sx={{ display: "flex", alignItems: "center", gap: 1 }}
                        >
                            <Box
                                sx={{
                                    width: 10,
                                    height: 10,
                                    borderRadius: "50%",
                                    bgcolor: r.color,
                                    flexShrink: 0,
                                }}
                            />
                            <Box>
                                <Typography
                                    sx={{ fontSize: 12.5, color: c.text }}
                                >
                                    {r.label}
                                </Typography>
                                <Typography
                                    sx={{
                                        fontSize: 12.5,
                                        fontWeight: 700,
                                        color: c.title,
                                    }}
                                >
                                    {r.amount} ({r.pct}%)
                                </Typography>
                            </Box>
                        </Box>
                    ))}
                </Box>
            </Box>
        </Panel>
    );
}