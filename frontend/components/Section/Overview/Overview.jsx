import React from "react";
import { Box, Grid } from "@mui/material";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import TrendingUpOutlined from "@mui/icons-material/TrendingUpOutlined";
import AccessTimeOutlined from "@mui/icons-material/AccessTimeOutlined";
import PauseCircleOutlineOutlined from "@mui/icons-material/PauseCircleOutlineOutlined";
import GpsFixedOutlined from "@mui/icons-material/GpsFixed";
import AssignmentOutlined from "@mui/icons-material/AssignmentOutlined";
import ChecklistRtlIcon from '@mui/icons-material/ChecklistRtl';
import Header from "../../Layout/Header/Header";
import KpiCard from "./Kpicard/Kpicard";
import OutputTrend from "./Outputtrend/Outputtrend";
import TimeDistribution from "./Timedistribution/Timedistribution";
import LiveFeed from "./Livefeed/Livefeed";
import OutputByProduct from "./Outputbyproduct/Outputbyproduct";
import TopOperators from "./Topoperators/Topoperators";
import LossBreakdown from "./Lossbreakdown/Lossbreakdown";
import RecentEvents from "./Recentevents/Recentevents";
import AlertsNotifications from "./Alertsnotifications/Alertsnotifications";
import { TbPackageExport } from "react-icons/tb";

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
        label: "Output / Hour",
        value: "156",
        delta: "8%",
        trend: "up",
        sub: "units/hour",
        icon: <TbPackageExport fontSize={24} />,
    },
    {
        label: "Productive Time",
        value: "6h 12m",
        delta: "78%",
        trend: null,
        sub: "of available time",
        icon: <AccessTimeOutlined />,
    },
    {
        label: "Idle / Waiting Time",
        value: "1h 18m",
        delta: "16%",
        trend: null,
        sub: "of available time",
        icon: <PauseCircleOutlineOutlined />,
    },
    {
        label: "Efficiency",
        value: "88%",
        delta: "6%",
        trend: "up",
        sub: "vs. previous shift",
        icon: <GpsFixedOutlined />,
    },
    {
        label: "SOP Adherence",
        value: "92%",
        delta: "4%",
        trend: "up",
        sub: "of observed cycles",
        icon: <ChecklistRtlIcon />,
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
                    {kpis.map((k) => (
                        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }} key={k.label}>
                            <KpiCard {...k} />
                        </Grid>
                    ))}

                    {/* Row 2 — trend / distribution / live feed */}
                    <Grid size={{ xs: 12, md: 6, lg: 5 }}>
                        <OutputTrend />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6, lg: 3 }} >
                        <TimeDistribution />
                    </Grid>
                    <Grid size={{ xs: 12, md: 12, lg: 4 }}>
                        <LiveFeed />
                    </Grid>

                    {/* Row 3 — product / operators / loss */}
                    <Grid size={{ xs: 12, md: 6, lg: 3 }} >
                        <OutputByProduct />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6, lg: 5 }}>
                        <TopOperators />
                    </Grid>
                    <Grid size={{ xs: 12, md: 12, lg: 4 }} >
                        <LossBreakdown />
                    </Grid>

                    {/* Row 4 — events / alerts */}
                    <Grid size={{ xs: 12, lg: 7 }} >
                        <RecentEvents />
                    </Grid>
                    <Grid size={{ xs: 12, lg: 5 }} >
                        <AlertsNotifications />
                    </Grid>
                </Grid>
            </Box>
        </>
    );
};

export default Overview;