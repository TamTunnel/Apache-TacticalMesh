// Copyright 2024 TacticalMesh Contributors
// SPDX-License-Identifier: Apache-2.0

import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#3b82f6',
            light: '#60a5fa',
            dark: '#2563eb',
        },
        secondary: {
            main: '#10b981',
            light: '#34d399',
            dark: '#059669',
        },
        error: {
            main: '#ef4444',
            light: '#f87171',
            dark: '#dc2626',
        },
        warning: {
            main: '#f59e0b',
            light: '#fbbf24',
            dark: '#d97706',
        },
        success: {
            main: '#10b981',
            light: '#34d399',
            dark: '#059669',
        },
        background: {
            default: '#0a1628',
            paper: '#1a2332',
        },
        text: {
            primary: '#f1f5f9',
            secondary: '#94a3b8',
        },
        divider: 'rgba(255, 255, 255, 0.1)',
    },
    typography: {
        fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        h1: {
            fontSize: '2.5rem',
            fontWeight: 700,
        },
        h2: {
            fontSize: '2rem',
            fontWeight: 600,
        },
        h3: {
            fontSize: '1.5rem',
            fontWeight: 600,
        },
        h4: {
            fontSize: '1.25rem',
            fontWeight: 600,
        },
        h5: {
            fontSize: '1rem',
            fontWeight: 600,
        },
        h6: {
            fontSize: '0.875rem',
            fontWeight: 600,
        },
    },
    shape: {
        borderRadius: 8,
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    textTransform: 'none',
                    fontWeight: 500,
                },
            },
        },
        MuiCard: {
            styleOverrides: {
                root: {
                    backgroundImage: 'none',
                    backgroundColor: 'rgba(26, 35, 50, 0.8)',
                    backdropFilter: 'blur(10px)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                },
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    backgroundImage: 'none',
                },
            },
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    backgroundImage: 'none',
                    backgroundColor: 'rgba(10, 22, 40, 0.9)',
                    backdropFilter: 'blur(10px)',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                },
            },
        },
        MuiDrawer: {
            styleOverrides: {
                paper: {
                    backgroundColor: '#0f1a2b',
                    borderRight: '1px solid rgba(255, 255, 255, 0.1)',
                },
            },
        },
        MuiTableCell: {
            styleOverrides: {
                root: {
                    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                },
            },
        },
        MuiChip: {
            styleOverrides: {
                root: {
                    fontWeight: 500,
                },
            },
        },
    },
});
