import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import About from './pages/About'
import Confirm from './pages/Confirm'
import Intake from './pages/Intake'
import Landing from './pages/Landing'
import Processing from './pages/Processing'
import Summary from './pages/Summary'
import Transcribe from './pages/Transcribe'
import { FlowProvider } from './state/FlowContext'

export default function App() {
  return (
    <FlowProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/intake" element={<Intake />} />
            <Route path="/transcribe" element={<Transcribe />} />
            <Route path="/review" element={<Confirm />} />
            <Route path="/confirm" element={<Confirm />} />
            <Route path="/processing" element={<Processing />} />
            <Route path="/summary" element={<Summary />} />
            <Route path="/about" element={<About />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </FlowProvider>
  )
}
