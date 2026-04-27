import Layout from "../layout/Layout"
import ComplianceStatusChart from "./ComplianceStatusChart"
import RiskBreakdownChart from "./RiskBreakdownChart"
import RiskScoreGauge from "./RiskScoreGauge"

type RiskSummaryItem = {
	name: string
	score: number
	barColorClass: string
}

const overallScore = 72

const breakdownData = [
	{ name: "Financial", score: 75 },
	{ name: "Legal", score: 45 },
	{ name: "Compliance", score: 60 },
	{ name: "Operational", score: 30 },
	{ name: "Reputational", score: 55 },
]

const riskSummary: RiskSummaryItem[] = [
	{ name: "Financial Risk", score: 75, barColorClass: "bg-orange-500" },
	{ name: "Legal Risk", score: 45, barColorClass: "bg-yellow-500" },
	{ name: "Compliance Risk", score: 60, barColorClass: "bg-orange-400" },
]

function RiskAnalysis() {
	return (
		<Layout title="Risk Analysis">
			<div className="space-y-6">
				<div className="grid grid-cols-3 gap-6">
					<div className="bg-white rounded-xl shadow-sm p-6">
						<h3 className="font-semibold text-gray-800 mb-4">Overall Risk Score</h3>
						<div className="flex justify-center">
							<RiskScoreGauge score={overallScore} />
						</div>
					</div>

					<div className="bg-white rounded-xl shadow-sm p-6">
						<h3 className="font-semibold text-gray-800 mb-4">Compliance Status</h3>
						<div className="flex justify-center">
							<ComplianceStatusChart />
						</div>
					</div>

					<div className="bg-white rounded-xl shadow-sm p-6">
						<h3 className="font-semibold text-gray-800 mb-4">Risk Summary</h3>
						<div className="space-y-4">
							{riskSummary.map((item) => (
								<div key={item.name}>
									<div className="flex items-center justify-between mb-1">
										<span className="text-sm text-gray-700">{item.name}</span>
										<span className="text-sm font-medium text-gray-700">{item.score}/100</span>
									</div>
									<div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
										<div
											className={`h-full rounded-full ${item.barColorClass}`}
											style={{ width: `${item.score}%` }}
										/>
									</div>
								</div>
							))}
						</div>
					</div>
				</div>

				<div className="bg-white rounded-xl shadow-sm p-6">
					<h3 className="font-semibold text-gray-800 mb-4">Risk Breakdown by Category</h3>
					<RiskBreakdownChart data={breakdownData} />
				</div>
			</div>
		</Layout>
	)
}

export default RiskAnalysis
