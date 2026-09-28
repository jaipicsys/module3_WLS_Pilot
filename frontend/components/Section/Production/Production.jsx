import React from "react";
import { Box, Grid } from "@mui/material";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import GpsFixed from "@mui/icons-material/GpsFixed";
import InsightsOutlined from "@mui/icons-material/InsightsOutlined";
import TimerOutlined from "@mui/icons-material/TimerOutlined";
import AccessTimeOutlined from "@mui/icons-material/AccessTimeOutlined";
import PauseCircleOutlineOutlined from "@mui/icons-material/PauseCircleOutlineOutlined";

import Header from "../../Layout/Header/Header";
import SopKpiCard from "./Sopkpicard/Sopkpicard";
import OutputTrend from "./Outputtrend/Outputtrend";
import EfficiencyTrend from "./Efficiencytrend/Efficiencytrend";
import OutputByProduct from "./Outputbyproduct/Outputbyproduct";
import ProductWisePerformance from "./Productwiseperformance/Productwiseperformance";
import OutputByHour from "./Outputbyhour/Outputbyhour";
import EfficiencyByProduct from "./Efficiencybyproduct/Efficiencybyproduct";
import RecentProductionEvents from "./Recentproductionevents/Recentproductionevents";
import DeviationCategories from "./Deviationcategories/Deviationcategories";

const RED = "#ef4444";

const productMix = [
  { label: "Towel – Standard", pct: 42, color: "#c0402a" },
  { label: "Towel – Premium", pct: 25, color: "#f4a58c" },
  { label: "Hand Towel", pct: 16, color: "#12b76a" },
  { label: "Bath Towel", pct: 12, color: "#f2734f" },
  { label: "Others", pct: 5, color: "#cbc6c0" },
];

const Production = () => {
  const kpis = [
    {
      label: "Total Output",
      value: "1,248",
      delta: "12%",
      trend: "up",
      sub: "vs. previous shift",
      icon: <Inventory2Outlined />,
    },
    {
      label: "Target Output",
      value: "1,200",
      progress: 104,
      progressLabel: "104%",
      icon: <GpsFixed />,
    },
    {
      label: "Overall Efficiency",
      value: "88%",
      delta: "6%",
      trend: "up",
      sub: "vs. previous shift",
      icon: <InsightsOutlined />,
    },
    {
      label: "Average Cycle Time",
      value: "28 sec",
      delta: "8%",
      trend: "down",
      deltaColor: RED,
      sub: "vs. previous shift",
      icon: <TimerOutlined />,
    },
    {
      label: "Productive Time",
      value: "6h 12m",
      sub: "of 8h (78%)",
      icon: <AccessTimeOutlined />,
    },
    {
      label: "Idle / Waiting Time",
      value: "1h 18m",
      sub: "(16%)",
      icon: <PauseCircleOutlineOutlined />,
    },
  ];

  return (
    <>
      <Header
        title="Output & Efficiency"
        description="Monitor production output, efficiency, and trends across products, operators and shifts"
      />

      <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
        <Grid container spacing={2}>
          {/* Row 1 — KPI cards */}
          {kpis.map((k) => (
            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }} key={k.label}>
              <SopKpiCard {...k} />
            </Grid>
          ))}

          {/* Row 2 — output vs target / efficiency / output by product */}
          <Grid size={{ xs: 12, md: 6, lg: 5 }}>
            <OutputTrend
              title="Output vs Target Trend"
              outputLabel="Actual Output"
              targetLabel="Target Output"
              height={320}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <EfficiencyTrend height={320} />
          </Grid>
          <Grid size={{ xs: 12, md: 12, lg: 3 }}>
            <OutputByProduct />
          </Grid>

          {/* Row 3 — product-wise table / output by hour / efficiency by product */}
          <Grid size={{ xs: 12, md: 6, lg: 5 }}>
            <ProductWisePerformance />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <OutputByHour />
          </Grid>
          <Grid size={{ xs: 12, md: 12, lg: 4 }}>
            <EfficiencyByProduct />
          </Grid>

          {/* Row 4 — recent events / product mix */}
          <Grid size={{ xs: 12, lg: 7 }}>
            <RecentProductionEvents />
          </Grid>
          <Grid size={{ xs: 12, lg: 5 }}>
            <DeviationCategories
              title="Product Mix (Output Share)"
              data={productMix}
              centerValue="1,248"
              centerLabel="Units"
            />
          </Grid>
        </Grid>
      </Box>
    </>
  );
};

export default Production;
