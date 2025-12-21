// Copyright 2024 Apache TacticalMesh Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Nodes Table Component
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
    InputAdornment,
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
} from '@mui/material';
import {
    Search,
    Refresh,
    Circle,
    Send,
    Delete,
    Visibility,
} from '@mui/icons-material';
import { apiClient, Node, NodeListResponse } from '../api/client';

interface NodesTableProps {
    onSendCommand?: (nodeId: string) => void;
}

const statusColors: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
    online: 'success',
    offline: 'error',
    degraded: 'warning',
    unknown: 'default',
};

const NodesTable: React.FC<NodesTableProps> = ({ onSendCommand }) => {
    const [nodes, setNodes] = useState<Node[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('');

    const fetchNodes = useCallback(async () => {
        setLoading(true);
        try {
            const response: NodeListResponse = await apiClient.getNodes({
                page: page + 1,
                page_size: rowsPerPage,
                status_filter: statusFilter || undefined,
                node_type: typeFilter || undefined,
            });
            setNodes(response.nodes);
            setTotal(response.total);
        } catch (error) {
            console.error('Failed to fetch nodes:', error);
        } finally {
            setLoading(false);
        }
    }, [page, rowsPerPage, statusFilter, typeFilter]);

    useEffect(() => {
        fetchNodes();
        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchNodes, 30000);
        return () => clearInterval(interval);
    }, [fetchNodes]);

    const handlePageChange = (_: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    const formatLastSeen = (timestamp: string | null) => {
        if (!timestamp) return 'Never';
        const date = new Date(timestamp);
        const now = new Date();
        const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

        if (diff < 60) return `${diff}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return date.toLocaleDateString();
    };

    const filteredNodes = nodes.filter(node =>
        node.node_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        node.name?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <Card>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                    <Typography variant="h5" fontWeight={600}>
                        Mesh Nodes
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip
                            label={`${total} total`}
                            size="small"
                            color="primary"
                            variant="outlined"
                        />
                        <Tooltip title="Refresh">
                            <IconButton onClick={fetchNodes} size="small">
                                <Refresh />
                            </IconButton>
                        </Tooltip>
                    </Box>
                </Box>

                {/* Filters */}
                <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
                    <TextField
                        size="small"
                        placeholder="Search nodes..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <Search />
                                </InputAdornment>
                            ),
                        }}
                        sx={{ minWidth: 250 }}
                    />
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Status</InputLabel>
                        <Select
                            value={statusFilter}
                            label="Status"
                            onChange={(e) => setStatusFilter(e.target.value)}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="online">Online</MenuItem>
                            <MenuItem value="offline">Offline</MenuItem>
                            <MenuItem value="degraded">Degraded</MenuItem>
                            <MenuItem value="unknown">Unknown</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Type</InputLabel>
                        <Select
                            value={typeFilter}
                            label="Type"
                            onChange={(e) => setTypeFilter(e.target.value)}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="vehicle">Vehicle</MenuItem>
                            <MenuItem value="dismounted">Dismounted</MenuItem>
                            <MenuItem value="sensor">Sensor</MenuItem>
                            <MenuItem value="uas">UAS</MenuItem>
                            <MenuItem value="relay">Relay</MenuItem>
                        </Select>
                    </FormControl>
                </Box>

                {/* Table */}
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Status</TableCell>
                                <TableCell>Node ID</TableCell>
                                <TableCell>Name</TableCell>
                                <TableCell>Type</TableCell>
                                <TableCell>Last Seen</TableCell>
                                <TableCell>CPU</TableCell>
                                <TableCell>Memory</TableCell>
                                <TableCell>IP Address</TableCell>
                                <TableCell align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {loading ? (
                                <TableRow>
                                    <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                                        <CircularProgress size={32} />
                                    </TableCell>
                                </TableRow>
                            ) : filteredNodes.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                                        <Typography color="text.secondary">No nodes found</Typography>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filteredNodes.map((node) => (
                                    <TableRow key={node.id} hover>
                                        <TableCell>
                                            <Chip
                                                icon={<Circle sx={{ fontSize: '10px !important' }} />}
                                                label={node.status}
                                                size="small"
                                                color={statusColors[node.status]}
                                                sx={{ textTransform: 'capitalize' }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" fontFamily="monospace">
                                                {node.node_id}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>{node.name || '-'}</TableCell>
                                        <TableCell>
                                            <Chip
                                                label={node.node_type || 'unknown'}
                                                size="small"
                                                variant="outlined"
                                                sx={{ textTransform: 'capitalize' }}
                                            />
                                        </TableCell>
                                        <TableCell>{formatLastSeen(node.last_heartbeat)}</TableCell>
                                        <TableCell>
                                            {node.cpu_usage !== null ? `${node.cpu_usage.toFixed(1)}%` : '-'}
                                        </TableCell>
                                        <TableCell>
                                            {node.memory_usage !== null ? `${node.memory_usage.toFixed(1)}%` : '-'}
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" fontFamily="monospace">
                                                {node.ip_address || '-'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Tooltip title="Send Command">
                                                <IconButton
                                                    size="small"
                                                    onClick={() => onSendCommand?.(node.node_id)}
                                                >
                                                    <Send fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="View Details">
                                                <IconButton size="small">
                                                    <Visibility fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
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
    );
};

export default NodesTable;
