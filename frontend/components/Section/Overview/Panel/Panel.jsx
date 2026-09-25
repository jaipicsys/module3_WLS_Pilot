import React from "react";
import { Box, Card, Typography, Link } from "@mui/material";
import useDashboardColors from "../Tokens/Tokens";

/*
 * The white rounded card used by every panel.
 *
 * Props:
 *   title         panel heading
 *   action        text for the top-right link (e.g. "View All"); omit to hide
 *   onActionClick handler for the action link
 *   headerRight   custom node rendered top-right instead of `action`
 *   sx / bodySx   style overrides for the card / body
 */
export default function Panel({
    title,
    action,
    onActionClick,
    headerRight,
    children,
    sx,
    bodySx,
}) {
    const c = useDashboardColors();

    return (
        <Card
            variant="outlined"
            sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                borderRadius: "14px",
                bgcolor: c.cardBg,
                border: `1px solid ${c.cardBorder}`,
                boxShadow: "none",
                p: 2,
                ...sx,
            }}
        >
            {(title || action || headerRight) && (
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        mb: 1.5,
                    }}
                >
                    {title && (
                        <Typography
                            sx={{ fontSize: 15, fontWeight: 700, color: c.title }}
                        >
                            {title}
                        </Typography>
                    )}

                    {/* {headerRight
                        ? headerRight
                        : action && (
                              <Link
                                  component="button"
                                  type="button"
                                  onClick={onActionClick}
                                  underline="none"
                                  sx={{
                                      fontSize: 12,
                                      fontWeight: 600,
                                      color: c.accent,
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: 0.4,
                                  }}
                              >
                                  {action} →
                              </Link>
                          )} */}
                </Box>
            )}

            <Box sx={{ flex: 1, minHeight: 0, ...bodySx }}>{children}</Box>
        </Card>
    );
}