import { useParams } from 'react-router-dom'

function StockAnalysis() {
  const { ticker } = useParams()

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>个股分析</h2>
      <p>当前标的：{ticker || '未选择'}</p>
      <p>（此处后续接入个股全景分析报告与评分面板）</p>
    </div>
  )
}

export default StockAnalysis
