import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

function Layout({ children }: LayoutProps) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{ width: '220px', padding: '20px', borderRight: '1px solid #333' }}>
        <h1 style={{ fontSize: '1.5rem', marginBottom: '24px' }}>Climbing</h1>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Link to="/">总览</Link>
          <Link to="/stock">个股分析</Link>
          <Link to="/portfolio">持仓管理</Link>
          <Link to="/plans">交易计划</Link>
          <Link to="/macro">宏观月报</Link>
          <Link to="/inspection">巡检中心</Link>
        </nav>
      </aside>
      <main style={{ flex: 1, padding: '24px' }}>{children}</main>
    </div>
  )
}

export default Layout
