import React from "react";
import { Box, Card, Typography } from "@mui/material";
import ArrowDropUpIcon from "@mui/icons-material/ArrowDropUp";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import useDashboardColors from "../Tokens/Tokens";

/*
 * A single KPI card. Render six of these in a Grid.
 *
 * Props:
 *   label   small caption (e.g. "Total Output")
 *   value   big value (e.g. "1,248", "6h 12m", "88%")
 *   delta   change text without arrow (e.g. "12%", "78%")
 *   trend   "up" | "down" | null  -> shows a coloured arrow before delta
 *   sub     muted sub-caption (e.g. "vs. previous shift")
 *   icon    a MUI icon element, e.g. <Inventory2Outlined />
 *   deltaColor  override the delta colour (defaults to green up / red down)
 */
export default function KpiCard({
    label,
    value,
    delta,
    trend = "up",
    sub,
    icon,
    deltaColor,
}) {
    const c = useDashboardColors();

    const color =
        deltaColor || (trend === "down" ? c.red : c.green);

    return (
        <Card
            variant="outlined"
            sx={{
                position: "relative",
                height: "100%",
                borderRadius: "14px",
                bgcolor: c.cardBg,
                border: `1px solid ${c.cardBorder}`,
                boxShadow: "none",
                p: 2,
            }}
        >
            {/* Icon top-right */}
            {icon && (
                <Box
                    sx={{
                        position: "absolute",
                        top: 16,
                        right: 16,
                        // color: c.accent,
                        display: "flex",
                        "& svg": { fontSize: 26 },
                    }}
                >
                    {icon}
                </Box>
            )}

            <Typography
                sx={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: c.muted,
                    pr: 4,
                }}
            >
                {label}
            </Typography>

            <Typography
                sx={{
                    fontSize: 28,
                    fontWeight: 800,
                    lineHeight: 1.1,
                    color: c.title,
                    mt: 0.75,
                }}
            >
                {value}
            </Typography>

            {(delta || sub) && (
                <Box sx={{ mt: 1 }}>
                    {delta && (
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                color,
                                fontSize: 14,
                                fontWeight: 700,
                            }}
                        >
                            {trend === "up" && (
                                <ArrowDropUpIcon sx={{ fontSize: 20, ml: "-4px" }} />
                            )}
                            {trend === "down" && (
                                <ArrowDropDownIcon
                                    sx={{ fontSize: 20, ml: "-4px" }}
                                />
                            )}
                            {delta}
                        </Box>
                    )}

                    {sub && (
                        <Typography
                            sx={{ fontSize: 12, color: c.muted, mt: 0.25 }}
                        >
                            {sub}
                        </Typography>
                    )}
                </Box>
            )}
        </Card>
    );
}