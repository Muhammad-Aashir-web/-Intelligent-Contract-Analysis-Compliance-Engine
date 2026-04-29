import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts"

type RiskBreakdownItem = {
	name: string
	score: number
}

type RiskBreakdownChartProps = {
	data?: RiskBreakdownItem[]
}

const defaultData: RiskBreakdownItem[] = [
	{ name: "Financial", score: 75 },
	{ name: "Legal", score: 45 },
	{ name: "Compliance", score: 60 },
	{ name: "Operational", score: 30 },
	{ name: "Reputational", score: 55 },
]

function getRiskColor(score: number): string {
	if (score <= 30) {
		return "#22c55e"
	}
	if (score <= 60) {
		return "#f59e0b"
	}
	if (score <= 80) {
		return "#f97316"
	}
	return "#ef4444"
}

function RiskBreakdownChart({ data }: RiskBreakdownChartProps) {
	const chartData = data && data.length > 0 ? data : defaultData

	return (
		<div className="w-full">
			<ResponsiveContainer width="100%" height={250}>
				<BarChart
					data={chartData}
					margin={{
						top: 5,
						right: 20,
						bottom: 5,
						left: 0,
					}}
				>
					<CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
					<XAxis dataKey="name" tick={{ fontSize: 12 }} />
					<YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
					<Tooltip formatter={(value) => `${value}%`} />
					<Bar dataKey="score" radius={[4, 4, 0, 0]}>
						{chartData.map((entry, index) => (
							<Cell key={`${entry.name}-${index}`} fill={getRiskColor(entry.score)} />
						))}
					</Bar>
				</BarChart>
			</ResponsiveContainer>
		</div>
	)
}

export default RiskBreakdownChart