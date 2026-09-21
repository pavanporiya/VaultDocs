import React, { useState } from 'react';
import {
  Button,
  Input,
  Select,
  Card,
  Table,
  Modal,
  Loader,
  EmptyState,
  ErrorState,
  PageHeader,
  useToast,
} from './shared/components';
import MainLayout from './shared/layouts/MainLayout';
import {
  Plus,
  Search,
  Download,
  Trash2,
  FileText,
  AlertCircle,
  Bell,
  SlidersHorizontal,
} from 'lucide-react';
import './App.css';

/**
 * Inner Showcase component rendered within ToastProvider via MainLayout
 */
function ShowcaseContent() {
  const toast = useToast();

  // Component States
  const [btnLoading, setBtnLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [selectValue, setSelectValue] = useState('');
  const [inputError, setInputError] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableEmpty, setTableEmpty] = useState(false);

  // Sample Table Data
  const sampleData = [
    { id: '1', name: 'Financial_Report_Q3.pdf', size: '2.4 MB', category: 'Finance', modified: '2026-09-20' },
    { id: '2', name: 'Project_Architecture_v2.docx', size: '1.1 MB', category: 'Engineering', modified: '2026-09-18' },
    { id: '3', name: 'Security_Audit_Summary.pdf', size: '850 KB', category: 'Security', modified: '2026-09-15' },
  ];

  const tableColumns = [
    {
      header: 'Document Name',
      key: 'name',
      render: (row) => (
        <div className="vd-showcase-doc-cell">
          <FileText size={18} className="vd-showcase-doc-icon" />
          <span className="vd-showcase-doc-name">{row.name}</span>
        </div>
      ),
    },
    { header: 'Category', key: 'category' },
    { header: 'Size', key: 'size' },
    { header: 'Last Modified', key: 'modified' },
    {
      header: 'Actions',
      key: 'actions',
      align: 'right',
      render: () => (
        <div className="vd-showcase-actions">
          <Button variant="ghost" size="sm" icon={Download} aria-label="Download document" />
          <Button variant="ghost" size="sm" icon={Trash2} aria-label="Delete document" />
        </div>
      ),
    },
  ];

  return (
    <div className="vd-showcase">
      <PageHeader
        title="Shared UI Foundation"
        description="Comprehensive design system, tokens, layout structure, and reusable UI components for VaultDocs."
        breadcrumbs={[{ label: 'VaultDocs' }, { label: 'Common Foundation' }]}
        actions={
          <Button variant="primary" icon={Plus} onClick={() => setIsModalOpen(true)}>
            Open Sample Modal
          </Button>
        }
      />

      {/* Buttons Showcase */}
      <Card title="Buttons & Variants" subtitle="Reusable button components supporting colors, sizes, icons, and loading states." elevation="sm">
        <div className="vd-showcase-row">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="primary" disabled>Disabled</Button>
          <Button
            variant="primary"
            loading={btnLoading}
            onClick={() => {
              setBtnLoading(true);
              setTimeout(() => setBtnLoading(false), 2000);
            }}
          >
            {btnLoading ? 'Processing' : 'Click to Load'}
          </Button>
          <Button variant="secondary" icon={Plus} iconPosition="left">
            With Icon
          </Button>
        </div>
      </Card>

      {/* Inputs Showcase */}
      <Card title="Inputs & Select Controls" subtitle="Form inputs with labels, helper text, error states, and accessibility bindings." elevation="sm">
        <div className="vd-showcase-grid">
          <Input
            label="Standard Input"
            placeholder="Enter text..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            helperText="Standard helper description text."
          />
          <Input
            label="Input with Icon"
            placeholder="Search documents..."
            icon={Search}
          />
          <Input
            label="Input with Error"
            placeholder="Enter email..."
            value="invalid-email"
            error={inputError || 'Please enter a valid email address.'}
            onChange={(e) => {
              setInputError('');
              setInputValue(e.target.value);
            }}
          />
          <Select
            label="Select Category"
            value={selectValue}
            onChange={(e) => setSelectValue(e.target.value)}
            options={[
              { value: 'finance', label: 'Finance & Accounting' },
              { value: 'engineering', label: 'Engineering Architecture' },
              { value: 'security', label: 'Security & Compliance' },
            ]}
          />
        </div>
      </Card>

      {/* Toast & Feedback Showcase */}
      <Card title="Toast Notifications & Feedback" subtitle="Global context-driven toast alerts, loader indicators, and empty/error states." elevation="sm">
        <div className="vd-showcase-row" style={{ marginBottom: '1.5rem' }}>
          <Button variant="outline" icon={Bell} onClick={() => toast.success('Document uploaded successfully!', 'Operation Complete')}>
            Success Toast
          </Button>
          <Button variant="outline" icon={AlertCircle} onClick={() => toast.error('Failed to connect to backend service.', 'Connection Error')}>
            Error Toast
          </Button>
          <Button variant="outline" onClick={() => toast.warning('Storage is approaching 90% capacity.', 'Storage Notice')}>
            Warning Toast
          </Button>
          <Button variant="outline" onClick={() => toast.info('System maintenance scheduled for tonight at 12:00 AM UTC.', 'System Update')}>
            Info Toast
          </Button>
        </div>

        <div className="vd-showcase-grid-3">
          <div className="vd-showcase-box">
            <span className="vd-showcase-box-title">Component Loader</span>
            <Loader size="md" text="Loading resources..." />
          </div>
          <div className="vd-showcase-box">
            <span className="vd-showcase-box-title">Empty State</span>
            <EmptyState
              title="No files in folder"
              description="Upload files to start managing your vault."
            />
          </div>
          <div className="vd-showcase-box">
            <span className="vd-showcase-box-title">Error State</span>
            <ErrorState
              title="Failed to load document"
              description="The requested resource could not be fetched."
              onRetry={() => toast.info('Retrying request...')}
            />
          </div>
        </div>
      </Card>

      {/* Data Table Showcase */}
      <Card
        title="Reusable Table Component"
        subtitle="Accessible data table with column rendering, skeleton loaders, and empty states."
        elevation="sm"
        headerAction={
          <div className="vd-showcase-row">
            <Button
              variant="ghost"
              size="sm"
              icon={SlidersHorizontal}
              onClick={() => setTableLoading(!tableLoading)}
            >
              Toggle Skeleton ({tableLoading ? 'ON' : 'OFF'})
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setTableEmpty(!tableEmpty)}
            >
              Toggle Empty ({tableEmpty ? 'ON' : 'OFF'})
            </Button>
          </div>
        }
      >
        <Table
          columns={tableColumns}
          data={tableEmpty ? [] : sampleData}
          loading={tableLoading}
          emptyTitle="No documents available"
          emptyDescription="You haven't added any documents to this view yet."
          emptyAction={
            <Button variant="primary" size="sm" icon={Plus}>
              Upload First Document
            </Button>
          }
        />
      </Card>

      {/* Modal Dialog Showcase */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Sample Modal Dialog"
        size="md"
        footer={
          <div className="vd-showcase-modal-footer">
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => {
              toast.success('Action confirmed inside modal!');
              setIsModalOpen(false);
            }}>
              Confirm Action
            </Button>
          </div>
        }
      >
        <p style={{ color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
          This is a reusable, accessible modal dialog overlay with backdrop blur, focus handling,
          Escape key detection, and body scroll prevention.
        </p>
        <Input label="Modal Input Example" placeholder="Type something..." />
      </Modal>
    </div>
  );
}

export function App() {
  const [activeNav, setActiveNav] = useState('dashboard');

  return (
    <MainLayout activeNavItem={activeNav} onNavItemClick={(item) => setActiveNav(item.id)}>
      <ShowcaseContent />
    </MainLayout>
  );
}

export default App;
