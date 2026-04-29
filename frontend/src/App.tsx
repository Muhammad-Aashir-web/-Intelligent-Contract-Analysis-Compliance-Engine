import { BrowserRouter, Route, Routes } from "react-router-dom"

import Compliance from "./pages/Compliance"
import Contracts from "./pages/Contracts"
import Dashboard from "./pages/Dashboard"
import RiskAnalysis from "./pages/RiskAnalysis"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/contracts" element={<Contracts />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/risk" element={<RiskAnalysis />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
