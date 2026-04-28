import { FormEvent, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Heart, Loader2, MessageCircle, Save, Search, Trash2, X } from 'lucide-react';
import {
  CaseComment,
  CaseItem,
  deleteAdminCase,
  deleteCaseComment,
  formatDate,
  listAdminCaseComments,
  listAdminCases,
  setAdminCaseLikeCount,
} from '../api';
import { useSite } from '../site';

const PAGE_SIZE = 12;

function visiblePages(current: number, pageCount: number) {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }
  const start = Math.max(1, Math.min(current - 3, pageCount - 6));
  return Array.from({ length: 7 }, (_, index) => start + index);
}

function caseImage(item: CaseItem) {
  return item.image_url || '';
}

function statusLabel(status: CaseItem['status'], t: ReturnType<typeof useSite>['t']) {
  if (status === 'visible') return t('case_status_visible');
  if (status === 'hidden') return t('case_status_hidden');
  return t('case_status_deleted');
}

export default function AdminCaseManager() {
  const { siteSettings, t } = useSite();
  const [items, setItems] = useState<CaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [queryDraft, setQueryDraft] = useState('');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null);
  const [comments, setComments] = useState<CaseComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [dialogError, setDialogError] = useState('');
  const [likeDraft, setLikeDraft] = useState('');
  const [savingLikes, setSavingLikes] = useState(false);
  const [deletingCommentId, setDeletingCommentId] = useState('');
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingCase, setDeletingCase] = useState(false);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pages = useMemo(() => visiblePages(page, pageCount), [page, pageCount]);

  async function loadCases(nextPage = page, nextQuery = query) {
    setLoading(true);
    setError('');
    try {
      const result = await listAdminCases({
        limit: PAGE_SIZE,
        offset: (nextPage - 1) * PAGE_SIZE,
        q: nextQuery,
      });
      setItems(result.items);
      setTotal(result.total);
      if (selectedCase) {
        const refreshed = result.items.find((item) => item.id === selectedCase.id);
        if (refreshed) {
          setSelectedCase(refreshed);
          setLikeDraft(String(refreshed.like_count));
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function loadComments(caseId: string) {
    setCommentsLoading(true);
    setDialogError('');
    try {
      const result = await listAdminCaseComments(caseId);
      setComments(result.items);
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err));
    } finally {
      setCommentsLoading(false);
    }
  }

  useEffect(() => {
    if (!siteSettings?.viewer.is_admin) {
      return;
    }
    loadCases(page, query);
  }, [page, query, siteSettings?.viewer.is_admin]);

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    const nextQuery = queryDraft.trim();
    setMessage('');
    if (page === 1 && nextQuery === query) {
      loadCases(1, nextQuery);
      return;
    }
    setPage(1);
    setQuery(nextQuery);
  }

  function openCase(item: CaseItem) {
    setSelectedCase(item);
    setLikeDraft(String(item.like_count));
    setDialogError('');
    setMessage('');
    setComments([]);
    setDeleteConfirmOpen(false);
    loadComments(item.id);
  }

  async function handleSaveLikes() {
    if (!selectedCase) return;
    const nextLikes = Number(likeDraft);
    if (!Number.isInteger(nextLikes) || nextLikes < 0) {
      setDialogError(t('case_admin_like_invalid'));
      return;
    }
    setSavingLikes(true);
    setDialogError('');
    try {
      const updated = await setAdminCaseLikeCount(selectedCase.id, nextLikes);
      setSelectedCase(updated);
      setLikeDraft(String(updated.like_count));
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage(t('case_admin_saved'));
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingLikes(false);
    }
  }

  async function handleDeleteComment(commentId: string) {
    if (!selectedCase) return;
    setDeletingCommentId(commentId);
    setDialogError('');
    try {
      await deleteCaseComment(commentId);
      await loadComments(selectedCase.id);
      await loadCases(page, query);
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingCommentId('');
    }
  }

  async function handleDeleteCase() {
    if (!selectedCase) return;
    setDeletingCase(true);
    setDialogError('');
    try {
      const deleted = await deleteAdminCase(selectedCase.id);
      setItems((current) => current.map((item) => (item.id === deleted.id ? deleted : item)));
      setSelectedCase(null);
      setDeleteConfirmOpen(false);
      setMessage(t('case_admin_deleted'));
      await loadCases(page, query);
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingCase(false);
    }
  }

  if (!siteSettings) {
    return (
      <section className="min-h-screen px-4 pb-12 pt-24 md:pl-64">
        <div className="mx-auto flex max-w-5xl items-center gap-2 border border-primary/25 bg-primary/5 p-6 text-sm text-primary">
          <Loader2 size={16} className="animate-spin" />
          {t('case_admin_loading')}
        </div>
      </section>
    );
  }

  if (!siteSettings.viewer.is_admin) {
    return (
      <section className="min-h-screen px-4 pb-12 pt-24 md:pl-64">
        <div className="mx-auto max-w-5xl border border-secondary/25 bg-secondary/5 p-6 text-sm text-secondary">
          {t('case_admin_admin_only')}
        </div>
      </section>
    );
  }

  return (
    <section className="min-h-screen px-4 pb-12 pt-24 md:pl-64">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-primary/20 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.24em] text-primary">{t('case_admin_tag')}</div>
            <h1 className="text-3xl font-black uppercase tracking-tight text-white sm:text-4xl">{t('case_admin_title')}</h1>
          </div>
          <form className="flex w-full max-w-lg gap-2" onSubmit={handleSearch}>
            <label className="sr-only" htmlFor="case-admin-search">
              {t('case_admin_search_prompt')}
            </label>
            <div className="flex min-w-0 flex-1 items-center gap-2 border border-primary/25 bg-surface-container px-3">
              <Search size={16} className="shrink-0 text-primary" />
              <input
                id="case-admin-search"
                className="min-h-11 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-on-surface-variant"
                placeholder={t('case_admin_search_prompt')}
                value={queryDraft}
                onChange={(event) => setQueryDraft(event.target.value)}
              />
            </div>
            <button
              className="flex h-11 shrink-0 items-center gap-2 border border-primary bg-primary px-4 text-xs font-bold uppercase tracking-widest text-black transition-colors hover:bg-white disabled:opacity-50"
              disabled={loading}
              type="submit"
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              {t('case_admin_search_submit')}
            </button>
          </form>
        </header>

        {(error || message) ? (
          <div className={`border px-4 py-3 text-sm ${error ? 'border-secondary/30 bg-secondary/10 text-secondary' : 'border-primary/30 bg-primary/10 text-primary'}`}>
            {error || message}
          </div>
        ) : null}

        <div className="border border-primary/15 bg-surface-container/60">
          <div className="grid grid-cols-[72px_minmax(0,1fr)_88px] gap-3 border-b border-white/10 px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant md:grid-cols-[80px_minmax(0,1.3fr)_minmax(0,1.7fr)_88px_116px_150px]">
            <span>{t('case_public_gallery')}</span>
            <span>{t('case_title')}</span>
            <span className="hidden md:block">{t('case_prompt')}</span>
            <span>{t('case_status')}</span>
            <span className="hidden md:block">{t('case_admin_stats')}</span>
            <span className="hidden md:block">{t('case_admin_created_at')}</span>
          </div>

          {loading && items.length === 0 ? (
            <div className="flex min-h-56 items-center justify-center gap-2 text-sm text-primary">
              <Loader2 size={17} className="animate-spin" />
              {t('case_admin_loading')}
            </div>
          ) : null}

          {!loading && items.length === 0 ? (
            <div className="min-h-56 px-4 py-16 text-center text-sm text-on-surface-variant">{t('case_admin_empty')}</div>
          ) : null}

          {items.map((item) => (
            <button
              key={item.id}
              className="grid w-full grid-cols-[72px_minmax(0,1fr)_88px] gap-3 border-b border-white/10 px-3 py-3 text-left transition-colors hover:bg-primary/5 md:grid-cols-[80px_minmax(0,1.3fr)_minmax(0,1.7fr)_88px_116px_150px]"
              type="button"
              onClick={() => openCase(item)}
            >
              <div className="h-14 w-16 overflow-hidden border border-white/10 bg-black/30">
                {caseImage(item) ? (
                  <img alt={item.title} className="h-full w-full object-cover" src={caseImage(item)} />
                ) : (
                  <div className="flex h-full items-center justify-center text-[10px] text-on-surface-variant">{t('case_admin_no_image')}</div>
                )}
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-bold text-white">{item.title}</div>
                <div className="mt-1 truncate text-[11px] text-on-surface-variant md:hidden">{item.prompt}</div>
                <div className="mt-2 text-[10px] uppercase tracking-wider text-primary">{item.source_type}</div>
              </div>
              <div className="hidden min-w-0 text-xs leading-5 text-on-surface-variant md:block">
                <span className="line-clamp-2">{item.prompt}</span>
              </div>
              <div>
                <span className={`inline-flex border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
                  item.status === 'visible'
                    ? 'border-primary/35 text-primary'
                    : item.status === 'hidden'
                      ? 'border-tertiary/35 text-tertiary'
                      : 'border-secondary/35 text-secondary'
                }`}>
                  {statusLabel(item.status, t)}
                </span>
              </div>
              <div className="hidden items-center gap-3 text-xs text-on-surface-variant md:flex">
                <span className="inline-flex items-center gap-1">
                  <Heart size={13} />
                  {item.like_count}
                </span>
                <span className="inline-flex items-center gap-1">
                  <MessageCircle size={13} />
                  {item.comment_count}
                </span>
              </div>
              <div className="hidden text-xs text-on-surface-variant md:block">{formatDate(item.created_at)}</div>
            </button>
          ))}

          <div className="flex flex-col gap-3 px-3 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-on-surface-variant">
              {t('case_admin_page_status', { page, pages: pageCount, total })}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                className="flex h-9 w-9 items-center justify-center border border-white/15 text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-35"
                disabled={page <= 1 || loading}
                title={t('case_admin_prev')}
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft size={16} />
              </button>
              {pages[0] > 1 ? (
                <button
                  className="h-9 min-w-9 border border-white/15 px-3 text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
                  type="button"
                  onClick={() => setPage(1)}
                >
                  1
                </button>
              ) : null}
              {pages[0] > 2 ? <span className="px-1 text-xs text-on-surface-variant">...</span> : null}
              {pages.map((item) => (
                <button
                  key={item}
                  className={`h-9 min-w-9 border px-3 text-xs font-bold transition-colors ${
                    item === page
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-white/15 text-on-surface-variant hover:border-primary hover:text-primary'
                  }`}
                  disabled={loading}
                  type="button"
                  onClick={() => setPage(item)}
                >
                  {item}
                </button>
              ))}
              {pages[pages.length - 1] < pageCount - 1 ? <span className="px-1 text-xs text-on-surface-variant">...</span> : null}
              {pages[pages.length - 1] < pageCount ? (
                <button
                  className="h-9 min-w-9 border border-white/15 px-3 text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
                  type="button"
                  onClick={() => setPage(pageCount)}
                >
                  {pageCount}
                </button>
              ) : null}
              <button
                className="flex h-9 w-9 items-center justify-center border border-white/15 text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-35"
                disabled={page >= pageCount || loading}
                title={t('case_admin_next')}
                type="button"
                onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {selectedCase ? (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/80 p-3 backdrop-blur-sm sm:p-6" role="dialog" aria-modal="true">
          <div className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden border border-primary/25 bg-surface shadow-[0_0_36px_rgba(0,243,255,0.12)]">
            <div className="flex items-center justify-between gap-4 border-b border-primary/20 px-4 py-3">
              <div className="min-w-0">
                <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-primary">{t('case_admin_detail')}</div>
                <h2 className="truncate text-lg font-black text-white">{selectedCase.title}</h2>
              </div>
              <button
                className="flex h-10 w-10 shrink-0 items-center justify-center border border-white/15 text-on-surface-variant transition-colors hover:border-secondary hover:text-secondary"
                type="button"
                onClick={() => setSelectedCase(null)}
                title={t('mobile_menu_close')}
              >
                <X size={17} />
              </button>
            </div>

            <div className="grid gap-5 overflow-y-auto p-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <div className="space-y-4">
                <div className="aspect-[4/3] overflow-hidden border border-white/10 bg-black/35">
                  {caseImage(selectedCase) ? (
                    <img alt={selectedCase.title} className="h-full w-full object-contain" src={caseImage(selectedCase)} />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-on-surface-variant">{t('case_admin_no_image')}</div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs text-on-surface-variant">
                  <div className="border border-white/10 bg-white/5 p-3">
                    <div className="mb-1 text-[10px] uppercase tracking-widest text-on-surface-variant">{t('case_status')}</div>
                    <div className="font-bold text-white">{statusLabel(selectedCase.status, t)}</div>
                  </div>
                  <div className="border border-white/10 bg-white/5 p-3">
                    <div className="mb-1 text-[10px] uppercase tracking-widest text-on-surface-variant">{t('case_admin_created_at')}</div>
                    <div className="font-bold text-white">{formatDate(selectedCase.created_at)}</div>
                  </div>
                </div>
              </div>

              <div className="space-y-5">
                <div>
                  <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.24em] text-primary">{t('case_prompt')}</div>
                  <div className="max-h-40 overflow-y-auto border border-white/10 bg-white/5 p-3 text-sm leading-6 text-on-surface-variant">
                    {selectedCase.prompt}
                  </div>
                </div>

                <div className="border border-primary/15 bg-primary/5 p-4">
                  <label className="mb-2 block text-[10px] font-bold uppercase tracking-[0.24em] text-primary" htmlFor="case-like-count">
                    {t('case_admin_like_count')}
                  </label>
                  <div className="flex gap-2">
                    <div className="flex min-w-0 flex-1 items-center gap-2 border border-primary/25 bg-surface-container px-3">
                      <Heart size={16} className="shrink-0 text-primary" />
                      <input
                        id="case-like-count"
                        className="min-h-11 min-w-0 flex-1 bg-transparent text-sm text-white outline-none"
                        min={0}
                        type="number"
                        value={likeDraft}
                        onChange={(event) => setLikeDraft(event.target.value)}
                      />
                    </div>
                    <button
                      className="flex h-11 shrink-0 items-center gap-2 border border-primary bg-primary px-4 text-xs font-bold uppercase tracking-widest text-black transition-colors hover:bg-white disabled:opacity-50"
                      disabled={savingLikes}
                      type="button"
                      onClick={handleSaveLikes}
                    >
                      {savingLikes ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
                      {t('case_admin_save_likes')}
                    </button>
                  </div>
                </div>

                <div className="border border-white/10">
                  <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                    <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.24em] text-primary">
                      <MessageCircle size={15} />
                      {t('case_admin_comments')}
                    </div>
                    {commentsLoading ? <Loader2 size={15} className="animate-spin text-primary" /> : null}
                  </div>
                  {comments.length === 0 && !commentsLoading ? (
                    <div className="px-4 py-8 text-center text-sm text-on-surface-variant">{t('case_comments_empty')}</div>
                  ) : null}
                  <div className="max-h-72 overflow-y-auto">
                    {comments.map((comment) => (
                      <div key={comment.id} className="grid grid-cols-[minmax(0,1fr)_44px] gap-3 border-b border-white/10 px-4 py-3">
                        <div className="min-w-0">
                          <div className="mb-1 flex flex-wrap items-center gap-2">
                            <span className="truncate text-xs font-bold text-white">{comment.author || '--'}</span>
                            <span className="border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-widest text-on-surface-variant">
                              {statusLabel(comment.status, t)}
                            </span>
                            <span className="text-[10px] text-on-surface-variant">{formatDate(comment.created_at)}</span>
                          </div>
                          <div className="text-sm leading-6 text-on-surface-variant">{comment.body}</div>
                        </div>
                        <button
                          className="flex h-10 w-10 items-center justify-center border border-secondary/30 text-secondary transition-colors hover:bg-secondary/10 disabled:opacity-35"
                          disabled={deletingCommentId === comment.id || comment.status === 'deleted'}
                          title={t('case_admin_delete_comment')}
                          type="button"
                          onClick={() => handleDeleteComment(comment.id)}
                        >
                          {deletingCommentId === comment.id ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border border-secondary/25 bg-secondary/5 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-secondary">{t('case_admin_delete_case')}</div>
                    <button
                      className="flex h-9 items-center gap-2 border border-secondary/35 px-3 text-[10px] font-bold uppercase tracking-widest text-secondary transition-colors hover:bg-secondary/10 disabled:opacity-35"
                      disabled={selectedCase.status === 'deleted' || deletingCase}
                      type="button"
                      onClick={() => setDeleteConfirmOpen(true)}
                    >
                      <Trash2 size={13} />
                      {t('case_admin_delete_case')}
                    </button>
                  </div>
                  {deleteConfirmOpen ? (
                    <div className="border border-secondary/35 bg-black/25 p-3">
                      <div className="text-sm font-bold text-white">{t('case_admin_delete_confirm_title')}</div>
                      <p className="mt-2 text-xs leading-5 text-on-surface-variant">{t('case_admin_delete_confirm_body')}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          className="h-9 border border-white/15 px-3 text-[10px] uppercase tracking-widest text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
                          disabled={deletingCase}
                          type="button"
                          onClick={() => setDeleteConfirmOpen(false)}
                        >
                          {t('history_delete_confirm_cancel')}
                        </button>
                        <button
                          className="flex h-9 items-center gap-2 border border-secondary bg-secondary px-3 text-[10px] font-bold uppercase tracking-widest text-white transition-colors hover:bg-white hover:text-black disabled:opacity-50"
                          disabled={deletingCase}
                          type="button"
                          onClick={handleDeleteCase}
                        >
                          {deletingCase ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                          {t('case_admin_delete_confirm_action')}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>

                {dialogError ? (
                  <div className="border border-secondary/30 bg-secondary/10 px-4 py-3 text-sm text-secondary">{dialogError}</div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
