import DataCard from '../components/DataCard'

function Dashboard() {
  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>总览</h2>
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <DataCard title="关注标的" value={3} note="来自 config/tickers.yaml" />
        <DataCard title="持仓数量" value={0} note="需导入持仓 CSV" />
        <DataCard title="激活计划" value={0} note="需创建交易计划" />
        <DataCard title="最新快照" value="暂无" note="运行日更后生成" />
      </div>
    </div>
  )
}

export default Dashboard
