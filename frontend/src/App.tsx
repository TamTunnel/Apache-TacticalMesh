// Copyright 2024 TacticalMesh Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Main App Component
 */

import React, { useState } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import {
    Box,
    AppBar,
    Toolbar,
    Typography,
    IconButton,
    Drawer,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Divider,
    Avatar,
    Menu,
    MenuItem,
    Chip,
    Tooltip,
    CircularProgress,
} from '@mui/material';
import {
    Menu as MenuIcon,
    Dashboard,
    Hub,
    Terminal,
    Settings,
    Logout,
    Person,
    HubOutlined,
} from '@mui/icons-material';
import { useAuth } from './context/AuthContext';
import LoginPage from './components/LoginPage';
import NodesTable from './components/NodesTable';
import CommandsPanel from './components/CommandsPanel';

const DRAWER_WIDTH = 260;

const App: React.FC = () => {
    const { isAuthenticated, isLoading, user, logout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [drawerOpen, setDrawerOpen] = useState(true);
    const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    const handleSendCommand = (nodeId: string) => {
        setSelectedNodeId(nodeId);
    };

    const handleCommandCreated = () => {
        setSelectedNodeId(undefined);
    };

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleMenuClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        handleMenuClose();
        logout();
        navigate('/login');
    };

    const menuItems = [
        { text: 'Dashboard', icon: <Dashboard />, path: '/' },
        { text: 'Nodes', icon: <Hub />, path: '/nodes' },
        { text: 'Commands', icon: <Terminal />, path: '/commands' },
        { text: 'Settings', icon: <Settings />, path: '/settings' },
    ];

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minHeight: '100vh',
                }}
            >
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return <LoginPage />;
    }

    const roleColors: Record<string, 'primary' | 'secondary' | 'default'> = {
        admin: 'primary',
        operator: 'secondary',
        observer: 'default',
    };

    return (
        <Box sx={{ display: 'flex', minHeight: '100vh' }}>
            {/* App Bar */}
            <AppBar
                position="fixed"
                sx={{
                    zIndex: (theme) => theme.zIndex.drawer + 1,
                    boxShadow: 'none',
                }}
            >
                <Toolbar>
                    <IconButton
                        color="inherit"
                        onClick={() => setDrawerOpen(!drawerOpen)}
                        edge="start"
                        sx={{ mr: 2 }}
                    >
                        <MenuIcon />
                    </IconButton>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <HubOutlined sx={{ color: '#10b981' }} />
                        <Typography variant="h6" fontWeight={600}>
                            TacticalMesh
                        </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                        Operations Console
                    </Typography>
                    <Box sx={{ flexGrow: 1 }} />
                    <Chip
                        label={user?.role || 'unknown'}
                        size="small"
                        color={roleColors[user?.role || 'observer']}
                        sx={{ mr: 2, textTransform: 'capitalize' }}
                    />
                    <Tooltip title="Account">
                        <IconButton onClick={handleMenuOpen} color="inherit">
                            <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
                                {user?.username?.charAt(0).toUpperCase() || 'U'}
                            </Avatar>
                        </IconButton>
                    </Tooltip>
                    <Menu
                        anchorEl={anchorEl}
                        open={Boolean(anchorEl)}
                        onClose={handleMenuClose}
                    >
                        <MenuItem disabled>
                            <ListItemIcon>
                                <Person />
                            </ListItemIcon>
                            <ListItemText primary={user?.username} secondary={user?.email} />
                        </MenuItem>
                        <Divider />
                        <MenuItem onClick={handleLogout}>
                            <ListItemIcon>
                                <Logout />
                            </ListItemIcon>
                            Logout
                        </MenuItem>
                    </Menu>
                </Toolbar>
            </AppBar>

            {/* Side Drawer */}
            <Drawer
                variant="persistent"
                open={drawerOpen}
                sx={{
                    width: drawerOpen ? DRAWER_WIDTH : 0,
                    flexShrink: 0,
                    '& .MuiDrawer-paper': {
                        width: DRAWER_WIDTH,
                        boxSizing: 'border-box',
                    },
                }}
            >
                <Toolbar />
                <Box sx={{ overflow: 'auto', p: 2 }}>
                    <List>
                        {menuItems.map((item) => (
                            <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
                                <ListItemButton
                                    onClick={() => navigate(item.path)}
                                    selected={location.pathname === item.path}
                                    sx={{
                                        borderRadius: 2,
                                        '&.Mui-selected': {
                                            bgcolor: 'rgba(59, 130, 246, 0.15)',
                                            '&:hover': {
                                                bgcolor: 'rgba(59, 130, 246, 0.2)',
                                            },
                                        },
                                    }}
                                >
                                    <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
                                    <ListItemText primary={item.text} />
                                </ListItemButton>
                            </ListItem>
                        ))}
                    </List>
                </Box>
            </Drawer>

            {/* Main Content */}
            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    p: 3,
                    mt: 8,
                    ml: drawerOpen ? 0 : `-${DRAWER_WIDTH}px`,
                    transition: 'margin 0.3s',
                }}
            >
                <Routes>
                    <Route
                        path="/"
                        element={
                            <Box>
                                <Typography variant="h4" fontWeight={600} gutterBottom>
                                    Dashboard
                                </Typography>
                                <Typography color="text.secondary" paragraph>
                                    Welcome to TacticalMesh Operations Console. Monitor your mesh network and manage edge nodes.
                                </Typography>
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                    <NodesTable onSendCommand={handleSendCommand} />
                                    <CommandsPanel selectedNodeId={selectedNodeId} onCommandCreated={handleCommandCreated} />
                                </Box>
                            </Box>
                        }
                    />
                    <Route
                        path="/nodes"
                        element={
                            <Box>
                                <Typography variant="h4" fontWeight={600} gutterBottom>
                                    Mesh Nodes
                                </Typography>
                                <NodesTable onSendCommand={handleSendCommand} />
                            </Box>
                        }
                    />
                    <Route
                        path="/commands"
                        element={
                            <Box>
                                <Typography variant="h4" fontWeight={600} gutterBottom>
                                    Commands
                                </Typography>
                                <CommandsPanel selectedNodeId={selectedNodeId} onCommandCreated={handleCommandCreated} />
                            </Box>
                        }
                    />
                    <Route
                        path="/settings"
                        element={
                            <Box>
                                <Typography variant="h4" fontWeight={600} gutterBottom>
                                    Settings
                                </Typography>
                                <Typography color="text.secondary">
                                    Settings panel coming soon.
                                </Typography>
                            </Box>
                        }
                    />
                    <Route path="/login" element={<Navigate to="/" replace />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </Box>
        </Box>
    );
};

export default App;
