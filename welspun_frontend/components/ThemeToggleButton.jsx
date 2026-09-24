// components/ThemeToggleButton.js
import React from 'react';
import { IconButton, useTheme } from '@mui/material';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import { useColorMode } from '../context/ColorModeContext';

export default function ThemeToggleButton() {
    const theme = useTheme();
    const { toggleColorMode } = useColorMode();

    return (
        <IconButton onClick={toggleColorMode} color="inherit">
            {theme.palette.mode === 'dark' ? <LightModeIcon fontSize='small' /> : <DarkModeIcon fontSize='small' />}
        </IconButton>
    );
}
     