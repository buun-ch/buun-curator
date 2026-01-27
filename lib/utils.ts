/**
 * Utility functions for the application.
 *
 * @module lib/utils
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges class names with Tailwind CSS conflict resolution.
 *
 * Combines clsx for conditional classes with tailwind-merge for
 * proper handling of conflicting Tailwind utilities.
 *
 * @param inputs - Class values to merge (strings, objects, arrays)
 * @returns Merged class string with conflicts resolved
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
