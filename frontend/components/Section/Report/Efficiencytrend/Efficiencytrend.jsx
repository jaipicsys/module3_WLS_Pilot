import React from "react";
import { Box, Typography } from "@mui/material";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  { day: "Nov 1", value: 72 },
  { day: "", value: 80 },
  { day: "Nov 3", value: 82 },
  { day: "", value: 79 },
  { day: "Nov 5", value: 81 },
  { day: "", value: 83 },
  { day: "Nov 7", value: 82 },
  { day: "", value: 85 },
  { day: "Nov 9", value: 84 },
  { day: "", value: 86 },
  { day: "Nov 11", value: 88 },
  { day: "", value: 87 },
  { day: "Nov 13", value: 91 },
];

function LegendDot({ color, dashed, label, c }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
      {dashed ? (
        <Box sx={{ width: 16, borderTop: `2px dashed ${color}` }} />
      ) : (
        <Box
          sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: color }}
        />
      )}
      <Typography sx={{ fontSize: 12, color: c.muted }}>{label}</Typography>
    </Box>
  );
}

export default function EfficiencyTrend({
  data = DEFAULT_DATA,
  target = 82,
  height = 320,
}) {
  const c = useDashboardColors();

  return (
    <Panel
      title="Efficiency Trend"
      headerRight={
        <Box sx={{ display: "flex", gap: 2 }}>
          <LegendDot color={c.green} label="Efficiency" c={c} />
          <LegendDot color={c.muted} dashed label="Target" c={c} />
        </Box>
      }
      sx={{ minHeight: height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 8, left: -14, bottom: 0 }}
        >
          <CartesianGrid
            vertical={false}
            stroke={c.track}
            strokeDasharray="3 3"
          />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={{ stroke: c.track }}
            tick={{ fontSize: 11, fill: c.muted }}
            interval={0}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            tickFormatter={(v) => `${v}%`}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: c.muted }}
            label={{
              value: "Efficiency (%)",
              angle: -90,
              position: "insideLeft",
              offset: 20,
              style: { fontSize: 11, fill: c.muted },
            }}
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
          />
          <ReferenceLine y={target} stroke={c.muted} strokeDasharray="5 4" />
          <Line
            type="monotone"
            dataKey="value"
            name="Efficiency"
            stroke={c.green}
            strokeWidth={2.5}
            dot={{ r: 3, fill: c.green, strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}
