import { useState } from "react"
import { Search } from "lucide-react"

import type { Clause } from "../../types/contract"
import ClauseCard from "./ClauseCard"

type ClauseListProps = {
	clauses: Clause[]
	isLoading?: boolean
}

function ClauseList({ clauses, isLoading = false }: ClauseListProps) {
	const [searchTerm, setSearchTerm] = useState<string>("")
	const [filterRisk, setFilterRisk] = useState<string>("all")
	const [expandedId, setExpandedId] = useState<string | null>(null)

	const filteredClauses = clauses.filter((clause) => {
		const searchMatch =
			clause.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
			clause.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
			clause.type.toLowerCase().includes(searchTerm.toLowerCase())

		const riskMatch = filterRisk === "all" || clause.riskLevel === filterRisk

		return searchMatch && riskMatch
	})

	const handleToggle = (clauseId: string) => {
		setExpandedId((currentExpandedId) =>
			currentExpandedId === clauseId ? null : clauseId,
		)
	}

	return (
		<div>
			<div className="flex gap-3 mb-4">
				<div className="relative flex-1">
					<Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
					<input
						type="text"
						placeholder="Search clauses..."
						value={searchTerm}
						onChange={(event) => setSearchTerm(event.target.value)}
						className="flex-1 pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
					/>
				</div>
				<select
					value={filterRisk}
					onChange={(event) => setFilterRisk(event.target.value)}
					className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none"
				>
					<option value="all">All Risk Levels</option>
					<option value="low">Low Risk</option>
					<option value="medium">Medium Risk</option>
					<option value="high">High Risk</option>
					<option value="critical">Critical</option>
				</select>
			</div>

			<div className="text-sm text-gray-500 mb-3">
				Showing {filteredClauses.length} of {clauses.length} clauses
			</div>

			{isLoading ? (
				<div className="space-y-3">
					<div className="animate-pulse bg-gray-200 rounded-lg h-16 mb-3" />
					<div className="animate-pulse bg-gray-200 rounded-lg h-16 mb-3" />
					<div className="animate-pulse bg-gray-200 rounded-lg h-16 mb-3" />
				</div>
			) : filteredClauses.length === 0 ? (
				<div className="text-center text-gray-500 py-8">No clauses match your search</div>
			) : (
				<div>
					{filteredClauses.map((clause) => (
						<ClauseCard
							key={clause.id}
							clause={clause}
							isExpanded={expandedId === clause.id}
							onToggle={() => handleToggle(clause.id)}
						/>
					))}
				</div>
			)}
		</div>
	)
}

export default ClauseList
