import { Link, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Bell, ListTodo, LogOut } from 'lucide-react';
import { AccountInfo, formatBalance, getAccount, logoutAccount } from '../api';
import { useAuth } from '../auth';
import { useSite } from '../site';
import { useTasks } from '../tasks';
import AvatarBadge from './AvatarBadge';
import jokoLogo from '../../joko.svg';

export default function TopNavBar() {
  const location = useLocation();
  const { viewer, refresh } = useAuth();
  const { siteSettings, openAnnouncement, t } = useSite();
  const { activeCount, openDrawer } = useTasks();
  const [account, setAccount] = useState<AccountInfo | null>(null);

  useEffect(() => {
    getAccount().then(setAccount).catch(() => setAccount(null));
  }, [viewer?.owner_id]);

  async function handleLogout() {
    try {
      await logoutAccount();
    } finally {
      await refresh();
      const refreshed = await getAccount().catch(() => null);
      setAccount(refreshed);
      window.location.href = '/';
    }
  }

  const viewerLabel = viewer?.authenticated
    ? (viewer.user?.username || viewer.user?.email || 'USER')
    : t('home_guest', { value: viewer?.guest_id?.slice(0, 8) || '--' });
  const rechargeUrl = 'https://ai.get-money.locker';

  return (
    <header className="fixed top-0 left-0 w-full z-[100] flex justify-between items-center px-6 h-16 bg-surface-bright border-b border-primary/30 shadow-[0_0_20px_rgba(0,243,255,0.1)] shrink-0 font-mono">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-4">
          <img alt="joko-image" className="h-10 w-10 rounded-sm object-contain" src={jokoLogo} />
          <div className="flex flex-col gap-1">
            <Link to="/" className="text-2xl font-black tracking-tighter text-white hover:text-primary transition-colors">
              joko-<span className="text-secondary">image</span>
            </Link>
            <div className="w-fit border border-secondary/30 bg-secondary/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.25em] text-secondary">
              JOKO-AI
            </div>
          </div>
        </div>
        <nav className="hidden md:flex gap-6">
          <Link
            to="/history"
            className={`text-xs uppercase tracking-widest font-bold px-3 py-2 transition-all duration-300 hover:bg-primary/10 hover:text-primary ${
              location.pathname === '/history' ? 'text-primary border-b-2 border-primary' : 'text-on-surface-variant'
            }`}
          >
            {t('top_history')}
          </Link>
          {!viewer?.authenticated && (
            <Link
              to="/register"
              className={`text-xs uppercase tracking-widest font-bold px-3 py-2 transition-all duration-300 hover:bg-primary/10 hover:text-primary ${
                location.pathname === '/register' ? 'text-primary border-b-2 border-primary' : 'text-on-surface-variant'
              }`}
            >
              {t('top_register')}
            </Link>
          )}
        </nav>
      </div>
      <div className="flex items-center gap-4 md:gap-6">
        <div className="hidden md:flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase text-on-surface-variant">{t('top_owner')}</span>
            <span className="text-xs text-tertiary">{viewerLabel}</span>
          </div>
          <div className="h-10 px-4 bg-surface-container-highest border border-primary/20 flex items-center gap-3 rounded-tr-xl">
            <span className="text-xs uppercase text-on-surface-variant">{t('top_credits')}</span>
            <span className="font-bold text-lg text-secondary">⚡ {formatBalance(account?.balance)}</span>
            <Link to="/billing" className="ml-2 px-3 py-1 bg-secondary text-white text-[10px] font-bold uppercase hover:bg-secondary/80 transition-colors shadow-[0_0_10px_rgba(255,0,255,0.3)]">
              {t('top_ledger')}
            </Link>
          </div>
        </div>

        <button
          className="relative flex h-10 w-10 items-center justify-center border border-primary/20 text-primary transition-colors hover:bg-primary/10"
          type="button"
          onClick={openDrawer}
          title={t('top_tasks')}
        >
          <ListTodo size={16} />
          {activeCount > 0 ? (
            <span className="absolute -right-1 -top-1 min-w-[18px] rounded-full bg-secondary px-1.5 py-0.5 text-[9px] font-bold text-white">
              {activeCount}
            </span>
          ) : null}
        </button>

        <button
          className="relative flex h-10 w-10 items-center justify-center border border-primary/20 text-primary transition-colors hover:bg-primary/10"
          type="button"
          onClick={openAnnouncement}
          title={t('top_announcement')}
        >
          <Bell size={16} />
          {siteSettings?.announcement.enabled ? <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-secondary" /> : null}
        </button>

        <a
          className="flex h-10 items-center border border-primary/30 px-4 text-[10px] font-bold uppercase tracking-widest text-primary transition-colors hover:bg-primary/10"
          href={rechargeUrl}
          rel="noreferrer"
          target="_blank"
        >
          {t('top_recharge')}
        </a>

        {viewer?.authenticated ? (
          <button
            className="h-10 px-4 border border-secondary/40 text-secondary text-[10px] uppercase tracking-widest hover:bg-secondary/10 transition-colors flex items-center gap-2"
            type="button"
            onClick={handleLogout}
          >
            <LogOut size={14} />
            {t('top_logout')}
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <Link className="h-10 px-4 border border-primary/30 text-primary text-[10px] uppercase tracking-widest hover:bg-primary/10 transition-colors flex items-center" to="/login">
              {t('top_login')}
            </Link>
            <Link className="h-10 px-4 bg-secondary text-white text-[10px] font-bold uppercase tracking-widest hover:bg-white hover:text-black transition-colors flex items-center" to="/register">
              {t('top_register')}
            </Link>
          </div>
        )}

        <Link to="/config" className="cursor-pointer hover:border-primary transition-colors shadow-[0_0_8px_rgba(255,0,255,0.2)]">
          <AvatarBadge
            className="w-10 h-10 rounded-full border-2"
            textClassName="text-xs"
            name={viewer?.user?.username}
            email={viewer?.user?.email}
            guestId={viewer?.guest_id}
          />
        </Link>
      </div>
    </header>
  );
}
