import { ChevronDown, ChevronUp, Lightbulb } from "lucide-react"

import type { Clause } from "../../types/contract"

type ClauseCardProps = {
	clause: Clause
	isExpanded: boolean
	onToggle: () => void
}

const riskBadgeClasses: Record<Clause["riskLevel"], string> = {
	low: "bg-green-100 text-green-700",
	medium: "bg-yellow-100 text-yellow-700",
	high: "bg-orange-100 text-orange-700",
	critical: "bg-red-100 text-red-700",
}

function ClauseCard({ clause, isExpanded, onToggle }: ClauseCardProps) {
	return (
		<div className="border rounded-lg overflow-hidden mb-3 cursor-pointer">
			<div className="flex justify-between items-center p-4 bg-white hover:bg-gray-50" onClick={onToggle}>
				<div className="flex items-center gap-3">
					<span
						className={`px-2 py-1 rounded-full text-xs font-medium uppercase ${riskBadgeClasses[clause.riskLevel]}`}
					>
						{clause.riskLevel}
					</span>
					<div className="font-medium text-gray-800">{clause.title}</div>
					<div className="text-sm text-gray-500">{clause.type}</div>
				</div>
				<div className="text-gray-500">
					{isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
				</div>
			</div>

			{isExpanded ? (
				<div className="p-4 bg-gray-50 border-t border-gray-200">
					<div className="text-sm text-gray-700 leading-relaxed mb-3">{clause.content}</div>
					{typeof clause.page === "number" ? (
						<div className="text-xs text-gray-400">Found on page {clause.page}</div>
					) : null}
					{clause.suggestions && clause.suggestions.length > 0 ? (
						<div className="mt-4">
							<div className="text-sm font-medium text-gray-700 mb-2">Suggestions</div>
							<div className="space-y-2">
								{clause.suggestions.map((suggestion, index) => (
									<div key={`${suggestion}-${index}`} className="flex items-start gap-2">
										<Lightbulb size={16} className="mt-0.5 text-yellow-500 flex-shrink-0" />
										<div className="text-sm text-gray-600">{suggestion}</div>
									</div>
								))}
							</div>
						</div>
					) : null}
				</div>
			) : null}
		</div>
	)
}

export default ClauseCard