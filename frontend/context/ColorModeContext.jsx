// context/ColorModeContext.js
import React, { createContext, useContext, useMemo, useState, useEffect } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { getDesignTokens } from '../lib/theme';

const ColorModeContext = createContext();

export const useColorMode = () => useContext(ColorModeContext);

export const ColorModeProvider = ({ children }) => {
    const [mode, setMode] = useState('light');

    // Load from localStorage
    useEffect(() => {
        const storedMode = localStorage.getItem('theme');
        if (storedMode) setMode(storedMode);
    }, []);

    const toggleColorMode = () => {
        setMode((prevMode) => {
            const nextMode = prevMode === 'light' ? 'dark' : 'light';
            localStorage.setItem('theme', nextMode);
            return nextMode;
        });
    };

    const theme = useMemo(() => createTheme(getDesignTokens(mode)), [mode]);

    return (
        <ColorModeContext.Provider value={{ mode, toggleColorMode }}>
            <ThemeProvider theme={theme}>
                <CssBaseline />
                {children}
            </ThemeProvider>
        </ColorModeContext.Provider>
    );
};
