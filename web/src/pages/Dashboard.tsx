import { useEffect, useState } from 'react'
import DataCard from '../components/DataCard'
import {
  fetchSecurityMaster,
  fetchSystemStatus,
  type SecurityMasterItem,
  type SystemStatus,
} from '../services/api'

function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [securities, setSecurities] = useState<SecurityMasterItem[]>([])

  useEffect(() => {
    fetchSystemStatus().then(setStatus)
    fetchSecurityMaster().then(setSecurities)
  }, [])

  const lastSnapshot = status
    ? `${new Date(status.last_snapshot_at).toLocaleString()} (${status.last_snapshot_version})`
    : '暂无'

  const watchlistNames =
    securities.length > 0
      ? securities.map((s) => s.name).join('、')
      : '运行 climbing update securities 后生成'

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>总览</h2>
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <DataCard
          title="关注标的"
          value={securities.length}
          note={watchlistNames}
        />
        <DataCard title="持仓数量" value={0} note="需导入持仓 CSV" />
        <DataCard title="激活计划" value={0} note="需创建交易计划" />
        <DataCard title="最新快照" value={lastSnapshot} note="运行日更后生成" />
      </div>
    </div>
  )
}

export default Dashboard
