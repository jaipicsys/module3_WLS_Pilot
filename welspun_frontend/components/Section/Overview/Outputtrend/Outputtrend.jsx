import React from "react";
import { Box, Typography } from "@mui/material";
import {
    ComposedChart,
    Bar,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

const DEFAULT_DATA = [
    { time: "6 AM", output: 95, target: 110 },
    { time: "", output: 78, target: 112 },
    { time: "", output: 120, target: 115 },
    { time: "8 AM", output: 105, target: 118 },
    { time: "", output: 132, target: 120 },
    { time: "", output: 92, target: 122 },
    { time: "10 AM", output: 118, target: 125 },
    { time: "", output: 140, target: 128 },
    { time: "", output: 110, target: 130 },
    { time: "12 PM", output: 150, target: 132 },
    { time: "", output: 128, target: 134 },
    { time: "", output: 158, target: 136 },
    { time: "2 PM", output: 142, target: 138 },
];

function LegendDot({ color, dashed, label, c }) {
    return (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            {dashed ? (
                <Box
                    sx={{
                        width: 16,
                        borderTop: `2px dashed ${color}`,
                    }}
                />
            ) : (
                <Box
                    sx={{
                        width: 9,
                        height: 9,
                        borderRadius: "50%",
                        bgcolor: color,
                    }}
                />
            )}
            <Typography sx={{ fontSize: 12, color: c.muted }}>{label}</Typography>
        </Box>
    );
}

export default function OutputTrend({ data = DEFAULT_DATA, height = 300 }) {
    const c = useDashboardColors();

    return (
        <Panel
            title="Output Trend"
            headerRight={
                <Box sx={{ display: "flex", gap: 2 }}>
                    <LegendDot color={c.accent} label="Output" c={c} />
                    <LegendDot color={c.muted} dashed label="Target" c={c} />
                </Box>
            }
            sx={{ minHeight: height }}
        >
            <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                    data={data}
                    margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                >
                    <CartesianGrid
                        vertical={false}
                        stroke={c.track}
                        strokeDasharray="3 3"
                    />
                    <XAxis
                        dataKey="time"
                        tickLine={false}
                        axisLine={{ stroke: c.track }}
                        tick={{ fontSize: 11, fill: c.muted }}
                        interval={0}
                    />
                    <YAxis
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 11, fill: c.muted }}
                        label={{
                            value: "Units",
                            angle: -90,
                            position: "insideLeft",
                            offset: 16,
                            style: { fontSize: 11, fill: c.muted },
                        }}
                    />
                    <Tooltip
                        contentStyle={{
                            background: c.cardBg,
                            border: `1px solid ${c.cardBorder}`,
                            borderRadius: 8,
                            fontSize: 12,
                        }}
                        labelStyle={{ color: c.title }}
                        cursor={{ fill: c.track, opacity: 0.4 }}
                    />
                    <Bar
                        dataKey="output"
                        name="Output"
                        fill={c.accent}
                        radius={[3, 3, 0, 0]}
                        barSize={14}
                    />
                    <Line
                        type="monotone"
                        dataKey="target"
                        name="Target"
                        stroke={c.muted}
                        strokeWidth={2}
                        strokeDasharray="5 4"
                        dot={false}
                    />
                </ComposedChart>
            </ResponsiveContainer>
        </Panel>
    );
}