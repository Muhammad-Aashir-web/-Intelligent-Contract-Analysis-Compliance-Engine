import { useEffect } from "react"
import {
	AlertTriangle,
	CheckCircle,
	Clock,
	FileText,
	type LucideIcon,
} from "lucide-react"

import Layout from "../components/layout/Layout"
import useContract from "../hooks/useContract"

type StatCard = {
	label: string
	value: string
	colorClass: string
	icon: LucideIcon
}

function Dashboard() {
	const { contracts, isLoading, fetchContracts } = useContract()

	useEffect(() => {
		fetchContracts()
	}, [])

	const highRiskCount = contracts.filter((c) => (c.riskScore ?? 0) > 70).length
	const compliantCount = contracts.filter((c) => c.status === "completed").length
	const pendingCount = contracts.filter((c) => c.status === "processing" || c.status === "pending").length

	const stats: StatCard[] = [
		{
			label: "Total Contracts",
			value: String(contracts.length),
			colorClass: "text-blue-600",
			icon: FileText,
		},
		{
			label: "High Risk",
			value: String(highRiskCount),
			colorClass: "text-red-600",
			icon: AlertTriangle,
		},
		{
			label: "Compliant",
			value: String(compliantCount),
			colorClass: "text-green-600",
			icon: CheckCircle,
		},
		{
			label: "Pending Review",
			value: String(pendingCount),
			colorClass: "text-yellow-600",
			icon: Clock,
		},
	]

	return (
		<Layout title="Dashboard">
			<div className="space-y-6">
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6 w-full">
					{stats.map((stat) => {
						const Icon = stat.icon

						return (
							<div
								key={stat.label}
								className="bg-white rounded-xl shadow-sm p-6 flex justify-between items-center min-w-[220px]"
							>
								<div>
									<p className="text-sm text-gray-500">{stat.label}</p>
									<p className={`mt-2 text-3xl font-bold ${stat.colorClass}`}>{stat.value}</p>
								</div>
								<Icon className={`h-8 w-8 ${stat.colorClass}`} />
							</div>
						)
					})}
				</div>

				{isLoading ? (
					<div className="bg-white rounded-xl shadow-sm p-16 text-center text-gray-400">
						Loading contracts...
					</div>
				) : contracts.length === 0 ? (
					<div className="bg-white rounded-xl shadow-sm p-16 text-center text-gray-400">
						Upload a contract to get started
					</div>
				) : (
					<div className="bg-white rounded-xl shadow-sm p-6">
						<h3 className="text-lg font-semibold mb-4">Recent Contracts</h3>
						<div className="space-y-4">
							{contracts.slice(0, 5).map((contract) => (
								<div key={contract.id} className="flex justify-between items-center p-4 border border-gray-200 rounded-lg">
									<div>
										<p className="font-medium">{contract.fileName}</p>
										<p className="text-sm text-gray-500">{contract.status}</p>
									</div>
									<p className={`font-semibold ${{"completed": "text-green-600", "processing": "text-yellow-600", "pending": "text-gray-600", "failed": "text-red-600"}[contract.status] || "text-gray-600"}`}>
										{contract.riskScore ? `Risk: ${contract.riskScore.toFixed(1)}%` : "Not analyzed"}
									</p>
								</div>
							))}
						</div>
					</div>
				)}
			</div>
		</Layout>
	)
}

export default Dashboard