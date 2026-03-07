/**
 * Taurus Vision — useResponsive Hook
 *
 * Barcha komponentlar uchun yagona breakpoint tizimi.
 * SSR-safe, performance-optimized (ResizeObserver).
 *
 * FOYDALANISH:
 *   const { isMobile, isTablet, isDesktop, width } = useResponsive();
 *
 * BREAKPOINTLAR:
 *   mobile:  < 768px   (telefon)
 *   tablet:  768-1023px
 *   desktop: >= 1024px
 *
 * QULAY HELPER:
 *   const cols = responsive(1, 2, 3); // mobile/tablet/desktop ustunlar
 */

import { useState, useEffect, useCallback } from 'react';

export interface ResponsiveState {
  width:     number;
  height:    number;
  isMobile:  boolean;   // < 768
  isTablet:  boolean;   // 768-1023
  isDesktop: boolean;   // >= 1024
  isMobileOrTablet: boolean; // < 1024
  /** mobile → a | tablet → b | desktop → c */
  responsive: <T>(mobile: T, tablet: T, desktop: T) => T;
  /** mobile → a | else → b */
  mobileOnly: <T>(mobile: T, other: T) => T;
}

const MOBILE_MAX  = 767;
const TABLET_MAX  = 1023;

function getState(): ResponsiveState {
  if (typeof window === 'undefined') {
    // SSR fallback — desktop deb hisob
    const responsive = <T>(_: T, __: T, d: T) => d;
    const mobileOnly = <T>(_: T, o: T) => o;
    return {
      width: 1280, height: 800,
      isMobile: false, isTablet: false, isDesktop: true,
      isMobileOrTablet: false,
      responsive, mobileOnly,
    };
  }

  const w = window.innerWidth;
  const h = window.innerHeight;
  const isMobile  = w <= MOBILE_MAX;
  const isTablet  = w >= MOBILE_MAX + 1 && w <= TABLET_MAX;
  const isDesktop = w >= TABLET_MAX + 1;

  const responsive = <T>(mobile: T, tablet: T, desktop: T): T =>
    isMobile ? mobile : isTablet ? tablet : desktop;

  const mobileOnly = <T>(mobile: T, other: T): T =>
    isMobile ? mobile : other;

  return {
    width: w, height: h,
    isMobile, isTablet, isDesktop,
    isMobileOrTablet: isMobile || isTablet,
    responsive, mobileOnly,
  };
}

export function useResponsive(): ResponsiveState {
  const [state, setState] = useState<ResponsiveState>(getState);

  const update = useCallback(() => {
    setState(getState());
  }, []);

  useEffect(() => {
    // ResizeObserver — window.resize dan aniqroq
    let ro: ResizeObserver | undefined;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(update);
      ro.observe(document.documentElement);
    } else {
      window.addEventListener('resize', update, { passive: true });
    }

    return () => {
      if (ro) {
        ro.disconnect();
      } else {
        window.removeEventListener('resize', update);
      }
    };
  }, [update]);

  return state;
}

/**
 * Faqat isMobile kerak bo'lganda — yengil variant.
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.innerWidth <= MOBILE_MAX
  );

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_MAX}px)`);
    const fn  = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', fn);
    setIsMobile(mq.matches);
    return () => mq.removeEventListener('change', fn);
  }, []);

  return isMobile;
}