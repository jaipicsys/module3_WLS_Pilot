import React from "react";
import HBarList from "../Hbarlist/Hbarlist";

const DEFAULT_DATA = [
  { label: "Material Waiting", amount: "32m", pct: 41, color: "#f0563a" },
  { label: "QC Waiting", amount: "18m", pct: 23, color: "#f59e0b" },
  { label: "Changeover", amount: "16m", pct: 21, color: "#f47a4e" },
  { label: "Personal Break", amount: "8m", pct: 10, color: "#f89b78" },
  { label: "Others", amount: "4m", pct: 5, color: "#c7bfb8" },
];

export default function TopLossReasons({ data = DEFAULT_DATA }) {
  const max = Math.max(...data.map((d) => d.pct), 1);

  const rows = data.map((d) => ({
    label: d.label,
    display: `${d.amount} (${d.pct}%)`,
    pct: (d.pct / max) * 100,
    color: d.color,
  }));

  return (
    <HBarList
      title="Top Loss Reasons (Last 14 Days)"
      rows={rows}
      labelWidth={100}
      valueWidth={78}
    />
  );
}
