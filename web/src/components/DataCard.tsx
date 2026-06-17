interface DataCardProps {
  title: string
  value: string | number
  note?: string
}

function DataCard({ title, value, note }: DataCardProps) {
  return (
    <div
      style={{
        background: '#1a1a1a',
        borderRadius: '8px',
        padding: '16px',
        minWidth: '180px',
      }}
    >
      <div style={{ fontSize: '0.875rem', color: '#888', marginBottom: '8px' }}>{title}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{value}</div>
      {note && <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '4px' }}>{note}</div>}
    </div>
  )
}

export default DataCard
