import { useEffect } from 'react'

/**
 * Attaches an IntersectionObserver to every `.reveal` element in the DOM.
 * When an element enters the viewport it gets the `is-visible` class,
 * which triggers its CSS fade-up transition. Call once per page component.
 */
export function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.reveal')

    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.12, rootMargin: '0px 0px -32px 0px' },
    )

    els.forEach(el => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}
