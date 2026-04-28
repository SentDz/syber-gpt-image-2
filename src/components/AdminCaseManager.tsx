import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import { Edit3, ImageIcon, Loader2, MessageSquare, Plus, RefreshCw, Save, Search, Trash2 } from 'lucide-react';
import {
  CaseComment,
  CaseItem,
  createAdminCase,
  createAdminComment,
  deleteAdminCase,
  deleteCaseComment,
  formatDate,
  listAdminCases,
  listAdminComments,
  updateAdminCase,
  updateCaseComment,
} from '../api';
import { useSite } from '../site';

type CaseStatus = CaseItem['status'];
type CommentStatus = CaseComment['status'];

type CaseForm = {
  title: string;
  author: string;
  prompt: string;
  image_url: string;
  image_path: string;
  model: string;
  size: string;
  aspect_ratio: string;
  quality: string;
  status: CaseStatus;
};

type CommentForm = {
  case_id: string;
  author: string;
  body: string;
  status: CommentStatus;
};

const EMPTY_CASE_FORM: CaseForm = {
  title: '',
  author: '',
  prompt: '',
  image_url: '',
  image_path: '',
  model: 'gpt-image-2',
  size: '',
  aspect_ratio: '',
  quality: '',
  status: 'visible',
};

const EMPTY_COMMENT_FORM: CommentForm = {
  case_id: '',
  author: '',
  body: '',
  status: 'visible',
};

const STATUS_OPTIONS: CaseStatus[] = ['visible', 'hidden', 'deleted'];
const COMMENT_STATUS_OPTIONS: CommentStatus[] = ['visible', 'hidden', 'deleted'];

export default function AdminCaseManager() {
  const { t } = useSite();
  const [activeTab, setActiveTab] = useState<'cases' | 'comments'>('cases');
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [comments, setComments] = useState<CaseComment[]>([]);
  const [caseQuery, setCaseQuery] = useState('');
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [caseForm, setCaseForm] = useState<CaseForm>(EMPTY_CASE_FORM);
  const [commentForm, setCommentForm] = useState<CommentForm>(EMPTY_COMMENT_FORM);
  const [editingCommentId, setEditingCommentId] = useState('');
  const [commentEditBody, setCommentEditBody] = useState('');
  const [commentEditStatus, setCommentEditStatus] = useState<CommentStatus>('visible');
  const [loadingCases, setLoadingCases] = useState(false);
  const [loadingComments, setLoadingComments] = useState(false);
  const [savingCase, setSavingCase] = useState(false);
  const [savingComment, setSavingComment] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) || null,
    [cases, selectedCaseId],
  );

  async function refreshCases(nextQuery = caseQuery) {
    setLoadingCases(true);
    setError('');
    try {
      const result = await listAdminCases({ limit: 80, q: nextQuery.trim() });
      setCases(result.items);
      if (selectedCaseId && !result.items.some((item) => item.id === selectedCaseId)) {
        setSelectedCaseId('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingCases(false);
    }
  }

  async function refreshComments() {
    setLoadingComments(true);
    setError('');
    try {
      const result = await listAdminComments({ limit: 100 });
      setComments(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingComments(false);
    }
  }

  useEffect(() => {
    refreshCases('').catch(() => undefined);
    refreshComments().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!commentForm.case_id && selectedCaseId) {
      setCommentForm((current) => ({ ...current, case_id: selectedCaseId }));
    }
  }, [commentForm.case_id, selectedCaseId]);

  function setCaseField<Key extends keyof CaseForm>(key: Key, value: CaseForm[Key]) {
    setCaseForm((current) => ({ ...current, [key]: value }));
  }

  function setCommentField<Key extends keyof CommentForm>(key: Key, value: CommentForm[Key]) {
    setCommentForm((current) => ({ ...current, [key]: value }));
  }

  function startNewCase() {
    setSelectedCaseId('');
    setCaseForm(EMPTY_CASE_FORM);
    setMessage('');
    setError('');
  }

  function startEditCase(item: CaseItem) {
    setSelectedCaseId(item.id);
    setCaseForm({
      title: item.title || '',
      author: item.author || '',
      prompt: item.prompt || '',
      image_url: item.image_url || '',
      image_path: item.image_path || '',
      model: item.model || '',
      size: item.size || '',
      aspect_ratio: item.aspect_ratio || '',
      quality: item.quality || '',
      status: item.status,
    });
    setCommentForm((current) => ({ ...current, case_id: item.id }));
    setMessage('');
    setError('');
  }

  async function handleSaveCase(event: FormEvent) {
    event.preventDefault();
    const payload = {
      title: caseForm.title.trim(),
      author: caseForm.author.trim() || undefined,
      prompt: caseForm.prompt.trim(),
      image_url: caseForm.image_url.trim() || undefined,
      image_path: caseForm.image_path.trim() || undefined,
      model: caseForm.model.trim(),
      size: caseForm.size.trim(),
      aspect_ratio: caseForm.aspect_ratio.trim(),
      quality: caseForm.quality.trim(),
      status: caseForm.status,
    };
    if (!payload.title || !payload.prompt || (!payload.image_url && !payload.image_path)) {
      setError(t('case_admin_required'));
      return;
    }
    setSavingCase(true);
    setError('');
    setMessage('');
    try {
      const saved = selectedCaseId
        ? await updateAdminCase(selectedCaseId, payload)
        : await createAdminCase({ ...payload, title: payload.title, prompt: payload.prompt });
      setSelectedCaseId(saved.id);
      startEditCase(saved);
      await refreshCases(caseQuery);
      setMessage(t('case_admin_saved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingCase(false);
    }
  }

  async function handleDeleteCase(item: CaseItem) {
    setSavingCase(true);
    setError('');
    setMessage('');
    try {
      const deleted = await deleteAdminCase(item.id);
      setCases((current) => current.map((caseItem) => (caseItem.id === deleted.id ? deleted : caseItem)));
      if (selectedCaseId === item.id) {
        startEditCase(deleted);
      }
      setMessage(t('case_admin_saved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingCase(false);
    }
  }

  async function handleCreateComment(event: FormEvent) {
    event.preventDefault();
    if (!commentForm.case_id || !commentForm.body.trim()) {
      setError(t('case_admin_comment_required'));
      return;
    }
    setSavingComment(true);
    setError('');
    setMessage('');
    try {
      await createAdminComment({
        case_id: commentForm.case_id,
        author: commentForm.author.trim() || undefined,
        body: commentForm.body.trim(),
        status: commentForm.status,
      });
      setCommentForm((current) => ({ ...EMPTY_COMMENT_FORM, case_id: current.case_id }));
      await refreshComments();
      await refreshCases(caseQuery);
      setMessage(t('case_admin_saved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingComment(false);
    }
  }

  function startEditComment(comment: CaseComment) {
    setEditingCommentId(comment.id);
    setCommentEditBody(comment.body);
    setCommentEditStatus(comment.status);
  }

  async function handleUpdateComment(commentId: string) {
    if (!commentEditBody.trim()) {
      setError(t('case_admin_comment_required'));
      return;
    }
    setSavingComment(true);
    setError('');
    setMessage('');
    try {
      const updated = await updateCaseComment(commentId, {
        body: commentEditBody.trim(),
        status: commentEditStatus,
      });
      setComments((current) => current.map((comment) => (comment.id === updated.id ? updated : comment)));
      setEditingCommentId('');
      await refreshCases(caseQuery);
      setMessage(t('case_admin_saved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingComment(false);
    }
  }

  async function handleDeleteComment(commentId: string) {
    setSavingComment(true);
    setError('');
    setMessage('');
    try {
      const deleted = await deleteCaseComment(commentId);
      setComments((current) => current.map((comment) => (comment.id === deleted.id ? deleted : comment)));
      await refreshCases(caseQuery);
      setMessage(t('case_admin_saved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingComment(false);
    }
  }

  return (
    <section className="col-span-12 border border-primary/20 bg-black p-6 md:p-8">
      <div className="mb-6 flex flex-col gap-4 border-b border-white/10 pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-primary">
            <ImageIcon size={15} />
            {t('case_admin_title')}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 md:w-80">
          <button
            className={`h-10 border px-3 text-xs font-bold uppercase tracking-widest transition-colors ${
              activeTab === 'cases' ? 'border-primary bg-primary/12 text-primary' : 'border-white/10 bg-white/5 text-white/50 hover:text-white'
            }`}
            type="button"
            onClick={() => setActiveTab('cases')}
          >
            {t('case_admin_cases_tab')}
          </button>
          <button
            className={`h-10 border px-3 text-xs font-bold uppercase tracking-widest transition-colors ${
              activeTab === 'comments' ? 'border-secondary bg-secondary/12 text-secondary' : 'border-white/10 bg-white/5 text-white/50 hover:text-white'
            }`}
            type="button"
            onClick={() => setActiveTab('comments')}
          >
            {t('case_admin_comments')}
          </button>
        </div>
      </div>

      {(error || message) && (
        <div className={`mb-5 border p-3 text-xs ${error ? 'border-error/40 bg-error/10 text-error' : 'border-tertiary/40 bg-tertiary/10 text-tertiary'}`}>
          {error || message}
        </div>
      )}

      {activeTab === 'cases' ? (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)]">
          <div className="min-w-0">
            <div className="mb-4 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-primary/40" size={15} />
                <input
                  className="input-cyber pl-10"
                  value={caseQuery}
                  onChange={(event) => setCaseQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') refreshCases().catch(() => undefined);
                  }}
                  placeholder={t('history_search')}
                />
              </div>
              <button
                className="flex h-11 w-11 shrink-0 items-center justify-center border border-primary/30 text-primary hover:bg-primary/10 disabled:opacity-50"
                type="button"
                onClick={() => refreshCases().catch(() => undefined)}
                disabled={loadingCases}
                title={t('case_admin_refresh')}
              >
                {loadingCases ? <Loader2 className="animate-spin" size={15} /> : <RefreshCw size={15} />}
              </button>
            </div>

            <div className="max-h-[720px] overflow-y-auto border border-white/10">
              {cases.length === 0 ? (
                <div className="p-6 text-sm text-white/40">{t('case_admin_empty')}</div>
              ) : (
                cases.map((item) => (
                  <button
                    key={item.id}
                    className={`grid w-full grid-cols-[64px_1fr] gap-3 border-b border-white/10 p-3 text-left transition-colors last:border-b-0 ${
                      selectedCaseId === item.id ? 'bg-primary/10' : 'bg-white/[0.02] hover:bg-white/[0.05]'
                    }`}
                    type="button"
                    onClick={() => startEditCase(item)}
                  >
                    <div className="flex h-16 w-16 items-center justify-center overflow-hidden border border-white/10 bg-black">
                      {item.image_url ? (
                        <img alt={item.title} className="h-full w-full object-cover" src={item.image_url} />
                      ) : (
                        <ImageIcon size={18} className="text-white/25" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <div className="truncate text-sm font-bold text-white">{item.title}</div>
                        <StatusBadge status={item.status} label={caseStatusLabel(item.status, t)} />
                      </div>
                      <div className="mb-2 line-clamp-2 text-xs leading-5 text-white/45">{item.prompt}</div>
                      <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-widest text-white/30">
                        <span>{item.source_type}</span>
                        <span>{item.like_count} LIKE</span>
                        <span>{item.comment_count} COMMENT</span>
                        <span>{formatDate(item.updated_at)}</span>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <form className="min-w-0 border border-white/10 bg-white/[0.02] p-5" onSubmit={handleSaveCase}>
            <div className="mb-5 flex items-center justify-between gap-3 border-b border-white/10 pb-4">
              <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-secondary">
                {selectedCase ? <Edit3 size={14} /> : <Plus size={14} />}
                {selectedCase ? t('case_admin_edit') : t('case_admin_create')}
              </div>
              <button className="text-[10px] uppercase tracking-widest text-primary hover:text-white" type="button" onClick={startNewCase}>
                {t('case_admin_new')}
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <AdminField label={t('case_title')}>
                <input className="input-cyber" value={caseForm.title} onChange={(event) => setCaseField('title', event.target.value)} />
              </AdminField>
              <AdminField label={t('case_author')}>
                <input className="input-cyber" value={caseForm.author} onChange={(event) => setCaseField('author', event.target.value)} />
              </AdminField>
              <AdminField label={t('case_image_url')}>
                <input className="input-cyber" value={caseForm.image_url} onChange={(event) => setCaseField('image_url', event.target.value)} />
              </AdminField>
              <AdminField label={t('case_image_path')}>
                <input className="input-cyber" value={caseForm.image_path} onChange={(event) => setCaseField('image_path', event.target.value)} />
              </AdminField>
              <AdminField label={t('config_model')}>
                <input className="input-cyber" value={caseForm.model} onChange={(event) => setCaseField('model', event.target.value)} />
              </AdminField>
              <AdminField label={t('case_status')}>
                <select className="input-cyber" value={caseForm.status} onChange={(event) => setCaseField('status', event.target.value as CaseStatus)}>
                  {STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {caseStatusLabel(status, t)}
                    </option>
                  ))}
                </select>
              </AdminField>
              <AdminField label={t('config_size')}>
                <input className="input-cyber" value={caseForm.size} onChange={(event) => setCaseField('size', event.target.value)} />
              </AdminField>
              <AdminField label={t('home_aspect_ratio')}>
                <input className="input-cyber" value={caseForm.aspect_ratio} onChange={(event) => setCaseField('aspect_ratio', event.target.value)} />
              </AdminField>
              <AdminField label={t('home_quality')}>
                <input className="input-cyber" value={caseForm.quality} onChange={(event) => setCaseField('quality', event.target.value)} />
              </AdminField>
            </div>

            <div className="mt-4">
              <AdminField label={t('case_prompt')}>
                <textarea className="input-cyber min-h-36 resize-y" value={caseForm.prompt} onChange={(event) => setCaseField('prompt', event.target.value)} />
              </AdminField>
            </div>

            <div className="mt-5 flex flex-col gap-3 border-t border-white/10 pt-5 sm:flex-row sm:justify-end">
              {selectedCase ? (
                <button
                  className="flex h-11 items-center justify-center gap-2 border border-error/30 px-5 text-xs font-bold uppercase tracking-widest text-error hover:bg-error/10 disabled:opacity-50"
                  type="button"
                  onClick={() => handleDeleteCase(selectedCase)}
                  disabled={savingCase}
                >
                  <Trash2 size={14} />
                  {t('history_delete')}
                </button>
              ) : null}
              <button
                className="flex h-11 items-center justify-center gap-2 bg-secondary px-6 text-xs font-bold uppercase tracking-widest text-white hover:bg-white hover:text-black disabled:opacity-50"
                type="submit"
                disabled={savingCase}
              >
                {savingCase ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />}
                {selectedCase ? t('case_admin_update') : t('case_admin_create')}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(360px,0.85fr)_minmax(0,1.15fr)]">
          <form className="border border-white/10 bg-white/[0.02] p-5" onSubmit={handleCreateComment}>
            <div className="mb-5 flex items-center gap-2 border-b border-white/10 pb-4 text-[10px] font-bold uppercase tracking-widest text-secondary">
              <MessageSquare size={14} />
              {t('case_admin_add_comment')}
            </div>
            <div className="space-y-4">
              <AdminField label={t('case_title')}>
                <select className="input-cyber" value={commentForm.case_id} onChange={(event) => setCommentField('case_id', event.target.value)}>
                  <option value="">{t('case_admin_select_case')}</option>
                  {cases
                    .filter((item) => item.status !== 'deleted')
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title}
                      </option>
                    ))}
                </select>
              </AdminField>
              <AdminField label={t('case_author')}>
                <input className="input-cyber" value={commentForm.author} onChange={(event) => setCommentField('author', event.target.value)} />
              </AdminField>
              <AdminField label={t('case_status')}>
                <select className="input-cyber" value={commentForm.status} onChange={(event) => setCommentField('status', event.target.value as CommentStatus)}>
                  {COMMENT_STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {caseStatusLabel(status, t)}
                    </option>
                  ))}
                </select>
              </AdminField>
              <AdminField label={t('case_comment_body')}>
                <textarea className="input-cyber min-h-32 resize-y" value={commentForm.body} onChange={(event) => setCommentField('body', event.target.value)} />
              </AdminField>
            </div>
            <button
              className="mt-5 flex h-11 w-full items-center justify-center gap-2 bg-primary px-5 text-xs font-bold uppercase tracking-widest text-black hover:bg-white disabled:opacity-50"
              type="submit"
              disabled={savingComment}
            >
              {savingComment ? <Loader2 className="animate-spin" size={14} /> : <Plus size={14} />}
              {t('case_admin_add_comment')}
            </button>
          </form>

          <div className="min-w-0">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="text-[10px] font-bold uppercase tracking-widest text-primary">{t('case_admin_comments')}</div>
              <button
                className="flex h-10 items-center gap-2 border border-primary/30 px-4 text-xs uppercase tracking-widest text-primary hover:bg-primary/10 disabled:opacity-50"
                type="button"
                onClick={() => refreshComments().catch(() => undefined)}
                disabled={loadingComments}
              >
                {loadingComments ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />}
                {t('case_admin_refresh')}
              </button>
            </div>

            <div className="max-h-[720px] overflow-y-auto border border-white/10">
              {comments.length === 0 ? (
                <div className="p-6 text-sm text-white/40">{t('case_comments_empty')}</div>
              ) : (
                comments.map((comment) => (
                  <div key={comment.id} className="border-b border-white/10 bg-white/[0.02] p-4 last:border-b-0">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-bold text-white">{comment.case_title || comment.case_id}</div>
                        <div className="mt-1 flex flex-wrap gap-2 text-[10px] uppercase tracking-widest text-white/35">
                          <span>{comment.author || t('top_owner')}</span>
                          <span>{formatDate(comment.updated_at)}</span>
                        </div>
                      </div>
                      <StatusBadge status={comment.status} label={caseStatusLabel(comment.status, t)} />
                    </div>

                    {editingCommentId === comment.id ? (
                      <div className="space-y-3">
                        <textarea className="input-cyber min-h-24 resize-y" value={commentEditBody} onChange={(event) => setCommentEditBody(event.target.value)} />
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto]">
                          <select className="input-cyber" value={commentEditStatus} onChange={(event) => setCommentEditStatus(event.target.value as CommentStatus)}>
                            {COMMENT_STATUS_OPTIONS.map((status) => (
                              <option key={status} value={status}>
                                {caseStatusLabel(status, t)}
                              </option>
                            ))}
                          </select>
                          <button className="h-11 border border-white/15 px-4 text-xs uppercase tracking-widest text-white/60 hover:text-white" type="button" onClick={() => setEditingCommentId('')}>
                            {t('case_admin_cancel_edit')}
                          </button>
                          <button
                            className="flex h-11 items-center justify-center gap-2 bg-secondary px-4 text-xs font-bold uppercase tracking-widest text-white hover:bg-white hover:text-black disabled:opacity-50"
                            type="button"
                            onClick={() => handleUpdateComment(comment.id)}
                            disabled={savingComment}
                          >
                            {savingComment ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />}
                            {t('case_admin_update')}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="whitespace-pre-wrap text-sm leading-6 text-white/70">{comment.body}</p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            className="flex h-9 items-center gap-2 border border-primary/30 px-3 text-[10px] uppercase tracking-widest text-primary hover:bg-primary/10"
                            type="button"
                            onClick={() => startEditComment(comment)}
                          >
                            <Edit3 size={12} />
                            {t('case_admin_edit')}
                          </button>
                          <button
                            className="flex h-9 items-center gap-2 border border-error/30 px-3 text-[10px] uppercase tracking-widest text-error hover:bg-error/10 disabled:opacity-50"
                            type="button"
                            onClick={() => handleDeleteComment(comment.id)}
                            disabled={savingComment || comment.status === 'deleted'}
                          >
                            <Trash2 size={12} />
                            {t('history_delete')}
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function AdminField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-white/40">{label}</span>
      {children}
    </label>
  );
}

function StatusBadge({ status, label }: { status: CaseStatus | CommentStatus; label: string }) {
  const className =
    status === 'visible'
      ? 'border-tertiary/35 bg-tertiary/10 text-tertiary'
      : status === 'hidden'
        ? 'border-primary/30 bg-primary/10 text-primary'
        : 'border-error/35 bg-error/10 text-error';
  return (
    <span className={`shrink-0 border px-2 py-1 text-[9px] uppercase tracking-widest ${className}`}>
      {label}
    </span>
  );
}

function caseStatusLabel(status: CaseStatus | CommentStatus, t: ReturnType<typeof useSite>['t']) {
  if (status === 'visible') return t('case_status_visible');
  if (status === 'hidden') return t('case_status_hidden');
  return t('case_status_deleted');
}
