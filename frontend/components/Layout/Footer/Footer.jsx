import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';

export default function Footer() {
    // Get the current theme
    const theme = useTheme();
    
    // Define background and text colors based on the current theme
    const footerBackgroundColor = theme.palette.mode === 'dark' ? '#222' : '#f2f2f2';
    const footerTextColor = theme.palette.mode === 'dark' ? '#fff' : '#000';

    return (
        <Box sx={{
            color: footerTextColor,
            padding: '1px',
            textAlign: 'center',
            position: 'relative',
            pl:2,
            bottom: 0,
            // width: '100%',
            marginTop: 'auto',
        }}>
            <Typography variant="body2" color="textDisabled">
                Powered by Nexilis Edge AI | On-Device | Privacy-First | Model v3.1
            </Typography>
        </Box>
    );
}
