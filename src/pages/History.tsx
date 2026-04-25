import { useEffect, useState } from 'react';
import { Search, Filter, Download, Trash2, RefreshCw, ArrowDown, Loader2, Maximize2 } from 'lucide-react';
import { deleteHistory, formatDate, generateImage, getHistory, HistoryItem } from '../api';
import { useAuth } from '../auth';
import ImagePreviewModal from '../components/ImagePreviewModal';
import { useSite } from '../site';
import { useTasks } from '../tasks';

function mergeHistory(items: HistoryItem[]) {
  const merged = new Map<string, HistoryItem>();
  for (const item of items) {
    merged.set(item.id, item);
  }
  return [...merged.values()].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

const getColorClasses = (colorMode: string) => {
  if (colorMode === 'primary') {
    return {
      borderHover: 'hover:border-primary/50',
      textId: 'text-primary',
      bgTag: 'bg-primary/10 border-primary/30',
      btnBg: 'bg-primary border-primary',
      btnText: 'text-black hover:text-white',
      btnShadow: 'shadow-[0_0_10px_rgba(0,243,255,0.5)]'
    };
  }
  return {
    borderHover: 'hover:border-secondary/50',
    textId: 'text-secondary',
    bgTag: 'bg-secondary/10 border-secondary/30',
    btnBg: 'bg-secondary border-secondary',
    btnText: 'text-white hover:text-black',
    btnShadow: 'shadow-[0_0_10px_rgba(255,0,255,0.5)]'
  };
};

export default function History() {
  const { viewer } = useAuth();
  const { t } = useSite();
  const { addTask, openDrawer, taskHistoryItems } = useTasks();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [removedIds, setRemovedIds] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [previewItem, setPreviewItem] = useState<HistoryItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load(nextOffset = 0, append = false) {
    setLoading(true);
    setError('');
    try {
      const data = await getHistory({ limit: 24, offset: nextOffset, q: query });
      setItems((current) => (append ? [...current, ...data.items] : data.items));
      if (!append) {
        setRemovedIds([]);
      }
      setOffset(nextOffset + data.items.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(0, false);
  }, [viewer?.owner_id]);

  async function handleDelete(id: string) {
    await deleteHistory(id);
    setItems((current) => current.filter((item) => item.id !== id));
    setRemovedIds((current) => (current.includes(id) ? current : [...current, id]));
  }

  async function handleRegenerate(item: HistoryItem) {
    setLoading(true);
    setError('');
    try {
      const submittedTask = await generateImage({ prompt: item.prompt, size: item.size, quality: item.quality });
      addTask(submittedTask);
      openDrawer();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const visibleItems = mergeHistory([...taskHistoryItems, ...items]).filter((item) => !removedIds.includes(item.id));

  return (
    <div className="md:ml-64 px-6 md:px-12 py-8 max-w-[1440px] mx-auto min-h-screen pt-24 pb-12 bg-[radial-gradient(ellipse_at_top,var(--color-surface-container-high),var(--color-background))] font-mono">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-10 gap-6 border-b border-white/10 pb-6">
        <div className="flex flex-col gap-2">
           <div className="flex items-center gap-2 text-[10px] text-primary uppercase font-bold tracking-widest">
              <span className="w-4 h-[1px] bg-primary"></span> {t('history_tag')}
           </div>
          <h1 className="text-4xl md:text-5xl text-on-surface font-bold tracking-tighter">{t('history_title')}</h1>
          <p className="text-white/50 text-sm">{t('history_subtitle')}</p>
        </div>

        <div className="flex gap-4 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-primary/50" size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') load(0, false);
              }}
              className="w-full bg-black border border-primary/20 focus:border-primary focus:ring-0 text-primary pl-10 py-2 font-code-data transition-colors placeholder:text-primary/20 outline-none text-xs shadow-inner"
              placeholder={t('history_search')}
              type="text"
            />
          </div>
          <button onClick={() => load(0, false)} className="bg-black border border-primary/20 p-2 hover:border-primary hover:bg-primary/5 transition-colors flex items-center justify-center">
            <Filter size={16} className="text-primary" />
          </button>
        </div>
      </div>

      {error && <div className="mb-6 border border-error/40 bg-error/10 p-4 text-error text-xs">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {visibleItems.map((item, index) => {
          const colors = getColorClasses(index % 2 === 0 ? 'primary' : 'secondary');
          return (
          <div
            key={item.id}
            className={`group relative aspect-[4/5] bg-black border border-white/10 overflow-hidden flex flex-col ${colors.borderHover} transition-all duration-300`}
          >
            <div className={`absolute top-3 right-3 z-10 px-2 py-1 border text-[9px] tracking-widest uppercase ${colors.textId} ${colors.bgTag} backdrop-blur-sm`}>
              ID:{item.id.slice(0, 4).toUpperCase()}
            </div>

            {item.image_url ? (
              <img
                alt={item.prompt}
                className="w-full h-full cursor-zoom-in object-cover opacity-80 transition-all duration-500 group-hover:opacity-100"
                src={item.image_url}
                onClick={() => setPreviewItem(item)}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-error/60 text-xs uppercase px-6 text-center">
                {item.error || t('history_failed')}
              </div>
            )}

            <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent opacity-100 flex flex-col justify-end p-5">
               <div className="flex justify-between items-center mb-4 translate-y-8 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">
                  <div className="flex items-center gap-2">
                    <button
                      className="w-8 h-8 rounded-none border border-white/20 bg-white/5 flex items-center justify-center text-white hover:text-primary hover:border-primary transition-all backdrop-blur-md"
                      type="button"
                      title={t('history_preview')}
                      onClick={() => setPreviewItem(item)}
                    >
                      <Maximize2 size={14} />
                    </button>
                    <a href={item.image_url || '#'} download className="w-8 h-8 rounded-none border border-white/20 bg-white/5 flex items-center justify-center text-white hover:text-primary hover:border-primary transition-all backdrop-blur-md" title={t('history_download')}>
                      <Download size={14} />
                    </a>
                  </div>
                  <button onClick={() => handleDelete(item.id)} className="w-8 h-8 rounded-none border border-error/20 bg-error/5 flex items-center justify-center text-error hover:bg-error/20 transition-all backdrop-blur-md" title={t('history_delete')}>
                    <Trash2 size={14} />
                  </button>
               </div>

               <div>
                  <p className={`text-sm text-on-surface line-clamp-2 mb-2 ${colors.textId} transition-colors min-h-[40px]`}>
                    {item.prompt}
                  </p>
                  <div className="flex items-center gap-3 text-white/40 text-[10px] uppercase tracking-wider mt-2 mb-4 font-bold">
                    <span>{formatDate(item.created_at)}</span>
                    <span className="w-1 h-1 rounded-full bg-white/20"></span>
                    <span>{item.size}</span>
                  </div>
               </div>

               <button
                 onClick={() => handleRegenerate(item)}
                 className={`pointer-events-none w-full translate-y-6 py-3 opacity-0 ${colors.btnBg} ${colors.btnText} font-black text-xs uppercase flex items-center justify-center gap-2 ${colors.btnShadow} transition-all duration-300 hover:bg-white hover:border-white shadow-white/50 group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100`}
               >
                 <RefreshCw size={14} />
                 {t('history_regenerate')}
               </button>
            </div>
          </div>
          );
        })}
      </div>

      <div className="mt-12 flex justify-center">
        <button
          onClick={() => load(offset, true)}
          disabled={loading}
          className="border border-primary/30 hover:border-primary text-primary px-8 py-3 uppercase tracking-widest transition-colors flex items-center gap-2 text-xs bg-primary/5 shadow-[0_0_15px_rgba(0,243,255,0.1)] disabled:opacity-50"
        >
          {loading ? <Loader2 className="animate-spin" size={14} /> : <ArrowDown size={14} />}
          {t('history_load_more')}
        </button>
      </div>

      <ImagePreviewModal
        imageUrl={previewItem?.image_url || null}
        alt={previewItem?.prompt || 'preview'}
        subtitle={previewItem?.prompt}
        onClose={() => setPreviewItem(null)}
      />
    </div>
  );
}
