import { render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import NodesTable from '../components/NodesTable';
import { AuthProvider } from '../context/AuthContext';

// Mock API client
vi.mock('../api/client', () => ({
    apiClient: {
        isAuthenticated: vi.fn(() => false),
        getCurrentUser: vi.fn(),
        login: vi.fn(),
        logout: vi.fn(),
        clearToken: vi.fn(),
        getNodes: vi.fn(() => Promise.resolve({ nodes: [], total: 0, page: 1, page_size: 10 })),
    },
    default: {
        isAuthenticated: vi.fn(() => false),
        getCurrentUser: vi.fn(),
        login: vi.fn(),
        logout: vi.fn(),
        clearToken: vi.fn(),
        getNodes: vi.fn(() => Promise.resolve({ nodes: [], total: 0, page: 1, page_size: 10 })),
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

describe('NodesTable', () => {
    it('renders without crashing', async () => {
        const { container } = renderWithProviders(<NodesTable />);
        await waitFor(() => expect(container).toBeTruthy());
    });

    it('renders header text', async () => {
        const { container } = renderWithProviders(<NodesTable />);
        await waitFor(() => {
            expect(container.textContent).toContain('Mesh Nodes');
        });
    });
});
