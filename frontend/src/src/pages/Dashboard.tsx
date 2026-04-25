import {
	AlertTriangle,
	CheckCircle,
	Clock,
	FileText,
	type LucideIcon,
} from "lucide-react"

import Layout from "../components/layout/Layout"

type StatCard = {
	label: string
	value: string
	colorClass: string
	icon: LucideIcon
}

const stats: StatCard[] = [
	{
		label: "Total Contracts",
		value: "0",
		colorClass: "text-blue-600",
		icon: FileText,
	},
	{
		label: "High Risk",
		value: "0",
		colorClass: "text-red-600",
		icon: AlertTriangle,
	},
	{
		label: "Compliant",
		value: "0",
		colorClass: "text-green-600",
		icon: CheckCircle,
	},
	{
		label: "Pending Review",
		value: "0",
		colorClass: "text-yellow-600",
		icon: Clock,
	},
]

function Dashboard() {
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

				<div className="bg-white rounded-xl shadow-sm p-16 text-center text-gray-400">
					Upload a contract to get started
				</div>
			</div>
		</Layout>
	)
}

export default Dashboard
