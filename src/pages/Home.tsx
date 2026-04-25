import { useCallback, useEffect, useRef, useState } from 'react';
import { ImagePlus, Grid, List, Maximize2, RefreshCw, Loader2, X } from 'lucide-react';
import { editImage, generateImage, getHistory, getInspirations, getInspirationStats, HistoryItem, InspirationItem } from '../api';
import { useAuth } from '../auth';
import ImagePreviewModal from '../components/ImagePreviewModal';
import { useSite } from '../site';
import { useTasks } from '../tasks';

const FEED_PAGE_SIZE = 24;

function mergeHistory(items: HistoryItem[]) {
  const merged = new Map<string, HistoryItem>();
  for (const item of items) {
    merged.set(item.id, item);
  }
  return [...merged.values()].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

export default function Home() {
  const { viewer } = useAuth();
  const { t } = useSite();
  const { addTask, openDrawer, taskHistoryItems } = useTasks();
  const [promptValue, setPromptValue] = useState('');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [inspirations, setInspirations] = useState<InspirationItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewItem, setPreviewItem] = useState<{ imageUrl: string; prompt: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [feedLoading, setFeedLoading] = useState(true);
  const [loadingMoreFeed, setLoadingMoreFeed] = useState(false);
  const [hasMoreInspirations, setHasMoreInspirations] = useState(true);
  const [inspirationOffset, setInspirationOffset] = useState(0);
  const [inspirationTotal, setInspirationTotal] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setFeedLoading(true);
    setLoadingMoreFeed(false);
    setHasMoreInspirations(true);
    setInspirationOffset(0);
    setInspirationTotal(0);
    setInspirations([]);
    setError('');
    const task = Promise.all([
      getHistory({ limit: 12 }),
      getInspirations({ limit: FEED_PAGE_SIZE, offset: 0 }),
      getInspirationStats(),
    ]);
    task
      .then(([historyData, inspirationData, statsData]) => {
        if (cancelled) return;
        setHistory(historyData.items.filter((item) => item.status === 'succeeded' && Boolean(item.image_url)));
        setInspirations(inspirationData.items);
        const nextTotal = Number(statsData.total || inspirationData.items.length || 0);
        setInspirationTotal(nextTotal);
        setInspirationOffset(inspirationData.items.length);
        setHasMoreInspirations(inspirationData.items.length < nextTotal);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setFeedLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [viewer?.owner_id]);

  const loadMoreInspirations = useCallback(async () => {
    if (feedLoading || loadingMoreFeed || !hasMoreInspirations) {
      return;
    }
    setLoadingMoreFeed(true);
    try {
      const data = await getInspirations({ limit: FEED_PAGE_SIZE, offset: inspirationOffset });
      setInspirations((current) => {
        const seen = new Set(current.map((item) => item.id));
        const nextItems = data.items.filter((item) => !seen.has(item.id));
        return [...current, ...nextItems];
      });
      const nextOffset = inspirationOffset + data.items.length;
      setInspirationOffset(nextOffset);
      setHasMoreInspirations(inspirationTotal > 0 ? nextOffset < inspirationTotal : data.items.length === FEED_PAGE_SIZE);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingMoreFeed(false);
    }
  }, [feedLoading, hasMoreInspirations, inspirationOffset, inspirationTotal, loadingMoreFeed]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || feedLoading || loadingMoreFeed || !hasMoreInspirations) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          loadMoreInspirations().catch(() => undefined);
        }
      },
      { rootMargin: '480px 0px', threshold: 0.01 },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [feedLoading, hasMoreInspirations, loadMoreInspirations, loadingMoreFeed]);

  async function handleExecute() {
    const prompt = promptValue.trim();
    if (!prompt || loading) return;
    setLoading(true);
    setError('');
    setMessage(selectedFile ? t('home_message_edit_sent') : t('home_message_generate_sent'));
    try {
      const submittedTask = selectedFile
        ? await editImage({ prompt }, selectedFile)
        : await generateImage({ prompt });
      addTask(submittedTask);
      openDrawer();
      setMessage(submittedTask.status === 'running' ? t('home_message_processing') : t('home_message_queued'));
      setSelectedFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage('');
    } finally {
      setLoading(false);
    }
  }

  const mergedHistory = mergeHistory([
    ...taskHistoryItems.filter((item) => item.status === 'succeeded' && Boolean(item.image_url)),
    ...history,
  ]);

  const generatedFeed = mergedHistory.map((item) => ({
        id: `ID:${item.id.slice(0, 4).toUpperCase()}`,
        img: item.image_url || '',
        prompt: item.prompt,
        title: item.mode.toUpperCase(),
      }));
  const inspirationFeed = inspirations.map((item) => ({
    id: item.author || item.section,
    img: item.image_url || '',
    prompt: item.prompt,
    title: item.title,
  }));
  const visibleFeed = [...generatedFeed, ...inspirationFeed].filter((item) => item.img);

  return (
    <div className="pt-24 pb-48 px-6 max-w-[1440px] mx-auto min-h-screen bg-[radial-gradient(ellipse_at_top,var(--color-surface-container-high),var(--color-background))] font-mono">
      <div className="flex justify-between items-end mb-8">
        <div className="flex flex-col gap-2">
           <div className="flex items-center gap-2 text-[10px] text-secondary uppercase font-bold tracking-widest">
              <span className="w-4 h-[1px] bg-secondary"></span> {t('home_scan')}
           </div>
          <h1 className="text-4xl md:text-5xl text-on-surface font-bold tracking-tighter">{t('home_title')}</h1>
          <div className="text-xs text-white/40 uppercase tracking-widest">
            {viewer?.authenticated
              ? t('home_owner', { value: viewer.user?.username || viewer.user?.email || '--' })
              : t('home_guest', { value: viewer?.guest_id?.slice(0, 8) || '--' })}
          </div>
        </div>
        <div className="hidden sm:flex gap-2">
          <button className="w-10 h-10 border border-outline-variant flex items-center justify-center text-outline-variant hover:text-primary hover:border-primary bg-surface-container-low transition-colors">
            <Grid size={20} />
          </button>
          <button className="w-10 h-10 border border-outline-variant flex items-center justify-center text-outline-variant hover:text-primary hover:border-primary bg-surface-container-low transition-colors">
            <List size={20} />
          </button>
        </div>
      </div>

      {error && <div className="mb-6 border border-error/40 bg-error/10 p-4 text-error text-xs">{error}</div>}

      {feedLoading ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={index} className="relative aspect-[3/4] overflow-hidden border border-primary/20 bg-black/60">
              <div className="absolute inset-0 animate-pulse bg-[linear-gradient(180deg,rgba(0,243,255,0.08),rgba(255,0,255,0.08))]" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.08),transparent_55%)]" />
              <div className="absolute bottom-0 left-0 right-0 p-4">
                <div className="mb-3 h-3 w-24 animate-pulse bg-white/10" />
                <div className="mb-2 h-4 w-full animate-pulse bg-white/10" />
                <div className="h-4 w-3/4 animate-pulse bg-white/10" />
              </div>
            </div>
          ))}
          <div className="col-span-full flex items-center justify-center gap-3 py-4 text-xs uppercase tracking-[0.3em] text-primary/70">
            <Loader2 className="animate-spin" size={16} />
            {t('home_loading_feed')}
          </div>
        </div>
      ) : visibleFeed.length > 0 ? (
        <>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {visibleFeed.map((item, index) => (
              <div
                key={`${item.id}-${index}`}
                className="relative group aspect-[3/4] border border-primary/30 overflow-hidden bg-black flex flex-col cursor-zoom-in"
                role="button"
                tabIndex={0}
                onClick={() => setPreviewItem({ imageUrl: item.img, prompt: item.prompt })}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setPreviewItem({ imageUrl: item.img, prompt: item.prompt });
                  }
                }}
              >
                <img
                  alt={item.id}
                  className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-all duration-500"
                  loading="lazy"
                  src={item.img}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent"></div>

                <button
                  className="absolute left-4 top-4 z-10 flex h-10 w-10 items-center justify-center border border-white/10 bg-black/45 text-white/70 opacity-0 backdrop-blur-sm transition-all duration-300 hover:border-primary hover:text-primary group-hover:opacity-100"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setPreviewItem({ imageUrl: item.img, prompt: item.prompt });
                  }}
                  title={t('history_preview')}
                >
                  <Maximize2 size={15} />
                </button>

                <div className="absolute top-4 right-4 z-10 font-code-data text-white/50 text-[10px] border border-white/20 px-2 py-1 bg-black/50 backdrop-blur-sm shadow-[0_0_10px_rgba(0,0,0,0.5)]">
                  {item.id}
                </div>

                <div className="absolute bottom-0 left-0 right-0 p-4 transform translate-y-8 group-hover:translate-y-0 transition-transform flex flex-col gap-3 backdrop-blur-sm bg-gradient-to-t from-black/90 to-transparent">
                  {'title' in item && item.title && <div className="text-[10px] text-secondary uppercase tracking-widest line-clamp-1">{item.title}</div>}
                  <p className="font-body-md text-white mb-2 line-clamp-3 text-sm">{item.prompt}</p>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      setPromptValue(item.prompt);
                    }}
                    className="pointer-events-none w-full translate-y-3 py-2 opacity-0 bg-primary text-black font-black text-xs uppercase shadow-[0_0_10px_rgba(0,243,255,0.5)] flex items-center justify-center gap-2 hover:bg-white hover:shadow-white/50 transition-all duration-300 group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100"
                  >
                    <RefreshCw size={14} />
                    {t('home_clone_prompt')}
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex flex-col items-center gap-4 py-8">
            {loadingMoreFeed ? (
              <div className="flex items-center justify-center gap-3 text-xs uppercase tracking-[0.3em] text-primary/70">
                <Loader2 className="animate-spin" size={16} />
                {t('home_loading_more')}
              </div>
            ) : hasMoreInspirations ? (
              <button
                className="border border-primary/30 bg-primary/5 px-6 py-3 text-xs font-bold uppercase tracking-[0.25em] text-primary transition-colors hover:bg-primary/10"
                type="button"
                onClick={() => loadMoreInspirations().catch(() => undefined)}
              >
                {t('home_load_more')}
              </button>
            ) : (
              <div className="text-xs uppercase tracking-[0.3em] text-white/35">{t('home_all_loaded')}</div>
            )}
            <div ref={loadMoreRef} className="h-2 w-full" />
          </div>
        </>
      ) : (
        <div className="flex min-h-[320px] items-center justify-center border border-primary/20 bg-black/50 px-6 text-sm text-white/50">
          {t('home_empty_feed')}
        </div>
      )}

      <div className="fixed bottom-6 left-6 right-6 md:left-auto md:right-auto md:w-[calc(100%-3rem)] max-w-[960px] mx-auto bg-surface-container/90 backdrop-blur-xl border border-primary/40 p-5 rounded-sm shadow-[0_-20px_40px_rgba(0,0,0,0.8)] z-50 font-mono">
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-2 text-[10px] text-white/50 border-r border-white/10 pr-4">
             <span className="w-2 h-2 bg-secondary rounded-full animate-pulse"></span> {t('home_mode')}: {selectedFile ? t('home_mode_edit') : t('home_mode_generate')}
          </div>
          <div className="text-[10px] text-primary uppercase tracking-widest truncate">
            {message || (promptValue ? t('home_message_loaded') : t('home_message_waiting'))}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 flex flex-col gap-2 relative">
            <textarea
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              className="w-full h-20 bg-black border border-primary/20 p-3 text-sm text-primary focus:outline-none focus:border-primary placeholder:text-primary/20 resize-none shadow-inner"
              placeholder={t('home_placeholder')}
            ></textarea>
            <div className="absolute top-0 right-0 p-2 text-[8px] text-primary/40 uppercase">
              UTF-8 // AI-GEN // [{promptValue.length}/8000]
            </div>
          </div>

          <div className="flex gap-4">
            <input
              ref={fileInputRef}
              className="hidden"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-20 md:w-24 h-20 border border-dashed border-primary/20 flex flex-col items-center justify-center cursor-pointer hover:bg-primary/5 transition-colors group relative"
            >
              {selectedFile ? (
                <>
                  <X className="w-5 h-5 mb-1 text-secondary" />
                  <span className="text-[9px] uppercase text-secondary px-1 truncate max-w-full">{selectedFile.name}</span>
                </>
              ) : (
                <>
                  <ImagePlus className="w-6 h-6 mb-1 text-white/30 group-hover:text-primary transition-colors" />
                  <span className="text-[9px] uppercase text-white/40 group-hover:text-primary">{t('home_ref_image')}</span>
                </>
              )}
            </button>
            <button
              onClick={handleExecute}
              disabled={loading || !promptValue.trim()}
              className="w-32 bg-primary text-black font-black flex flex-col items-center justify-center hover:scale-95 transition-transform shadow-[0_0_15px_rgba(0,243,255,0.4)] disabled:opacity-40 disabled:hover:scale-100"
            >
              {loading ? <Loader2 className="animate-spin" size={24} /> : <span className="text-xl mb-[-4px]">{t('home_execute')}</span>}
              <span className="text-[10px] opacity-70 italic">{selectedFile ? t('home_edit') : t('home_generate')}</span>
            </button>
          </div>
        </div>
      </div>

      <ImagePreviewModal
        imageUrl={previewItem?.imageUrl || null}
        alt={previewItem?.prompt || 'preview'}
        subtitle={previewItem?.prompt}
        onClose={() => setPreviewItem(null)}
      />
    </div>
  );
}
