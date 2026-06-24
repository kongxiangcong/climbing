import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import StockAnalysis from './pages/StockAnalysis'
import Portfolio from './pages/Portfolio'
import Plans from './pages/Plans'
import MacroReport from './pages/MacroReport'
import InspectionCenter from './pages/InspectionCenter'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/stock/:ticker?" element={<StockAnalysis />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/macro" element={<MacroReport />} />
        <Route path="/inspection" element={<InspectionCenter />} />
      </Routes>
    </Layout>
  )
}

export default App
