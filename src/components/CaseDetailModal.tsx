import { useEffect, useState } from 'react';
import { Heart, Loader2, MessageCircle, Send, Trash2, X } from 'lucide-react';
import {
  CaseComment,
  CaseItem,
  createCaseComment,
  deleteCaseComment,
  getCaseComments,
  likeCase,
  unlikeCase,
} from '../api';
import { useAuth } from '../auth';
import { useSite } from '../site';

type Props = {
  item: CaseItem | null;
  onClose: () => void;
  onCaseChange?: (item: CaseItem) => void;
};

export default function CaseDetailModal({ item, onClose, onCaseChange }: Props) {
  const { viewer } = useAuth();
  const { t } = useSite();
  const [comments, setComments] = useState<CaseComment[]>([]);
  const [commentBody, setCommentBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!item) {
      setComments([]);
      setCommentBody('');
      setError('');
      return;
    }
    let cancelled = false;
    setLoading(true);
    getCaseComments(item.id)
      .then((response) => {
        if (!cancelled) setComments(response.items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [item?.id]);

  if (!item) return null;

  async function handleToggleLike() {
    if (!item || saving) return;
    if (!viewer?.authenticated) {
      setError(t('case_login_required'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      const next = item.liked ? await unlikeCase(item.id) : await likeCase(item.id);
      onCaseChange?.(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmitComment() {
    const body = commentBody.trim();
    if (!item || !body || saving) return;
    if (!viewer?.authenticated) {
      setError(t('case_login_required'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      const comment = await createCaseComment(item.id, body);
      setComments((current) => [...current, comment]);
      setCommentBody('');
      onCaseChange?.({ ...item, comment_count: item.comment_count + 1 });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteComment(comment: CaseComment) {
    setSaving(true);
    setError('');
    try {
      await deleteCaseComment(comment.id);
      setComments((current) => current.filter((currentComment) => currentComment.id !== comment.id));
      onCaseChange?.({ ...item, comment_count: Math.max(0, item.comment_count - 1) });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/80 px-4 py-6 backdrop-blur-sm" onClick={onClose}>
      <div
        className="grid max-h-[92vh] w-full max-w-6xl grid-cols-1 overflow-hidden border border-primary/30 bg-surface-container-high shadow-[0_0_40px_rgba(0,243,255,0.18)] lg:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex min-h-[320px] items-center justify-center bg-black">
          {item.image_url ? (
            <img alt={item.title} className="max-h-[92vh] w-full object-contain" src={item.image_url} />
          ) : (
            <div className="px-8 text-center text-xs uppercase tracking-widest text-white/35">{t('history_failed')}</div>
          )}
        </div>

        <div className="flex max-h-[92vh] flex-col border-l border-white/10 bg-black/70">
          <div className="flex items-start justify-between gap-4 border-b border-white/10 p-5">
            <div className="min-w-0">
              <div className="mb-2 text-[10px] uppercase tracking-widest text-secondary">{item.author || t('case_public_gallery')}</div>
              <h2 className="text-xl font-black text-white">{item.title}</h2>
              <div className="mt-2 flex flex-wrap gap-3 text-[10px] uppercase tracking-wider text-white/35">
                {item.model ? <span>{item.model}</span> : null}
                {item.size ? <span>{item.size}</span> : null}
                {item.aspect_ratio ? <span>{item.aspect_ratio}</span> : null}
                {item.quality ? <span>{item.quality}</span> : null}
              </div>
            </div>
            <button className="flex h-10 w-10 shrink-0 items-center justify-center border border-white/10 text-white/60 hover:border-primary hover:text-primary" type="button" onClick={onClose} title={t('modal_close')}>
              <X size={16} />
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {error ? <div className="mb-4 border border-error/40 bg-error/10 p-3 text-xs text-error">{error}</div> : null}
            <p className="whitespace-pre-wrap text-sm leading-7 text-white/80">{item.prompt}</p>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                className={`flex h-11 items-center justify-center gap-2 border text-xs font-bold uppercase tracking-widest transition-colors ${
                  item.liked ? 'border-secondary bg-secondary/15 text-secondary' : 'border-white/10 bg-white/5 text-white/70 hover:border-secondary hover:text-secondary'
                }`}
                type="button"
                onClick={handleToggleLike}
                disabled={saving}
              >
                {saving ? <Loader2 className="animate-spin" size={14} /> : <Heart size={15} />}
                {item.like_count}
              </button>
              <div className="flex h-11 items-center justify-center gap-2 border border-white/10 bg-white/5 text-xs font-bold uppercase tracking-widest text-white/60">
                <MessageCircle size={15} />
                {item.comment_count}
              </div>
            </div>

            <div className="mt-6">
              <div className="mb-3 text-[10px] font-bold uppercase tracking-widest text-primary">{t('case_comments')}</div>
              {loading ? (
                <div className="flex items-center gap-2 py-4 text-xs uppercase tracking-widest text-primary/70">
                  <Loader2 className="animate-spin" size={14} />
                  {t('case_comments_loading')}
                </div>
              ) : comments.length > 0 ? (
                <div className="space-y-3">
                  {comments.map((comment) => (
                    <div key={comment.id} className="border border-white/10 bg-white/[0.03] p-3">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <span className="min-w-0 truncate text-[10px] uppercase tracking-widest text-secondary">{comment.author || t('top_owner')}</span>
                        {comment.can_delete ? (
                          <button className="text-error/70 hover:text-error" type="button" onClick={() => handleDeleteComment(comment)} title={t('history_delete')}>
                            <Trash2 size={13} />
                          </button>
                        ) : null}
                      </div>
                      <p className="whitespace-pre-wrap text-sm leading-6 text-white/75">{comment.body}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="border border-white/10 bg-white/[0.03] p-4 text-sm text-white/40">{t('case_comments_empty')}</div>
              )}
            </div>
          </div>

          <div className="border-t border-white/10 p-5">
            <textarea
              className="input-cyber min-h-24 resize-y"
              value={commentBody}
              onChange={(event) => setCommentBody(event.target.value)}
              placeholder={viewer?.authenticated ? t('case_comment_placeholder') : t('case_login_required')}
              disabled={!viewer?.authenticated || saving}
            />
            <button
              className="mt-3 flex h-11 w-full items-center justify-center gap-2 bg-primary px-4 text-xs font-black uppercase tracking-widest text-black transition-colors hover:bg-white disabled:opacity-50"
              type="button"
              onClick={handleSubmitComment}
              disabled={!viewer?.authenticated || !commentBody.trim() || saving}
            >
              {saving ? <Loader2 className="animate-spin" size={14} /> : <Send size={14} />}
              {t('case_comment_submit')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
