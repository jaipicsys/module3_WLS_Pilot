import React, { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors, { barShades } from "../Tokens/Tokens";
import { getOutputByProduct } from "../../../../utils/api";

/*
 * Output per product. Loads from the API and refreshes every 10 seconds.
 * Pass `data` ([{ label, value }]) to override the API.
 */
export default function OutputByProduct({ data }) {
    const c = useDashboardColors();
    const [rows, setRows] = useState([]);

    useEffect(() => {
        if (data) return undefined;

        let active = true;

        const load = async () => {
            try {
                const res = await getOutputByProduct();
                if (active) {
                    setRows(
                        (res.products || []).map((p) => ({
                            label: p.name,
                            value: p.value,
                        }))
                    );
                }
            } catch (err) {
                console.error("Failed to fetch output by product:", err);
            }
        };

        load();
        const intervalId = setInterval(load, 10000);

        return () => {
            active = false;
            clearInterval(intervalId);
        };
    }, [data]);

    const list = data ?? rows;
    const max = Math.max(...list.map((d) => d.value), 1);

    return (
        <Panel title="Output by Product">
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
                {list.map((row, i) => {
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
                                    fontSize: 14,
                                    color: c.text,
                                }}
                            >
                                {row.label}
                            </Typography>

                            <Box
                                sx={{
                                    flex: 1,
                                    height: 30,
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