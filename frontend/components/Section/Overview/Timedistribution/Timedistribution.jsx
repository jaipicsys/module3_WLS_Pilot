import React from "react";
import { Box, Typography } from "@mui/material";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

export default function TimeDistribution({
    data,
    centerValue = "—",
    centerLabel = "Available Time",
    height = 300,
}) {
    const c = useDashboardColors();

    /*
     * Colors are assigned here based on the category.
     * API only needs to provide:
     * {
     *   label,
     *   value,
     *   amount,
     *   pct
     * }
     */
    const rows = (data || []).map((r) => ({
        ...r,
        color:
            r.color ||
            (r.label === "Productive"
                ? c.green
                : r.label === "Idle / Waiting"
                ? c.orange
                : r.label === "Away"
                ? c.red
                : c.gray),
    }));

    return (
        <Panel title="Time Distribution" sx={{ minHeight: height }}>
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
                <Box
                    sx={{
                        position: "relative",
                        width: 170,
                        height: 170,
                        flexShrink: 0,
                    }}
                >
                    {rows.length > 0 ? (
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
                                        <Cell
                                            key={r.label}
                                            fill={r.color}
                                        />
                                    ))}
                                </Pie>
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <Box
                            sx={{
                                width: "100%",
                                height: "100%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                            }}
                        >
                            <Typography
                                sx={{
                                    fontSize: 12,
                                    color: c.muted,
                                }}
                            >
                                No data
                            </Typography>
                        </Box>
                    )}

                    {/* Center value */}
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
                            sx={{
                                fontSize: 24,
                                fontWeight: 800,
                                color: c.title,
                                lineHeight: 1.1,
                            }}
                        >
                            {centerValue}
                        </Typography>

                        <Typography
                            sx={{
                                fontSize: 11,
                                color: c.muted,
                                mt: 0.5,
                            }}
                        >
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
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 1,
                            }}
                        >
                            {/* Color dot */}
                            <Box
                                sx={{
                                    width: 10,
                                    height: 10,
                                    borderRadius: "50%",
                                    bgcolor: r.color,
                                    flexShrink: 0,
                                }}
                            />

                            {/* Text */}
                            <Box sx={{ minWidth: 0 }}>
                                <Typography
                                    sx={{
                                        fontSize: 12.5,
                                        color: c.text,
                                        lineHeight: 1.3,
                                    }}
                                >
                                    {r.label}
                                </Typography>

                                <Typography
                                    sx={{
                                        fontSize: 12.5,
                                        fontWeight: 700,
                                        color: c.title,
                                        lineHeight: 1.3,
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