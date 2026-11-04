import React, { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const TaskContext = createContext();
export const useTasks = () => useContext(TaskContext);

export function TaskProvider({ children }) {
  const { user } = useAuth();
  const [tasks, setTasks] = useState({});
  const tasksRef = useRef({});
  const pollRef = useRef(null);
  const isAuthenticatedRef = useRef(true);

  const fetchTasks = useCallback(async () => {
    if (!isAuthenticatedRef.current) return;
    try {
      const res = await axios.get('/tasks');
      const list = Array.isArray(res.data) ? res.data : [];

      const map = {};
      list.forEach(t => {
        map[t.id] = t;
      });

      tasksRef.current = map;
      setTasks(map);
    } catch (e) {
      if (e.response && e.response.status === 401) {
        isAuthenticatedRef.current = false;
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    }
  }, []);

  useEffect(() => {
    if (!user) {
      isAuthenticatedRef.current = false;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      setTasks({});
      tasksRef.current = {};
      return;
    }
    isAuthenticatedRef.current = true;
    if (!pollRef.current) {
      pollRef.current = setInterval(fetchTasks, 2500);
    }
    fetchTasks();
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [user, fetchTasks]);

  const startTask = useCallback(async (type, params) => {
    try {
      const res = await axios.post('/tasks/start', { type, params });
      if (!res.data.success) {
        throw new Error(res.data.error || 'Erro ao iniciar tarefa');
      }
      return res.data.task_id;
    } catch (e) {
      throw new Error((e.response && e.response.data && e.response.data.error) || e.message || 'Erro ao iniciar tarefa');
    }
  }, []);

  const runningTypes = useMemo(() => {
    const types = new Set();
    Object.values(tasks).forEach(t => {
      if (t.status === 'pending' || t.status === 'running') {
        types.add(t.name);
      }
    });
    return types;
  }, [tasks]);

  const isRunning = useCallback((type) => runningTypes.has(type), [runningTypes]);

  const allTasks = Object.values(tasks);
  const activeTasks = allTasks.filter(t => t.status === 'pending' || t.status === 'running');

  return (
    <TaskContext.Provider value={{
      tasks,
      activeTasks,
      startTask,
      fetchTasks,
      isRunning,
    }}>
      {children}
    </TaskContext.Provider>
  );
}