// src/App.tsx
// Sprint 5: Parameterized routes for multi-stock support.
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar }       from './components/layout/Sidebar';
import { Header }        from './components/layout/Header';
import { Overview }      from './pages/Overview';
import { StockAnalysis } from './pages/StockAnalysis';
import { BacktestLab }   from './pages/BacktestLab';
import { TradeJournal }  from './pages/TradeJournal';
import { DataCenter }    from './pages/DataCenter';

function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <div className="main-area">
          <Header />
          <Routes>
            <Route path="/"                   element={<Overview />}      />
            {/* Parameterized routes (Sprint 5) */}
            <Route path="/stocks/:symbol"     element={<StockAnalysis />} />
            <Route path="/backtest/:symbol"   element={<BacktestLab />}   />
            <Route path="/trades/:symbol"     element={<TradeJournal />}  />
            <Route path="/data/:symbol"       element={<DataCenter />}    />
            {/* Legacy redirect — old Sprint 4 paths */}
            <Route path="/backtest"           element={<Navigate to="/backtest/ITC" replace />} />
            <Route path="/trades"             element={<Navigate to="/trades/ITC" replace />}   />
            <Route path="/data"               element={<Navigate to="/data/ITC" replace />}     />
            <Route path="*"                   element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
