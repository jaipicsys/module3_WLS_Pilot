import React from "react";
import { Box, Card, Typography, Button } from "@mui/material";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import AddIcon from "@mui/icons-material/Add";
import useDashboardColors from "../../Overview/Tokens/Tokens";

export default function ScheduleReports({ onSchedule }) {
  const c = useDashboardColors();

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: "14px",
        bgcolor: c.cardBg,
        border: `1px solid ${c.cardBorder}`,
        boxShadow: "none",
        p: 2,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 1.5 }}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: "9px",
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "#025f531e",
            color: c.accent,
          }}
        >
          <AccessTimeIcon sx={{ fontSize: 20 }} />
        </Box>
        <Box>
          <Typography sx={{ fontSize: 14, fontWeight: 700, color: c.title }}>
            Schedule Reports
          </Typography>
          <Typography sx={{ fontSize: 11.5, color: c.muted }}>
            Automate report generation and delivery.
          </Typography>
        </Box>
      </Box>

      <Button
        onClick={onSchedule}
        fullWidth
        startIcon={<AddIcon sx={{ fontSize: 18 }} />}
        sx={{
          textTransform: "none",
          fontSize: 13,
          fontWeight: 700,
          color: c.accent,
          border: `1px solid ${c.accent}`,
          borderRadius: "10px",
          py: 1,
          "&:hover": { bgcolor: c.accentSoft, border: `1px solid ${c.accent}` },
        }}
      >
        Schedule a Report
      </Button>
    </Card>
  );
}
