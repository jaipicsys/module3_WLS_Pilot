import React from "react";
import HBarList from "../Hbarlist/Hbarlist";

const shades = ["#e0491d", "#ef5323", "#f47a4e", "#f89b78", "#c7bfb8"];

const DEFAULT_DATA = [
    { label: "Towel – Standard", value: 7240 },
    { label: "Towel – Premium", value: 5180 },
    { label: "Hand Towel", value: 3120 },
    { label: "Bath Towel", value: 1980 },
    { label: "Others", value: 900 },
];

export default function OutputByProduct({ data = DEFAULT_DATA }) {
    const max = Math.max(...data.map((d) => d.value), 1);

    const rows = data.map((d, i) => {
        const isOther = d.label.toLowerCase().startsWith("other");
        return {
            label: d.label,
            display: d.value.toLocaleString(),
            pct: (d.value / max) * 100,
            color: isOther ? "#c7bfb8" : shades[Math.min(i, shades.length - 1)],
        };
    });

    return <HBarList title="Output by Product" rows={rows} />;
}