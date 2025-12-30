// Copyright 2024 TacticalMesh Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * API Client for TacticalMesh Controller
 * 
 * Provides typed API methods for interacting with the Mesh Controller backend.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

// API Base URL - defaults to same origin
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Types matching OpenAPI schema
export interface User {
    id: string;
    username: string;
    email: string | null;
    role: 'admin' | 'operator' | 'observer';
    is_active: boolean;
    created_at: string;
    last_login: string | null;
}

export interface Token {
    access_token: string;
    token_type: string;
    expires_in: number;
    role: 'admin' | 'operator' | 'observer';
}

export interface Node {
    id: string;
    node_id: string;
    name: string | null;
    description: string | null;
    node_type: string | null;
    status: 'online' | 'offline' | 'degraded' | 'unknown';
    last_heartbeat: string | null;
    cpu_usage: number | null;
    memory_usage: number | null;
    disk_usage: number | null;
    latitude: number | null;
    longitude: number | null;
    altitude: number | null;
    ip_address: string | null;
    metadata: Record<string, unknown> | null;
    registered_at: string;
    updated_at: string;
}

export interface NodeListResponse {
    nodes: Node[];
    total: number;
    page: number;
    page_size: number;
}

export interface Command {
    id: string;
    command_type: 'ping' | 'reload_config' | 'update_config' | 'change_role' | 'custom';
    status: 'pending' | 'sent' | 'acknowledged' | 'executing' | 'completed' | 'failed' | 'timeout';
    target_node_id: string;
    payload: Record<string, unknown> | null;
    result: Record<string, unknown> | null;
    error_message: string | null;
    created_by: string | null;
    created_at: string;
    sent_at: string | null;
    acknowledged_at: string | null;
    completed_at: string | null;
}

export interface CommandListResponse {
    commands: Command[];
    total: number;
    page: number;
    page_size: number;
}

export interface CommandCreate {
    target_node_id: string;
    command_type: 'ping' | 'reload_config' | 'update_config' | 'change_role' | 'custom';
    payload?: Record<string, unknown>;
}

export interface ApiError {
    detail: string;
    success?: boolean;
}

/**
 * API Client class with authentication support
 */
class ApiClient {
    private client: AxiosInstance;
    private token: string | null = null;

    constructor() {
        this.client = axios.create({
            baseURL: API_BASE_URL,
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Response interceptor for error handling
        this.client.interceptors.response.use(
            (response) => response,
            (error: AxiosError<ApiError>) => {
                if (error.response?.status === 401) {
                    // Token expired or invalid
                    this.clearToken();
                    window.location.href = '/login';
                }
                return Promise.reject(error);
            }
        );

        // Load token from localStorage
        const savedToken = localStorage.getItem('access_token');
        if (savedToken) {
            this.setToken(savedToken);
        }
    }

    setToken(token: string) {
        this.token = token;
        this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        localStorage.setItem('access_token', token);
    }

    clearToken() {
        this.token = null;
        delete this.client.defaults.headers.common['Authorization'];
        localStorage.removeItem('access_token');
    }

    isAuthenticated(): boolean {
        return this.token !== null;
    }

    // Authentication endpoints
    async login(username: string, password: string): Promise<Token> {
        const response = await this.client.post<Token>('/auth/login', { username, password });
        this.setToken(response.data.access_token);
        return response.data;
    }

    async logout(): Promise<void> {
        this.clearToken();
    }

    async getCurrentUser(): Promise<User> {
        const response = await this.client.get<User>('/auth/me');
        return response.data;
    }

    // Node endpoints
    async getNodes(params?: {
        page?: number;
        page_size?: number;
        status_filter?: string;
        node_type?: string;
    }): Promise<NodeListResponse> {
        const response = await this.client.get<NodeListResponse>('/nodes', { params });
        return response.data;
    }

    async getNode(nodeId: string): Promise<Node> {
        const response = await this.client.get<Node>(`/nodes/${nodeId}`);
        return response.data;
    }

    async deleteNode(nodeId: string): Promise<void> {
        await this.client.delete(`/nodes/${nodeId}`);
    }

    // Command endpoints
    async getCommands(params?: {
        page?: number;
        page_size?: number;
        status_filter?: string;
        command_type?: string;
        target_node_id?: string;
    }): Promise<CommandListResponse> {
        const response = await this.client.get<CommandListResponse>('/commands', { params });
        return response.data;
    }

    async getCommand(commandId: string): Promise<Command> {
        const response = await this.client.get<Command>(`/commands/${commandId}`);
        return response.data;
    }

    async createCommand(command: CommandCreate): Promise<Command> {
        const response = await this.client.post<Command>('/commands', command);
        return response.data;
    }

    async cancelCommand(commandId: string): Promise<void> {
        await this.client.delete(`/commands/${commandId}`);
    }

    // Health check
    async healthCheck(): Promise<{ status: string; version: string; timestamp: string }> {
        const response = await this.client.get('/health');
        return response.data;
    }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
