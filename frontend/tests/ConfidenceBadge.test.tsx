import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConfidenceBadge } from '../src/components/common/ConfidenceBadge';

describe('ConfidenceBadge', () => {
  it('renders a safe zero-confidence state when the confidence payload is missing', () => {
    render(<ConfidenceBadge confidence={undefined as any} />);
    expect(screen.getByRole('button')).toHaveTextContent('0% confidence');
  });
});
