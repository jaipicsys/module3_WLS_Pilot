import React, { useState } from "react";
import { Box, Grid, Tabs, Tab, Typography } from "@mui/material";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import InsightsOutlined from "@mui/icons-material/InsightsOutlined";
import GpsFixed from "@mui/icons-material/GpsFixed";
import AssignmentOutlined from "@mui/icons-material/AssignmentOutlined";

import Header from "../../Layout/Header/Header";
import ReportKpiCard from "./Reportkpicard/Reportkpicard";
import ProductionTrend from "./Productiontrend/Productiontrend";
import EfficiencyTrend from "./Efficiencytrend/Efficiencytrend";
import OutputByProduct from "./Outputbyproduct/Outputbyproduct";
import TopLossReasons from "./Toplossreasons/Toplossreasons";
import OutputByShift from "./Outputbyshift/Outputbyshift";
import QuickReports from "./Quickreports/Quickreports";
import ScheduleReports from "./Schedulereports/Schedulereports";
import RecentReports from "./Recentreports/Recentreports";
import DataDrivenImprovement from "./Datadrivenimprovement/Datadrivenimprovement";

const TABS = [
  "Production",
  "Operator",
  "Loss Analysis",
  "SOP Compliance",
  "Custom Report",
];

const kpis = [
  {
    label: "Total Output",
    value: "18,420",
    delta: "12%",
    trend: "up",
    sub: "vs. previous period",
    icon: <Inventory2Outlined />,
  },
  {
    label: "Average Output / Hour",
    value: "154",
    delta: "8%",
    trend: "up",
    sub: "vs. previous period",
    icon: <InsightsOutlined />,
  },
  {
    label: "Overall Efficiency",
    value: "88%",
    delta: "6%",
    trend: "up",
    sub: "vs. previous period",
    icon: <GpsFixed />,
  },
  {
    label: "SOP Adherence",
    value: "92%",
    delta: "4%",
    trend: "up",
    sub: "vs. previous period",
    icon: <AssignmentOutlined />,
  },
];

function ProductionTab() {
  return (
    <Grid container spacing={2}>
      {/* KPIs */}
      {kpis.map((k) => (
        <Grid size={{ xs: 12, sm: 6, md: 3 }} key={k.label}>
          <ReportKpiCard {...k} />
        </Grid>
      ))}

      {/* Trends */}
      <Grid size={{ xs: 12, lg: 6 }}>
        <ProductionTrend />
      </Grid>
      <Grid size={{ xs: 12, lg: 6 }}>
        <EfficiencyTrend />
      </Grid>

      {/* Bar panels */}
      <Grid size={{ xs: 12, md: 6, lg: 4 }}>
        <OutputByProduct />
      </Grid>
      <Grid size={{ xs: 12, md: 6, lg: 4 }}>
        <TopLossReasons />
      </Grid>
      <Grid size={{ xs: 12, md: 12, lg: 4 }}>
        <OutputByShift />
      </Grid>
    </Grid>
  );
}

const Report = () => {
  const [tab, setTab] = useState(0);

  return (
    <>
      <Header
        title={"Reports & Trends"}
        description={
          "Access detailed reports and trends for data-driven decision making"
        }
      />

      <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
        {/* Tabs */}
        <Tabs
          value={tab}
          onChange={(e, v) => setTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            mb: 2,
            minHeight: 40,
            "& .MuiTab-root": {
              textTransform: "none",
              fontSize: 14,
              fontWeight: 600,
              minHeight: 40,
              px: 2,
            },
            "& .Mui-selected": { color: "#008a67 !important" },
            "& .MuiTabs-indicator": { backgroundColor: "#008a67" },
          }}
        >
          {TABS.map((t) => (
            <Tab key={t} label={t} />
          ))}
        </Tabs>

        <Grid container spacing={2}>
          {/* Main tab content */}
          <Grid size={{ xs: 12, lg: 9 }}>
            {tab === 0 ? (
              <ProductionTab />
            ) : (
              <Box
                sx={{
                  p: 6,
                  textAlign: "center",
                  border: "1px dashed",
                  borderColor: "divider",
                  borderRadius: "14px",
                }}
              >
                <Typography color="text.secondary">
                  {TABS[tab]} report — coming soon.
                </Typography>
              </Box>
            )}
          </Grid>

          {/* Sidebar */}
          <Grid size={{ xs: 12, lg: 3 }}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <QuickReports onSelect={() => setTab(0)} />
              <ScheduleReports />
            </Box>
          </Grid>

          {/* Bottom row */}
          <Grid size={{ xs: 12, lg: 8 }}>
            <RecentReports />
          </Grid>
          <Grid size={{ xs: 12, lg: 4 }}>
            <DataDrivenImprovement />
          </Grid>
        </Grid>
      </Box>
    </>
  );
};

export default Report;
