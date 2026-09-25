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
  { time: "6 AM", value: 72 },
  { time: "", value: 74 },
  { time: "", value: 73 },
  { time: "8 AM", value: 75 },
  { time: "", value: 74 },
  { time: "", value: 76 },
  { time: "10 AM", value: 77 },
  { time: "", value: 78 },
  { time: "", value: 80 },
  { time: "12 PM", value: 79 },
  { time: "", value: 81 },
  { time: "", value: 82 },
  { time: "2 PM", value: 83 },
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

export default function SopAdherenceTrend({
  data = DEFAULT_DATA,
  target = 75,
  current = "92%",
  height = 320,
}) {
  const c = useDashboardColors();

  return (
    <Panel
      title="SOP Adherence Trend"
      headerRight={
        <Box sx={{ display: "flex", gap: 2 }}>
          <LegendDot color={c.green} label="SOP Adherence" c={c} />
          <LegendDot color={c.red} dashed label="Target" c={c} />
        </Box>
      }
      sx={{ minHeight: height }}
    >
      <Box sx={{ position: "relative", height: "100%" }}>
        {current && (
          <Typography
            sx={{
              position: "absolute",
              top: 4,
              right: 8,
              fontSize: 14,
              fontWeight: 800,
              color: c.title,
              zIndex: 1,
            }}
          >
            {current}
          </Typography>
        )}

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
              dataKey="time"
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
                value: "Adherence (%)",
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
            <ReferenceLine y={target} stroke={c.red} strokeDasharray="5 4" />
            <Line
              type="monotone"
              dataKey="value"
              name="SOP Adherence"
              stroke={c.green}
              strokeWidth={2.5}
              dot={{ r: 3, fill: c.green, strokeWidth: 0 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </Box>
    </Panel>
  );
}
