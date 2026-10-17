import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

const DONUT_COLORS = ['#22c55e', '#ef4444'];

export default function IndexDonut({ indexed, notIndexed, size = 160, innerRadius = 50, outerRadius = 72 }) {
  const total = indexed + notIndexed;
  if (!total) return null;
  const pct = (indexed / total * 100).toFixed(1);
  const data = [
    { name: 'Indexed', value: indexed },
    { name: 'Not Indexed', value: notIndexed },
  ];

  return (
    <div className="relative flex items-center justify-center">
      <ResponsiveContainer width={size} height={size}>
        <PieChart>
          <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={innerRadius} outerRadius={outerRadius}
            paddingAngle={3} startAngle={90} endAngle={-270} strokeWidth={0}>
            {data.map((_, i) => <Cell key={i} fill={DONUT_COLORS[i]} />)}
          </Pie>
          <Tooltip formatter={v => (v ?? 0).toLocaleString()} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-2xl font-extrabold text-emerald-700">{pct}%</span>
        <span className="text-[10px] text-slate-400 font-medium">indexed</span>
      </div>
    </div>
  );
}
