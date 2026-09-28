import React from "react";
import HBarList from "../Hbarlist/Hbarlist";

const DEFAULT_DATA = [
  { label: "Day (6 AM – 2 PM)", value: 8420, color: "#e0491d" },
  { label: "Evening (2 PM – 10 PM)", value: 6180, color: "#f2734f" },
  { label: "Night (10 PM – 6 AM)", value: 3820, color: "#f9b79c" },
];

export default function OutputByShift({ data = DEFAULT_DATA }) {
  const max = Math.max(...data.map((d) => d.value), 1);

  const rows = data.map((d) => ({
    label: d.label,
    display: d.value.toLocaleString(),
    pct: (d.value / max) * 100,
    color: d.color,
  }));

  return (
    <HBarList
      title="Output by Shift"
      rows={rows}
      labelWidth={130}
      valueWidth={56}
      barHeight={34}
      gap={2.5}
    />
  );
}
