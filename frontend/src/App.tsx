import { BrowserRouter, Route, Routes } from "react-router-dom"

import Contracts from "./src/pages/Contracts"
import Dashboard from "./src/pages/Dashboard"
import Compliance from "./pages/Compliance"
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
