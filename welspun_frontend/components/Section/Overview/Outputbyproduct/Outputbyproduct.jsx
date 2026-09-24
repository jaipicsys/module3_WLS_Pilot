import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors, { barShades } from "../Tokens/Tokens";

const DEFAULT_DATA = [
    { label: "Towel – Standard", value: 520 },
    { label: "Towel – Premium", value: 310 },
    { label: "Hand Towel", value: 198 },
    { label: "Bath Towel", value: 150 },
    { label: "Others", value: 70 },
];

export default function OutputByProduct({ data = DEFAULT_DATA }) {
    const c = useDashboardColors();
    const max = Math.max(...data.map((d) => d.value), 1);

    return (
        <Panel title="Output by Product">
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
                {data.map((row, i) => {
                    const isOther = row.label.toLowerCase().startsWith("other");
                    const color = isOther
                        ? c.gray
                        : barShades[Math.min(i, barShades.length - 1)];

                    return (
                        <Box
                            key={row.label}
                            sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
                        >
                            <Typography
                                sx={{
                                    width: 110,
                                    flexShrink: 0,
                                    fontSize: 12.5,
                                    color: c.text,
                                }}
                            >
                                {row.label}
                            </Typography>

                            <Box
                                sx={{
                                    flex: 1,
                                    height: 20,
                                    borderRadius: "4px",
                                    bgcolor: c.track,
                                    overflow: "hidden",
                                }}
                            >
                                <Box
                                    sx={{
                                        width: `${(row.value / max) * 100}%`,
                                        height: "100%",
                                        borderRadius: "4px",
                                        bgcolor: color,
                                        transition: "width 0.4s ease",
                                    }}
                                />
                            </Box>

                            <Typography
                                sx={{
                                    width: 40,
                                    flexShrink: 0,
                                    textAlign: "right",
                                    fontSize: 12.5,
                                    fontWeight: 700,
                                    color: c.title,
                                }}
                            >
                                {row.value}
                            </Typography>
                        </Box>
                    );
                })}
            </Box>
        </Panel>
    );
}