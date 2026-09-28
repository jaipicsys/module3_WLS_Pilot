import React, { useEffect, useMemo, useState } from "react";
import { Box, Grid } from "@mui/material";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import AccessTimeOutlined from "@mui/icons-material/AccessTimeOutlined";
import PauseCircleOutlineOutlined from "@mui/icons-material/PauseCircleOutlineOutlined";
import GpsFixedOutlined from "@mui/icons-material/GpsFixed";
import ChecklistRtlIcon from "@mui/icons-material/ChecklistRtl";
import { TbPackageExport } from "react-icons/tb";

import Header from "../../Layout/Header/Header";
import { getKpiCards, getTimeDistribution } from "../../../utils/api";
import KpiCard from "./Kpicard/Kpicard";
import OutputTrend from "./Outputtrend/Outputtrend";
import TimeDistribution from "./Timedistribution/Timedistribution";
import LiveFeed from "./Livefeed/Livefeed";
import OutputByProduct from "./Outputbyproduct/Outputbyproduct";
import TopOperators from "./Topoperators/Topoperators";
import LossBreakdown from "./Lossbreakdown/Lossbreakdown";
import RecentEvents from "./Recentevents/Recentevents";
import AlertsNotifications from "./Alertsnotifications/Alertsnotifications";

/* Turn a change percentage into { delta, trend } for KpiCard */
const change = (pct) => ({
  delta: `${Math.abs(pct ?? 0)}%`,
  trend: pct > 0 ? "up" : pct < 0 ? "down" : null,
});

const Overview = () => {
  const [kpi, setKpi] = useState(null);
  const [timeDistribution, setTimeDistribution] = useState(null);

  /* Fetch KPI cards and time distribution immediately, then poll every 10 seconds */
  useEffect(() => {
    let intervalId;

    const loadData = async () => {
      try {
        const [kpiData, timeData] = await Promise.all([
          getKpiCards(),
          getTimeDistribution(),
        ]);

        setKpi(kpiData);
        setTimeDistribution(timeData);
      } catch (err) {
        console.error("Failed to fetch overview data:", err);
      }
    };

    loadData();
    intervalId = setInterval(loadData, 10000);

    return () => clearInterval(intervalId);
  }, []);

  /* Map the API response onto the cards */
  const kpis = useMemo(() => {
    const d = kpi || {};

    return [
      {
        label: "Total Output",
        value: d.total_output
          ? Number(d.total_output.value).toLocaleString()
          : "—",
        ...(d.total_output ? change(d.total_output.change_pct) : {}),
        sub: "vs. previous shift",
        icon: <Inventory2Outlined />,
      },
      {
        label: "Output / Hour",
        value: d.output_per_hour
          ? Number(d.output_per_hour.value).toLocaleString()
          : "—",
        ...(d.output_per_hour ? change(d.output_per_hour.change_pct) : {}),
        sub: "units/hour",
        icon: <TbPackageExport fontSize={24} />,
      },
      {
        label: "Productive Time",
        value: d.productive_time?.display ?? "—",
        delta: d.productive_time
          ? `${d.productive_time.pct_of_available}%`
          : undefined,
        trend: null,
        sub: "of available time",
        icon: <AccessTimeOutlined />,
      },
      {
        label: "Idle / Waiting Time",
        value: d.idle_time?.display ?? "—",
        delta: d.idle_time
          ? `${d.idle_time.pct_of_available}%`
          : undefined,
        trend: null,
        sub: "of available time",
        icon: <PauseCircleOutlineOutlined />,
      },
      {
        label: "Efficiency",
        value: d.efficiency ? `${d.efficiency.value_pct}%` : "—",
        ...(d.efficiency ? change(d.efficiency.change_pct) : {}),
        sub: "vs. previous shift",
        icon: <GpsFixedOutlined />,
      },
      {
        label: "SOP Adherence",
        value: d.sop_adherence
          ? `${d.sop_adherence.value_pct}%`
          : "—",
        ...(d.sop_adherence ? change(d.sop_adherence.change_pct) : {}),
        sub: "of observed cycles",
        icon: <ChecklistRtlIcon />,
      },
    ];
  }, [kpi]);

  /* Convert API response into TimeDistribution rows */
  const timeRows = useMemo(() => {
    if (!timeDistribution?.total?.seconds) {
      return undefined;
    }

    const total = Number(timeDistribution.total.seconds);

    const getPct = (seconds) =>
      Number(((Number(seconds || 0) / total) * 100).toFixed(1));

    return [
      {
        label: "Productive",
        value: Number(timeDistribution.productive?.seconds || 0),
        amount: timeDistribution.productive?.display || "—",
        pct: getPct(timeDistribution.productive?.seconds),
      },
      {
        label: "Idle / Waiting",
        value: Number(timeDistribution.idle?.seconds || 0),
        amount: timeDistribution.idle?.display || "—",
        pct: getPct(timeDistribution.idle?.seconds),
      },
      {
        label: "Away",
        value: Number(timeDistribution.away?.seconds || 0),
        amount: timeDistribution.away?.display || "—",
        pct: getPct(timeDistribution.away?.seconds),
      },
    ];
  }, [timeDistribution]);

  const availableTime = timeDistribution?.total?.display || "—";

  return (
    <>
      <Header
        title="Plant Overview"
        description="Real-time visibility into towel packing operations, productivity and performance."
      />

      <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
        <Grid container spacing={2}>
          {/* Row 1 — KPI cards */}
          {kpis.map((k) => (
            <Grid
              size={{ xs: 12, sm: 6, md: 4, lg: 2 }}
              key={k.label}
            >
              <KpiCard {...k} />
            </Grid>
          ))}

          {/* Row 2 — trend / distribution / live feed */}
          <Grid size={{ xs: 12, md: 6, lg: 5 }}>
            <OutputTrend />
          </Grid>

          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <TimeDistribution
              data={timeRows}
              centerValue={availableTime}
              centerLabel="Available Time"
            />
          </Grid>

          <Grid size={{ xs: 12, md: 12, lg: 4 }}>
            <LiveFeed />
          </Grid>

          {/* Row 3 — product / operators / loss */}
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <OutputByProduct />
          </Grid>

          <Grid size={{ xs: 12, md: 6, lg: 5 }}>
            <TopOperators />
          </Grid>

          <Grid size={{ xs: 12, md: 12, lg: 4 }}>
            <LossBreakdown />
          </Grid>

          {/* Row 4 — events / alerts */}
          <Grid size={{ xs: 12, lg: 7 }}>
            <RecentEvents />
          </Grid>

          <Grid size={{ xs: 12, lg: 5 }}>
            <AlertsNotifications />
          </Grid>
        </Grid>
      </Box>
    </>
  );
};

export default Overview;