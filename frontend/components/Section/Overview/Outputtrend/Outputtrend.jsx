import React, { useEffect, useState } from "react";
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
import { getOutputTrend } from "../../../../utils/api";

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

/*
 * Output per 5 minutes. Loads from the API and refreshes every 10 seconds.
 * Pass `data` ([{ time, output, target }]) to override the API.
 */
export default function OutputTrend({ data, mode = "live", height = 300 }) {
  const c = useDashboardColors();
  const [series, setSeries] = useState([]);

  useEffect(() => {
    if (data) return undefined;

    let active = true;
    setSeries([]); // clear the other mode's data

    const load = async () => {
      try {
        const res = await getOutputTrend(mode);
        if (active) {
          setSeries(
            (res.series || []).map((p) => ({
              time: p.label,
              output: p.output,
              target: p.target,
            })),
          );
        }
      } catch (err) {
        console.error("Failed to fetch output trend:", err);
      }
    };

    load();
    const intervalId = setInterval(load, 10000);

    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [data, mode]);

  const chartData = data ?? series;

  // Show every label for short ranges; thin them out when there are many bars.
  const tickInterval = Math.max(0, Math.ceil(chartData.length / 8) - 1);

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
          data={chartData}
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
            barSize={64}
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
