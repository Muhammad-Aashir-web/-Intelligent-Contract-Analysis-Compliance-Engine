import { Cell, Pie, PieChart } from "recharts"

type RiskScoreGaugeProps = {
	score: number
	label?: string
}

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

function getRiskLabel(score: number): string {
	if (score <= 30) {
		return "Low Risk"
	}
	if (score <= 60) {
		return "Medium Risk"
	}
	if (score <= 80) {
		return "High Risk"
	}
	return "Critical Risk"
}

function RiskScoreGauge({ score, label }: RiskScoreGaugeProps) {
	const clampedScore = Math.max(0, Math.min(100, score))
	const color = getRiskColor(clampedScore)
	const riskLabel = getRiskLabel(clampedScore)

	return (
		<div className="text-center">
			<PieChart width={200} height={200}>
				<Pie
					startAngle={180}
					endAngle={0}
					data={[{ value: 100 }]}
					dataKey="value"
					fill="#e5e7eb"
					innerRadius={60}
					outerRadius={80}
					stroke="none"
				/>
				<Pie
					startAngle={180}
					endAngle={180 - clampedScore * 1.8}
					data={[{ value: clampedScore }, { value: 100 - clampedScore }]}
					dataKey="value"
					innerRadius={60}
					outerRadius={80}
					stroke="none"
				>
					<Cell fill={color} />
					<Cell fill="transparent" />
				</Pie>
			</PieChart>

			<div className="-mt-4">
				<div className="text-3xl font-bold" style={{ color }}>
					{Math.round(clampedScore)}
				</div>
				<div className="text-gray-600">{riskLabel}</div>
				{label ? <div className="text-xs text-gray-500 mt-1">{label}</div> : null}
			</div>
		</div>
	)
}

export default RiskScoreGauge
