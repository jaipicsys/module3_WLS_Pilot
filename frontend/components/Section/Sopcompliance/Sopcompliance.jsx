import React from "react";
import { Box, Grid } from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";

import Header from "../../Layout/Header/Header";
import SopKpiCard from "./Sopkpicard/Sopkpicard";
import SopAdherenceTrend from "./Sopadherencetrend/Sopadherencetrend";
import AdherenceByStation from "./Adherencebystation/Adherencebystation";
import LiveFeed from "../Overview/Livefeed/Livefeed";
import RecentSopDeviations from "./Recentsopdeviations/Recentsopdeviations";
import DeviationCategories from "./Deviationcategories/Deviationcategories";
import VideoClip from "./Videoclip/Videoclip";
import SopComplianceByProduct from "./Sopcompliancebyproduct/Sopcompliancebyproduct";
import KeyInsights from "./Keyinsights/Keyinsights";

const GREEN = "#12b76a";
const RED = "#ef4444";
const AMBER = "#f59e0b";
const ACCENT = "#ef5323";

const Sopcompliance = () => {
  const kpis = [
    {
      label: "Overall SOP Adherence",
      value: "92%",
      delta: "4%",
      trend: "up",
      sub: "vs. previous shift",
      icon: <CheckCircleOutlineIcon />,
      iconColor: GREEN,
    },
    {
      label: "Compliant Cycles",
      value: "1,148",
      delta: "7%",
      trend: "up",
      icon: <CheckCircleIcon />,
      iconColor: ACCENT,
    },
    {
      label: "Non-Compliant Cycles",
      value: "100",
      delta: "12%",
      trend: "down",
      deltaColor: RED,
      icon: <CancelIcon />,
      iconColor: RED,
    },
    {
      label: "Most Common Deviation",
      value: "Incorrect Folding (42%)",
      valueFontSize: 18,
      icon: <WarningAmberRoundedIcon />,
      iconColor: AMBER,
    },
  ];

  return (
    <>
      <Header
        title="SOP / Process Compliance"
        description="Ensure standard work is followed and maintain process consistency"
      />

      <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
        <Grid container spacing={2}>
          {/* Row 1 — KPI cards */}
          {kpis.map((k) => (
            <Grid size={{ xs: 12, sm: 6, md: 3 }} key={k.label}>
              <SopKpiCard {...k} />
            </Grid>
          ))}

          {/* Row 2 — trend / station / live feed */}
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <SopAdherenceTrend />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <AdherenceByStation />
          </Grid>
          <Grid size={{ xs: 12, md: 12, lg: 4 }}>
            <LiveFeed
              title="Live Feed – Line 1 (Packing)"
              caption="Line 1 – Towel Packing"
              timestamp="Nov 14, 2024   11:32:13"
              height={320}
            />
          </Grid>

          {/* Row 3 — deviations / categories / clip */}
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <RecentSopDeviations />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <DeviationCategories />
          </Grid>
          <Grid size={{ xs: 12, md: 12, lg: 4 }}>
            <VideoClip />
          </Grid>

          {/* Row 4 — compliance table / insights */}
          <Grid size={{ xs: 12, lg: 7 }}>
            <SopComplianceByProduct />
          </Grid>
          <Grid size={{ xs: 12, lg: 5 }}>
            <KeyInsights />
          </Grid>
        </Grid>
      </Box>
    </>
  );
};

export default Sopcompliance;
