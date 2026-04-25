import { CheckCircle2, X, XCircle } from 'lucide-react';
import { useSite } from '../site';
import { useTasks } from '../tasks';

export default function TaskToastStack() {
  const { t } = useSite();
  const { toasts, dismissToast } = useTasks();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed right-6 top-20 z-[160] flex w-[min(92vw,380px)] flex-col gap-3">
      {toasts.map((toast) => {
        const succeeded = toast.status === 'succeeded';
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto border p-4 shadow-[0_16px_40px_rgba(0,0,0,0.55)] backdrop-blur-xl ${
              succeeded
                ? 'border-secondary/40 bg-secondary/10'
                : 'border-error/40 bg-error/10'
            }`}
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 shrink-0">
                {succeeded ? (
                  <CheckCircle2 size={18} className="text-secondary" />
                ) : (
                  <XCircle size={18} className="text-error" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-white/60">
                  {succeeded ? t('tasks_toast_succeeded') : t('tasks_toast_failed')}
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-white/85">{toast.prompt}</p>
                {toast.error ? <div className="mt-2 text-xs text-error">{toast.error}</div> : null}
              </div>
              <button
                className="flex h-8 w-8 items-center justify-center border border-white/10 text-white/55 transition-colors hover:border-white/25 hover:text-white"
                type="button"
                onClick={() => dismissToast(toast.id)}
                title={t('modal_close')}
              >
                <X size={14} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
