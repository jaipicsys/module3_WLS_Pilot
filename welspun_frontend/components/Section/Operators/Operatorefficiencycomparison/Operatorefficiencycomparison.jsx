import React from "react";
import { Box, Typography } from "@mui/material";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    LabelList,
    ResponsiveContainer,
} from "recharts";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
    { op: "OP-104", eff: 94, util: 86 },
    { op: "OP-087", eff: 91, util: 82 },
    { op: "OP-118", eff: 89, util: 78 },
    { op: "OP-132", eff: 62, util: 68 },
    { op: "OP-095", eff: 84, util: 72 },
];

function LegendDot({ color, label, c }) {
    return (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: color }} />
            <Typography sx={{ fontSize: 12, color: c.muted }}>{label}</Typography>
        </Box>
    );
}

export default function OperatorEfficiencyComparison({
    data = DEFAULT_DATA,
    height = 300,
}) {
    const c = useDashboardColors();
    const utilColor = "#f9b79c";

    return (
        <Panel
            title="Operator Efficiency Comparison"
            headerRight={
                <Box sx={{ display: "flex", gap: 2 }}>
                    <LegendDot color={c.accent} label="Efficiency" c={c} />
                    <LegendDot color={utilColor} label="Utilization" c={c} />
                </Box>
            }
            sx={{ minHeight: height }}
        >
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={data}
                    margin={{ top: 16, right: 8, left: -20, bottom: 0 }}
                    barGap={2}
                >
                    <CartesianGrid vertical={false} stroke={c.track} strokeDasharray="3 3" />
                    <XAxis
                        dataKey="op"
                        tickLine={false}
                        axisLine={{ stroke: c.track }}
                        tick={{ fontSize: 11, fill: c.muted }}
                    />
                    <YAxis
                        domain={[0, 100]}
                        ticks={[0, 20, 40, 60, 80, 100]}
                        tickFormatter={(v) => `${v}%`}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 11, fill: c.muted }}
                    />
                    <Tooltip
                        formatter={(v) => `${v}%`}
                        contentStyle={{
                            background: c.cardBg,
                            border: `1px solid ${c.cardBorder}`,
                            borderRadius: 8,
                            fontSize: 12,
                        }}
                        labelStyle={{ color: c.title }}
                        cursor={{ fill: c.track, opacity: 0.4 }}
                    />
                    <Bar dataKey="eff" name="Efficiency" fill={c.accent} radius={[3, 3, 0, 0]} barSize={16}>
                        <LabelList
                            dataKey="eff"
                            position="top"
                            formatter={(v) => `${v}%`}
                            style={{ fontSize: 10, fill: c.muted, fontWeight: 600 }}
                        />
                    </Bar>
                    <Bar dataKey="util" name="Utilization" fill={utilColor} radius={[3, 3, 0, 0]} barSize={16}>
                        <LabelList
                            dataKey="util"
                            position="top"
                            formatter={(v) => `${v}%`}
                            style={{ fontSize: 10, fill: c.muted, fontWeight: 600 }}
                        />
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </Panel>
    );
}