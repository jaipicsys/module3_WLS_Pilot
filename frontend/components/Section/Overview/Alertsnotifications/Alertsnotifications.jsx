import React from "react";
import { useRouter } from "next/router";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

const ALERT_DATA = [
  {
    severity: "medium",
    title: "Towel Count Correction",
    detail:
      "Incorrect towel count is reported and corrected by adding or removing towels.",
    time: "",
  },
];

export default function AlertsNotifications({ onViewAll }) {
  const c = useDashboardColors();
  const router = useRouter();

  const handleAlertClick = () => {
    router.push("/alerts");
  };

  const dotColor = {
    high: c.red,
    medium: c.orange,
    low: "#eab308",
  };

  return (
    <Panel
      title="Alerts & Notifications"
      action="View All"
      onActionClick={() => router.push("/alerts")}
    >
      <Box sx={{ display: "flex", flexDirection: "column" }}>
        {ALERT_DATA.map((row, i) => (
          <Box
            key={i}
            onClick={handleAlertClick}
            sx={{
              display: "flex",
              alignItems: "flex-start",
              gap: 1.25,
              py: 1.25,
              cursor: "pointer",
              borderRadius: 1,
              "&:hover": {
                bgcolor: c.track,
              },
            }}
          >
            <Box
              sx={{
                mt: "5px",
                width: 9,
                height: 9,
                borderRadius: "50%",
                bgcolor: dotColor[row.severity] || c.gray,
                flexShrink: 0,
              }}
            />

            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                sx={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: c.title,
                }}
              >
                {row.title}
              </Typography>

              <Typography
                sx={{
                  fontSize: 12,
                  color: c.muted,
                }}
              >
                {row.detail}
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>
    </Panel>
  );
}
