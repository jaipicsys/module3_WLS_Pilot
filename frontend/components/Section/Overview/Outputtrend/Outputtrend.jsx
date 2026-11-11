import React from "react";
import { Box, Typography } from "@mui/material";
import {
  ComposedChart,
  Bar,
  Line,
  LabelList,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

/* Static output per 5 minutes */
const CHART_DATA = [
  { time: "11:00 AM", output: 7 },
  { time: "11:05 AM", output: 7 },
  { time: "11:10 AM", output: 10 },
  { time: "11:15 AM", output: 8 },
  { time: "11:20 AM", output: 7 },
  { time: "11:25 AM", output: 3 },
  { time: "11:30 AM", output: 1 },
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

/* Output per 5 minutes (static data). */
export default function OutputTrend({ height = 300 }) {
  const c = useDashboardColors();

  // Show every label for short ranges; thin them out when there are many bars.
  const tickInterval = Math.max(0, Math.ceil(CHART_DATA.length / 8) - 1);

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
          data={CHART_DATA}
          margin={{ top: 20, right: 8, left: -8, bottom: 0 }}
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
            interval={tickInterval}
          />

          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: c.muted }}
            allowDecimals={false}
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
            barSize={40}
            isAnimationActive={false}
          >
            <LabelList
              dataKey="output"
              position="top"
              fill={c.title}
              fontSize={11}
              fontWeight={600}
            />
          </Bar>

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
