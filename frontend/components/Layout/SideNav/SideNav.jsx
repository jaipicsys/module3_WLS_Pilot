import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import {
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Box,
    IconButton,
    Typography,
    Button,
    TextField,
    MenuItem,
    Collapse
} from "@mui/material";

import MenuIcon from "@mui/icons-material/Menu";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import GridViewOutlinedIcon from "@mui/icons-material/GridViewOutlined";
import AssignmentOutlinedIcon from "@mui/icons-material/AssignmentOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ChecklistRtlIcon from '@mui/icons-material/ChecklistRtl';
import NotificationsOutlinedIcon from "@mui/icons-material/NotificationsOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import { GiPlatform } from "react-icons/gi";
import Person2OutlinedIcon from '@mui/icons-material/Person2Outlined';
import { useTheme } from "@mui/material/styles";
import Image from "next/image";
import PrecisionManufacturingIcon from '@mui/icons-material/PrecisionManufacturing';
import { useDispatch } from "react-redux";
import { logout } from "../../../store/authSlice";
import { logoutUser, fetchAlerts } from "../../../utils/api";
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';

const navSections = [
    {
        label: "",
        items: [
            {
                id: 1,
                title: "Overview",
                route: "/overview",
                icon: <GridViewOutlinedIcon />,
            },
            {
                id: 2,
                title: "Operators",
                route: "/operator",
                icon: <Person2OutlinedIcon />,
            },
            {
                id: 3,
                title: "Stations/Lines",
                route: "/stations",
                icon: <GiPlatform fontSize={26} />,
            },
            {
                id: 4,
                title: "Production",
                route: "/production",
                icon: <PrecisionManufacturingIcon />,
            },
            {
                id: 5,
                title: "Loss Analysis",
                route: "/loss-analysis",
                icon: <TrendingDownIcon />,
            },
            {
                id: 6,
                title: "SOP Compliance",
                route: "/sop",
                icon: <ChecklistRtlIcon />,
            },
            {
                id: 7,
                title: "Reports",
                route: "/reports",
                icon: <FileDownloadOutlinedIcon />,
            },
            {
                id: 13,
                title: "Settings",
                route: "/settings",
                icon: <SettingsOutlinedIcon />,
            }
        ],
    },
];

export default function SideNav() {
    const theme = useTheme();
    const { asPath } = useRouter();

    const [open, setOpen] = useState(false);
    const [alertCount, setAlertCount] = useState(0);
    // Labeled sections are minimized by default; user expands as needed
    const [openSections, setOpenSections] = useState({});

    const toggleSection = (label) => {
        setOpenSections((prev) => ({
            ...prev,
            [label]: !prev[label],
        }));
    };

    const isDarkMode = theme.palette.mode === "dark";

    const dispatch = useDispatch();

    const colors = {
        borderColor: "#fff",
    };

    // useEffect(() => {
    //     let intervalId;

    //     const loadAlerts = async () => {
    //         try {
    //             const response = await fetchAlerts();
    //             setAlertCount(response.total || 0);
    //         } catch (err) {
    //             console.error("Failed to fetch alerts:", err);
    //         }
    //     };

    //     loadAlerts();

    //     intervalId = setInterval(loadAlerts, 10000);

    //     return () => clearInterval(intervalId);
    // }, []);

    const handleLogout = async () => {
        try {
            sessionStorage.removeItem("filters");

            await logoutUser();

            dispatch(logout());

            window.location.href = "/auth/login";
        } catch (err) {
            console.error("Logout Error:", err);
        }
    };

    // Logout lives with Settings but isn't a route — it fires handleLogout directly
    const logoutItem = {
        id: 14,
        title: "Logout",
        icon: <LogoutOutlinedIcon color="error" />,
        onClick: handleLogout,
    };

    const renderNavItem = (item) => {
        const isActive = item.route ? asPath.startsWith(item.route) : false;

        const navItem = (
            <ListItem
                sx={{
                    borderRadius: "5px",
                    mb: 1,
                    cursor: "pointer",

                    backgroundColor: isActive
                        ? isDarkMode
                            ? "#252545"
                            : "#00886a"
                        : "transparent",

                    "&:hover": {
                        backgroundColor: isDarkMode && "#000",
                    },
                }}
            >
                <ListItemIcon
                    sx={{
                        minWidth: 32,
                        color: "#fff"
                    }}
                >
                    {item.icon}
                </ListItemIcon>

                <ListItemText
                    primary={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                // width: "100%",
                            }}
                        >
                            <Typography
                                fontSize={16}
                                fontWeight={500}
                                color={"#fff"}
                            >
                                {item.title}
                            </Typography>

                            {/* ALERT COUNT */}
                            {item.title === "Alerts" && alertCount > 0 && (
                                <Box
                                    sx={{
                                        minWidth: 35,
                                        height: 20,
                                        // px: 0.6,
                                        // ml: 1,
                                        borderRadius: "10px",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        backgroundColor: "#d32f2f",
                                        color: "#fff",
                                        fontSize: "14px",
                                        fontWeight: 700,
                                        lineHeight: 1,
                                    }}
                                >
                                    {alertCount > 99 ? "99+" : alertCount}
                                </Box>
                            )}
                        </Box>
                    }
                />
            </ListItem>
        );

        // Items with an onClick (e.g. Logout) fire the handler directly, no route
        if (item.onClick) {
            return (
                <Box key={item.id} onClick={item.onClick}>
                    {navItem}
                </Box>
            );
        }

        // Everything else, including Settings, is a normal clickable link
        return (
            <Link
                key={item.id}
                href={item.route}
                style={{
                    textDecoration: "none",
                    display: "block",
                }}
            >
                {navItem}
            </Link>
        );
    };

    const renderNavItems = () => (
        <Box>
            {/* Sections */}
            {navSections.map((section, i) => {
                const isOpen = !!openSections[section.label];

                return (
                    <Box key={i} sx={{ mb: 2, p: 1 }}>
                        {section.label && (
                            <Box
                                onClick={() => toggleSection(section.label)}
                                sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    px: 1,
                                    mb: 1,
                                    cursor: "pointer",
                                    userSelect: "none",
                                }}
                            >
                                <Typography
                                    sx={{
                                        fontSize: 11,
                                        fontWeight: 900,
                                        letterSpacing: 0.5,
                                        color: " #fff",
                                    }}
                                >
                                    {section.label}
                                </Typography>

                                <KeyboardArrowDownIcon
                                    sx={{
                                        fontSize: 18,
                                        color: "#fff",
                                        transform: isOpen
                                            ? "rotate(0deg)"
                                            : "rotate(-90deg)",
                                        transition: "transform 0.2s ease",
                                    }}
                                />
                            </Box>
                        )}

                        <Collapse
                            in={!section.label || isOpen}
                            timeout="auto"
                            unmountOnExit
                        >
                            <List disablePadding>
                                {section.items.map((item) => renderNavItem(item))}
                            </List>
                        </Collapse>
                    </Box>
                );
            })}

            {/* Settings + Logout — separate section, scrolls with the rest */}
            <Box sx={{ mt: 4, p: 1 }}>
                <List disablePadding>
                    {renderNavItem(logoutItem)}
                </List>
            </Box>
        </Box>
    );

    return (
        <>
            {/* Mobile Menu Button */}
            <Box
                sx={{
                    display: {
                        xs: "flex",
                        md: "none",
                    },
                    position: "absolute",
                    top: 10,
                    left: 10,
                    zIndex: 1301,
                }}
            >
                <IconButton
                    onClick={() => setOpen(true)}
                    sx={{
                        color: theme.palette.text.primary,
                    }}
                >
                    <MenuIcon />
                </IconButton>
            </Box>

            {/* Desktop Sidebar */}
            <Box
                sx={{
                    display: {
                        xs: "none",
                        md: "flex",
                    },
                    height: "100vh",
                    borderRight: `1px solid ${colors.borderColor}`,
                    flexDirection: "column",
                    backgroundColor: "#001f25",
                }}
            >
                {/* Fixed Logo */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        // p: 1.5,
                        flexShrink: 0,
                    }}
                >
                    <Image
                        src="/logo.svg"
                        alt="EigenstateAI"
                        width={240}
                        height={100}

                        style={{
                            objectFit: "contain",
                        }}
                    />
                </Box>

                {/* Scrollable Navigation */}
                <Box
                    sx={{
                        flex: 1,
                        minHeight: 0,
                        overflowY: "auto",
                        scrollbarWidth: "none",
                        "&::-webkit-scrollbar": {
                            display: "none",
                        },
                    }}
                >
                    {renderNavItems()}
                </Box>
            </Box>
        </>
    );
}