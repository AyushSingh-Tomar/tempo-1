import { describeError } from '../../api/errors';

export function ErrorState({
  error,
  title = 'Something went wrong',
  onRetry,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-red-800">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm">{describeError(error)}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
        >
          Retry
        </button>
      )}
    </div>
  );
}
