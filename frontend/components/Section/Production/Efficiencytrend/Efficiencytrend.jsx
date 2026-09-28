import React from "react";
import {
  LineChart,
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
  { time: "6 AM", value: 62 },
  { time: "", value: 66 },
  { time: "", value: 68 },
  { time: "8 AM", value: 72 },
  { time: "", value: 74 },
  { time: "", value: 78 },
  { time: "10 AM", value: 80 },
  { time: "", value: 84 },
  { time: "", value: 88 },
  { time: "12 PM", value: 92 },
  { time: "", value: 82 },
  { time: "", value: 84 },
  { time: "2 PM", value: 81 },
];

export default function EfficiencyTrend({ data = DEFAULT_DATA, height = 300 }) {
  const c = useDashboardColors();

  // index of the peak, used to draw a larger labelled dot there
  const peak = data.reduce(
    (best, d, i) => (d.value > data[best].value ? i : best),
    0,
  );

  const renderDot = (props) => {
    const { cx, cy, index } = props;
    if (index === peak) {
      return (
        <g key={index}>
          <text
            x={cx}
            y={cy - 14}
            textAnchor="middle"
            style={{ fontSize: 12, fontWeight: 700, fill: c.title }}
          >
            {data[peak].value}%
          </text>
          <circle
            cx={cx}
            cy={cy}
            r={5.5}
            fill={c.green}
            stroke="#fff"
            strokeWidth={2}
          />
        </g>
      );
    }
    return <circle key={index} cx={cx} cy={cy} r={3} fill={c.green} />;
  };

  return (
    <Panel title="Efficiency Trend" sx={{ minHeight: height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 20, right: 8, left: -14, bottom: 0 }}
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
              value: "Efficiency",
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
          <Line
            type="monotone"
            dataKey="value"
            name="Efficiency"
            stroke={c.green}
            strokeWidth={2.5}
            dot={renderDot}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}
