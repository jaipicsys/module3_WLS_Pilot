import React from "react";
import { Box, Card, Typography } from "@mui/material";
import ArrowDropUpIcon from "@mui/icons-material/ArrowDropUp";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import useDashboardColors from "../../Overview/Tokens/Tokens";

/*
 * KPI card with the icon on the LEFT of the value (used on the SOP page).
 *
 * Props:
 *   label, value, delta, trend ("up"|"down"|null), sub
 *   icon        MUI icon element
 *   iconColor   colour for the icon
 *   deltaColor  override delta colour
 *   valueFontSize  override big-value size (default 28)
 */
export default function SopKpiCard({
  label,
  value,
  delta,
  trend = "up",
  sub,
  icon,
  iconColor,
  deltaColor,
  valueFontSize = 28,
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
              "& svg": { fontSize: 40 },
            }}
          >
            {icon}
          </Box>
        )}

        <Box sx={{ minWidth: 0 }}>
          <Typography
            sx={{
              fontSize: valueFontSize,
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
