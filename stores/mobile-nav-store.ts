/**
 * Mobile navigation state management.
 *
 * Manages the navigation stack for mobile layout mode,
 * enabling push/pop navigation between views.
 *
 * @module stores/mobile-nav-store
 */

import { create } from "zustand";

/** Available views in mobile navigation. */
export type MobileView = "subscriptions" | "list" | "viewer" | "settings";

/** Navigation direction: 1 = push (forward), -1 = pop (backward). */
export type NavDirection = 1 | -1;

/** Mobile navigation state interface. */
interface MobileNavState {
  /** Current view stack. */
  viewStack: MobileView[];

  /** Navigation direction: 1 = push (forward), -1 = pop (backward). */
  direction: NavDirection;

  /** Push a new view onto the stack. */
  push: (view: MobileView) => void;

  /** Pop the top view from the stack. */
  pop: () => void;

  /** Reset stack to initial state. */
  reset: () => void;

  /** Get the current (top) view. */
  currentView: () => MobileView;

  /** Set the entire stack (for URL sync). */
  setStack: (stack: MobileView[]) => void;
}

/** Initial view stack. */
const INITIAL_STACK: MobileView[] = ["subscriptions"];

/**
 * Mobile navigation store.
 *
 * Not persisted - resets on page load and syncs with URL state.
 */
export const useMobileNavStore = create<MobileNavState>()((set, get) => ({
  viewStack: INITIAL_STACK,
  direction: 1,

  push: (view) =>
    set((state) => {
      // Don't push if already on this view
      if (state.viewStack[state.viewStack.length - 1] === view) {
        return state;
      }
      return { viewStack: [...state.viewStack, view], direction: 1 };
    }),

  pop: () =>
    set((state) => {
      if (state.viewStack.length <= 1) {
        return state; // Keep at least one view
      }
      return { viewStack: state.viewStack.slice(0, -1), direction: -1 };
    }),

  reset: () => set({ viewStack: INITIAL_STACK, direction: 1 }),

  currentView: () => {
    const stack = get().viewStack;
    return stack[stack.length - 1];
  },

  setStack: (stack) =>
    set((state) => {
      const newStack = stack.length > 0 ? stack : INITIAL_STACK;
      // Skip if stack hasn't changed (preserve current direction)
      if (
        newStack.length === state.viewStack.length &&
        newStack.every((v, i) => v === state.viewStack[i])
      ) {
        return state;
      }
      // Determine direction based on stack length change
      // push (forward): stack grows, pop (backward): stack shrinks
      const direction: NavDirection =
        newStack.length > state.viewStack.length ? 1 : -1;
      return { viewStack: newStack, direction };
    }),
}));
