import { Cell, Legend, Pie, PieChart, Tooltip } from "recharts"

type ComplianceStatusItem = {
	name: string
	value: number
	color?: string
}

type ComplianceStatusChartProps = {
	data?: ComplianceStatusItem[]
}

const defaultData: ComplianceStatusItem[] = [
	{ name: "Compliant", value: 0, color: "#22c55e" },
	{ name: "Non-Compliant", value: 0, color: "#ef4444" },
	{ name: "Needs Review", value: 0, color: "#f59e0b" },
]

function ComplianceStatusChart({ data }: ComplianceStatusChartProps) {
	const chartData = data && data.length > 0 ? data : defaultData
	const total = chartData.reduce((sum, item) => sum + item.value, 0)

	if (total === 0) {
		return (
			<div className="flex flex-col items-center">
				<div className="text-gray-500 text-center">No compliance data yet</div>
			</div>
		)
	}

	return (
		<div className="flex flex-col items-center">
			<PieChart width={300} height={250}>
				<Pie data={chartData} dataKey="value" cx="50%" cy="50%" outerRadius={80}>
					{chartData.map((item, index) => (
						<Cell key={`${item.name}-${index}`} fill={item.color || "#9ca3af"} />
					))}
				</Pie>
				<Tooltip />
				<Legend />
			</PieChart>
		</div>
	)
}

export default ComplianceStatusChart
