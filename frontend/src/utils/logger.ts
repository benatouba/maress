/**
 * Centralized logger for the Maress frontend.
 *
 * - In production builds (`import.meta.env.PROD`) only warnings and errors
 *   are emitted; debug/info calls are silenced.
 * - Provides a single place to later plug in an error reporting service
 *   (e.g. Sentry) without touching every call-site.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
}

const currentLevel: number = import.meta.env.PROD ? LOG_LEVELS.warn : LOG_LEVELS.debug

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= currentLevel
}

export const logger = {
  debug(message: string, ...args: unknown[]): void {
    if (shouldLog('debug')) console.debug(`[DEBUG] ${message}`, ...args)
  },

  info(message: string, ...args: unknown[]): void {
    if (shouldLog('info')) console.info(`[INFO] ${message}`, ...args)
  },

  warn(message: string, ...args: unknown[]): void {
    if (shouldLog('warn')) console.warn(`[WARN] ${message}`, ...args)
  },

  error(message: string, ...args: unknown[]): void {
    if (shouldLog('error')) console.error(`[ERROR] ${message}`, ...args)
  },
}

export default logger
