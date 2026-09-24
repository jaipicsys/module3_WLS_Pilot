// lib/theme.js
export const getDesignTokens = (mode) => ({
    palette: {
        mode,
        ...(mode === 'light'
            ? {
                primary: { main: '#1976d2' },
                background: { default: '#fff', paper: '#fff' },
            }
            : {
                primary: { main: '#90caf9' },
                background: { default: '#121212', paper: '#1e1e1e' },
            }),
    },
});
