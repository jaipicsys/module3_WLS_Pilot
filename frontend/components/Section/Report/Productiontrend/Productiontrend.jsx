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
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  { day: "Nov 1", output: 1200, target: 1500 },
  { day: "", output: 1350, target: 1550 },
  { day: "Nov 3", output: 1500, target: 1700 },
  { day: "", output: 1650, target: 1800 },
  { day: "Nov 5", output: 1400, target: 1750 },
  { day: "", output: 1850, target: 1900 },
  { day: "Nov 7", output: 1750, target: 2050 },
  { day: "", output: 1600, target: 2000 },
  { day: "Nov 9", output: 1500, target: 1950 },
  { day: "", output: 1900, target: 2150 },
  { day: "Nov 11", output: 2200, target: 2300 },
  { day: "", output: 2050, target: 2250 },
  { day: "Nov 13", output: 2250, target: 2350 },
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

export default function ProductionTrend({ data = DEFAULT_DATA, height = 320 }) {
  const c = useDashboardColors();

  return (
    <Panel
      title="Production Trend"
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
          margin={{ top: 8, right: 8, left: -6, bottom: 0 }}
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
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: c.muted }}
            label={{
              value: "Output (units)",
              angle: -90,
              position: "insideLeft",
              offset: 20,
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
            barSize={16}
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
