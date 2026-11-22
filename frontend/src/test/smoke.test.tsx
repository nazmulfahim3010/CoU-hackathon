import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('Application Smoke Test', () => {
  it('renders base layout with branding and medical disclaimer', () => {
    render(<App />)

    // Check header logo and branding
    const header = screen.getByRole('banner')
    expect(within(header).getByText(/Kotha/i)).toBeInTheDocument()
    expect(within(header).getByText('কথা')).toBeInTheDocument()

    // Check mandatory medical disclaimer in footer
    const footer = screen.getByRole('contentinfo')
    expect(
      within(footer).getByText(/Kotha is not a diagnostic tool\. Medical decisions must be made by a qualified healthcare professional\./i)
    ).toBeInTheDocument()

    // Check primary navigation link
    expect(within(header).getByRole('link', { name: /start/i })).toBeInTheDocument()
  })
})
