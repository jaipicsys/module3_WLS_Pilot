import React, { useState, useEffect } from "react";
import {
    Toolbar,
    MenuItem,
    Menu,
    AppBar,
    Box,
    Card,
    Avatar,
    IconButton,
    Typography,
    FormControl,
    Select,
    Badge,
    TextField,
    InputAdornment,
} from "@mui/material";
import CalendarTodayIcon from "@mui/icons-material/CalendarToday";
import ArrowBackIosNewIcon from "@mui/icons-material/ArrowBackIosNew";
import NotificationsOutlinedIcon from "@mui/icons-material/NotificationsOutlined";
import { useDispatch, useSelector } from "react-redux";
import { logout } from "../../../store/authSlice";
import { useRouter } from "next/router";
import { logoutUser, fetchAlerts } from "../../../utils/api";
import { useTheme } from "@mui/material";

const bellShake = {
    "@keyframes bellShake": {
        "0%": { transform: "rotate(0)" },
        "15%": { transform: "rotate(-15deg)" },
        "30%": { transform: "rotate(10deg)" },
        "45%": { transform: "rotate(-10deg)" },
        "60%": { transform: "rotate(6deg)" },
        "75%": { transform: "rotate(-4deg)" },
        "100%": { transform: "rotate(0)" },
    },
};

/* "2024-11-14" -> "Nov 14, 2024" */
const formatDate = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
};

export default function Header({
    title,
    description,
    showBackButton = false,
}) {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === "dark";

    const router = useRouter();
    const dispatch = useDispatch();

    const [anchorEl, setAnchorEl] = React.useState(null);
    const [alertCount, setAlertCount] = useState(0);

    const [plant, setPlant] = useState("Unit 1 - Textile");
    const [line, setLine] = useState("All Lines");
    const [date, setDate] = useState("2026-09-21");
    const [shift, setShift] = useState("Day (6 AM - 2 PM)");

    const user = useSelector((state) => state.auth.user);

    /*
     * Fetch alerts count
     */
    useEffect(() => {
        let intervalId;

        const loadAlerts = async () => {
            try {
                const response = await fetchAlerts();
                setAlertCount(response.total);
            } catch (err) {
                console.error("Failed to fetch alerts:", err);
            }
        };

        loadAlerts();
        intervalId = setInterval(loadAlerts, 10000);

        return () => clearInterval(intervalId);
    }, []);

    const handleMenu = (event) => setAnchorEl(event.currentTarget);
    const handleClose = () => setAnchorEl(null);
    const handleBack = () => router.back();

    const handleLogout = async () => {
        try {
            sessionStorage.removeItem("filters");
            await logoutUser();
            dispatch(logout());
            router.push("/auth/login");
        } catch (err) {
            console.error("Logout Error:", err);
        }
    };

    const { asPath } = router;

    const isLine = title?.toLowerCase().startsWith("line");

    /*
     * Theme-aware colour tokens
     */
    const colors = {
        appBarBg: isDarkMode ? "#0e0e14" : "#f4f4f6",
        borderColor: isDarkMode ? "#2a2a3a" : "#e2e2ea",
        navInactive: isDarkMode ? "#9090a8" : "#6a6a80",
        fieldBg: isDarkMode ? "#181820" : "#ffffff",
        fieldBorder: isDarkMode ? "#2a2a3a" : "#d0d0dc",
        fieldText: isDarkMode ? "#d8d8e8" : "#2a2a3a",
        filterLabel: isDarkMode ? "#8888a0" : "#8a8a9c",
        titleColor: isDarkMode ? "#f0f0f8" : "#1a1a2e",
        descColor: isDarkMode ? "#9090a8" : "#6a6a80",
        userCardBg: isDarkMode ? "#1a1a2a" : "#ffffff",
        userCardBorder: isDarkMode ? "#2a2a3a" : "#e2e2ea",
        userCardHover: isDarkMode ? "#222234" : "#f0f0f4",
        avatarBg: isDarkMode ? "#3a3a4a" : "#016b51",
        userName: isDarkMode ? "#d8d8e8" : "#1a1a2e",
        role: isDarkMode ? "#9090a8" : "#6a6a80",
        menuBg: isDarkMode ? "#1a1a2a" : "#ffffff",
        menuText: isDarkMode ? "#d8d8e8" : "#1a1a2e",
        menuHover: isDarkMode ? "#2a2a3a" : "#f0f0f8",
        menuShadow: isDarkMode
            ? "0 4px 20px rgba(0,0,0,0.5)"
            : "0 4px 20px rgba(0,0,0,0.12)",
    };

    /* Shared styles for the labelled filter controls */
    const filterLabelSx = {
        position: "absolute",
        top: "-8px",
        left: "9px",
        px: "4px",
        bgcolor: colors.appBarBg,
        color: colors.filterLabel,
        border: "none",
        fontSize: "12px",
        lineHeight: 1,
        fontWeight: 800,
        zIndex: 1,
    };

    const fieldRootSx = {
        "& .MuiOutlinedInput-root": {
            height: 40,
            borderRadius: "8px",
            bgcolor: colors.fieldBg,
            fontSize: "13px",
            fontWeight: 600,
            color: colors.fieldText,
        },
        "& .MuiOutlinedInput-notchedOutline": {
            border: "none",
        },
        "& .MuiSelect-select": {
            py: 1,
            px: 1.25,
            fontSize: "13px",
            fontWeight: 600,
        },
    };

    const menuProps = {
        PaperProps: {
            sx: {
                bgcolor: colors.menuBg,
                color: colors.menuText,
                border: `1px solid ${colors.userCardBorder}`,
                boxShadow: colors.menuShadow,
                "& .MuiMenuItem-root": { fontSize: "13px" },
            },
        },
    };

    return (
        <>
            <AppBar
                position="sticky"
                color="inherit"
                variant="dense"
                elevation={0}
                sx={{
                    boxShadow: "none",
                    backdropFilter: "blur(6px)",
                    // borderBottom: `1px solid ${colors.borderColor}`,
                    transition: "background-color 0.2s, border-color 0.2s",
                }}
            >
                <Toolbar
                    sx={{
                        minHeight: "64px !important",
                        px: {
                            xs: "12px !important",
                            md: "20px !important",
                        },
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 2,
                        flexWrap: "wrap",
                        bgcolor: colors.appBarBg,
                    }}
                >
                    {/* LEFT — title + description */}
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            flexShrink: 0,
                        }}
                    >
                        {showBackButton && (
                            <IconButton
                                onClick={handleBack}
                                size="small"
                                sx={{ color: colors.navInactive }}
                            >
                                <ArrowBackIosNewIcon fontSize="small" />
                            </IconButton>
                        )}

                        <Box>
                            <Box
                                sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 1,
                                }}
                            >
                                <Typography
                                    variant="h6"
                                    sx={{
                                        fontWeight: "bold",
                                        lineHeight: 1.2,
                                        color: colors.titleColor,
                                    }}
                                >
                                    {title}
                                </Typography>

                                {isLine && (
                                    <Box
                                        sx={{
                                            width: 8,
                                            height: 8,
                                            borderRadius: "50%",
                                            bgcolor: "#4caf50",
                                            animation: "pulse 1.5s infinite",
                                        }}
                                    />
                                )}
                            </Box>

                            {description && (
                                <Typography
                                    sx={{
                                        fontSize: 12,
                                        color: colors.descColor,
                                        mt: "2px",
                                    }}
                                >
                                    {description}
                                </Typography>
                            )}
                        </Box>
                    </Box>

                    {/* RIGHT — filters + bell + user */}
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1.25,
                            flexWrap: "wrap",
                            mt:1
                        }}
                    >
                        {/* PLANT */}
                        <FormControl
                            size="small"
                            disabled
                            sx={{ width: 150, ...fieldRootSx }}
                        >
                            <Typography sx={filterLabelSx}>Plant</Typography>
                            <Select
                                value={plant}
                                onChange={(e) => setPlant(e.target.value)}
                                MenuProps={menuProps}
                            >
                                <MenuItem value="Unit 1 - Textile">
                                    Unit 1 - Textile
                                </MenuItem>
                            </Select>
                        </FormControl>

                        {/* LINE */}
                        <FormControl
                            size="small"
                            disabled
                            sx={{ width: 130, ...fieldRootSx }}
                        >
                            <Typography sx={filterLabelSx}>Line</Typography>
                            <Select
                                value={line}
                                onChange={(e) => setLine(e.target.value)}
                                MenuProps={menuProps}
                            >
                                <MenuItem value="All Lines">All Lines</MenuItem>
                            </Select>
                        </FormControl>

                        {/* DATE */}
                        <Box sx={{ position: "relative", width: 150 }}>
                            <Typography sx={filterLabelSx}>Date</Typography>
                            <TextField
                                value={formatDate(date)}
                                size="small"
                                fullWidth
                                disabled
                                InputProps={{
                                    readOnly: true,
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <CalendarTodayIcon
                                                sx={{
                                                    fontSize: 16,
                                                    color: colors.navInactive,
                                                }}
                                            />
                                        </InputAdornment>
                                    ),
                                }}
                                sx={{
                                    "& .MuiOutlinedInput-root": {
                                        height: 40,
                                        borderRadius: "8px",
                                        bgcolor: colors.fieldBg,
                                    },
                                    "& .MuiOutlinedInput-notchedOutline": {
                                        border: "none",
                                    },
                                    "& input": {
                                        fontSize: "13px",
                                        fontWeight: 600,
                                        color: colors.fieldText,
                                        py: 1,
                                        px: 1.25,
                                    },
                                }}
                            />
                        </Box>

                        {/* SHIFT */}
                        <FormControl
                            size="small"
                            disabled
                            sx={{ width: 180, ...fieldRootSx }}
                        >
                            <Typography sx={filterLabelSx}>Shift</Typography>
                            <Select
                                value={shift}
                                onChange={(e) => setShift(e.target.value)}
                                MenuProps={menuProps}
                            >
                                <MenuItem value="Day (6 AM - 2 PM)">
                                    Day (6 AM - 2 PM)
                                </MenuItem>
                                <MenuItem value="Evening (2 PM - 10 PM)">
                                    Evening (2 PM - 10 PM)
                                </MenuItem>
                                <MenuItem value="Night (10 PM - 6 AM)">
                                    Night (10 PM - 6 AM)
                                </MenuItem>
                            </Select>
                        </FormControl>

                        {/* ALERT BELL */}
                        {asPath !== "/alerts" && (
                            <Box sx={bellShake}>
                                <IconButton
                                    size="small"
                                    onClick={() => router.push("/alerts")}
                                    sx={{
                                        width: 36,
                                        height: 36,
                                        borderRadius: "8px",
                                        backgroundColor: "transparent",
                                        transition: "background-color 0.15s",
                                        "&:hover": {
                                            backgroundColor: colors.userCardHover,
                                        },
                                    }}
                                >
                                    <Badge
                                        badgeContent={alertCount}
                                        color="error"
                                        max={99}
                                        invisible={alertCount === 0}
                                        overlap="circular"
                                        anchorOrigin={{
                                            vertical: "top",
                                            horizontal: "right",
                                        }}
                                        sx={{
                                            "& .MuiBadge-badge": {
                                                fontSize: "0.6rem",
                                                height: 16,
                                                minWidth: 16,
                                                padding: "0 4px",
                                            },
                                        }}
                                    >
                                        <NotificationsOutlinedIcon
                                            sx={{
                                                color:
                                                    alertCount > 0
                                                        ? "#d12727ff"
                                                        : colors.navInactive,
                                                fontSize: 24,
                                                animation:
                                                    alertCount > 0
                                                        ? "bellShake 1s ease infinite"
                                                        : "none",
                                                animationDelay:
                                                    alertCount > 0 ? "2s" : "0s",
                                            }}
                                        />
                                    </Badge>
                                </IconButton>
                            </Box>
                        )}

                        {/* USER CARD */}
                        <Card
                            variant="outlined"
                            onClick={handleMenu}
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                cursor: "pointer",
                                height: 44,
                                px: 1,
                                gap: 1,
                                borderRadius: "10px",
                                bgcolor: colors.userCardBg,
                                border: `1px solid ${colors.userCardBorder}`,
                                boxShadow: "none",
                                transition:
                                    "background-color 0.15s, border-color 0.15s",
                                "&:hover": { bgcolor: colors.userCardHover },
                            }}
                        >
                            {/* Avatar with initials */}
                            <Avatar
                                sx={{
                                    width: 30,
                                    height: 30,
                                    flexShrink: 0,
                                    bgcolor: colors.avatarBg,
                                    color: "#ffffff",
                                    fontSize: "12px",
                                    fontWeight: 700,
                                }}
                            >
                                {user?.name
                                    ? user.name
                                          .split(" ")
                                          .map((n) => n[0])
                                          .join("")
                                          .slice(0, 2)
                                          .toUpperCase()
                                    : "SK"}
                            </Avatar>

                            {/* Name + role */}
                            <Box
                                sx={{
                                    minWidth: 0,
                                    display: "flex",
                                    flexDirection: "column",
                                    justifyContent: "center",
                                    lineHeight: 1,
                                }}
                            >
                                <Typography
                                    sx={{
                                        fontSize: "12px",
                                        fontWeight: 700,
                                        color: colors.userName,
                                        lineHeight: "15px",
                                        whiteSpace: "nowrap",
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                    }}
                                >
                                    {user?.name || "Admin"}
                                </Typography>

                                <Typography
                                    sx={{
                                        mt: "1px",
                                        fontSize: "11px",
                                        fontWeight: 500,
                                        color: colors.role,
                                        lineHeight: "13px",
                                        whiteSpace: "nowrap",
                                    }}
                                >
                                    {user?.role || "Plant Manager"}
                                </Typography>
                            </Box>
                        </Card>

                        {/* USER MENU */}
                        <Menu
                            id="menu-appbar"
                            anchorEl={anchorEl}
                            anchorOrigin={{
                                vertical: "bottom",
                                horizontal: "right",
                            }}
                            keepMounted
                            transformOrigin={{
                                vertical: "top",
                                horizontal: "right",
                            }}
                            open={Boolean(anchorEl)}
                            onClose={handleClose}
                            PaperProps={{
                                sx: {
                                    mt: 0.5,
                                    minWidth: 140,
                                    bgcolor: colors.menuBg,
                                    border: `1px solid ${colors.userCardBorder}`,
                                    boxShadow: colors.menuShadow,
                                    borderRadius: "8px",
                                },
                            }}
                        >
                            <MenuItem
                                onClick={handleLogout}
                                sx={{
                                    fontSize: "13px",
                                    fontWeight: 400,
                                    color: colors.menuText,
                                    "&:hover": { bgcolor: colors.menuHover },
                                }}
                            >
                                Logout
                            </MenuItem>
                        </Menu>
                    </Box>
                </Toolbar>
            </AppBar>
        </>
    );
}