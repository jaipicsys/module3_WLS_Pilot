import React from "react";
import { Box, Typography } from "@mui/material";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  { hour: "6 AM", output: 68 },
  { hour: "7 AM", output: 96 },
  { hour: "8 AM", output: 90 },
  { hour: "9 AM", output: 112 },
  { hour: "10 AM", output: 120 },
  { hour: "11 AM", output: 118 },
  { hour: "12 PM", output: 135 },
  { hour: "1 PM", output: 150 },
  { hour: "2 PM", output: 158 },
];

function LegendDot({ color, label, c }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
      <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: color }} />
      <Typography sx={{ fontSize: 12, color: c.muted }}>{label}</Typography>
    </Box>
  );
}

export default function OutputByHour({ data = DEFAULT_DATA, height = 300 }) {
  const c = useDashboardColors();

  return (
    <Panel
      title="Output by Hour"
      headerRight={<LegendDot color={c.accent} label="Output" c={c} />}
      sx={{ minHeight: height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: -14, bottom: 0 }}
        >
          <CartesianGrid
            vertical={false}
            stroke={c.track}
            strokeDasharray="3 3"
          />
          <XAxis
            dataKey="hour"
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
            barSize={18}
          />
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );
}
