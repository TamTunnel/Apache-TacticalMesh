// Copyright 2024 TacticalMesh Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Commands Panel Component
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Chip,
    IconButton,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    CircularProgress,
    Tooltip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TablePagination,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Alert,
} from '@mui/material';
import {
    Refresh,
    Add,
    Cancel,
    CheckCircle,
    Error,
    HourglassEmpty,
    Send,
} from '@mui/icons-material';
import { apiClient, Command, CommandListResponse, CommandCreate } from '../api/client';

interface CommandsPanelProps {
    selectedNodeId?: string;
    onCommandCreated?: () => void;
}

const statusIcons: Record<string, React.ReactNode> = {
    pending: <HourglassEmpty color="warning" />,
    sent: <Send color="info" />,
    acknowledged: <CheckCircle color="info" />,
    executing: <CircularProgress size={16} />,
    completed: <CheckCircle color="success" />,
    failed: <Error color="error" />,
    timeout: <Error color="warning" />,
};

const statusColors: Record<string, 'success' | 'error' | 'warning' | 'info' | 'default'> = {
    pending: 'warning',
    sent: 'info',
    acknowledged: 'info',
    executing: 'info',
    completed: 'success',
    failed: 'error',
    timeout: 'warning',
};

const CommandsPanel: React.FC<CommandsPanelProps> = ({ selectedNodeId, onCommandCreated }) => {
    const [commands, setCommands] = useState<Command[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('');

    // Create command dialog state
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [newCommand, setNewCommand] = useState<CommandCreate>({
        target_node_id: selectedNodeId || '',
        command_type: 'ping',
        payload: {},
    });
    const [createError, setCreateError] = useState<string | null>(null);
    const [creating, setCreating] = useState(false);

    const fetchCommands = useCallback(async () => {
        setLoading(true);
        try {
            const response: CommandListResponse = await apiClient.getCommands({
                page: page + 1,
                page_size: rowsPerPage,
                status_filter: statusFilter || undefined,
                target_node_id: selectedNodeId || undefined,
            });
            setCommands(response.commands);
            setTotal(response.total);
        } catch (error) {
            console.error('Failed to fetch commands:', error);
        } finally {
            setLoading(false);
        }
    }, [page, rowsPerPage, statusFilter, selectedNodeId]);

    useEffect(() => {
        fetchCommands();
        // Auto-refresh every 10 seconds
        const interval = setInterval(fetchCommands, 10000);
        return () => clearInterval(interval);
    }, [fetchCommands]);

    useEffect(() => {
        if (selectedNodeId) {
            setNewCommand(prev => ({ ...prev, target_node_id: selectedNodeId }));
            setCreateDialogOpen(true);
        }
    }, [selectedNodeId]);

    const handlePageChange = (_: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    const handleCreateCommand = async () => {
        setCreating(true);
        setCreateError(null);
        try {
            await apiClient.createCommand(newCommand);
            setCreateDialogOpen(false);
            fetchCommands();
            onCommandCreated?.();
            setNewCommand({ target_node_id: '', command_type: 'ping', payload: {} });
        } catch (error: unknown) {
            const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create command';
            setCreateError(errorMessage);
        } finally {
            setCreating(false);
        }
    };

    const handleCancelCommand = async (commandId: string) => {
        try {
            await apiClient.cancelCommand(commandId);
            fetchCommands();
        } catch (error) {
            console.error('Failed to cancel command:', error);
        }
    };

    const formatTime = (timestamp: string | null) => {
        if (!timestamp) return '-';
        return new Date(timestamp).toLocaleString();
    };

    return (
        <>
            <Card>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                        <Typography variant="h5" fontWeight={600}>
                            Commands
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                                variant="contained"
                                startIcon={<Add />}
                                onClick={() => setCreateDialogOpen(true)}
                                size="small"
                            >
                                New Command
                            </Button>
                            <Tooltip title="Refresh">
                                <IconButton onClick={fetchCommands} size="small">
                                    <Refresh />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Box>

                    {/* Filters */}
                    <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                        <FormControl size="small" sx={{ minWidth: 150 }}>
                            <InputLabel>Status</InputLabel>
                            <Select
                                value={statusFilter}
                                label="Status"
                                onChange={(e) => setStatusFilter(e.target.value)}
                            >
                                <MenuItem value="">All</MenuItem>
                                <MenuItem value="pending">Pending</MenuItem>
                                <MenuItem value="sent">Sent</MenuItem>
                                <MenuItem value="completed">Completed</MenuItem>
                                <MenuItem value="failed">Failed</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Table */}
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Status</TableCell>
                                    <TableCell>Command Type</TableCell>
                                    <TableCell>Target Node</TableCell>
                                    <TableCell>Created</TableCell>
                                    <TableCell>Completed</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {loading ? (
                                    <TableRow>
                                        <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                                            <CircularProgress size={32} />
                                        </TableCell>
                                    </TableRow>
                                ) : commands.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                                            <Typography color="text.secondary">No commands found</Typography>
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    commands.map((command) => (
                                        <TableRow key={command.id} hover>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    {statusIcons[command.status]}
                                                    <Chip
                                                        label={command.status}
                                                        size="small"
                                                        color={statusColors[command.status]}
                                                        sx={{ textTransform: 'capitalize' }}
                                                    />
                                                </Box>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={command.command_type.replace('_', ' ')}
                                                    size="small"
                                                    variant="outlined"
                                                    sx={{ textTransform: 'capitalize' }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2" fontFamily="monospace">
                                                    {command.target_node_id.slice(0, 8)}...
                                                </Typography>
                                            </TableCell>
                                            <TableCell>{formatTime(command.created_at)}</TableCell>
                                            <TableCell>{formatTime(command.completed_at)}</TableCell>
                                            <TableCell align="right">
                                                {command.status === 'pending' && (
                                                    <Tooltip title="Cancel">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleCancelCommand(command.id)}
                                                        >
                                                            <Cancel fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>

                    {/* Pagination */}
                    <TablePagination
                        component="div"
                        count={total}
                        page={page}
                        onPageChange={handlePageChange}
                        rowsPerPage={rowsPerPage}
                        onRowsPerPageChange={handleRowsPerPageChange}
                        rowsPerPageOptions={[10, 25, 50]}
                    />
                </CardContent>
            </Card>

            {/* Create Command Dialog */}
            <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Create New Command</DialogTitle>
                <DialogContent>
                    {createError && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            {createError}
                        </Alert>
                    )}
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <TextField
                            label="Target Node ID"
                            value={newCommand.target_node_id}
                            onChange={(e) => setNewCommand({ ...newCommand, target_node_id: e.target.value })}
                            fullWidth
                            required
                        />
                        <FormControl fullWidth>
                            <InputLabel>Command Type</InputLabel>
                            <Select
                                value={newCommand.command_type}
                                label="Command Type"
                                onChange={(e) => setNewCommand({ ...newCommand, command_type: e.target.value as CommandCreate['command_type'] })}
                            >
                                <MenuItem value="ping">Ping</MenuItem>
                                <MenuItem value="reload_config">Reload Config</MenuItem>
                                <MenuItem value="update_config">Update Config</MenuItem>
                                <MenuItem value="change_role">Change Role</MenuItem>
                                <MenuItem value="custom">Custom</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField
                            label="Payload (JSON)"
                            value={JSON.stringify(newCommand.payload || {})}
                            onChange={(e) => {
                                try {
                                    setNewCommand({ ...newCommand, payload: JSON.parse(e.target.value) });
                                } catch {
                                    // Invalid JSON, ignore
                                }
                            }}
                            fullWidth
                            multiline
                            rows={3}
                            helperText="Optional JSON payload for the command"
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={handleCreateCommand}
                        variant="contained"
                        disabled={creating || !newCommand.target_node_id}
                        startIcon={creating ? <CircularProgress size={16} /> : <Send />}
                    >
                        Send Command
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default CommandsPanel;
