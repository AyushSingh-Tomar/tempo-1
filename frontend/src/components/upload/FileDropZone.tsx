import { useRef, useState } from 'react';
import { ACCEPTED_UPLOAD_EXTENSIONS, MAX_UPLOAD_BYTES } from '../../config/env';

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ACCEPTED_UPLOAD_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Drag/drop or file-picker upload. The extension/size check here is a
 * client-side convenience only - the server is the real authority and its
 * rejection is surfaced by the caller (`onFileSelected` just hands back a
 * validated-looking File; upload errors come back through the mutation).
 */
export function FileDropZone({
  onFileSelected,
  disabled,
}: {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function validateAndSelect(file: File) {
    if (!hasAcceptedExtension(file.name)) {
      setLocalError('Please choose an Excel (.xlsx) or CSV (.csv) file. The server performs the authoritative check.');
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setLocalError(`File is larger than the ${formatBytes(MAX_UPLOAD_BYTES)} limit.`);
      return;
    }
    setLocalError(null);
    setSelected(file);
    onFileSelected(file);
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        aria-label="Upload file: drag and drop or press Enter to browse"
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === 'Enter' || e.key === ' ')) inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (disabled) return;
          const file = e.dataTransfer.files?.[0];
          if (file) validateAndSelect(file);
        }}
        className={[
          'cursor-pointer rounded-md border-2 border-dashed p-8 text-center transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500',
          dragOver ? 'border-slate-500 bg-slate-50' : 'border-slate-300',
          disabled ? 'cursor-not-allowed opacity-50' : '',
        ].join(' ')}
      >
        <p className="font-medium text-slate-700">Drag and drop a file here, or click to browse</p>
        <p className="mt-1 text-sm text-slate-500">Accepted formats: .xlsx, .csv</p>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.csv"
          className="sr-only"
          disabled={disabled}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) validateAndSelect(file);
            e.target.value = '';
          }}
        />
      </div>
      {selected && !localError && (
        <p className="mt-2 text-sm text-slate-600">
          Selected: <span className="font-medium">{selected.name}</span> ({formatBytes(selected.size)})
        </p>
      )}
      {localError && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {localError}
        </p>
      )}
    </div>
  );
}
