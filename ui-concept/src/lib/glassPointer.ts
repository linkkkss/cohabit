/**
 * 流体玻璃按钮：把指针位置写进 .btn 的 --mx / --my，CSS 用径向高光跟随指针。
 * 事件委托 + rAF 节流，不给每个按钮单独绑事件。
 */
export function installGlassPointer(): () => void {
  if (typeof window === 'undefined') return () => undefined
  const fine = window.matchMedia?.('(pointer: fine)').matches ?? true
  if (!fine) return () => undefined

  let frame = 0
  let last: { el: HTMLElement; x: number; y: number } | null = null
  let current: HTMLElement | null = null

  const apply = (): void => {
    frame = 0
    if (!last) return
    const rect = last.el.getBoundingClientRect()
    last.el.style.setProperty('--mx', `${((last.x - rect.left) / Math.max(rect.width, 1)) * 100}%`)
    last.el.style.setProperty('--my', `${((last.y - rect.top) / Math.max(rect.height, 1)) * 100}%`)
  }

  const onPointerMove = (event: PointerEvent): void => {
    if (event.pointerType === 'touch') return
    const target = (event.target as Element | null)?.closest?.('.btn, .glass')
    if (!(target instanceof HTMLElement)) return
    if (target !== current) {
      current?.classList.remove('is-tracking')
      current = target
      current.classList.add('is-tracking')
    }
    last = { el: target, x: event.clientX, y: event.clientY }
    if (!frame) frame = requestAnimationFrame(apply)
  }

  const onPointerOut = (event: PointerEvent): void => {
    const target = (event.target as Element | null)?.closest?.('.btn, .glass')
    if (!(target instanceof HTMLElement)) return
    const next = event.relatedTarget
    if (next instanceof Node && target.contains(next)) return
    target.classList.remove('is-tracking')
    if (target === current) current = null
  }

  document.addEventListener('pointermove', onPointerMove, { passive: true })
  document.addEventListener('pointerout', onPointerOut, { passive: true })

  return () => {
    if (frame) cancelAnimationFrame(frame)
    document.removeEventListener('pointermove', onPointerMove)
    document.removeEventListener('pointerout', onPointerOut)
  }
}
