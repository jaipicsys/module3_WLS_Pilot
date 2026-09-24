import React from "react";
import { Box, Grid } from "@mui/material";
import PeopleAltOutlined from "@mui/icons-material/PeopleAltOutlined";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import GpsFixed from "@mui/icons-material/GpsFixed";
import InsightsOutlined from "@mui/icons-material/InsightsOutlined";
import EmojiEventsOutlined from "@mui/icons-material/EmojiEventsOutlined";
import WarningAmberOutlined from "@mui/icons-material/WarningAmberOutlined";

import Header from "../../Layout/Header/Header";
import KpiCard from "./Kpicard/Kpicard";
import OperatorPerformanceTable from "./Operatorperformancetable/Operatorperformancetable";
import LiveFeed from "./Livefeed/Livefeed";
import CurrentActivity from "./Currentactivity/Currentactivity";
import OperatorEfficiencyComparison from "./Operatorefficiencycomparison/Operatorefficiencycomparison";
import TimeDistribution from "./Timedistribution/Timedistribution";
import OutputByOperator from "./Outputbyoperator/Outputbyoperator";

const GREEN = "#12b76a";
const RED = "#ef4444";

const utilData = [
    { label: "Productive", value: 78, amount: "6h 12m", pct: 78, color: "#12b76a" },
    { label: "Idle / Waiting", value: 16, amount: "1h 18m", pct: 16, color: "#f59e0b" },
    { label: "Changeover", value: 4, amount: "18m", pct: 4, color: "#ef4444" },
    { label: "Break", value: 2, amount: "12m", pct: 2, color: "#9ca3af" },
];

const Operators = () => {
    const kpis = [
        {
            label: "Total Operators",
            value: "24",
            sub: (
                <>
                    <Box component="span" sx={{ color: GREEN, fontWeight: 600 }}>
                        20 Active
                    </Box>{" "}
                    &nbsp;|&nbsp; 4 Inactive
                </>
            ),
            icon: <PeopleAltOutlined />,
        },
        {
            label: "Total Output",
            value: "1,248",
            delta: "12%",
            trend: "up",
            sub: "vs. previous shift",
            icon: <Inventory2Outlined />,
        },
        {
            label: "Avg. Operator Efficiency",
            value: "88%",
            delta: "6%",
            trend: "up",
            sub: "vs. previous shift",
            icon: <GpsFixed />,
        },
        {
            label: "Avg. Utilization",
            value: "82%",
            delta: "5%",
            trend: "up",
            sub: "of shift time",
            icon: <InsightsOutlined />,
        },
        {
            label: "Top Performer",
            value: "OP-104",
            delta: "94% efficiency",
            trend: null,
            deltaColor: GREEN,
            icon: <EmojiEventsOutlined />,
            iconColor: "#e0a410",
        },
        {
            label: "Needs Attention",
            value: "OP-132",
            delta: "62% efficiency",
            trend: null,
            deltaColor: RED,
            icon: <WarningAmberOutlined />,
            iconColor: RED,
        },
    ];

    return (
        <>
            <Header
                title="Operators Performance"
                description="Track Operator Productivity, output and adherence across packing lines"
            />

            <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
                <Grid container spacing={2}>
                    {/* Row 1 — KPI cards */}
                    {kpis.map((k) => (
                        <Grid size={{xs:12, sm:6, md:4, lg:2}} key={k.label}>
                            <KpiCard {...k} />
                        </Grid>
                    ))}

                    {/* Row 2 — table (left) + live feed & current activity (right) */}
                    <Grid size={{ xs: 12, lg: 8 }} >
                        <OperatorPerformanceTable />
                    </Grid>
                    <Grid size={{ xs: 12, lg: 4 }}>
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                            <LiveFeed
                                title="Live Feed – Line 1 (Packing)"
                                caption="Line 1 – Packing Station 1"
                                timestamp="Nov 14, 2024   11:32:18"
                                height={260}
                            />
                            <CurrentActivity />
                        </Box>
                    </Grid>

                    {/* Row 3 — efficiency comparison / utilization / output */}
                    <Grid size={{ xs: 12, md: 6, lg: 4 }}>
                        <OperatorEfficiencyComparison />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6, lg: 4 }} >
                        <TimeDistribution
                            title="Operator Utilization (Shift)"
                            data={utilData}
                            centerValue="82%"
                            centerLabel="Avg. Utilization"
                        />
                    </Grid>
                    <Grid size={{ xs: 12, md: 12, lg: 4 }}>
                        <OutputByOperator />
                    </Grid>
                </Grid>
            </Box>
        </>
    );
};

export default Operators;