import React from "react";
import { Box, Card, Typography } from "@mui/material";
import ArrowDropUpIcon from "@mui/icons-material/ArrowDropUp";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import useDashboardColors from "../../Overview/Tokens/Tokens";

/*
 * KPI card with a left-aligned coloured icon.
 * Props: label, value, delta, trend ("up"|"down"|null), sub, icon, iconColor, deltaColor
 */
export default function ReportKpiCard({
  label,
  value,
  delta,
  trend = "up",
  sub,
  icon,
  iconColor,
  deltaColor,
}) {
  const c = useDashboardColors();
  const color = deltaColor || (trend === "down" ? c.red : c.green);

  return (
    <Card
      variant="outlined"
      sx={{
        height: "100%",
        borderRadius: "14px",
        bgcolor: c.cardBg,
        border: `1px solid ${c.cardBorder}`,
        boxShadow: "none",
        p: 2,
      }}
    >
      <Typography sx={{ fontSize: 12, fontWeight: 600, color: c.muted }}>
        {label}
      </Typography>

      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mt: 1 }}>
        {icon && (
          <Box
            sx={{
            //   color: iconColor || c.accent,
              display: "flex",
              flexShrink: 0,
              "& svg": { fontSize: 38 },
            }}
          >
            {icon}
          </Box>
        )}

        <Box sx={{ minWidth: 0 }}>
          <Typography
            sx={{
              fontSize: 28,
              fontWeight: 800,
              lineHeight: 1.1,
              color: c.title,
            }}
          >
            {value}
          </Typography>

          {delta && (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                color,
                fontSize: 13,
                fontWeight: 700,
                mt: 0.5,
              }}
            >
              {trend === "up" && (
                <ArrowDropUpIcon sx={{ fontSize: 20, ml: "-4px" }} />
              )}
              {trend === "down" && (
                <ArrowDropDownIcon sx={{ fontSize: 20, ml: "-4px" }} />
              )}
              {delta}
            </Box>
          )}

          {sub && (
            <Typography sx={{ fontSize: 11.5, color: c.muted, mt: 0.25 }}>
              {sub}
            </Typography>
          )}
        </Box>
      </Box>
    </Card>
  );
}
