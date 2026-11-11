import React from "react";
import { Box, Grid } from "@mui/material";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import AccessTimeOutlined from "@mui/icons-material/AccessTimeOutlined";
import PauseCircleOutlineOutlined from "@mui/icons-material/PauseCircleOutlineOutlined";
import DonutLargeIcon from "@mui/icons-material/DonutLarge";
import { TbPackageExport } from "react-icons/tb";
import Header from "../../Layout/Header/Header";
import KpiCard from "./Kpicard/Kpicard";
import OutputTrend from "./Outputtrend/Outputtrend";
import LiveCameraFeed from "./Livecamerafeed/Livecamerafeed";
import OutputByProduct from "./Outputbyproduct/Outputbyproduct";
import TopOperators from "./Topoperators/Topoperators";
import LossBreakdown from "./Lossbreakdown/Lossbreakdown";
import AlertsNotifications from "./Alertsnotifications/Alertsnotifications";

/* Static KPI data */
const KPIS = [
  {
    label: "Total Output",
    value: "43",
    delta: "12%",
    trend: "up",
    sub: "vs. previous shift",
    icon: <Inventory2Outlined />,
  },
  {
    label: "Throughput",
    value: "86",
    delta: "4%",
    trend: "up",
    sub: "units/hour",
    icon: <TbPackageExport fontSize={24} />,
  },
  {
    label: "Productive Time",
    value: "2h 34m",
    delta: "78%",
    trend: null,
    sub: "of available time",
    icon: <AccessTimeOutlined />,
  },
  {
    label: "Utilization",
    value: "73.5%",
    sub: "productive time / total operator time",
    icon: <DonutLargeIcon />,
  },
  {
    label: "Idle / Waiting Time",
    value: "0h 26m",
    delta: "22%",
    trend: null,
    sub: "of available time",
    icon: <PauseCircleOutlineOutlined />,
  },
];

const Overview = () => {
  return (
    <>
      <Header
        title="Plant Overview"
        description="Real-time visibility into towel packing operations, productivity and performance."
      />

      <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
        <Grid container spacing={2}>
          {/* Row 1 — KPI cards */}
          {KPIS.map((k) => (
            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }} key={k.label}>
              <KpiCard {...k} />
            </Grid>
          ))}

          {/* Row 2 — trend / live camera */}
          <Grid size={{ xs: 12, md: 6, lg: 6 }}>
            <OutputTrend />
          </Grid>

          <Grid size={{ xs: 12, md: 12, lg: 6 }}>
            <LiveCameraFeed />
          </Grid>

          {/* Row 3 — product / operators / loss */}
          <Grid size={{ xs: 12, md: 6, lg: 6 }}>
            <OutputByProduct />
          </Grid>

          <Grid size={{ xs: 12, md: 6, lg: 6 }}>
            <TopOperators />
          </Grid>

          <Grid size={{ xs: 12, md: 12, lg: 6 }}>
            <LossBreakdown />
          </Grid>

          {/* Row 4 — alerts */}
          <Grid size={{ xs: 12, lg: 6 }}>
            <AlertsNotifications />
          </Grid>
        </Grid>
      </Box>
    </>
  );
};

export default Overview;
