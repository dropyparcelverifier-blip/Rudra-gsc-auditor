import { CheckCircle, Upload, AlertTriangle, XCircle, Clock } from 'lucide-react';

export const STATUS_HEX = {
  indexed: '#22c55e',
  requested: '#3b82f6',
  submitted: '#3b82f6',
  not_indexed: '#f59e0b',
  inspect_only: '#f59e0b',
  error: '#ef4444',
  pending: '#94a3b8',
};

export const STATUS_COLORS = {
  indexed: 'text-green-600 bg-green-50 border-green-200',
  requested: 'text-blue-600 bg-blue-50 border-blue-200',
  submitted: 'text-blue-600 bg-blue-50 border-blue-200',
  not_indexed: 'text-amber-600 bg-amber-50 border-amber-200',
  inspect_only: 'text-amber-600 bg-amber-50 border-amber-200',
  error: 'text-red-600 bg-red-50 border-red-200',
  pending: 'text-slate-400 bg-slate-50 border-slate-200',
};

export const STATUS_LABELS = {
  indexed: 'Indexed',
  requested: 'Requested',
  submitted: 'Submitted',
  not_indexed: 'Not Indexed',
  inspect_only: 'Not Indexed',
  error: 'Error',
  pending: 'Pending',
};

export const STATUS_ICON = {
  indexed: CheckCircle,
  requested: Upload,
  submitted: Upload,
  not_indexed: AlertTriangle,
  inspect_only: AlertTriangle,
  error: XCircle,
  pending: Clock,
};
