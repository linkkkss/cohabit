/**
 * 滚动揭示：用 IntersectionObserver 给进入视口的元素加 `.is-in`，
 * 只用 opacity / translate，配合 ease-out 让它“快速进入、自然减速”。
 * 同时监听 DOM 变化，路由切换与列表筛选后新出现的节点会自动接管。
 */
const DEFAULT_SELECTOR = [
  '[data-reveal]',
  '.section-head',
  '.page-head',
  '.card',
  '.panel',
  '.step-card',
  '.auth-card',
  '.quote',
  '.hero-copy',
  '.hero-art',
].join(',')

const SKIP_INSIDE = '.no-reveal, [data-reveal="none"]'

export interface RevealOptions {
  selector?: string
  rootMargin?: string
  threshold?: number
}

export function installScrollReveal(root: HTMLElement, options: RevealOptions = {}): () => void {
  const selector = options.selector ?? DEFAULT_SELECTOR
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const observed = new WeakSet<Element>()
  const done = new WeakSet<Element>()

  if (reduce || typeof IntersectionObserver === 'undefined') {
    root.querySelectorAll(selector).forEach((el) => el.classList.add('reveal', 'is-in'))
    return () => undefined
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        const el = entry.target as HTMLElement
        el.classList.add('is-in')
        done.add(el)
        observer.unobserve(el)
      })
    },
    { threshold: options.threshold ?? 0.08, rootMargin: options.rootMargin ?? '0px 0px -6% 0px' },
  )

  const register = (el: Element): void => {
    if (!(el instanceof HTMLElement)) return
    if (observed.has(el) || done.has(el)) return
    if (el.closest(SKIP_INSIDE)) return

    const variant = el.dataset.reveal
    el.classList.add('reveal')
    if (variant && variant !== 'none') el.classList.add(`reveal--${variant}`)

    // 同一父容器内按顺序递增延迟，形成轻微的瀑布感
    const siblings = Array.from(el.parentElement?.children ?? []).filter((child) =>
      child.classList.contains('reveal'),
    )
    const index = Math.max(0, siblings.indexOf(el))
    el.style.setProperty('--reveal-delay', `${Math.min(index * 55, 260)}ms`)

    const rect = el.getBoundingClientRect()
    if (rect.bottom < 0) {
      el.classList.add('is-in')
      done.add(el)
      return
    }
    if (rect.top < window.innerHeight * 0.92) {
      // 首屏元素：下一帧进入，避免与首屏骨架屏切换撞在一起
      requestAnimationFrame(() => {
        requestAnimationFrame(() => el.classList.add('is-in'))
      })
      done.add(el)
      return
    }
    observed.add(el)
    observer.observe(el)
  }

  const scan = (): void => {
    root.querySelectorAll(selector).forEach(register)
  }

  scan()

  let pending = 0
  const mutation = new MutationObserver(() => {
    if (pending) return
    pending = requestAnimationFrame(() => {
      pending = 0
      scan()
    })
  })
  mutation.observe(root, { childList: true, subtree: true })

  return () => {
    if (pending) cancelAnimationFrame(pending)
    mutation.disconnect()
    observer.disconnect()
    root.querySelectorAll('.reveal').forEach((el) => el.classList.add('is-in'))
  }
}
