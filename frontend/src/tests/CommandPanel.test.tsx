import { render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import CommandPanel from '../components/CommandsPanel';
import { AuthProvider } from '../context/AuthContext';

// Mock API client
vi.mock('../api/client', () => ({
    apiClient: {
        isAuthenticated: vi.fn(() => false),
        getCurrentUser: vi.fn(),
        createCommand: vi.fn(),
        login: vi.fn(),
        logout: vi.fn(),
        clearToken: vi.fn(),
        getCommands: vi.fn(() => Promise.resolve({ commands: [], total: 0, page: 1, page_size: 10 })),
    },
    default: {
        isAuthenticated: vi.fn(() => false),
        getCurrentUser: vi.fn(),
        createCommand: vi.fn(),
        login: vi.fn(),
        logout: vi.fn(),
        clearToken: vi.fn(),
        getCommands: vi.fn(() => Promise.resolve({ commands: [], total: 0, page: 1, page_size: 10 })),
    }
}));

const renderWithProviders = (component: React.ReactNode) => {
    return render(
        <BrowserRouter>
            <AuthProvider>
                {component}
            </AuthProvider>
        </BrowserRouter>
    );
};

describe('CommandPanel', () => {
    it('renders without crashing', async () => {
        const { container } = renderWithProviders(<CommandPanel />);
        await waitFor(() => expect(container).toBeTruthy());
    });

    it('renders header text', async () => {
        const { container } = renderWithProviders(<CommandPanel />);
        await waitFor(() => {
            expect(container.textContent).toContain('Commands');
        });
    });
});
