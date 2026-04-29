import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { HistoryItem, ImageTask, listImageTasks } from './api';
import { useAuth } from './auth';

export type TaskToast = {
  id: string;
  taskId: string;
  status: 'succeeded' | 'failed';
  prompt: string;
  createdAt: number;
  error: string | null;
};

type TaskCenterValue = {
  tasks: ImageTask[];
  activeCount: number;
  drawerOpen: boolean;
  taskHistoryItems: HistoryItem[];
  toasts: TaskToast[];
  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  addTask: (task: ImageTask) => void;
  removeHistoryItem: (historyId: string) => void;
  refreshTasks: () => Promise<void>;
  dismissToast: (toastId: string) => void;
};

const TASK_FETCH_LIMIT = 20;
const TASK_POLL_INTERVAL_MS = 5000;

const TaskCenterContext = createContext<TaskCenterValue | null>(null);

function sortTasks(tasks: ImageTask[]) {
  return [...tasks].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

function mergeTasks(current: ImageTask[], incoming: ImageTask[]) {
  const merged = new Map<string, ImageTask>();
  for (const task of current) {
    merged.set(task.id, task);
  }
  for (const task of incoming) {
    merged.set(task.id, task);
  }
  return sortTasks(Array.from(merged.values())).slice(0, TASK_FETCH_LIMIT);
}

function mergeHistoryItems(items: HistoryItem[]) {
  const merged = new Map<string, HistoryItem>();
  for (const item of items) {
    merged.set(item.id, item);
  }
  return [...merged.values()].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

function isCompletedTask(task: ImageTask): task is ImageTask & { status: TaskToast['status'] } {
  return task.status === 'succeeded' || task.status === 'failed';
}

export function TaskCenterProvider({ children }: { children: ReactNode }) {
  const { viewer } = useAuth();
  const [tasks, setTasks] = useState<ImageTask[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toasts, setToasts] = useState<TaskToast[]>([]);
  const tasksRef = useRef<ImageTask[]>([]);

  const dismissToast = useCallback((toastId: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== toastId));
  }, []);

  const notifyCompletedTasks = useCallback((previous: ImageTask[], next: ImageTask[]) => {
    const previousById = new Map(previous.map((task) => [task.id, task]));
    const completed = next.filter((task): task is ImageTask & { status: TaskToast['status'] } => {
      const previousTask = previousById.get(task.id);
      if (!previousTask) {
        return false;
      }
      const wasActive = previousTask.status === 'queued' || previousTask.status === 'running';
      return wasActive && isCompletedTask(task);
    });
    if (completed.length === 0) {
      return;
    }
    const newToasts = completed.map((task) => ({
      id: `${task.id}:${task.status}:${task.updated_at}`,
      taskId: task.id,
      status: task.status,
      prompt: task.prompt,
      createdAt: Date.now(),
      error: task.error,
    }));
    setToasts((current) => [...newToasts, ...current].slice(0, 6));
  }, []);

  const refreshTasks = useCallback(async () => {
    if (!viewer?.owner_id) {
      tasksRef.current = [];
      setTasks([]);
      setToasts([]);
      return;
    }
    try {
      const response = await listImageTasks({ limit: TASK_FETCH_LIMIT });
      const nextTasks = sortTasks(response.items);
      tasksRef.current = nextTasks;
      setTasks(nextTasks);
    } catch {
      tasksRef.current = [];
      setTasks([]);
    }
  }, [viewer?.owner_id]);

  useEffect(() => {
    refreshTasks().catch(() => undefined);
  }, [refreshTasks]);

  const addTask = useCallback((task: ImageTask) => {
    const merged = mergeTasks(tasksRef.current, [task]);
    tasksRef.current = merged;
    setTasks(merged);
    if (isCompletedTask(task)) {
      setToasts((current) => [
        {
          id: `${task.id}:${task.status}:${task.updated_at}`,
          taskId: task.id,
          status: task.status,
          prompt: task.prompt,
          createdAt: Date.now(),
          error: task.error,
        },
        ...current,
      ].slice(0, 6));
    }
    setDrawerOpen(true);
  }, []);

  const removeHistoryItem = useCallback((historyId: string) => {
    const changedTaskIds = new Set<string>();
    const removedTaskIds = new Set<string>();
    const nextTasks = sortTasks(
      tasksRef.current
        .map((task) => {
          const currentItems = task.items || [];
          const nextItems = currentItems.filter((item) => item.id !== historyId);
          if (nextItems.length === currentItems.length) {
            return task;
          }
          changedTaskIds.add(task.id);
          return { ...task, items: nextItems };
        })
        .filter((task) => {
          const completed = task.status === 'succeeded' || task.status === 'failed';
          const shouldRemove = changedTaskIds.has(task.id) && completed && (task.items || []).length === 0;
          if (shouldRemove) {
            removedTaskIds.add(task.id);
          }
          return !shouldRemove;
        }),
    );
    tasksRef.current = nextTasks;
    setTasks(nextTasks);
    if (removedTaskIds.size > 0) {
      setToasts((current) => current.filter((toast) => !removedTaskIds.has(toast.taskId)));
    }
  }, []);

  const activeTaskIds = useMemo(
    () =>
      tasks
        .filter((task) => task.status === 'queued' || task.status === 'running')
        .map((task) => task.id),
    [tasks],
  );
  const activeTaskKey = activeTaskIds.join(':');

  useEffect(() => {
    if (!viewer?.owner_id || activeTaskIds.length === 0) {
      return;
    }
    let cancelled = false;
    let timer = 0;
    let polling = false;

    const poll = async () => {
      if (cancelled || polling) {
        return;
      }
      polling = true;
      try {
        const response = await listImageTasks({ limit: TASK_FETCH_LIMIT });
        if (cancelled) {
          return;
        }
        const activeTaskIdSet = new Set(activeTaskIds);
        const nextTasks = response.items.filter((task) => activeTaskIdSet.has(task.id));
        if (nextTasks.length > 0) {
          const previous = tasksRef.current;
          const merged = mergeTasks(previous, nextTasks);
          tasksRef.current = merged;
          setTasks(merged);
          notifyCompletedTasks(previous, merged);
        }
      } finally {
        polling = false;
        if (!cancelled) {
          timer = window.setTimeout(poll, TASK_POLL_INTERVAL_MS);
        }
      }
    };

    timer = window.setTimeout(poll, TASK_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeTaskKey, activeTaskIds, viewer?.owner_id]);

  const taskHistoryItems = useMemo(
    () => mergeHistoryItems(tasks.flatMap((task) => task.items || [])),
    [tasks],
  );

  useEffect(() => {
    if (toasts.length === 0) {
      return;
    }
    const timers = toasts.map((toast) =>
      window.setTimeout(() => {
        dismissToast(toast.id);
      }, 5000),
    );
    return () => {
      for (const timer of timers) {
        window.clearTimeout(timer);
      }
    };
  }, [dismissToast, toasts]);

  const value = useMemo<TaskCenterValue>(
    () => ({
      tasks,
      activeCount: activeTaskIds.length,
      drawerOpen,
      taskHistoryItems,
      toasts,
      openDrawer: () => setDrawerOpen(true),
      closeDrawer: () => setDrawerOpen(false),
      toggleDrawer: () => setDrawerOpen((current) => !current),
      addTask,
      removeHistoryItem,
      refreshTasks,
      dismissToast,
    }),
    [activeTaskIds.length, addTask, dismissToast, drawerOpen, refreshTasks, removeHistoryItem, taskHistoryItems, tasks, toasts],
  );

  return <TaskCenterContext.Provider value={value}>{children}</TaskCenterContext.Provider>;
}

export function useTasks() {
  const context = useContext(TaskCenterContext);
  if (!context) {
    throw new Error('useTasks must be used inside TaskCenterProvider');
  }
  return context;
}
