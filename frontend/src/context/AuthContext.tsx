// Copyright 2024 Apache TacticalMesh Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Authentication Context Provider
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient, User, Token } from '../api/client';

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
    error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const isAuthenticated = user !== null;

    useEffect(() => {
        // Check if we have a saved token and try to get user info
        const checkAuth = async () => {
            if (apiClient.isAuthenticated()) {
                try {
                    const currentUser = await apiClient.getCurrentUser();
                    setUser(currentUser);
                } catch {
                    // Token is invalid, clear it
                    apiClient.clearToken();
                }
            }
            setIsLoading(false);
        };

        checkAuth();
    }, []);

    const login = async (username: string, password: string) => {
        setError(null);
        try {
            const token = await apiClient.login(username, password);
            const currentUser = await apiClient.getCurrentUser();
            setUser(currentUser);
        } catch (err: unknown) {
            const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Login failed';
            setError(errorMessage);
            throw new Error(errorMessage);
        }
    };

    const logout = () => {
        apiClient.logout();
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout, error }}>
            {children}
        </AuthContext.Provider>
    );
};
