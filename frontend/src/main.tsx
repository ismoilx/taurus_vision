import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import './index.css';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/*
      QueryClientProvider: Barcha sahifalarda kesh ishlaydi.
      WebSocketProvider App.tsx ichida Layout darajasida qo'shilgan
      (faqat login qilgandan keyin ulanishi uchun).
    */}
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);